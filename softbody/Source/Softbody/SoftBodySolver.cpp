#include "SoftBodySolver.h"

namespace SoftBodySolver
{
    constexpr double FixedStep = 1.0 / 120.0;
    constexpr int32 Iterations = 8;
    constexpr int32 MaximumSteps = 8;

    uint64 EdgeKey(int32 A, int32 B)
    {
        return (static_cast<uint64>(FMath::Min(A, B)) << 32) | static_cast<uint32>(FMath::Max(A, B));
    }
}

FSoftBodySolver::FSoftBodySolver()
{
    Initialize(BallRadius);
}

void FSoftBodySolver::Initialize(float Radius)
{
    BallRadius = FMath::IsFinite(Radius) ? FMath::Clamp(Radius, 1.0f, 500.0f) : 18.0f;
    BuildSurface();
    BuildConstraints();
    Positions = RestPositions;
    RestVolume = CalculateVolume();
    PreviousPositions.SetNum(Positions.Num());
    Velocities.SetNum(Positions.Num());
    ShapeLambdas.SetNum(Positions.Num());
    VolumeGradients.SetNum(Positions.Num());
    Reset();
}

void FSoftBodySolver::SetSoftness(float InSoftness)
{
    if (FMath::IsFinite(InSoftness))
    {
        Softness = FMath::Clamp(InSoftness, 0.0f, 1.0f);
    }
}

void FSoftBodySolver::Reset()
{
    Positions = RestPositions;
    PreviousPositions = RestPositions;
    for (FVector& Velocity : Velocities)
    {
        Velocity = FVector::ZeroVector;
    }
    Accumulator = 0.0;
    VolumeLambda = 0.0;
    ContactCount = 0;
    ContactFlags.Reset();
}

void FSoftBodySolver::BuildSurface()
{
    // Three subdivisions give a closed 642-vertex / 1,280-triangle surface without pole artifacts.
    const double T = (1.0 + FMath::Sqrt(5.0)) * 0.5;
    RestPositions = {
        FVector(-1,T,0), FVector(1,T,0), FVector(-1,-T,0), FVector(1,-T,0),
        FVector(0,-1,T), FVector(0,1,T), FVector(0,-1,-T), FVector(0,1,-T),
        FVector(T,0,-1), FVector(T,0,1), FVector(-T,0,-1), FVector(-T,0,1)
    };
    Triangles = {
        0,11,5, 0,5,1, 0,1,7, 0,7,10, 0,10,11,
        1,5,9, 5,11,4, 11,10,2, 10,7,6, 7,1,8,
        3,9,4, 3,4,2, 3,2,6, 3,6,8, 3,8,9,
        4,9,5, 2,4,11, 6,2,10, 8,6,7, 9,8,1
    };
    for (FVector& Position : RestPositions)
    {
        Position = Position.GetSafeNormal();
    }

    for (int32 Subdivision = 0; Subdivision < 3; ++Subdivision)
    {
        TMap<uint64, int32> Midpoints;
        const auto Midpoint = [this, &Midpoints](int32 A, int32 B)
        {
            const uint64 Key = SoftBodySolver::EdgeKey(A, B);
            if (const int32* Existing = Midpoints.Find(Key))
            {
                return *Existing;
            }
            const int32 NewIndex = RestPositions.Add((RestPositions[A] + RestPositions[B]).GetSafeNormal());
            Midpoints.Add(Key, NewIndex);
            return NewIndex;
        };
        TArray<int32> Subdivided;
        Subdivided.Reserve(Triangles.Num() * 4);
        for (int32 Index = 0; Index < Triangles.Num(); Index += 3)
        {
            const int32 A = Triangles[Index];
            const int32 B = Triangles[Index + 1];
            const int32 C = Triangles[Index + 2];
            const int32 AB = Midpoint(A, B);
            const int32 BC = Midpoint(B, C);
            const int32 CA = Midpoint(C, A);
            Subdivided.Append({A, AB, CA, B, BC, AB, C, CA, BC, AB, BC, CA});
        }
        Triangles = MoveTemp(Subdivided);
    }
    for (FVector& Position : RestPositions)
    {
        Position *= BallRadius;
    }
}

