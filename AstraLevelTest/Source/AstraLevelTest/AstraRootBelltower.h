#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AstraRootBelltower.generated.h"

class AStaticMeshActor;
class UAudioComponent;
class USoundBase;
class UMaterialInstanceDynamic;

/** A quiet bell and living-root response local to the root belltower map. */
UCLASS()
class ASTRALEVELTEST_API AAstraRootBelltower : public AActor
{
    GENERATED_BODY()
public:
    AAstraRootBelltower();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Tick(float DeltaSeconds) override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Belltower") TObjectPtr<AStaticMeshActor> BellActor;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Belltower") TArray<TObjectPtr<AStaticMeshActor>> RootActors;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Belltower") FVector ResonanceCenter=FVector(-600,0,170);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Belltower") TObjectPtr<USoundBase> ChimeSound;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Belltower") float Resonance=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Belltower") int32 ChimeCount=0;
private:
    UPROPERTY() TObjectPtr<UAudioComponent> ChimeAudio;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> RootGlow;
    FTransform BellRest;
    float Elapsed=0,LastChime=-20,StageStart=0,MaxSwing=0,MaxPivotDrift=0;
    bool bWasNear=false,bConfiguredCamera=false,bValidate=false,bFinished=false;
    int32 TestStage=0,Failures=0;
    FVector MovementStart;
    TArray<FString> Checks;
    void Validate(float DeltaSeconds);
    void Check(const FString& Name,bool Passed,const FString& Detail=FString());
    void FinishValidation();
};
