#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AstraStarPond.generated.h"

class AStaticMeshActor;
class UMaterialInstanceDynamic;
class USkeletalMeshComponent;

/** Level-local pond discovery: standing on the observatory connects the sunken stars. */
UCLASS()
class ASTRALEVELTEST_API AAstraStarPond : public AActor
{
    GENERATED_BODY()
public:
    AAstraStarPond();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Star Pond") TObjectPtr<AStaticMeshActor> WaterActor;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Star Pond") FVector Observatory = FVector(-1600,0,148);
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Star Pond") float Alignment = 0.f;
private:
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> WaterMaterial;
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> Guardian;
    bool bValidate = false;
    bool bFinished = false;
    int32 TestStage = 0;
    float Elapsed = 0.f;
    float StageStart = 0.f;
    FVector MovementStart;
    TArray<FString> Checks;
    int32 Failures = 0;
    TMap<FName,FTransform> InitialBones;
    float MaxMovingBoneDelta = 0.f;
    float MaxFootDrift = 0.f;
    FVector GuardianStart;
    void Validate(float DeltaSeconds);
    void Check(const FString& Name, bool Passed, const FString& Detail=FString());
    void FinishValidation();
};
