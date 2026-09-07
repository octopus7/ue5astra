#include "AstraDemoPlayback.h"
#include "AstraDemoValidation.h"
#include "AstraLevelConfig.h"
#include "AstraWorld.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/FileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

UAstraDemoPlayback::UAstraDemoPlayback()
{
    PrimaryComponentTick.bCanEverTick = false; // Controller updates this before accepting WASD.
    auto Add = [this](const TCHAR* Name, TArray<FVector2D> Points, float Seconds, float Width, FVector Offset)
    {
        FAstraDemoShot& Shot = Shots.AddDefaulted_GetRef();
        Shot.Name = Name;
        Shot.Waypoints = MoveTemp(Points);
        Shot.MinimumSeconds = Seconds;
        Shot.OrthoWidth = Width;
        Shot.CameraOffset = Offset;
    };
    Add(TEXT("Clearing"), {{-1050,-1200},{-600,-1000},{-350,-1100},{-600,-1450}}, 10.f, 2400.f, {0,-130,30});
    Add(TEXT("Bridge"), {{-700,-240},{-700,300},{-700,950}}, 10.f, 2400.f, {0,0,40});
    Add(TEXT("PinkHouse"), {{800,3500},{1000,3820},{1210,3900},{1410,3900},{1460,4000}}, 11.f, 2600.f, {280,160,100});
    Add(TEXT("Camp"), {{3300,-1850},{3300,-1100},{3300,-500},{3300,-250}}, 13.f, 3000.f, {220,80,100});
    Add(TEXT("Ruins"), {{1650,-2650},{1750,-2350},{1750,-2050}}, 9.f, 2600.f, {440,0,160});
    Add(TEXT("FishingDock"), {{100,2800},{500,2800},{940,2800}}, 10.f, 2400.f, {300,0,30});
    Add(TEXT("BrokenBridge"), {{-3000,-2100},{-2950,-1700},{-2900,-1350}}, 9.f, 2500.f, {0,430,60});
}

UAstraDemoPlayback::~UAstraDemoPlayback() = default;

void UAstraDemoPlayback::BeginPlay()
{
    Super::BeginPlay();
    Controller = Cast<AAstraController>(GetOwner());
    if (const AAstraLevelConfig* LevelConfig = AAstraLevelConfig::FindForWorld(GetWorld()))
    {
        Shots = LevelConfig->DemoShots;
        UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO loaded %d level-local shots from %s"),
            Shots.Num(), *LevelConfig->GetName());
    }
    if (Controller && FParse::Param(FCommandLine::Get(), TEXT("AstraDemoTest")))
        Validation = MakeUnique<FAstraDemoValidation>(*this);
}

void UAstraDemoPlayback::EndPlay(const EEndPlayReason::Type Reason)
{
    Stop();
    Super::EndPlay(Reason);
}

void UAstraDemoPlayback::Toggle()
{
    if (bActive) Stop();
    else Start();
}

bool UAstraDemoPlayback::Start()
{
    if (bActive) return true;
    Cat = Controller ? Cast<AAstraCat>(Controller->GetPawn()) : nullptr;
    if (!IsValid(Cat) || Shots.IsEmpty()) return false;
    // Validate editable shot data before changing the player's state.
    for (const FAstraDemoShot& Shot : Shots)
    {
        if (Shot.Waypoints.Num() < 2 || Shot.WalkSpeed < 50.f || !FMath::IsFinite(Shot.WalkSpeed)
            || !FMath::IsFinite(Shot.MinimumSeconds) || Shot.MinimumSeconds < 3.f
            || !FMath::IsFinite(Shot.OrthoWidth) || Shot.OrthoWidth < 1500.f || Shot.CameraOffset.ContainsNaN()) return false;
        for (const FVector2D& Point : Shot.Waypoints)
            if (Point.ContainsNaN() || FMath::Abs(Point.X) > 4900 || FMath::Abs(Point.Y) > 4900) return false;
    }
    UCharacterMovementComponent* Movement = Cat->GetCharacterMovement();
    SavedTransform = Cat->GetActorTransform();
    SavedVelocity = Movement->Velocity;
    SavedMovementMode = Movement->MovementMode;
    SavedCustomMovementMode = Movement->CustomMovementMode;
    SavedWalkSpeed = Movement->MaxWalkSpeed;
    SavedOrthoWidth = Cat->TopDownCamera->OrthoWidth;
    SavedCameraOffset = Cat->CameraBoom->TargetOffset;
    bSavedCameraLag = Cat->CameraBoom->bEnableCameraLag;
    SavedViewTarget = Controller->GetViewTarget();
    SavedSafeLocation = Cat->SafeLocation;
    SavedGait = Cat->Gait;
    bActive = true;
    CompletedLoops = 0;
    Controller->SetViewTarget(Cat);
    if (!BeginShot(0))
    {
        Stop();
        return false;
    }
    UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO started; P returns to the original play state"));
    return true;
}

