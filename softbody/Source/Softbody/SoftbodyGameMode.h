#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "SoftbodyGameMode.generated.h"

class ASoftbodyCharacter;
class ASoftBodyBall;
class ACameraActor;

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
    void Capture(const FString& Name, const FVector& Position, const FVector& Target);
    void WriteReport();
    ASoftBodyBall* FindBall(bool bHand, bool bDouble = false) const;
};
