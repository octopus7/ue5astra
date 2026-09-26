#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "SoftbodyGameMode.generated.h"

class ASoftbodyCharacter;
class ASoftBodyBall;
class ACameraActor;
class APlayerController;

UCLASS()
class SOFTBODY_API ASoftbodyHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};

UCLASS()
class SOFTBODY_API ASoftbodyGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ASoftbodyGameMode();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
private:
    bool bValidate = false;
    float TestTime = 0;
    int32 Stage = 0;
    float Baseline = 0;
    float PeakDeformation[2] = {0,0};
    float ReleasedDeformation[2] = {0,0};
    float VolumeMinimum = 1;
    float VolumeMaximum = 1;
    float BodyDeformation = 0;
    float BodyTravel = 0;
    float BodyBaseline = 0;
    float BodyReleased = 0;
    float BodyContactDeformation = 0;
    float BodyRecoveryError = 0;
    TArray<FVector> BodyRestShape;
    int32 BodyContactFrames = 0;
    float WorstHandError = 0;
    float PalmDownMinimum = 1;
    bool OpposingContact[2] = {false, false};
    int32 PeakContacts = 0;
    UPROPERTY() TObjectPtr<ACameraActor> CaptureCamera;
    float RestoreCameraAt = 0;
    enum class EManualStage : uint8
    {
        Enter, Wheel, WheelIdle, LmbHold, LmbRelease, FinePressure, FineSide, WheelOpen,
        CameraToggle, WideReset, WidePressure, RestoreCloseCamera,
        Pressure, PressureCapture, Right, RightCapture, Left, LeftCapture, ShakeBack, Lift,
        Reset, PositiveLimit, PositiveSettle, PositiveOverrun, PositiveCheck, MiddleCurl, MiddleSettle, MiddleCapture,
        NegativeLimit, NegativeSettle, NegativeOverrun, NegativeCheck, FinalReset,
        DemoIdle, DemoMouseTakeover, DemoWheelReset, DemoWheelReady, DemoWheelTakeover, Exit, Reenter
    };
    struct FManualResult
    {
        bool bWheelPersists = false;
        bool bLmbRestoresWheel = false;
        bool bCurlKeepsHeight = false;
        bool bSmallMouseDelta = false;
        bool bCameraIndependent = false;
        bool bFovConsistent = false;
        bool bOpenPressure = false;
        bool bLateralIndependent = false;
        bool bShakeChangesShape = false;
        bool bLiftIndependent = false;
        bool bLimitsStable = true;
        bool bTableClearance = true;
        bool bReset = false;
        bool bDemoIdle = false;
        bool bDemoMouseTakeover = false;
        bool bDemoWheelTakeover = false;
        bool bExitReset = false;
        float WheelGrip = 0;
        float WheelIdleError = 0;
        float CloseViewPressure = 0;
        float WideViewPressure = 0;
        float FineSideAmount = 0;
        float CameraPoseChange = 0;
        float PressureDrop = 0;
        float PressureShapeChange = 0;
        float LateralTravel = 0;
        float LateralHeightError = 0;
        float ShakeShapeChange = 0;
        float LimitPoseDrift = 0;
        float MaxWristError = 0;
        float MinimumPalmDown = 1;
        float MinimumVolume = 1;
        float MaximumVolume = 1;
        float MinimumTableClearance = TNumericLimits<float>::Max();
        bool Passed() const;
    };
    FManualResult ManualResults[2];
    EManualStage ManualStage = EManualStage::Enter;
    int32 ManualBallIndex = 0;
    int32 ManualWheelSteps = 0;
    float ManualStageStarted = 0;
    FVector NeutralWrist = FVector::ZeroVector;
    FVector PressureWrist = FVector::ZeroVector;
    FVector RightWrist = FVector::ZeroVector;
    FVector LeftWrist = FVector::ZeroVector;
    FVector LimitWrist = FVector::ZeroVector;
    FVector CameraRight = FVector::RightVector;
    TArray<FVector> NeutralShape;
    TArray<FVector> RightShape;
    TArray<FVector> LeftShape;
    void StartManualValidation(ASoftbodyCharacter* Character, APlayerController* PC);
    void TickManualValidation(ASoftbodyCharacter* Character, APlayerController* PC, float DeltaSeconds);
    void AdvanceManualStage(EManualStage Next);
    void Capture(const FString& Name, const FVector& Position, const FVector& Target);
    void WriteReport();
    ASoftBodyBall* FindBall(bool bHand, bool bDouble = false) const;
};
