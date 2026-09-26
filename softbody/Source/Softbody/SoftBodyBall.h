#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SoftBodySolver.h"
#include "SoftBodyBall.generated.h"

class USphereComponent;
class UProceduralMeshComponent;

UCLASS()
class SOFTBODY_API ASoftBodyBall : public AActor
{
    GENERATED_BODY()
public:
    ASoftBodyBall();
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Softbody") float BallRadius = 3.35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Softbody") bool bHandInteractable = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Softbody") FString DisplayName = TEXT("TENNIS");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Softbody", meta=(ClampMin="0",ClampMax="1")) float Softness = .7f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USphereComponent> PhysicsRoot;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UProceduralMeshComponent> Surface;
    void SetHandContacts(const TArray<FSoftBodyContact>& InContacts);
    UFUNCTION(BlueprintCallable) void ResetBall();
    float GetVolumeRatio() const { return Solver.GetVolumeRatio(); }
    float GetMaxDisplacement() const { return Solver.GetMaxDisplacement(); }
    int32 GetContactCount() const { return Solver.GetContactCount(); }
    int32 GetVertexCount() const { return Solver.GetPositions().Num(); }
    const TArray<FVector>& GetParticlePositions() const { return Solver.GetPositions(); }
    bool HasContactInRange(int32 Start, int32 End) const;
    FVector GetRestLocation() const { return RestLocation; }
private:
    struct FRenderBinding
    {
        int32 A, B, C;
        FVector Weights;
        FVector RestPoint;
    };
    FSoftBodySolver Solver;
    TArray<FVector> RestParticles;
    TArray<FVector> ParticleNormals;
    TArray<FRenderBinding> RenderBindings;
    TArray<FSoftBodyContact> Contacts;
    TArray<FVector> RenderVertices;
    TArray<int32> RenderTriangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FLinearColor> Colors;
    FVector RestLocation;
    void BuildSurface();
    void UpdateSurface();
    void GatherBodyContacts();
};