void UAstraDemoPlayback::CutCamera()
{
    // Reset spring-arm history at a cut so neither entry nor return flies across the map.
    Cat->CameraBoom->bEnableCameraLag = false;
    Cat->CameraBoom->TickComponent(0.f, LEVELTICK_All, nullptr);
    if (Controller->PlayerCameraManager) Controller->PlayerCameraManager->SetGameCameraCutThisFrame();
}

bool UAstraDemoPlayback::BeginShot(int32 Index)
{
    if (!IsValid(Cat) || !Shots.IsValidIndex(Index)) return false;
    const FAstraDemoShot& Shot = Shots[Index];
    if (Shot.Waypoints.Num() < 2) return false;
    const FVector2D XY = Shot.Waypoints[0];
    FHitResult Floor;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(AstraDemoFloor), false, Cat);
    if (!GetWorld()->LineTraceSingleByChannel(Floor, FVector(XY, 3500), FVector(XY, -1000), ECC_Visibility, Query)
        || Floor.ImpactNormal.Z < Cat->GetCharacterMovement()->GetWalkableFloorZ())
    {
        UE_LOG(LogTemp, Error, TEXT("ASTRA DEMO %s has no walkable starting surface"), *Shot.Name.ToString());
        return false;
    }
    const FVector Start(XY, Floor.ImpactPoint.Z + Cat->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 2.5f);
    const FCollisionShape Capsule = FCollisionShape::MakeCapsule(Cat->GetCapsuleComponent()->GetScaledCapsuleRadius(), Cat->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    if (GetWorld()->OverlapBlockingTestByChannel(Start, FQuat::Identity, ECC_Pawn, Capsule, Query))
    {
        UE_LOG(LogTemp, Error, TEXT("ASTRA DEMO %s starting capsule is obstructed"), *Shot.Name.ToString());
        return false;
    }
    UCharacterMovementComponent* Movement = Cat->GetCharacterMovement();
    Movement->StopMovementImmediately();
    Cat->ConsumeMovementInputVector();
    const FVector2D Facing = Shot.Waypoints[1] - XY;
    Cat->SetActorLocationAndRotation(Start, FVector(Facing, 0).Rotation(), false, nullptr, ETeleportType::TeleportPhysics);
    Cat->SafeLocation = Start;
    Movement->SetMovementMode(MOVE_Walking);
    Movement->MaxWalkSpeed = FMath::Clamp(Shot.WalkSpeed, 50.f, 340.f);
    Cat->TopDownCamera->SetOrthoWidth(Shot.OrthoWidth);
    Cat->CameraBoom->TargetOffset = Shot.CameraOffset;
    CutCamera();
    ShotIndex = Index;
    WaypointIndex = 1;
    ShotTime = HoldTime = StuckTime = ShotTravel = UnsupportedTime = 0.f;
    LastPosition = Start;
    bShotCaptured = false;
    float Length = 0.f;
    for (int32 Point = 1; Point < Shot.Waypoints.Num(); ++Point)
        Length += FVector2D::Distance(Shot.Waypoints[Point-1], Shot.Waypoints[Point]);
    ShotDeadline = FMath::Max(Shot.MinimumSeconds + 5.f, Length / Movement->MaxWalkSpeed * 2.f + 6.f);
    UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO cut %d/%d %s start=%s"), Index+1, Shots.Num(), *Shot.Name.ToString(), *Start.ToString());
    return true;
}

