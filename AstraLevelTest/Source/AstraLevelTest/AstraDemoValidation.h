#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineBaseTypes.h"

class AAstraCat;
class AAstraController;
class UAstraDemoPlayback;

/** Opt-in in-world regression run, driven through the same P/WASD input as a player. */
struct FAstraDemoValidation
{
    explicit FAstraDemoValidation(UAstraDemoPlayback& InDemo);
    void Tick(float DeltaTime);
    void RecordShot(FName Name, bool bCompleted, float Travel, float UnsupportedSeconds);

private:
    enum class EStage : uint8
    {
        AwaitWorld,
        AwaitEntry,
        HoldP,
        Tour,
        AwaitFullStop,
        BeforeReentry,
        AwaitReentry,
        BeforeEarlyStop,
        AwaitEarlyStop,
        BeforeMovement,
        Movement,
        BetweenMovement,
        Finished
    };

    struct FSnapshot
    {
        FTransform Transform;
        FVector Velocity = FVector::ZeroVector;
        FVector CameraOffset = FVector::ZeroVector;
        FRotator CameraRotation = FRotator::ZeroRotator;
        TWeakObjectPtr<AActor> ViewTarget;
        float WalkSpeed = 0.f;
        float OrthoWidth = 0.f;
        float CameraArmLength = 0.f;
        uint8 MovementMode = 0;
        uint8 CustomMovementMode = 0;
        bool bCameraLag = false;
        bool bMoveInputIgnored = false;
    };

    AAstraController* GetController() const;
    AAstraCat* GetCat() const;
    void EnterStage(EStage NewStage);
    void SendP(EInputEvent Event);
    void CaptureSnapshot();
    void CheckRestored(const TCHAR* Prefix);
    void AddCheck(const FString& Name, bool bPassed, const FString& Detail = FString());
    void BeginMovement();
    void Finish(const FString& Failure = FString());

    UAstraDemoPlayback& Demo;
    FString ValidationPrefix;
    EStage Stage = EStage::AwaitWorld;
    FSnapshot Snapshot;
    TArray<FString> Checks;
    TArray<FString> ShotResults;
    TArray<FString> MovementResults;
    TSet<FName> RecordedShots;
    TWeakObjectPtr<AActor> ValidationCamera;
    FVector MovementStart = FVector::ZeroVector;
    float Elapsed = 0.f;
    float StageStarted = 0.f;
    float LastRepeat = 0.f;
    int32 MovementIndex = 0;
    int32 InitialShotIndex = INDEX_NONE;
    int32 ShotCount = 0;
    int32 FailedChecks = 0;
    bool bHeldPStayedActive = true;
};
