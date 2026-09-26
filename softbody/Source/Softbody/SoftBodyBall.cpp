#include "SoftBodyBall.h"
#include "ProceduralMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "Engine/World.h"

ASoftBodyBall::ASoftBodyBall()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
    PhysicsRoot = CreateDefaultSubobject<USphereComponent>(TEXT("PhysicsCore"));
    RootComponent = PhysicsRoot;
    PhysicsRoot->SetSphereRadius(BallRadius);
    PhysicsRoot->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Surface = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("SoftSurface"));
    Surface->SetupAttachment(PhysicsRoot);
    Surface->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Surface->bUseAsyncCooking = true;
}

void ASoftBodyBall::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    BallRadius = FMath::Clamp(BallRadius, 1.f, 100.f);
    Solver.Initialize(BallRadius);
    Solver.SetSoftness(Softness);
    PhysicsRoot->SetSphereRadius(BallRadius);
    BuildSurface();
}

void ASoftBodyBall::BeginPlay()
{
    Super::BeginPlay();
    BallRadius = FMath::Clamp(BallRadius, 1.f, 100.f);
    RestLocation = GetActorLocation();
    Solver.Initialize(BallRadius);
    Solver.SetSoftness(Softness);
    PhysicsRoot->SetSphereRadius(bHandInteractable ? BallRadius : BallRadius * .9f);
    if (!bHandInteractable)
    {
        PhysicsRoot->SetCollisionProfileName(TEXT("PhysicsActor"));
        PhysicsRoot->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        PhysicsRoot->BodyInstance.bLockXRotation = true;
        PhysicsRoot->BodyInstance.bLockYRotation = true;
        PhysicsRoot->BodyInstance.bLockZRotation = true;
        PhysicsRoot->SetSimulatePhysics(true);
        PhysicsRoot->SetMassOverrideInKg(NAME_None, 12.f);
        PhysicsRoot->SetLinearDamping(3.5f);
        PhysicsRoot->SetAngularDamping(2.f);
        PhysicsRoot->BodyInstance.bUseCCD = true;
    }
    BuildSurface();
    UE_LOG(LogTemp, Display, TEXT("SOFTBODY ball=%s radius=%.2f particles=%d hand=%d"), *DisplayName, BallRadius, Solver.GetPositions().Num(), bHandInteractable);
}

void ASoftBodyBall::SetHandContacts(const TArray<FSoftBodyContact>& InContacts)
{
    if (bHandInteractable) Contacts = InContacts;
}

bool ASoftBodyBall::HasContactInRange(int32 Start, int32 End) const
{
    const TArray<uint8>& Flags = Solver.GetContactFlags();
    for (int32 I = FMath::Max(0, Start); I < FMath::Min(End, Flags.Num()); ++I)
        if (Flags[I]) return true;
    return false;
}

void ASoftBodyBall::ResetBall()
{
    Contacts.Reset();
    if (PhysicsRoot->IsSimulatingPhysics())
    {
        PhysicsRoot->SetPhysicsLinearVelocity(FVector::ZeroVector);
        PhysicsRoot->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
    }
    SetActorLocationAndRotation(RestLocation, FRotator::ZeroRotator, false, nullptr, ETeleportType::TeleportPhysics);
    Solver.Reset();
    UpdateSurface();
}

void ASoftBodyBall::GatherBodyContacts()
{
    Contacts.Reset();
    ACharacter* Character = UGameplayStatics::GetPlayerCharacter(this, 0);
    if (!Character) return;
    const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
    const float Radius = Capsule->GetScaledCapsuleRadius();
    const float Segment = Capsule->GetScaledCapsuleHalfHeight() - Radius;
    const FVector Center = Capsule->GetComponentLocation();
    const FTransform BallTransform = GetActorTransform();
    for (int32 Index = 0; Index < 7; ++Index)
    {
        const FVector Sample = Center + FVector(0, 0, FMath::Lerp(-Segment, Segment, Index / 6.f));
        if (FVector::DistSquared(Sample, GetActorLocation()) < FMath::Square(BallRadius + Radius + 5.f))
        {
            FSoftBodyContact Contact;
            Contact.Center = BallTransform.InverseTransformPosition(Sample);
            Contact.Radius = Radius;
            Contacts.Add(Contact);
        }
    }
    if (!Contacts.IsEmpty())
    {
        const FVector Away = (GetActorLocation() - Center).GetSafeNormal2D();
        const float ClosingSpeed = FVector::DotProduct(Character->GetVelocity(), Away);
        if (ClosingSpeed > 1.f) PhysicsRoot->AddForce(Away * FMath::Clamp(ClosingSpeed * 35.f, 0.f, 10000.f));
    }
}

void ASoftBodyBall::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bHandInteractable)
    {
        // Reset before integrating an invalid floor plane, including leaving the studio.
        const FVector Location = GetActorLocation();
        if (Location.Z < 0 || FMath::Abs(Location.X) > 610 || FMath::Abs(Location.Y) > 610) ResetBall();
        const FVector Velocity = PhysicsRoot->GetPhysicsLinearVelocity();
        const FVector Horizontal = FVector(Velocity.X, Velocity.Y, 0).GetClampedToMaxSize(140.f);
        if (Velocity.SizeSquared2D() > FMath::Square(140.f))
            PhysicsRoot->SetPhysicsLinearVelocity(FVector(Horizontal.X, Horizontal.Y, Velocity.Z));
        GatherBodyContacts();
    }
    Solver.Advance(DeltaSeconds, Contacts, bHandInteractable ? -BallRadius : -GetActorLocation().Z);
    UpdateSurface();
}

