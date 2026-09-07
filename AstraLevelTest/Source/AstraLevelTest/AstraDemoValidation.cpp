#include "AstraDemoValidation.h"

#include "AstraDemoPlayback.h"
#include "AstraWorld.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "InputCoreTypes.h"
#include "InputKeyEventArgs.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace
{
    const FKey MovementKeys[] = { EKeys::W, EKeys::A, EKeys::S, EKeys::D };
    const FVector MovementDirections[] = {
        FVector(1, 0, 0), FVector(0, -1, 0), FVector(-1, 0, 0), FVector(0, 1, 0)
    };

    const TCHAR* JsonBool(bool bValue) { return bValue ? TEXT("true") : TEXT("false"); }

    FString JsonString(FString Value)
    {
        Value.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
        Value.ReplaceInline(TEXT("\""), TEXT("\\\""));
        Value.ReplaceInline(TEXT("\r"), TEXT("\\r"));
        Value.ReplaceInline(TEXT("\n"), TEXT("\\n"));
        Value.ReplaceInline(TEXT("\t"), TEXT("\\t"));
        return TEXT("\"") + Value + TEXT("\"");
    }
}

FAstraDemoValidation::FAstraDemoValidation(UAstraDemoPlayback& InDemo) : Demo(InDemo)
{
    UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO TEST: P toggle, seven shots, loop, restoration, early cancel, WASD; timeout 180 world seconds"));
}

AAstraController* FAstraDemoValidation::GetController() const
{
    return Cast<AAstraController>(Demo.GetOwner());
}

AAstraCat* FAstraDemoValidation::GetCat() const
{
    const AAstraController* Controller = GetController();
    return Controller ? Cast<AAstraCat>(Controller->GetPawn()) : nullptr;
}

void FAstraDemoValidation::EnterStage(EStage NewStage)
{
    Stage = NewStage;
    StageStarted = Elapsed;
}

void FAstraDemoValidation::SendP(EInputEvent Event)
{
    if (AAstraController* Controller = GetController())
        Controller->InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::P, Event, Event == IE_Released ? 0.f : 1.f));
}

void FAstraDemoValidation::AddCheck(const FString& Name, bool bPassed, const FString& Detail)
{
    Checks.Add(FString::Printf(TEXT("{\"name\":%s,\"pass\":%s,\"detail\":%s}"),
        *JsonString(Name), JsonBool(bPassed), *JsonString(Detail)));
    FailedChecks += bPassed ? 0 : 1;
    UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO TEST %s: %s %s"), *Name, bPassed ? TEXT("PASS") : TEXT("FAIL"), *Detail);
}

void FAstraDemoValidation::CaptureSnapshot()
{
    AAstraCat* Cat = GetCat();
    AAstraController* Controller = GetController();
    UCharacterMovementComponent* Movement = Cat->GetCharacterMovement();
    Snapshot.Transform = Cat->GetActorTransform();
    Snapshot.Velocity = Movement->Velocity;
    Snapshot.WalkSpeed = Movement->MaxWalkSpeed;
    Snapshot.MovementMode = Movement->MovementMode;
    Snapshot.CustomMovementMode = Movement->CustomMovementMode;
    Snapshot.CameraOffset = Cat->CameraBoom->TargetOffset;
    Snapshot.CameraRotation = Cat->CameraBoom->GetRelativeRotation();
    Snapshot.CameraArmLength = Cat->CameraBoom->TargetArmLength;
    Snapshot.OrthoWidth = Cat->TopDownCamera->OrthoWidth;
    Snapshot.bCameraLag = Cat->CameraBoom->bEnableCameraLag;
    Snapshot.ViewTarget = Controller->GetViewTarget();
    Snapshot.bMoveInputIgnored = Controller->IsMoveInputIgnored();
}