void FSoftBodySolver::BuildConstraints()
{
    Constraints.Reset();
    Constraints.Reserve(4200);
    TMap<uint64, int32> OppositeVertices;
    const auto AddConstraint = [this](int32 A, int32 B, uint8 Kind)
    {
        FDistanceConstraint Constraint;
        Constraint.A = A;
        Constraint.B = B;
        Constraint.RestLength = static_cast<float>(FVector::Distance(RestPositions[A], RestPositions[B]));
        Constraint.Kind = Kind;
        Constraints.Add(Constraint);
    };

    for (int32 Triangle = 0; Triangle < Triangles.Num(); Triangle += 3)
    {
        for (int32 Edge = 0; Edge < 3; ++Edge)
        {
            const int32 A = Triangles[Triangle + Edge];
            const int32 B = Triangles[Triangle + (Edge + 1) % 3];
            const int32 C = Triangles[Triangle + (Edge + 2) % 3];
            const uint64 Key = SoftBodySolver::EdgeKey(A, B);
            if (const int32* OtherOpposite = OppositeVertices.Find(Key))
            {
                // A spring across adjacent triangles resists sharp folds but permits a finger-sized dent.
                AddConstraint(*OtherOpposite, C, 1);
            }
            else
            {
                OppositeVertices.Add(Key, C);
                AddConstraint(A, B, 0);
            }
        }
    }

    // Sparse internal diameter springs prevent the hollow surface from turning inside out.
    for (int32 A = 0; A < RestPositions.Num(); ++A)
    {
        int32 B = A;
        double SmallestDot = TNumericLimits<double>::Max();
        for (int32 Candidate = 0; Candidate < RestPositions.Num(); ++Candidate)
        {
            const double Dot = FVector::DotProduct(RestPositions[A], RestPositions[Candidate]);
            if (Dot < SmallestDot)
            {
                SmallestDot = Dot;
                B = Candidate;
            }
        }
        if (A < B)
        {
            AddConstraint(A, B, 2);
        }
    }
}

void FSoftBodySolver::Advance(float DeltaSeconds, const TArray<FSoftBodyContact>& Contacts, float FloorZ)
{
    if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f || Positions.IsEmpty())
    {
        return;
    }
    const float SafeFloorZ = FMath::IsFinite(FloorZ) ? FloorZ : -BallRadius;
    // Discard excess wall time after a hitch instead of accumulating an unbounded catch-up workload.
    Accumulator += FMath::Min(static_cast<double>(DeltaSeconds), SoftBodySolver::FixedStep * SoftBodySolver::MaximumSteps);
    TArray<uint8> TouchedContacts;
    TouchedContacts.SetNumZeroed(Contacts.Num());
    int32 Steps = 0;
    while (Accumulator + 1.0e-10 >= SoftBodySolver::FixedStep && Steps < SoftBodySolver::MaximumSteps)
    {
        Step(static_cast<float>(SoftBodySolver::FixedStep), Contacts, SafeFloorZ, TouchedContacts);
        Accumulator -= SoftBodySolver::FixedStep;
        ++Steps;
    }
    if (Steps > 0)
    {
        ContactCount = 0;
        for (const uint8 Touched : TouchedContacts)
        {
            ContactCount += Touched != 0 ? 1 : 0;
        }
        ContactFlags = MoveTemp(TouchedContacts);
    }
}

