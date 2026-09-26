#pragma once

#include "CoreMinimal.h"

/** Kinematic hand collider in the ball's local coordinate system, in centimeters. */
struct FSoftBodyContact
{
    FVector Center = FVector::ZeroVector;
    float Radius = 2.0f;
};

/** Small, deterministic CPU XPBD solver. The owning actor supplies the ball's world transform. */
class FSoftBodySolver
{
public:
    FSoftBodySolver();

    void Initialize(float Radius);
    void Reset();
    void Advance(float DeltaSeconds, const TArray<FSoftBodyContact>& Contacts, float FloorZ);
    void SetSoftness(float InSoftness);

    const TArray<FVector>& GetPositions() const { return Positions; }
    const TArray<int32>& GetTriangles() const { return Triangles; }
    float GetVolumeRatio() const;
    float GetMaxDisplacement() const;
    int32 GetContactCount() const { return ContactCount; }
    const TArray<uint8>& GetContactFlags() const { return ContactFlags; }
    float GetRadius() const { return BallRadius; }

private:
    struct FDistanceConstraint
    {
        int32 A = 0;
        int32 B = 0;
        float RestLength = 0.0f;
        float Lambda = 0.0f;
        uint8 Kind = 0;
    };

    void BuildSurface();
    void BuildConstraints();
    void Step(float DeltaSeconds, const TArray<FSoftBodyContact>& Contacts, float FloorZ,
        TArray<uint8>& TouchedContacts);
    void SolveDistances(float DeltaSeconds);
    void SolveRestShape(float DeltaSeconds);
    void SolveVolume(float DeltaSeconds);
    void SolveContacts(const TArray<FSoftBodyContact>& Contacts, float FloorZ,
        TArray<uint8>& TouchedContacts);
    double CalculateVolume() const;

    TArray<FVector> RestPositions;
    TArray<FVector> Positions;
    TArray<FVector> PreviousPositions;
    TArray<FVector> Velocities;
    TArray<FVector> ShapeLambdas;
    TArray<FVector> VolumeGradients;
    TArray<int32> Triangles;
    TArray<FDistanceConstraint> Constraints;
    float BallRadius = 18.0f;
    float Softness = 0.65f;
    double RestVolume = 1.0;
    double VolumeLambda = 0.0;
    double Accumulator = 0.0;
    int32 ContactCount = 0;
    TArray<uint8> ContactFlags;
};
