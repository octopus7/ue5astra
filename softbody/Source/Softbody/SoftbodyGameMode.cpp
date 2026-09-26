#include "SoftbodyGameMode.h"
#include "SoftbodyCharacter.h"
#include "SoftBodyBall.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
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
    if (Stage >= 10)
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
    if (Character->bInteracting && Character->GripAmount > .95f)
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
        WriteReport(); Stage++; FPlatformMisc::RequestExit(false);
    }
}

void ASoftbodyGameMode::WriteReport()
{
    const bool bPassed = PeakDeformation[0] > .1f && PeakDeformation[1] > .2f &&
        ReleasedDeformation[0] < PeakDeformation[0] * .9f && ReleasedDeformation[1] < PeakDeformation[1] * .9f &&
        PeakContacts > 0 && OpposingContact[0] && OpposingContact[1] && BodyContactFrames > 3 && BodyContactDeformation > 1.f && BodyDeformation < 30.f &&
        BodyRecoveryError < FMath::Max(1.f, BodyContactDeformation * .25f) && BodyTravel > 10.f && WorstHandError < 1.f && PalmDownMinimum > .95f &&
        VolumeMinimum > .9f && VolumeMaximum < 1.1f;
    const FString Json = FString::Printf(TEXT("{\n  \"passed\": %s,\n  \"tennis_peak_cm\": %.4f,\n  \"tennis_released_cm\": %.4f,\n  \"double_peak_cm\": %.4f,\n  \"double_released_cm\": %.4f,\n  \"peak_hand_contacts\": %d,\n  \"body_deformation_cm\": %.4f,\n  \"body_travel_cm\": %.4f,\n  \"volume_min\": %.4f,\n  \"volume_max\": %.4f\n}\n"),
        bPassed ? TEXT("true") : TEXT("false"), PeakDeformation[0], ReleasedDeformation[0], PeakDeformation[1], ReleasedDeformation[1], PeakContacts, BodyDeformation, BodyTravel, VolumeMinimum, VolumeMaximum);
    FString DetailedJson = Json;
    DetailedJson.RemoveFromEnd(TEXT("}\n"));
    DetailedJson += FString::Printf(TEXT(",  \"tennis_thumb_and_fingers\": %s,\n  \"double_thumb_and_fingers\": %s\n"), OpposingContact[0] ? TEXT("true") : TEXT("false"), OpposingContact[1] ? TEXT("true") : TEXT("false"));
    DetailedJson += FString::Printf(TEXT(",  \"body_baseline_cm\": %.4f,\n  \"body_released_cm\": %.4f,\n  \"body_contact_deformation_cm\": %.4f,\n  \"body_recovery_error_cm\": %.4f,\n  \"body_contact_frames\": %d,\n  \"wrist_error_cm\": %.4f,\n  \"palm_down_dot\": %.4f\n}\n"), BodyBaseline, BodyReleased, BodyContactDeformation, BodyRecoveryError, BodyContactFrames, WorstHandError, PalmDownMinimum);
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
    const FString Controls = bGrip ? TEXT("HOLD LMB  squeeze    E  leave    C  inspect    R  reset    TAB  auto") : TEXT("WASD  move    MOUSE  look    SPACE  jump    E  reach ball    TAB  auto");
    DrawRect(FLinearColor(.012f,.022f,.035f,.92f), 26, Canvas->ClipY-78, FMath::Min(W-52,790.f), 52);
    DrawText(Controls, FLinearColor(.88f,.96f,1), 44, Canvas->ClipY-60, GEngine->GetSmallFont(), 1.15f);
    if (Ball)
    {
        const float X = W-257;
        DrawRect(FLinearColor(.012f,.022f,.035f,.88f), X, 24, 231, 134);
        DrawText(Ball->DisplayName, FLinearColor(.64f,.9f,.3f), X+18, 39, GEngine->GetMediumFont());
        DrawText(FString::Printf(TEXT("DIAMETER     %.1f cm"), Ball->BallRadius*2), FLinearColor::White, X+18, 73, GEngine->GetSmallFont());
        DrawText(FString::Printf(TEXT("DEFORMATION  %.2f cm"), Ball->GetMaxDisplacement()), FLinearColor(.65f,.77f,.85f), X+18, 95, GEngine->GetSmallFont());
        DrawText(FString::Printf(TEXT("VOLUME       %.0f %%"), Ball->GetVolumeRatio()*100), FLinearColor(.65f,.77f,.85f), X+18, 117, GEngine->GetSmallFont());
    }
}