void FSoftBodySolver::Step(float DeltaSeconds, const TArray<FSoftBodyContact>& Contacts, float FloorZ,
    TArray<uint8>& TouchedContacts)
{
    const double Damping = FMath::Exp(-5.0 * DeltaSeconds);
    for (int32 Index = 0; Index < Positions.Num(); ++Index)
    {
        PreviousPositions[Index] = Positions[Index];
        Velocities[Index] *= Damping;
        // The actor owns gross motion. Mild local gravity gives a soft, slightly flattened resting base.
        Velocities[Index].Z -= (BallRadius / 18.0) * 10.0 * DeltaSeconds;
        Positions[Index] += Velocities[Index] * DeltaSeconds;
        ShapeLambdas[Index] = FVector::ZeroVector;
    }
    for (FDistanceConstraint& Constraint : Constraints)
    {
        Constraint.Lambda = 0.0f;
    }
    VolumeLambda = 0.0;

    for (int32 Iteration = 0; Iteration < SoftBodySolver::Iterations; ++Iteration)
    {
        SolveDistances(DeltaSeconds);
        SolveRestShape(DeltaSeconds);
        SolveVolume(DeltaSeconds);
        SolveContacts(Contacts, FloorZ, TouchedContacts);
    }

    const double MaximumSpeed = BallRadius * 8.0;
    for (int32 Index = 0; Index < Positions.Num(); ++Index)
    {
        if (Positions[Index].ContainsNaN() || Positions[Index].SizeSquared() > FMath::Square(BallRadius * 6.0))
        {
            Reset();
            return;
        }
        Velocities[Index] = ((Positions[Index] - PreviousPositions[Index]) / DeltaSeconds).GetClampedToMaxSize(MaximumSpeed);
        if (Positions[Index].Z <= FloorZ + 0.001)
        {
            Velocities[Index].X *= 0.8;
            Velocities[Index].Y *= 0.8;
            Velocities[Index].Z = FMath::Max(0.0, Velocities[Index].Z);
        }
    }
}

void FSoftBodySolver::SolveDistances(float DeltaSeconds)
{
    const float Compliance[] = {
        FMath::Lerp(0.00002f, 0.00035f, Softness),
        FMath::Lerp(0.001f, 0.020f, Softness),
        FMath::Lerp(0.004f, 0.030f, Softness)
    };
    const float InverseStepSquared = 1.0f / FMath::Square(DeltaSeconds);
    for (FDistanceConstraint& Constraint : Constraints)
    {
        const FVector Difference = Positions[Constraint.A] - Positions[Constraint.B];
        const double Length = Difference.Size();
        if (Length < 1.0e-6)
        {
            continue;
        }
        const double Alpha = Compliance[Constraint.Kind] * InverseStepSquared;
        const double DeltaLambda = (-(Length - Constraint.RestLength) - Alpha * Constraint.Lambda) / (2.0 + Alpha);
        const FVector Correction = Difference * (DeltaLambda / Length);
        Positions[Constraint.A] += Correction;
        Positions[Constraint.B] -= Correction;
        Constraint.Lambda += static_cast<float>(DeltaLambda);
    }
}

void FSoftBodySolver::SolveRestShape(float DeltaSeconds)
{
    // Weak elastic tethers represent the interior material and recover the original shape after release.
    const double Alpha = FMath::Lerp(0.018, 0.065, static_cast<double>(Softness)) / FMath::Square(DeltaSeconds);
    for (int32 Index = 0; Index < Positions.Num(); ++Index)
    {
        const FVector DeltaLambda = (RestPositions[Index] - Positions[Index] - Alpha * ShapeLambdas[Index]) / (1.0 + Alpha);
        Positions[Index] += DeltaLambda;
        ShapeLambdas[Index] += DeltaLambda;
    }
}

