#include "SoftbodyGameMode.h"
#include "SoftbodyCharacter.h"
#include "SoftBodyBall.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/CameraTypes.h"
#include "Components/PoseableMeshComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputCoreTypes.h"
#include "InputKeyEventArgs.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "HighResScreenshot.h"
#include "UnrealClient.h"
#include "ShaderCompiler.h"
#include "AssetCompilingManager.h"

namespace
{
    void TapKey(APlayerController* PC, const FKey& Key)
    {
        PC->InputKey(FInputKeyEventArgs::CreateSimulated(Key, IE_Pressed, 1.f));
        PC->InputKey(FInputKeyEventArgs::CreateSimulated(Key, IE_Released, 0.f));
    }

    void MoveMouse(APlayerController* PC, const FKey& Axis, float Delta, float DeltaSeconds)
    {
        FInputKeyEventArgs Event = FInputKeyEventArgs::CreateSimulated(Axis, IE_Axis, Delta, 1);
        Event.DeltaTime = DeltaSeconds;
        PC->InputKey(Event);
    }

    FVector ReadWrist(const ASoftbodyCharacter* Character)
    {
        UPoseableMeshComponent* Pose = Character->FindComponentByClass<UPoseableMeshComponent>();
        return Pose ? Pose->GetBoneLocationByName(TEXT("hand_r"), EBoneSpaces::WorldSpace) : FVector::ZeroVector;
    }

    float ShapeDifference(const TArray<FVector>& A, const TArray<FVector>& B)
    {
        float Maximum = 0;
        for (int32 Index = 0; Index < FMath::Min(A.Num(), B.Num()); ++Index)
            Maximum = FMath::Max(Maximum, static_cast<float>(FVector::Distance(A[Index], B[Index])));
        return Maximum;
    }

    float LowestHandPoint(const ASoftbodyCharacter* Character)
    {
        UPoseableMeshComponent* Pose = Character->FindComponentByClass<UPoseableMeshComponent>();
        const USkeletalMesh* Mesh = Pose ? Cast<USkeletalMesh>(Pose->GetSkinnedAsset()) : nullptr;
        if (!Mesh) return -TNumericLimits<float>::Max();
        const FVector Wrist = Pose->GetBoneLocationByName(TEXT("hand_r"), EBoneSpaces::WorldSpace);
        const FVector Middle = Pose->GetBoneLocationByName(TEXT("middle_01_r"), EBoneSpaces::WorldSpace);
        float Lowest = FMath::Min(FMath::Lerp(Wrist, Middle, .55f).Z - 2.8f, FMath::Lerp(Wrist, Middle, .9f).Z - 2.4f);
        const TCHAR* Digits[] = { TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("pinky"), TEXT("thumb") };
        for (int32 Finger = 0; Finger < 5; ++Finger)
        {
            const float Radius = Finger == 4 ? 1.15f : (Finger == 3 ? .85f : 1.f);
            for (int32 Joint = 1; Joint <= 3; ++Joint)
            {
                const FName Name(*FString::Printf(TEXT("%s_%02d_r"), Digits[Finger], Joint));
                const FTransform Bone = Pose->GetBoneTransformByName(Name, EBoneSpaces::WorldSpace);
                FVector End;
                if (Joint < 3)
                {
                    const FName Next(*FString::Printf(TEXT("%s_%02d_r"), Digits[Finger], Joint + 1));
                    End = Pose->GetBoneLocationByName(Next, EBoneSpaces::WorldSpace);
                }
                else
                {
                    const int32 Index = Mesh->GetRefSkeleton().FindBoneIndex(Name);
                    if (Index == INDEX_NONE) return -TNumericLimits<float>::Max();
                    // Express the measured terminal length in this bone's local frame,
                    // then transform it with the actual posed terminal-bone rotation.
                    const FTransform& Reference = Mesh->GetRefSkeleton().GetRefBonePose()[Index];
                    const FVector TipLocal = Reference.GetRotation().UnrotateVector(Reference.GetTranslation()) * .8f;
                    End = Bone.TransformPosition(TipLocal);
                }
                Lowest = FMath::Min(Lowest, static_cast<float>(FMath::Min(Bone.GetLocation().Z, End.Z)) - Radius);
            }
        }
        return Lowest;
    }
}

ASoftbodyGameMode::ASoftbodyGameMode()
{
    DefaultPawnClass = ASoftbodyCharacter::StaticClass();
    HUDClass = ASoftbodyHUD::StaticClass();
    PrimaryActorTick.bCanEverTick = true;
}

void ASoftbodyGameMode::BeginPlay()
{
    Super::BeginPlay();
    bValidate = FParse::Param(FCommandLine::Get(), TEXT("SoftbodyValidate"));
    // The first uncooked run must finish material/mesh compilation before taking evidence.
#if WITH_EDITOR
    if (bValidate)
    {
        FAssetCompilingManager::Get().FinishAllCompilation();
        if (GShaderCompilingManager) GShaderCompilingManager->FinishAllCompilation();
    }
#endif
    if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
    {
        PC->SetInputMode(FInputModeGameOnly());
        PC->bShowMouseCursor = false;
        PC->SetControlRotation(FRotator(-12, 0, 0));
    }
}

ASoftBodyBall* ASoftbodyGameMode::FindBall(bool bHand, bool bDouble) const
{
    for (TActorIterator<ASoftBodyBall> It(GetWorld()); It; ++It)
        if (It->bHandInteractable == bHand && (!bHand || (It->BallRadius > 5.f) == bDouble)) return *It;
    return nullptr;
}