void FAstraDemoValidation::CheckRestored(const TCHAR* Prefix)
{
    AAstraCat* Cat = GetCat();
    AAstraController* Controller = GetController();
    const UCharacterMovementComponent* Movement = Cat->GetCharacterMovement();
    const FTransform Actual = Cat->GetActorTransform();
    const float PositionError = FVector::Distance(Actual.GetLocation(), Snapshot.Transform.GetLocation());
    const float RotationError = FMath::RadiansToDegrees(Actual.GetRotation().AngularDistance(Snapshot.Transform.GetRotation()));
    const auto Check = [this, Prefix](const TCHAR* Suffix, bool bPassed, const FString& Detail = FString())
    {
        AddCheck(FString(Prefix) + TEXT("_") + Suffix, bPassed, Detail);
    };
    Check(TEXT("transform"), PositionError <= 1.f && RotationError <= .1f && Actual.GetScale3D().Equals(Snapshot.Transform.GetScale3D(), .001f),
        FString::Printf(TEXT("position_error_cm=%.4f rotation_error_degrees=%.4f"), PositionError, RotationError));
    Check(TEXT("walk_speed"), FMath::IsNearlyEqual(Movement->MaxWalkSpeed, Snapshot.WalkSpeed, .01f));
    Check(TEXT("camera_offset"), Cat->CameraBoom->TargetOffset.Equals(Snapshot.CameraOffset, .01f));
    Check(TEXT("camera_ortho"), FMath::IsNearlyEqual(Cat->TopDownCamera->OrthoWidth, Snapshot.OrthoWidth, .01f));
    Check(TEXT("camera_lag"), Cat->CameraBoom->bEnableCameraLag == Snapshot.bCameraLag);
    Check(TEXT("camera_rotation_and_arm"), Cat->CameraBoom->GetRelativeRotation().Equals(Snapshot.CameraRotation, .01f)
        && FMath::IsNearlyEqual(Cat->CameraBoom->TargetArmLength, Snapshot.CameraArmLength, .01f));
    Check(TEXT("movement_mode"), Movement->MovementMode == Snapshot.MovementMode && Movement->CustomMovementMode == Snapshot.CustomMovementMode);
    Check(TEXT("velocity"), Movement->Velocity.Equals(Snapshot.Velocity, 1.f),
        FString::Printf(TEXT("expected=%s actual=%s"), *Snapshot.Velocity.ToString(), *Movement->Velocity.ToString()));
    Check(TEXT("view_target"), Controller->GetViewTarget() == Snapshot.ViewTarget.Get());
    Check(TEXT("movement_input_state"), Controller->IsMoveInputIgnored() == Snapshot.bMoveInputIgnored);
}

void FAstraDemoValidation::RecordShot(FName Name, bool bCompleted, float Travel, float UnsupportedSeconds)
{
    // User cancellation is checked separately, and should not count as a failed tour shot.
    if (Stage != EStage::HoldP && Stage != EStage::Tour) return;
    const AAstraCat* Cat = GetCat();
    const bool bGroundedAtEnd = Cat && Cat->GetCharacterMovement()->IsMovingOnGround();
    const bool bSupported = FMath::IsFinite(UnsupportedSeconds) && UnsupportedSeconds <= .5f && bGroundedAtEnd;
    const bool bMoved = FMath::IsFinite(Travel) && Travel > 100.f;
    const bool bUnique = !RecordedShots.Contains(Name);
    const bool bPassed = bCompleted && bSupported && bMoved && bUnique;
    RecordedShots.Add(Name);
    ++ShotCount;
    ShotResults.Add(FString::Printf(TEXT("{\"name\":%s,\"completed\":%s,\"travel_cm\":%.3f,\"unsupported_seconds\":%.4f,\"grounded_at_end\":%s,\"supported\":%s,\"pass\":%s}"),
        *JsonString(Name.ToString()), JsonBool(bCompleted), Travel, UnsupportedSeconds, JsonBool(bGroundedAtEnd), JsonBool(bSupported), JsonBool(bPassed)));
    AddCheck(TEXT("shot_") + Name.ToString(), bPassed,
        FString::Printf(TEXT("completed=%d travel_cm=%.2f unsupported_seconds=%.4f grounded_at_end=%d unique=%d"),
            bCompleted, Travel, UnsupportedSeconds, bGroundedAtEnd, bUnique));
}

void FAstraDemoValidation::BeginMovement()
{
    MovementStart = GetCat()->GetActorLocation();
    GetController()->InputKey(FInputKeyEventArgs::CreateSimulated(MovementKeys[MovementIndex], IE_Pressed, 1.f));
    EnterStage(EStage::Movement);
}