void FSoftBodySolver::SolveVolume(float DeltaSeconds)
{
    for (FVector& Gradient : VolumeGradients)
    {
        Gradient = FVector::ZeroVector;
    }
    double Volume = 0.0;
    const double Normalization = 1.0 / FMath::Square(static_cast<double>(BallRadius));
    for (int32 Triangle = 0; Triangle < Triangles.Num(); Triangle += 3)
    {
        const int32 A = Triangles[Triangle];
        const int32 B = Triangles[Triangle + 1];
        const int32 C = Triangles[Triangle + 2];
        const FVector CrossBC = FVector::CrossProduct(Positions[B], Positions[C]);
        Volume += FVector::DotProduct(Positions[A], CrossBC) / 6.0;
        VolumeGradients[A] += CrossBC * (Normalization / 6.0);
        VolumeGradients[B] += FVector::CrossProduct(Positions[C], Positions[A]) * (Normalization / 6.0);
        VolumeGradients[C] += FVector::CrossProduct(Positions[A], Positions[B]) * (Normalization / 6.0);
    }
    double GradientSquared = 0.0;
    for (const FVector& Gradient : VolumeGradients)
    {
        GradientSquared += Gradient.SizeSquared();
    }
    const double Alpha = FMath::Lerp(0.0000003, 0.000002, static_cast<double>(Softness)) / FMath::Square(DeltaSeconds);
    const double DeltaLambda = (-(Volume - RestVolume) * Normalization - Alpha * VolumeLambda) / (GradientSquared + Alpha);
    VolumeLambda += DeltaLambda;
    for (int32 Index = 0; Index < Positions.Num(); ++Index)
    {
        Positions[Index] += VolumeGradients[Index] * DeltaLambda;
    }
}

void FSoftBodySolver::SolveContacts(const TArray<FSoftBodyContact>& Contacts, float FloorZ,
    TArray<uint8>& TouchedContacts)
{
    // Repeat the collision sweep so neighboring finger spheres do not leave a vertex inside one another.
    for (int32 Sweep = 0; Sweep < 3; ++Sweep)
    {
        for (int32 Index = 0; Index < Positions.Num(); ++Index)
        {
            FVector& Position = Positions[Index];
            for (int32 ContactIndex = 0; ContactIndex < Contacts.Num(); ++ContactIndex)
            {
                const FSoftBodyContact& Contact = Contacts[ContactIndex];
                if (!FMath::IsFinite(Contact.Radius) || Contact.Radius <= 0.0f || Contact.Center.ContainsNaN())
                {
                    continue;
                }
                const FVector Offset = Position - Contact.Center;
                const double DistanceSquared = Offset.SizeSquared();
                if (DistanceSquared < FMath::Square(static_cast<double>(Contact.Radius)))
                {
                    const FVector Normal = DistanceSquared > 1.0e-12
                        ? Offset / FMath::Sqrt(DistanceSquared)
                        : (RestPositions[Index] - Contact.Center).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
                    Position = Contact.Center + Normal * Contact.Radius;
                    TouchedContacts[ContactIndex] = 1;
                }
            }
            Position.Z = FMath::Max(Position.Z, static_cast<double>(FloorZ));
        }
    }
}

double FSoftBodySolver::CalculateVolume() const
{
    double Volume = 0.0;
    for (int32 Triangle = 0; Triangle < Triangles.Num(); Triangle += 3)
    {
        Volume += FVector::DotProduct(Positions[Triangles[Triangle]],
            FVector::CrossProduct(Positions[Triangles[Triangle + 1]], Positions[Triangles[Triangle + 2]])) / 6.0;
    }
    return Volume;
}

float FSoftBodySolver::GetVolumeRatio() const
{
    return RestVolume > UE_SMALL_NUMBER ? static_cast<float>(CalculateVolume() / RestVolume) : 1.0f;
}

float FSoftBodySolver::GetMaxDisplacement() const
{
    double MaximumSquared = 0.0;
    for (int32 Index = 0; Index < Positions.Num(); ++Index)
    {
        MaximumSquared = FMath::Max(MaximumSquared, FVector::DistSquared(Positions[Index], RestPositions[Index]));
    }
    return static_cast<float>(FMath::Sqrt(MaximumSquared));
}