void ASoftbodyGameMode::Capture(const FString& Name, const FVector& Position, const FVector& Target)
{
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    if (!PC) return;
    if (!CaptureCamera) CaptureCamera = GetWorld()->SpawnActor<ACameraActor>();
    CaptureCamera->SetActorLocation(Position);
    CaptureCamera->SetActorRotation((Target - Position).Rotation());
    CaptureCamera->GetCameraComponent()->SetFieldOfView(45.f);
    CaptureCamera->GetCameraComponent()->bConstrainAspectRatio = false;
    PC->SetViewTarget(CaptureCamera);
    const FString Directory = FPaths::ProjectDir() / TEXT("Previews");
    IFileManager::Get().MakeDirectory(*Directory, true);
    FScreenshotRequest::RequestScreenshot(Directory / (Name + TEXT(".png")), false, false);
    RestoreCameraAt = TestTime + .35f;
}

void ASoftbodyGameMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    TestTime += DeltaSeconds;
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    ASoftbodyCharacter* Character = PC ? Cast<ASoftbodyCharacter>(PC->GetPawn()) : nullptr;
    if (!Character) return;
    if (!bValidate)
    {
        if (Stage == 0 && TestTime > 2 && FParse::Param(FCommandLine::Get(), TEXT("SoftbodyDemo")))
        { Character->SetAutoDemo(true); Stage = 1; }
        return;
    }
    if (RestoreCameraAt > 0 && TestTime > RestoreCameraAt)
    { PC->SetViewTarget(Character); RestoreCameraAt = 0; }
    if (TestTime < 2) return;
    ASoftBodyBall* Small = FindBall(true, false);
    ASoftBodyBall* Double = FindBall(true, true);
    ASoftBodyBall* Body = FindBall(false);
    if (!Small || !Double || !Body)
    {
        UE_LOG(LogTemp, Error, TEXT("SOFTBODY validation missing one of three balls"));
        if (TestTime > 5) FPlatformMisc::RequestExit(false);
        return;
    }
    for (ASoftBodyBall* Ball : { Small, Double, Body })
    {
        VolumeMinimum = FMath::Min(VolumeMinimum, Ball->GetVolumeRatio());
        VolumeMaximum = FMath::Max(VolumeMaximum, Ball->GetVolumeRatio());
    }
    if (Stage >= 2 && Stage <= 3) PeakDeformation[0] = FMath::Max(PeakDeformation[0], Small->GetMaxDisplacement());
    if (Stage >= 6 && Stage <= 7) PeakDeformation[1] = FMath::Max(PeakDeformation[1], Double->GetMaxDisplacement());
    PeakContacts = FMath::Max(PeakContacts, FMath::Max(Small->GetContactCount(), Double->GetContactCount()));
    if (Stage >= 10 && Stage <= 13)
    {
        BodyDeformation = FMath::Max(BodyDeformation, Body->GetMaxDisplacement());
        BodyTravel = FMath::Max(BodyTravel, FVector::Dist2D(Body->GetActorLocation(), Body->GetRestLocation()));
        if (Body->GetContactCount() > 0)
        {
            BodyContactFrames++;
            const TArray<FVector>& Positions = Body->GetParticlePositions();
            for (int32 I = 0; I < FMath::Min(Positions.Num(), BodyRestShape.Num()); ++I)
                BodyContactDeformation = FMath::Max(BodyContactDeformation, static_cast<float>(FVector::Dist(Positions[I], BodyRestShape[I])));
        }
    }
    if (Stage <= 8 && Character->bInteracting && Character->GripAmount > .95f)
    {
        WorstHandError = FMath::Max(WorstHandError, Character->GetHandContactError());
        PalmDownMinimum = FMath::Min(PalmDownMinimum, Character->GetPalmDownAlignment());
        if (ASoftBodyBall* Held = Character->GetBall())
        {
            const int32 BallIndex = Held->BallRadius > 5.f ? 1 : 0;
            // Character supplies two palm spheres, four fingers x9, then thumb x9.
            OpposingContact[BallIndex] |= Held->HasContactInRange(2, 38) && Held->HasContactInRange(38, 47);
        }
    }
    if (Stage == 0)
    {
        Capture(TEXT("01_Overview"), FVector(490,-560,315), FVector(65,10,88));
        Stage++;
    }
    else if (Stage == 1 && TestTime > 3)
    {
        Character->BeginInteraction(); Character->SetGripInput(0); Stage++;
    }
    else if (Stage == 2 && TestTime > 5)
    {
        Capture(TEXT("02_Tennis_Open"), Small->GetActorLocation()+FVector(26,-42,24), Small->GetActorLocation()+FVector(0,0,3));
        Character->SetGripInput(1); Stage++;
    }
    else if (Stage == 3 && TestTime > 8)
    {
        Capture(TEXT("03_Tennis_Grip"), Small->GetActorLocation()+FVector(26,-42,24), Small->GetActorLocation()+FVector(0,0,3));
        Character->SetGripInput(0); Stage++;
    }
    else if (Stage == 4 && TestTime > 12)
    {
        ReleasedDeformation[0] = Small->GetMaxDisplacement();
        Capture(TEXT("04_Tennis_Released"), Small->GetActorLocation()+FVector(26,-42,24), Small->GetActorLocation()+FVector(0,0,3));
        Character->EndInteraction();
        Character->SetActorLocation(FVector(-100,65,96));
        Stage++;
    }
    else if (Stage == 5 && TestTime > 13)
    { Character->BeginInteraction(); Character->SetGripInput(0); Stage++; }
    else if (Stage == 6 && TestTime > 15)
    {
        Capture(TEXT("05_Double_Open"), Double->GetActorLocation()+FVector(34,-55,30), Double->GetActorLocation()+FVector(0,0,4));
        Character->SetGripInput(1); Stage++;
    }
    else if (Stage == 7 && TestTime > 18)
    {
        Capture(TEXT("06_Double_Grip"), Double->GetActorLocation()+FVector(34,-55,30), Double->GetActorLocation()+FVector(0,0,4));
        Character->SetGripInput(0); Stage++;
    }
    else if (Stage == 8 && TestTime > 22)
    {
        ReleasedDeformation[1] = Double->GetMaxDisplacement();
        Capture(TEXT("07_Double_Released"), Double->GetActorLocation()+FVector(34,-55,30), Double->GetActorLocation()+FVector(0,0,4));
        Character->EndInteraction();
        Character->SetActorLocation(FVector(75,130,96));
        Character->SetActorRotation(FRotator::ZeroRotator);
        PC->SetControlRotation(FRotator::ZeroRotator);
        Stage++;
    }
    else if (Stage == 9 && TestTime > 23)
    {
        BodyBaseline = Body->GetMaxDisplacement();
        BodyRestShape = Body->GetParticlePositions();
        PC->InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::W, IE_Pressed, 1.f)); Stage++;
    }
    else if (Stage == 10 && TestTime > 24.1f)
    {
        Capture(TEXT("08_Body_Push"), Body->GetActorLocation()+FVector(-160,-330,160), Body->GetActorLocation()+FVector(-30,0,48)); Stage++;
    }
    else if (Stage == 11 && TestTime > 24.8f)
    {
        PC->InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::W, IE_Released, 0.f));
        Character->GetCharacterMovement()->StopMovementImmediately();
        Character->SetActorLocation(Character->GetActorLocation() + FVector(-90,0,0));
        Stage++;
    }
    else if (Stage == 12 && TestTime > 27)
    {
        Capture(TEXT("09_Body_Released"), Body->GetActorLocation()+FVector(-160,-330,160), Body->GetActorLocation()+FVector(-30,0,48)); Stage++;
    }
    else if (Stage == 13 && TestTime > 29)
    {
        BodyReleased = Body->GetMaxDisplacement();
        const TArray<FVector>& Positions = Body->GetParticlePositions();
        for (int32 I = 0; I < FMath::Min(Positions.Num(), BodyRestShape.Num()); ++I)
            BodyRecoveryError = FMath::Max(BodyRecoveryError, static_cast<float>(FVector::Dist(Positions[I], BodyRestShape[I])));
        StartManualValidation(Character, PC);
        Stage++;
    }
    else if (Stage == 14) TickManualValidation(Character, PC, DeltaSeconds);
}