void FAstraDemoValidation::Tick(float DeltaTime)
{
    if (Stage == EStage::Finished) return;
    Elapsed += DeltaTime;
    if (Elapsed >= 180.f)
    {
        Finish(TEXT("Timed out before all checks completed (180 world seconds)."));
        return;
    }

    AAstraController* Controller = GetController();
    AAstraCat* Cat = GetCat();
    if (!Controller || !Cat || !Cat->CameraBoom || !Cat->TopDownCamera) return;
    UCharacterMovementComponent* Movement = Cat->GetCharacterMovement();
    const float StageTime = Elapsed - StageStarted;

    switch (Stage)
    {
    case EStage::AwaitWorld:
        if (Elapsed < 1.f || !Movement->IsMovingOnGround()) break;
        AddCheck(TEXT("seven_shots_configured"), Demo.Shots.Num() == 7, FString::FromInt(Demo.Shots.Num()));
        // Non-default values prevent a hard-coded reset to gameplay defaults passing this test.
        Movement->MaxWalkSpeed = 287.f;
        Cat->CameraBoom->TargetOffset = FVector(73, -41, 65);
        Cat->TopDownCamera->OrthoWidth = 3175.f;
        Cat->CameraBoom->bEnableCameraLag = true;
        if (ACameraActor* Camera = Cat->GetWorld()->SpawnActor<ACameraActor>())
        {
            Camera->SetActorLocationAndRotation(Cat->TopDownCamera->GetComponentLocation(), Cat->TopDownCamera->GetComponentRotation());
            Camera->GetCameraComponent()->ProjectionMode = ECameraProjectionMode::Orthographic;
            Camera->GetCameraComponent()->OrthoWidth = Cat->TopDownCamera->OrthoWidth;
            ValidationCamera = Camera;
            Controller->SetViewTarget(Camera);
        }
        AddCheck(TEXT("distinct_restore_view_target"), ValidationCamera.IsValid() && Controller->GetViewTarget() == ValidationCamera.Get());
        CaptureSnapshot();
        SendP(IE_Pressed);
        EnterStage(EStage::AwaitEntry);
        break;

    case EStage::AwaitEntry:
        if (Demo.IsDemoActive())
        {
            AddCheck(TEXT("p_enters_demo"), true);
            AddCheck(TEXT("entry_uses_cat_camera"), Controller->GetViewTarget() == Cat);
            InitialShotIndex = Demo.GetShotIndex();
            LastRepeat = Elapsed;
            EnterStage(EStage::HoldP);
        }
        else if (StageTime > 2.f) Finish(TEXT("P input did not enter demo mode."));
        break;

    case EStage::HoldP:
        bHeldPStayedActive &= Demo.IsDemoActive() && Demo.GetShotIndex() == InitialShotIndex;
        if (Elapsed - LastRepeat >= .15f)
        {
            SendP(IE_Repeat);
            LastRepeat = Elapsed;
        }
        if (StageTime >= .9f)
        {
            SendP(IE_Released);
            AddCheck(TEXT("held_p_does_not_toggle_repeatedly"), bHeldPStayedActive);
            EnterStage(EStage::Tour);
        }
        break;

    case EStage::Tour:
        if (!Demo.IsDemoActive())
        {
            Finish(TEXT("Demo became inactive before one complete loop."));
            break;
        }
        if (Demo.GetCompletedLoops() >= 1 && Demo.GetShotIndex() == 0 && Demo.ShotTime >= .2f)
        {
            bool bEveryConfiguredShot = ShotCount == 7 && RecordedShots.Num() == 7;
            for (const FAstraDemoShot& Shot : Demo.Shots) bEveryConfiguredShot &= RecordedShots.Contains(Shot.Name);
            AddCheck(TEXT("all_seven_shots_recorded"), bEveryConfiguredShot, FString::Printf(TEXT("completed_records=%d unique_names=%d"), ShotCount, RecordedShots.Num()));
            AddCheck(TEXT("loop_restarts_at_first_shot"), true, FString::Printf(TEXT("loops=%d shot_index=%d shot_seconds=%.3f"), Demo.GetCompletedLoops(), Demo.GetShotIndex(), Demo.ShotTime));
            SendP(IE_Pressed);
            EnterStage(EStage::AwaitFullStop);
        }
        break;

    case EStage::AwaitFullStop:
        if (!Demo.IsDemoActive())
        {
            AddCheck(TEXT("p_exits_demo"), true);
            CheckRestored(TEXT("full_loop_restore"));
            SendP(IE_Released);
            EnterStage(EStage::BeforeReentry);
        }
        else if (StageTime > 2.f) Finish(TEXT("P input did not exit the looping demo."));
        break;

    case EStage::BeforeReentry:
        if (StageTime < .25f) break;
        Movement->MaxWalkSpeed = 319.f;
        Cat->CameraBoom->TargetOffset = FVector(-32, 27, 11);
        Cat->TopDownCamera->OrthoWidth = 3340.f;
        Cat->CameraBoom->bEnableCameraLag = false;
        CaptureSnapshot();
        SendP(IE_Pressed);
        EnterStage(EStage::AwaitReentry);
        break;

    case EStage::AwaitReentry:
        if (Demo.IsDemoActive())
        {
            AddCheck(TEXT("p_reenters_at_first_shot"), Demo.GetShotIndex() == 0 && Demo.GetCompletedLoops() == 0);
            SendP(IE_Released);
            EnterStage(EStage::BeforeEarlyStop);
        }
        else if (StageTime > 2.f) Finish(TEXT("P input did not re-enter demo mode."));
        break;

    case EStage::BeforeEarlyStop:
        AddCheck(TEXT("early_cancel_within_first_second"), Demo.ShotTime < 1.f);
        SendP(IE_Pressed);
        EnterStage(EStage::AwaitEarlyStop);
        break;

    case EStage::AwaitEarlyStop:
        if (!Demo.IsDemoActive())
        {
            AddCheck(TEXT("p_cancels_immediately_after_reentry"), true);
            CheckRestored(TEXT("early_cancel_restore"));
            SendP(IE_Released);
            EnterStage(EStage::BeforeMovement);
        }
        else if (StageTime > 2.f) Finish(TEXT("P input did not immediately cancel the restarted demo."));
        break;

    case EStage::BeforeMovement:
    case EStage::BetweenMovement:
        if (StageTime >= .3f) BeginMovement();
        break;

    case EStage::Movement:
        if (StageTime >= 1.15f)
        {
            Controller->InputKey(FInputKeyEventArgs::CreateSimulated(MovementKeys[MovementIndex], IE_Released, 0.f));
            const FVector Delta = Cat->GetActorLocation() - MovementStart;
            const float ForwardTravel = FVector::DotProduct(Delta, MovementDirections[MovementIndex]);
            const bool bGrounded = Movement->IsMovingOnGround();
            const bool bPassed = ForwardTravel > 150.f && bGrounded && !Demo.IsDemoActive();
            MovementResults.Add(FString::Printf(TEXT("{\"key\":%s,\"pass\":%s,\"dx\":%.3f,\"dy\":%.3f,\"dz\":%.3f,\"expected_direction_travel_cm\":%.3f,\"grounded\":%s}"),
                *JsonString(MovementKeys[MovementIndex].ToString()), JsonBool(bPassed), Delta.X, Delta.Y, Delta.Z, ForwardTravel, JsonBool(bGrounded)));
            AddCheck(TEXT("post_demo_input_") + MovementKeys[MovementIndex].ToString(), bPassed,
                FString::Printf(TEXT("forward_travel_cm=%.3f grounded=%d demo_active=%d"), ForwardTravel, bGrounded, Demo.IsDemoActive()));
            ++MovementIndex;
            if (MovementIndex == UE_ARRAY_COUNT(MovementKeys)) Finish();
            else EnterStage(EStage::BetweenMovement);
        }
        break;

    case EStage::Finished:
        break;
    }
}