void UAstraDemoPlayback::FinishShot(bool bCompleted)
{
    const FAstraDemoShot& Shot = Shots[ShotIndex];
    UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO %s completed=%d travel=%.1f unsupported=%.3f duration=%.2f"),
        *Shot.Name.ToString(), bCompleted, ShotTravel, UnsupportedTime, ShotTime);
    if (Validation) Validation->RecordShot(Shot.Name, bCompleted, ShotTravel, UnsupportedTime);
    const int32 Next = (ShotIndex + 1) % Shots.Num();
    if (Next == 0) ++CompletedLoops;
    if (!BeginShot(Next)) Stop();
}

void UAstraDemoPlayback::Update(float Dt)
{
    if (Validation) Validation->Tick(Dt);
    if (!bActive) return;
    if (!IsValid(Cat) || !Controller || Controller->GetPawn() != Cat || !Shots.IsValidIndex(ShotIndex))
    {
        Stop();
        return;
    }
    const FAstraDemoShot& Shot = Shots[ShotIndex];
    ShotTime += Dt;
    const FVector Position = Cat->GetActorLocation();
    const float Travel = FVector::Dist2D(Position, LastPosition);
    ShotTravel += Travel;
    LastPosition = Position;
    if (ShotTime > .5f && !Cat->GetCharacterMovement()->IsMovingOnGround()) UnsupportedTime += Dt;
    if (Validation && !bShotCaptured && ShotTime > 4.f)
    {
        bShotCaptured = true;
        const FString Directory = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("ArtSource/Previews"));
        IFileManager::Get().MakeDirectory(*Directory, true);
        FScreenshotRequest::RequestScreenshot(Directory / (TEXT("UE_Demo_") + Shot.Name.ToString() + TEXT(".png")), false, false);
    }
    // A brief opening hold establishes each place. Within a shot all motion uses normal character physics.
    if (ShotTime < 1.f) return;
    if (Shot.Waypoints.IsValidIndex(WaypointIndex))
    {
        const FVector2D Delta = Shot.Waypoints[WaypointIndex] - FVector2D(Position);
        const float Distance = Delta.Size();
        if (Distance <= 22.f)
        {
            ++WaypointIndex;
            StuckTime = 0.f;
            if (WaypointIndex == Shot.Waypoints.Num()) Cat->GetCharacterMovement()->StopMovementImmediately();
        }
        else
        {
            StuckTime = Travel < 6.f * Dt ? StuckTime + Dt : 0.f;
            Cat->AddMovementInput(FVector(Delta.GetSafeNormal(), 0), FMath::Clamp(Distance / 70.f, .3f, 1.f));
        }
    }
    else
    {
        HoldTime += Dt;
        if (HoldTime >= 1.5f && ShotTime >= Shot.MinimumSeconds)
        {
            FinishShot(true);
            return;
        }
    }
    // An edited map must not leave the cat pushing an obstacle forever or falling off a location.
    if (StuckTime > 2.5f || UnsupportedTime > .75f || ShotTime > ShotDeadline)
        FinishShot(false);
}

void UAstraDemoPlayback::Stop()
{
    if (!bActive) return;
    bActive = false;
    if (IsValid(Cat))
    {
        UCharacterMovementComponent* Movement = Cat->GetCharacterMovement();
        Movement->StopMovementImmediately();
        Cat->ConsumeMovementInputVector();
        Cat->SetActorTransform(SavedTransform, false, nullptr, ETeleportType::TeleportPhysics);
        Cat->SafeLocation = SavedSafeLocation;
        Cat->Gait = SavedGait;
        Movement->MaxWalkSpeed = SavedWalkSpeed;
        Movement->SetMovementMode(static_cast<EMovementMode>(SavedMovementMode), SavedCustomMovementMode);
        Movement->Velocity = SavedVelocity;
        Cat->TopDownCamera->SetOrthoWidth(SavedOrthoWidth);
        Cat->CameraBoom->TargetOffset = SavedCameraOffset;
        if (Controller)
        {
            Controller->SetViewTarget(IsValid(SavedViewTarget) ? SavedViewTarget.Get() : Cat.Get());
            CutCamera();
        }
        Cat->CameraBoom->bEnableCameraLag = bSavedCameraLag;
    }
    ShotIndex = INDEX_NONE;
    UE_LOG(LogTemp, Display, TEXT("ASTRA DEMO stopped; original play state restored"));
}