bool ASoftbodyGameMode::FManualResult::Passed() const
{
    return bWheelPersists && bLmbRestoresWheel && bCurlKeepsHeight && bSmallMouseDelta && bCameraIndependent && bFovConsistent && bOpenPressure &&
        bLateralIndependent && bShakeChangesShape && bLiftIndependent && bLimitsStable && bTableClearance &&
        bReset && bDemoIdle && bDemoMouseTakeover && bDemoWheelTakeover && bExitReset;
}

void ASoftbodyGameMode::AdvanceManualStage(EManualStage Next)
{
    ManualStage = Next;
    ManualStageStarted = TestTime;
}

void ASoftbodyGameMode::StartManualValidation(ASoftbodyCharacter* Character, APlayerController* PC)
{
    Character->EndInteraction();
    ASoftBodyBall* Ball = FindBall(true, ManualBallIndex == 1);
    Ball->ResetBall();
    Character->SetActorLocation(FVector(Ball->GetActorLocation().X - 70.f, Ball->GetActorLocation().Y, 96.f));
    PC->SetViewTarget(Character);
    RestoreCameraAt = 0;
    TapKey(PC, EKeys::E);
    AdvanceManualStage(EManualStage::Enter);
}

void ASoftbodyGameMode::TickManualValidation(ASoftbodyCharacter* Character, APlayerController* PC, float DeltaSeconds)
{
    ASoftBodyBall* Ball = FindBall(true, ManualBallIndex == 1);
    FManualResult& Result = ManualResults[ManualBallIndex];
    const float Elapsed = TestTime - ManualStageStarted;
    const float Radius = Ball->BallRadius;
    const FVector Wrist = ReadWrist(Character);
    const TArray<FVector>& Shape = Ball->GetParticlePositions();
    if (Character->bInteracting)
    {
        Result.MaxWristError = FMath::Max(Result.MaxWristError, Character->GetHandContactError());
        Result.MinimumPalmDown = FMath::Min(Result.MinimumPalmDown, Character->GetPalmDownAlignment());
        Result.MinimumVolume = FMath::Min(Result.MinimumVolume, Ball->GetVolumeRatio());
        Result.MaximumVolume = FMath::Max(Result.MaximumVolume, Ball->GetVolumeRatio());
        const float Clearance = LowestHandPoint(Character) - (Ball->GetActorLocation().Z - Radius);
        Result.MinimumTableClearance = FMath::Min(Result.MinimumTableClearance, Clearance);
        Result.bTableClearance &= FMath::IsFinite(Clearance) && Clearance >= -.02f;
        Result.bLimitsStable &= !Wrist.ContainsNaN() && FMath::IsFinite(Character->GripAmount) &&
            Character->GripAmount >= -.001f && Character->GripAmount <= 1.001f &&
            Character->GetHandContactError() < 1.f && Character->GetPalmDownAlignment() > .95f &&
            FMath::IsFinite(Ball->GetVolumeRatio()) && Ball->GetVolumeRatio() > .9f && Ball->GetVolumeRatio() < 1.1f;
        for (const FVector& Point : Shape)
            Result.bLimitsStable &= !Point.ContainsNaN() && Point.Size() < Radius * 2.f;
    }
    auto Axis = [&](const FKey& Key, float Delta) { MoveMouse(PC, Key, Delta, DeltaSeconds); };
    auto CaptureManual = [&](const TCHAR* Suffix)
    {
        const FVector Center = Ball->GetActorLocation();
        const float Scale = ManualBallIndex == 0 ? 1.f : 1.3f;
        Capture(FString::Printf(TEXT("%02d_%s_%s"), 10 + ManualBallIndex * 3,
            ManualBallIndex == 0 ? TEXT("Tennis") : TEXT("Double"), Suffix),
            Center + FVector(26,-42,24) * Scale, Center + FVector(0,0,3) * Scale);
    };
    auto AtNeutral = [&]()
    {
        return Character->bInteracting && Character->GripAmount < .02f && FVector::Distance(Wrist, NeutralWrist) < .12f;
    };
    auto DriveLimit = [&](bool bPositive)
    {
        TapKey(PC, bPositive ? EKeys::MouseScrollUp : EKeys::MouseScrollDown);
        Axis(EKeys::MouseX, bPositive ? 3000.f : -3000.f);
        Axis(EKeys::MouseY, bPositive ? -3000.f : 3000.f);
    };

    switch (ManualStage)
    {
    case EManualStage::Enter:
        if (Elapsed < 1.2f) break;
        Result.bLimitsStable &= Character->bInteracting && Character->GetBall() == Ball;
        NeutralWrist = Wrist;
        NeutralShape = Shape;
        {
            FMinimalViewInfo View;
            Character->CalcCamera(DeltaSeconds, View);
            CameraRight = FRotationMatrix(View.Rotation).GetUnitAxis(EAxis::Y).GetSafeNormal2D();
        }
        TapKey(PC, EKeys::MouseScrollUp);
        AdvanceManualStage(EManualStage::Wheel);
        break;
    case EManualStage::Wheel:
        if (Elapsed < .9f) break;
        Result.WheelGrip = Character->GripAmount;
        Result.bCurlKeepsHeight = FMath::Abs(Wrist.Z - NeutralWrist.Z) < .1f;
        AdvanceManualStage(EManualStage::WheelIdle);
        break;
    case EManualStage::WheelIdle:
        if (Elapsed < 1.f) break;
        Result.WheelIdleError = FMath::Abs(Character->GripAmount - Result.WheelGrip);
        Result.bWheelPersists = Result.WheelGrip > .02f && Result.WheelGrip < .9f && Result.WheelIdleError < .015f;
        PC->InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::LeftMouseButton, IE_Pressed, 1.f));
        AdvanceManualStage(EManualStage::LmbHold);
        break;
    case EManualStage::LmbHold:
        if (Elapsed < .9f) break;
        Result.bLmbRestoresWheel = Character->GripAmount > .95f && Result.WheelGrip > .02f && Result.WheelGrip < .9f;
        PC->InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::LeftMouseButton, IE_Released, 0.f));
        AdvanceManualStage(EManualStage::LmbRelease);
        break;
    case EManualStage::LmbRelease:
        if (Elapsed < .9f) break;
        Result.bLmbRestoresWheel &= FMath::Abs(Character->GripAmount - Result.WheelGrip) < .02f;
        Axis(EKeys::MouseY, -40.f);
        AdvanceManualStage(EManualStage::FinePressure);
        break;
    case EManualStage::FinePressure:
        if (Elapsed < .9f) break;
        Result.CloseViewPressure = Character->PressureAmount;
        PressureWrist = Wrist;
        Result.bSmallMouseDelta = Result.CloseViewPressure > .15f && Result.CloseViewPressure < .35f &&
            FMath::Abs(Character->GripAmount - Result.WheelGrip) < .02f &&
            FVector::Dist2D(Wrist, NeutralWrist) < .1f && NeutralWrist.Z - Wrist.Z > Radius * .03f;
        Axis(EKeys::MouseX, 40.f);
        AdvanceManualStage(EManualStage::FineSide);
        break;
    case EManualStage::FineSide:
        if (Elapsed < .9f) break;
        Result.FineSideAmount = Character->HandOffsetAmount;
        Result.bSmallMouseDelta &= Result.FineSideAmount > .15f && Result.FineSideAmount < .35f &&
            FMath::Abs(Character->PressureAmount - Result.CloseViewPressure) < .01f &&
            FMath::Abs(Character->GripAmount - Result.WheelGrip) < .02f &&
            FMath::Abs(Wrist.Z - PressureWrist.Z) < .1f && FVector::DotProduct(Wrist - PressureWrist, CameraRight) > Radius * .03f;
        TapKey(PC, EKeys::MouseScrollDown);
        AdvanceManualStage(EManualStage::WheelOpen);
        break;
    case EManualStage::WheelOpen:
        if (Elapsed < 1.2f) break;
        Result.bWheelPersists &= Character->GripAmount < .02f;
        PressureWrist = Wrist;
        TapKey(PC, EKeys::C);
        AdvanceManualStage(EManualStage::CameraToggle);
        break;
    case EManualStage::CameraToggle:
        if (Elapsed < .6f) break;
        Result.CameraPoseChange = FVector::Distance(Wrist, PressureWrist);
        Result.bCameraIndependent = Result.CameraPoseChange < .1f &&
            FMath::Abs(Character->PressureAmount - Result.CloseViewPressure) < .01f &&
            FMath::Abs(Character->HandOffsetAmount - Result.FineSideAmount) < .01f && Character->GripAmount < .02f;
        TapKey(PC, EKeys::R);
        AdvanceManualStage(EManualStage::WideReset);
        break;
    case EManualStage::WideReset:
        if (Elapsed < .9f) break;
        Result.bFovConsistent = AtNeutral() && Character->PressureAmount < .01f && FMath::Abs(Character->HandOffsetAmount) < .01f;
        Axis(EKeys::MouseY, -40.f);
        AdvanceManualStage(EManualStage::WidePressure);
        break;
    case EManualStage::WidePressure:
        if (Elapsed < .9f) break;
        Result.WideViewPressure = Character->PressureAmount;
        Result.bFovConsistent &= FMath::Abs(Result.WideViewPressure - Result.CloseViewPressure) < .01f;
        TapKey(PC, EKeys::R);
        TapKey(PC, EKeys::C);
        AdvanceManualStage(EManualStage::RestoreCloseCamera);
        break;
    case EManualStage::RestoreCloseCamera:
        if (Elapsed < 1.2f) break;
        Result.bCameraIndependent &= AtNeutral();
        NeutralShape = Shape;
        Axis(EKeys::MouseY, -3000.f); // Raw mouse down; LookUp has scale -1.
        AdvanceManualStage(EManualStage::Pressure);
        break;
    case EManualStage::Pressure:
        if (Elapsed < 1.4f) break;
        PressureWrist = Wrist;
        Result.PressureDrop = NeutralWrist.Z - Wrist.Z;
        Result.PressureShapeChange = ShapeDifference(NeutralShape, Shape);
        Result.bOpenPressure = Character->GripAmount < .02f && Result.PressureDrop > Radius * .1f &&
            Result.PressureDrop < Radius * .6f && Result.PressureShapeChange > .08f && Ball->GetContactCount() > 0;
        CaptureManual(TEXT("Open_Pressure"));
        AdvanceManualStage(EManualStage::PressureCapture);
        break;
    case EManualStage::PressureCapture:
        if (Elapsed < .5f) break;
        Axis(EKeys::MouseX, 3000.f);
        AdvanceManualStage(EManualStage::Right);
        break;
    case EManualStage::Right:
        if (Elapsed < 1.2f) break;
        RightWrist = Wrist;
        RightShape = Shape;
        Result.LateralTravel = FVector::DotProduct(Wrist - PressureWrist, CameraRight);
        Result.LateralHeightError = FMath::Abs(Wrist.Z - PressureWrist.Z);
        Result.bLateralIndependent = Result.LateralTravel > Radius * .1f && Result.LateralTravel < Radius &&
            Result.LateralHeightError < .1f && Character->GripAmount < .02f;
        CaptureManual(TEXT("Pressure_Right"));
        AdvanceManualStage(EManualStage::RightCapture);
        break;
    case EManualStage::RightCapture:
        if (Elapsed < .5f) break;
        Axis(EKeys::MouseX, -6000.f);
        AdvanceManualStage(EManualStage::Left);
        break;
    case EManualStage::Left:
        if (Elapsed < 1.2f) break;
        LeftWrist = Wrist;
        LeftShape = Shape;
        Result.ShakeShapeChange = ShapeDifference(RightShape, LeftShape);
        Result.bShakeChangesShape = FVector::DotProduct(RightWrist - LeftWrist, CameraRight) > Radius * .3f &&
            Result.ShakeShapeChange > .08f && Character->GripAmount < .02f && FMath::Abs(Wrist.Z - PressureWrist.Z) < .1f;
        CaptureManual(TEXT("Pressure_Left"));
        AdvanceManualStage(EManualStage::LeftCapture);
        break;
    case EManualStage::LeftCapture:
        if (Elapsed < .5f) break;
        Axis(EKeys::MouseX, 6000.f);
        AdvanceManualStage(EManualStage::ShakeBack);
        break;
    case EManualStage::ShakeBack:
        if (Elapsed < 1.2f) break;
        Result.bShakeChangesShape &= FVector::DotProduct(Wrist - LeftWrist, CameraRight) > Radius * .3f &&
            ShapeDifference(LeftShape, Shape) > .08f;
        RightWrist = Wrist;
        Axis(EKeys::MouseY, 6000.f);
        AdvanceManualStage(EManualStage::Lift);
        break;
    case EManualStage::Lift:
        if (Elapsed < 1.2f) break;
        Result.bLiftIndependent = Wrist.Z - RightWrist.Z > Radius * .1f &&
            FVector::Dist2D(Wrist, RightWrist) < .1f && Character->GripAmount < .02f;
        TapKey(PC, EKeys::R);
        AdvanceManualStage(EManualStage::Reset);
        break;
    case EManualStage::Reset:
        if (Elapsed < 1.2f) break;
        Result.bReset = AtNeutral();
        AdvanceManualStage(EManualStage::PositiveLimit);
        break;
    case EManualStage::PositiveLimit:
        DriveLimit(true);
        if (Elapsed > 1.f) AdvanceManualStage(EManualStage::PositiveSettle);
        break;
    case EManualStage::PositiveSettle:
        if (Elapsed < 1.2f) break;
        LimitWrist = Wrist;
        // At full curl the visible fingers may lift against the tabletop guard.
        Result.bLimitsStable &= Character->GripAmount > .98f && FMath::Abs(Wrist.Z - NeutralWrist.Z) < Radius &&
            FVector::Dist2D(Wrist, NeutralWrist) < Radius;
        CaptureManual(TEXT("Full_Curl_Pressure_Right"));
        AdvanceManualStage(EManualStage::PositiveOverrun);
        break;
    case EManualStage::PositiveOverrun:
        DriveLimit(true);
        if (Elapsed > .4f) AdvanceManualStage(EManualStage::PositiveCheck);
        break;
    case EManualStage::PositiveCheck:
        if (Elapsed < .9f) break;
        Result.LimitPoseDrift = FVector::Distance(Wrist, LimitWrist);
        Result.bLimitsStable &= Result.LimitPoseDrift < .1f;
        ManualWheelSteps = 0;
        AdvanceManualStage(EManualStage::MiddleCurl);
        break;
    case EManualStage::MiddleCurl:
        if (ManualWheelSteps++ < 5) TapKey(PC, EKeys::MouseScrollDown);
        else AdvanceManualStage(EManualStage::MiddleSettle);
        break;
    case EManualStage::MiddleSettle:
        if (Elapsed < .9f) break;
        Result.bLimitsStable &= Character->GripAmount > .4f && Character->GripAmount < .6f;
        CaptureManual(TEXT("Half_Curl_Pressure_Right"));
        AdvanceManualStage(EManualStage::MiddleCapture);
        break;
    case EManualStage::MiddleCapture:
        if (Elapsed < .5f) break;
        AdvanceManualStage(EManualStage::NegativeLimit);
        break;
    case EManualStage::NegativeLimit:
        DriveLimit(false);
        if (Elapsed > 1.f) AdvanceManualStage(EManualStage::NegativeSettle);
        break;
    case EManualStage::NegativeSettle:
        if (Elapsed < 1.2f) break;
        LimitWrist = Wrist;
        Result.bLimitsStable &= Character->GripAmount < .02f && FMath::Abs(Wrist.Z - NeutralWrist.Z) < .1f &&
            FVector::DotProduct(Wrist - NeutralWrist, CameraRight) < -Radius * .1f && FVector::Dist2D(Wrist, NeutralWrist) < Radius;
        AdvanceManualStage(EManualStage::NegativeOverrun);
        break;
    case EManualStage::NegativeOverrun:
        DriveLimit(false);
        if (Elapsed > .4f) AdvanceManualStage(EManualStage::NegativeCheck);
        break;
    case EManualStage::NegativeCheck:
        if (Elapsed < .9f) break;
        Result.LimitPoseDrift = FMath::Max(Result.LimitPoseDrift, static_cast<float>(FVector::Distance(Wrist, LimitWrist)));
        Result.bLimitsStable &= Result.LimitPoseDrift < .1f;
        TapKey(PC, EKeys::R);
        AdvanceManualStage(EManualStage::FinalReset);
        break;
    case EManualStage::FinalReset:
        if (Elapsed < 1.2f) break;
        Result.bReset &= AtNeutral();
        TapKey(PC, EKeys::Tab);
        AdvanceManualStage(EManualStage::DemoIdle);
        break;
    case EManualStage::DemoIdle:
        if (Elapsed < 1.8f) break;
        Result.bDemoIdle = Character->bAutoDemo && Character->GripAmount > .1f;
        Result.bDemoMouseTakeover = Character->bAutoDemo;
        Axis(EKeys::MouseY, -100.f);
        AdvanceManualStage(EManualStage::DemoMouseTakeover);
        break;
    case EManualStage::DemoMouseTakeover:
        if (Elapsed < .5f) break;
        Result.bDemoMouseTakeover &= !Character->bAutoDemo && Character->bInteracting;
        // Give each takeover test an independent starting state, even after failure.
        TapKey(PC, EKeys::R);
        AdvanceManualStage(EManualStage::DemoWheelReset);
        break;
    case EManualStage::DemoWheelReset:
        if (Elapsed < .3f) break;
        TapKey(PC, EKeys::Tab);
        AdvanceManualStage(EManualStage::DemoWheelReady);
        break;
    case EManualStage::DemoWheelReady:
        if (Elapsed < 1.8f) break;
        Result.bDemoIdle &= Character->bAutoDemo;
        Result.bDemoWheelTakeover = Character->bAutoDemo;
        TapKey(PC, EKeys::MouseScrollUp);
        AdvanceManualStage(EManualStage::DemoWheelTakeover);
        break;
    case EManualStage::DemoWheelTakeover:
        if (Elapsed < .5f) break;
        Result.bDemoWheelTakeover &= !Character->bAutoDemo && Character->bInteracting;
        TapKey(PC, EKeys::E);
        AdvanceManualStage(EManualStage::Exit);
        break;
    case EManualStage::Exit:
        if (Elapsed < .3f) break;
        Result.bExitReset = !Character->bInteracting && !Character->bAutoDemo && Character->GripAmount < .02f;
        TapKey(PC, EKeys::E);
        AdvanceManualStage(EManualStage::Reenter);
        break;
    case EManualStage::Reenter:
        if (Elapsed < 1.2f) break;
        Result.bExitReset &= AtNeutral() && !Character->bAutoDemo;
        UE_LOG(LogTemp, Display, TEXT("SOFTBODY manual input %s: %s"), *Ball->DisplayName, Result.Passed() ? TEXT("PASS") : TEXT("FAIL"));
        if (++ManualBallIndex < 2) StartManualValidation(Character, PC);
        else { WriteReport(); Stage++; FPlatformMisc::RequestExit(false); }
        break;
    }
}