void FAstraDemoValidation::Finish(const FString& Failure)
{
    if (Stage == EStage::Finished) return;
    if (!Failure.IsEmpty()) AddCheck(TEXT("completed_before_timeout"), false, Failure);
    if (AAstraController* Controller = GetController())
    {
        SendP(IE_Released);
        for (const FKey& Key : MovementKeys)
            Controller->InputKey(FInputKeyEventArgs::CreateSimulated(Key, IE_Released, 0.f));
    }
    EnterStage(EStage::Finished);
    const bool bPassed = FailedChecks == 0 && MovementIndex == UE_ARRAY_COUNT(MovementKeys) && ShotCount == 7;
    const FString OutputPath = FPaths::ProjectDir() / TEXT("ArtSource/Previews/UE_DemoValidation.json");
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(OutputPath), true);
    const FString Result = FString::Printf(TEXT("{\n  \"test\":\"AstraDemoTest\",\n  \"passed\":%s,\n  \"elapsed_world_seconds\":%.3f,\n  \"timeout_world_seconds\":180,\n  \"failed_checks\":%d,\n  \"shots\":[%s],\n  \"checks\":[%s],\n  \"post_demo_movement\":[%s]\n}\n"),
        JsonBool(bPassed), Elapsed, FailedChecks, *FString::Join(ShotResults, TEXT(",\n    ")), *FString::Join(Checks, TEXT(",\n    ")), *FString::Join(MovementResults, TEXT(",\n    ")));
    const bool bSaved = FFileHelper::SaveStringToFile(Result, *OutputPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO TEST %s: %d failed checks, %.3f world seconds, saved=%d, %s"),
        bPassed && bSaved ? TEXT("PASS") : TEXT("FAIL"), FailedChecks, Elapsed, bSaved, *OutputPath);
    FPlatformMisc::RequestExitWithStatus(false, bPassed && bSaved ? 0 : 1);
}