void ASoftBodyBall::BuildSurface()
{
    RestParticles = Solver.GetPositions();
    ParticleNormals.SetNum(RestParticles.Num());
    RenderBindings.Reset(); RenderVertices.Reset(); RenderTriangles.Reset();
    const TArray<int32>& Faces = Solver.GetTriangles();
    // Interpolate the physical cage onto a finer spherical surface. Physics remains 642 particles.
    constexpr int32 Divisions = 4;
    const auto GridIndex = [](int32 I, int32 J) { return I * 5 - I * (I-1) / 2 + J; };
    for (int32 Face = 0; Face < Faces.Num(); Face += 3)
    {
        const int32 A = Faces[Face], B = Faces[Face+1], C = Faces[Face+2];
        const int32 Base = RenderVertices.Num();
        for (int32 I = 0; I <= Divisions; ++I)
            for (int32 J = 0; J <= Divisions-I; ++J)
            {
                const FVector Weights(1.f-(I+J)/4.f, I/4.f, J/4.f);
                const FVector Point = (RestParticles[A]*Weights.X + RestParticles[B]*Weights.Y + RestParticles[C]*Weights.Z).GetSafeNormal()*BallRadius;
                RenderBindings.Add({A,B,C,Weights,Point});
                RenderVertices.Add(Point);
            }
        for (int32 I = 0; I < Divisions; ++I)
            for (int32 J = 0; J < Divisions-I; ++J)
            {
                // UE front faces are clockwise; solver faces remain outward for signed volume.
                RenderTriangles.Append({Base+GridIndex(I,J), Base+GridIndex(I,J+1), Base+GridIndex(I+1,J)});
                if (J < Divisions-I-1)
                    RenderTriangles.Append({Base+GridIndex(I+1,J), Base+GridIndex(I,J+1), Base+GridIndex(I+1,J+1)});
            }
    }
    Normals.SetNum(RenderVertices.Num());
    UVs.SetNum(RenderVertices.Num());
    Colors.SetNum(RenderVertices.Num());
    for (int32 I = 0; I < RenderVertices.Num(); ++I)
    {
        const FVector Direction = RenderVertices[I].GetSafeNormal();
        Normals[I] = Direction;
        UVs[I] = FVector2D(.5f + FMath::Atan2(Direction.Y, Direction.X) / (2.f * PI), .5f - FMath::Asin(Direction.Z) / PI);
        // Two curved ivory seams follow the sphere, anchored to material particles.
        const float Seam = FMath::Abs(Direction.Z - .5f * FMath::Cos(2.f * FMath::Atan2(Direction.Y, Direction.X)));
        const FLinearColor Base = bHandInteractable ? FLinearColor(.59f,.83f,.045f) : FLinearColor(.025f,.38f,.48f);
        Colors[I] = FMath::Lerp(FLinearColor(.93f,.95f,.73f), Base, FMath::SmoothStep(.025f,.048f, Seam));
    }
    Surface->CreateMeshSection_LinearColor(0, RenderVertices, RenderTriangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), false);
    if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Softbody/Materials/M_Ball.M_Ball"))) Surface->SetMaterial(0, Material);
}

void ASoftBodyBall::UpdateSurface()
{
    const TArray<FVector>& Positions = Solver.GetPositions();
    const TArray<int32>& Faces = Solver.GetTriangles();
    for (FVector& Normal : ParticleNormals) Normal = FVector::ZeroVector;
    for (int32 I = 0; I < Faces.Num(); I += 3)
    {
        const int32 A = Faces[I], B = Faces[I+1], C = Faces[I+2];
        const FVector Normal = FVector::CrossProduct(Positions[B]-Positions[A], Positions[C]-Positions[A]);
        ParticleNormals[A] += Normal; ParticleNormals[B] += Normal; ParticleNormals[C] += Normal;
    }
    for (FVector& Normal : ParticleNormals) Normal.Normalize();
    for (int32 I = 0; I < RenderBindings.Num(); ++I)
    {
        const FRenderBinding& Binding = RenderBindings[I];
        const FVector W = Binding.Weights;
        RenderVertices[I] = Binding.RestPoint +
            (Positions[Binding.A]-RestParticles[Binding.A])*W.X +
            (Positions[Binding.B]-RestParticles[Binding.B])*W.Y +
            (Positions[Binding.C]-RestParticles[Binding.C])*W.Z;
        Normals[I] = (ParticleNormals[Binding.A]*W.X + ParticleNormals[Binding.B]*W.Y + ParticleNormals[Binding.C]*W.Z).GetSafeNormal();
    }
    Surface->UpdateMeshSection_LinearColor(0, RenderVertices, Normals, UVs, Colors, TArray<FProcMeshTangent>());
}
