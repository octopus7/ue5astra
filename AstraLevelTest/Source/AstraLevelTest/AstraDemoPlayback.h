#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AstraDemoValidation.h"
#include "AstraDemoPlayback.generated.h"

class AAstraCat;
class AAstraController;
struct FAstraDemoValidation;

USTRUCT(BlueprintType)
struct FAstraDemoShot
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite) FName Name;
    // World XY in centimetres. The actual collision surface supplies the starting height.
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FVector2D> Waypoints;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(ClampMin="50", ClampMax="340")) float WalkSpeed = 180.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(ClampMin="3")) float MinimumSeconds = 9.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, meta=(ClampMin="1500")) float OrthoWidth = 2600.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FVector CameraOffset = FVector::ZeroVector;
};

/** P toggles a looping, collision-aware location tour. No saved level actors are modified. */
UCLASS(ClassGroup=(Astra), meta=(BlueprintSpawnableComponent))
class ASTRALEVELTEST_API UAstraDemoPlayback : public UActorComponent
{
    GENERATED_BODY()
public:
    UAstraDemoPlayback();
    virtual ~UAstraDemoPlayback() override;
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    void Update(float DeltaTime);
    UFUNCTION(BlueprintCallable, Category="Astra|Demo") void Toggle();
    UFUNCTION(BlueprintCallable, Category="Astra|Demo") bool Start();
    UFUNCTION(BlueprintCallable, Category="Astra|Demo") void Stop();
    UFUNCTION(BlueprintPure, Category="Astra|Demo") bool IsDemoActive() const { return bActive; }
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Astra|Demo") TArray<FAstraDemoShot> Shots;
    int32 GetShotIndex() const { return ShotIndex; }
    int32 GetCompletedLoops() const { return CompletedLoops; }

private:
    friend struct FAstraDemoValidation;
    bool BeginShot(int32 Index);
    void FinishShot(bool bCompleted);
    void CutCamera();
    UPROPERTY(Transient) TObjectPtr<AAstraController> Controller;
    UPROPERTY(Transient) TObjectPtr<AAstraCat> Cat;
    UPROPERTY(Transient) TObjectPtr<AActor> SavedViewTarget;
    FTransform SavedTransform;
    FVector SavedVelocity = FVector::ZeroVector;
    FVector SavedSafeLocation = FVector::ZeroVector;
    FVector SavedCameraOffset = FVector::ZeroVector;
    float SavedGait = 0.f;
    float SavedWalkSpeed = 340.f;
    float SavedOrthoWidth = 3000.f;
    uint8 SavedMovementMode = 0;
    uint8 SavedCustomMovementMode = 0;
    bool bSavedCameraLag = true;
    bool bActive = false;
    int32 ShotIndex = INDEX_NONE;
    int32 WaypointIndex = 1;
    int32 CompletedLoops = 0;
    float ShotTime = 0.f;
    float HoldTime = 0.f;
    float StuckTime = 0.f;
    float ShotDeadline = 20.f;
    float ShotTravel = 0.f;
    float UnsupportedTime = 0.f;
    FVector LastPosition = FVector::ZeroVector;
    bool bShotCaptured = false;
    TUniquePtr<FAstraDemoValidation> Validation;
};