void ASoftbodyGameMode::WriteReport()
{
    const bool bPassed = PeakDeformation[0] > .1f && PeakDeformation[1] > .2f &&
        ReleasedDeformation[0] < PeakDeformation[0] * .9f && ReleasedDeformation[1] < PeakDeformation[1] * .9f &&
        PeakContacts > 0 && OpposingContact[0] && OpposingContact[1] && BodyContactFrames > 3 && BodyContactDeformation > 1.f && BodyDeformation < 30.f &&
        BodyRecoveryError < FMath::Max(1.f, BodyContactDeformation * .25f) && BodyTravel > 10.f && WorstHandError < 1.f && PalmDownMinimum > .95f &&
        VolumeMinimum > .9f && VolumeMaximum < 1.1f && ManualResults[0].Passed() && ManualResults[1].Passed();
    const FString Json = FString::Printf(TEXT("{\n  \"passed\": %s,\n  \"tennis_peak_cm\": %.4f,\n  \"tennis_released_cm\": %.4f,\n  \"double_peak_cm\": %.4f,\n  \"double_released_cm\": %.4f,\n  \"peak_hand_contacts\": %d,\n  \"body_deformation_cm\": %.4f,\n  \"body_travel_cm\": %.4f,\n  \"volume_min\": %.4f,\n  \"volume_max\": %.4f\n}\n"),
        bPassed ? TEXT("true") : TEXT("false"), PeakDeformation[0], ReleasedDeformation[0], PeakDeformation[1], ReleasedDeformation[1], PeakContacts, BodyDeformation, BodyTravel, VolumeMinimum, VolumeMaximum);
    FString DetailedJson = Json;
    DetailedJson.RemoveFromEnd(TEXT("}\n"));
    DetailedJson += FString::Printf(TEXT(",  \"tennis_thumb_and_fingers\": %s,\n  \"double_thumb_and_fingers\": %s\n"), OpposingContact[0] ? TEXT("true") : TEXT("false"), OpposingContact[1] ? TEXT("true") : TEXT("false"));
    DetailedJson += FString::Printf(TEXT(",  \"body_baseline_cm\": %.4f,\n  \"body_released_cm\": %.4f,\n  \"body_contact_deformation_cm\": %.4f,\n  \"body_recovery_error_cm\": %.4f,\n  \"body_contact_frames\": %d,\n  \"wrist_error_cm\": %.4f,\n  \"palm_down_dot\": %.4f\n}\n"), BodyBaseline, BodyReleased, BodyContactDeformation, BodyRecoveryError, BodyContactFrames, WorstHandError, PalmDownMinimum);
    DetailedJson.RemoveFromEnd(TEXT("}\n"));
    DetailedJson += TEXT(",  \"manual_input\": [\n");
    for (int32 Index = 0; Index < 2; ++Index)
    {
        const FManualResult& Result = ManualResults[Index];
        auto JsonBool = [](bool Value) { return Value ? TEXT("true") : TEXT("false"); };
        DetailedJson += FString::Printf(TEXT("    {\n      \"ball\": \"%s\",\n      \"passed\": %s,\n"),
            Index == 0 ? TEXT("tennis") : TEXT("double"), JsonBool(Result.Passed()));
        DetailedJson += FString::Printf(TEXT(
            "      \"small_mouse_delta\": %s,\n      \"camera_preserves_hand\": %s,\n      \"mouse_fov_consistent\": %s,\n"
            "      \"hand_clears_table\": %s,\n      \"close_view_pressure\": %.4f,\n      \"wide_view_pressure\": %.4f,\n"
            "      \"fine_side_amount\": %.4f,\n      \"camera_pose_change_cm\": %.4f,\n      \"minimum_table_clearance_cm\": %.4f,\n"),
            JsonBool(Result.bSmallMouseDelta), JsonBool(Result.bCameraIndependent), JsonBool(Result.bFovConsistent),
            JsonBool(Result.bTableClearance), Result.CloseViewPressure, Result.WideViewPressure, Result.FineSideAmount,
            Result.CameraPoseChange, Result.MinimumTableClearance);
        DetailedJson += FString::Printf(TEXT(
            "      \"wheel_persists\": %s,\n      \"lmb_restores_wheel\": %s,\n      \"curl_keeps_height\": %s,\n"
            "      \"open_hand_pressure\": %s,\n      \"lateral_independent\": %s,\n      \"shake_changes_shape\": %s,\n"
            "      \"lift_independent\": %s,\n      \"limits_stable\": %s,\n      \"reset_restores_neutral\": %s,\n"
            "      \"idle_preserves_demo\": %s,\n      \"mouse_takes_over_demo\": %s,\n      \"wheel_takes_over_demo\": %s,\n"
            "      \"exit_reentry_resets\": %s,\n"),
            JsonBool(Result.bWheelPersists), JsonBool(Result.bLmbRestoresWheel), JsonBool(Result.bCurlKeepsHeight),
            JsonBool(Result.bOpenPressure), JsonBool(Result.bLateralIndependent), JsonBool(Result.bShakeChangesShape),
            JsonBool(Result.bLiftIndependent), JsonBool(Result.bLimitsStable), JsonBool(Result.bReset),
            JsonBool(Result.bDemoIdle), JsonBool(Result.bDemoMouseTakeover), JsonBool(Result.bDemoWheelTakeover), JsonBool(Result.bExitReset));
        DetailedJson += FString::Printf(TEXT(
            "      \"wheel_grip\": %.4f,\n      \"wheel_idle_error\": %.4f,\n      \"pressure_drop_cm\": %.4f,\n"
            "      \"pressure_shape_change_cm\": %.4f,\n      \"lateral_travel_cm\": %.4f,\n      \"lateral_height_error_cm\": %.4f,\n"
            "      \"shake_shape_change_cm\": %.4f,\n      \"limit_pose_drift_cm\": %.4f,\n      \"max_wrist_error_cm\": %.4f,\n"
            "      \"minimum_palm_down_dot\": %.4f,\n      \"volume_min\": %.4f,\n      \"volume_max\": %.4f\n    }%s\n"),
            Result.WheelGrip, Result.WheelIdleError, Result.PressureDrop, Result.PressureShapeChange, Result.LateralTravel,
            Result.LateralHeightError, Result.ShakeShapeChange, Result.LimitPoseDrift, Result.MaxWristError,
            Result.MinimumPalmDown, Result.MinimumVolume, Result.MaximumVolume, Index == 0 ? TEXT(",") : TEXT(""));
    }
    DetailedJson += TEXT("  ]\n}\n");
    FFileHelper::SaveStringToFile(DetailedJson, *(FPaths::ProjectSavedDir()/TEXT("RuntimeValidation.json")));
    UE_LOG(LogTemp, Display, TEXT("SOFTBODY runtime validation %s: %s"), bPassed ? TEXT("PASS") : TEXT("FAIL"), *Json);
}

void ASoftbodyHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas) return;
    const float W = Canvas->ClipX;
    DrawRect(FLinearColor(.012f,.022f,.035f,.92f), 26, 24, 352, 100);
    DrawRect(FLinearColor(.25f,.9f,.62f,1), 26, 24, 3, 100);
    DrawText(TEXT("SOFTBODY / TACTILE LAB"), FLinearColor(.88f,.96f,1), 46, 39, GEngine->GetMediumFont(), 1.1f);
    DrawText(TEXT("01  TENNIS  6.7 cm     02  DOUBLE  13.4 cm"), FLinearColor(.6f,.72f,.8f), 46, 77, GEngine->GetSmallFont());
    DrawText(TEXT("03  BODY  1 metre"), FLinearColor(.6f,.72f,.8f), 46, 97, GEngine->GetSmallFont());
    const ASoftbodyCharacter* Character = Cast<ASoftbodyCharacter>(GetOwningPawn());
    const ASoftBodyBall* Ball = Character ? Character->GetBall() : nullptr;
    const bool bGrip = Character && Character->bInteracting;
    if (Character && !bGrip)
    {
        double Nearest = TNumericLimits<double>::Max();
        for (TActorIterator<ASoftBodyBall> It(GetWorld()); It; ++It)
        {
            const double Distance = FVector::DistSquared2D(Character->GetActorLocation(), It->GetActorLocation());
            if (Distance < Nearest) { Nearest = Distance; Ball = *It; }
        }
    }
    const FLinearColor ControlColor(.88f,.96f,1);
    if (bGrip)
    {
        DrawRect(FLinearColor(.012f,.022f,.035f,.92f), 26, Canvas->ClipY-102, FMath::Min(W-52,1050.f), 76);
        DrawText(TEXT("WHEEL  curl    MOUSE UP / DOWN  lift / press    MOUSE LEFT / RIGHT  slide hand"),
            ControlColor, 44, Canvas->ClipY-86, GEngine->GetSmallFont(), 1.1f);
        DrawText(TEXT("HOLD LMB  temporary squeeze    E  leave    C  inspect    R  reset    TAB  auto"),
            ControlColor, 44, Canvas->ClipY-61, GEngine->GetSmallFont(), 1.1f);
    }
    else
    {
        DrawRect(FLinearColor(.012f,.022f,.035f,.92f), 26, Canvas->ClipY-78, FMath::Min(W-52,790.f), 52);
        DrawText(TEXT("WASD  move    MOUSE  look    SPACE  jump    E  reach ball    TAB  auto"),
            ControlColor, 44, Canvas->ClipY-60, GEngine->GetSmallFont(), 1.15f);
    }
    if (Ball)
    {
        const float X = W-257;
        DrawRect(FLinearColor(.012f,.022f,.035f,.88f), X, 24, 231, bGrip ? 211 : 134);
        DrawText(Ball->DisplayName, FLinearColor(.64f,.9f,.3f), X+18, 39, GEngine->GetMediumFont());
        DrawText(FString::Printf(TEXT("DIAMETER     %.1f cm"), Ball->BallRadius*2), FLinearColor::White, X+18, 73, GEngine->GetSmallFont());
        DrawText(FString::Printf(TEXT("DEFORMATION  %.2f cm"), Ball->GetMaxDisplacement()), FLinearColor(.65f,.77f,.85f), X+18, 95, GEngine->GetSmallFont());
        DrawText(FString::Printf(TEXT("VOLUME       %.0f %%"), Ball->GetVolumeRatio()*100), FLinearColor(.65f,.77f,.85f), X+18, 117, GEngine->GetSmallFont());
        if (bGrip)
        {
            const FLinearColor HandColor(.64f,.9f,.3f);
            DrawRect(FLinearColor(.25f,.4f,.43f,.7f), X+18, 142, 195, 1);
            DrawText(FString::Printf(TEXT("CURL         %.0f %%"), Character->GripAmount*100), HandColor, X+18, 153, GEngine->GetSmallFont());
            DrawText(FString::Printf(TEXT("PRESS        %.0f %%"), Character->PressureAmount*100), HandColor, X+18, 176, GEngine->GetSmallFont());
            DrawText(FString::Printf(TEXT("SIDE         %+.0f %%"), Character->HandOffsetAmount*100), HandColor, X+18, 199, GEngine->GetSmallFont());
        }
    }
}
