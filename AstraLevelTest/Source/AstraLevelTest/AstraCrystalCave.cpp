#include "AstraCrystalCave.h"

#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/PointLightComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Engine/PointLight.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "InputKeyEventArgs.h"
#include "Landscape.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#if WITH_EDITOR
#include "Editor.h"
#include "LandscapeEdit.h"
#include "LandscapeEditLayer.h"
#include "LandscapeInfo.h"
#endif

namespace
{
    const FKey CaveKeys[] = { EKeys::W, EKeys::A, EKeys::S, EKeys::D };
    const FVector CaveDirections[] = { FVector(1,0,0), FVector(0,-1,0), FVector(-1,0,0), FVector(0,1,0) };

    TArray<TSharedPtr<FJsonValue>> JsonPosition(const FVector& Position)
    {
        return { MakeShared<FJsonValueNumber>(Position.X), MakeShared<FJsonValueNumber>(Position.Y), MakeShared<FJsonValueNumber>(Position.Z) };
    }

    struct FCaveRoute
    {
        FString Name;
        FString Kind;
        FName ExpectedBlockerTag;
        TArray<FVector> Waypoints;
    };
}

/** Tests use the same InputKey -> IsInputKeyDown -> AddMovementInput path as the player.
 * The only position writes place the cat at the initial point of an independent test route.
 * Coordinates in cave_routes.json are UE XY centimetres; Landscape supplies initial Z.
 */
struct FAstraCaveValidation
{
    enum class EPhase { Waiting, SmokeSettle, SmokePress, SmokeRelease, RouteSettle, Walking, Collision, Done };
    explicit FAstraCaveValidation(AAstraCrystalCaveController& InController) : Controller(InController) {}

    AAstraCrystalCaveController& Controller;
    TArray<FCaveRoute> Routes;
    TArray<TSharedPtr<FJsonValue>> Checks;
    TArray<TSharedPtr<FJsonValue>> RouteResults;
    TArray<TSharedPtr<FJsonValue>> Samples;
    TArray<TSharedPtr<FJsonValue>> ReachedWaypoints;
    TSharedPtr<FJsonObject> CurrentResult;
    EPhase Phase = EPhase::Waiting;
    int32 RouteIndex = -1;
    int32 WaypointIndex = 1;
    int32 SmokeIndex = 0;
    int32 FailedChecks = 0;
    int32 DiscontinuousMoves = 0;
    float Elapsed = 0;
    float PhaseStarted = 0;
    float RouteStarted = 0;
    float SegmentStarted = 0;
    float LastSampleTime = 0;
    float Tolerance = 50;
    float WalkSpeed = 260;
    float MinimumSegmentSeconds = 20;
    float SegmentDeadline = 20;
    float UnsupportedSeconds = 0;
    float MaximumUnsupportedSeconds = 0;
    float Travel = 0;
    float StationarySeconds = 0;
    float ExpectedCollisionTravel = 0;
    float MinX = -1450;
    float MaxX = 1450;
    float MinY = -2450;
    float MaxY = 2450;
    bool bKeys[4] = { false, false, false, false };
    bool bRouteCameraFixed = true;
    bool bWithinBounds = true;
    FVector LastPosition = FVector::ZeroVector;
    FVector SmokeStart = FVector::ZeroVector;
    FVector ProbeStart = FVector::ZeroVector;
    FVector ProbeDirection = FVector::ZeroVector;
    FVector ExpectedStop = FVector::ZeroVector;
    FRotator CameraRotation = FRotator(-58,0,0);

    AAstraCat* Cat() const { return Cast<AAstraCat>(Controller.GetPawn()); }
    void Enter(EPhase Next) { Phase = Next; PhaseStarted = Elapsed; }

    void Key(int32 Index, bool bPressed)
    {
        if (bKeys[Index] == bPressed) return;
        Controller.InputKey(FInputKeyEventArgs::CreateSimulated(CaveKeys[Index], bPressed ? IE_Pressed : IE_Released, bPressed ? 1.f : 0.f));
        bKeys[Index] = bPressed;
    }
    void ReleaseKeys() { for (int32 Index = 0; Index < 4; ++Index) Key(Index, false); }
    void Steer(const FVector& Difference, float DeadZone)
    {
        Key(0, Difference.X > DeadZone);
        Key(1, Difference.Y < -DeadZone);
        Key(2, Difference.X < -DeadZone);
        Key(3, Difference.Y > DeadZone);
    }
    bool Grounded() const
    {
        const AAstraCat* Player = Cat();
        return Player && Player->GetCharacterMovement()->IsMovingOnGround()
            && Player->GetCharacterMovement()->CurrentFloor.IsWalkableFloor();
    }
    bool FixedCamera() const
    {
        const AAstraCat* Player = Cat();
        return Player && Player->TopDownCamera->GetComponentRotation().Equals(CameraRotation, .05f)
            && Player->CameraBoom->GetComponentRotation().Equals(CameraRotation, .05f)
            && FMath::IsNearlyEqual(Player->TopDownCamera->OrthoWidth, 2300.f, .1f)
            && Controller.GetViewTarget() == Player;
    }
    void Check(const FString& Name, bool bPass, const FString& Detail)
    {
        TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
        Result->SetStringField(TEXT("name"), Name);
        Result->SetBoolField(TEXT("passed"), bPass);
        Result->SetStringField(TEXT("detail"), Detail);
        Checks.Add(MakeShared<FJsonValueObject>(Result));
        FailedChecks += bPass ? 0 : 1;
        UE_LOG(LogTemp, Display, TEXT("ASTRA CAVE %s: %s %s"), *Name, bPass ? TEXT("PASS") : TEXT("FAIL"), *Detail);
    }
    void Finish(const FString& Failure = FString())
    {
        ReleaseKeys();
        if (!Failure.IsEmpty()) Check(TEXT("completion"), false, Failure);
        TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
        const bool bPass = Failure.IsEmpty() && FailedChecks == 0 && RouteIndex == Routes.Num() && SmokeIndex == 4;
        Root->SetNumberField(TEXT("schema_version"), 1);
        Root->SetStringField(TEXT("map"), Controller.GetWorld()->GetMapName());
        Root->SetBoolField(TEXT("passed"), bPass);
        Root->SetNumberField(TEXT("exit_code"), bPass ? 0 : 1);
        Root->SetNumberField(TEXT("elapsed_game_seconds"), Elapsed);
        Root->SetNumberField(TEXT("failed_checks"), FailedChecks);
        Root->SetStringField(TEXT("input_method"), TEXT("FInputKeyEventArgs::CreateSimulated -> AAstraController::PlayerTick WASD -> CharacterMovement"));
        Root->SetStringField(TEXT("route_source"), TEXT("ArtSource/Layout/CrystalCave/cave_routes.json"));
        Root->SetStringField(TEXT("position_writes"), TEXT("Initial route placement only; no teleport or SetActorLocation during traversal"));
        Root->SetNumberField(TEXT("camera_pitch"), CameraRotation.Pitch);
        Root->SetNumberField(TEXT("camera_yaw"), CameraRotation.Yaw);
        Root->SetNumberField(TEXT("ortho_width_cm"), 2300);
        Root->SetNumberField(TEXT("walk_speed_cm_s"), WalkSpeed);
        Root->SetNumberField(TEXT("waypoint_tolerance_cm"), Tolerance);
        Root->SetNumberField(TEXT("routes_expected"), Routes.Num());
        Root->SetNumberField(TEXT("routes_completed"), RouteResults.Num());
        Root->SetArrayField(TEXT("checks"), Checks);
        Root->SetArrayField(TEXT("routes"), RouteResults);
        FString Json;
        FJsonSerializer::Serialize(Root.ToSharedRef(), TJsonWriterFactory<>::Create(&Json));
        const FString Directory = FPaths::ProjectDir() / TEXT("ArtSource/Previews/CrystalCave");
        IFileManager::Get().MakeDirectory(*Directory, true);
        const bool bSaved = FFileHelper::SaveStringToFile(Json, *(Directory / TEXT("UE_CaveMovementValidation.json")));
        UE_LOG(LogTemp, Display, TEXT("ASTRA CAVE COMPLETE passed=%d saved=%d completed_routes=%d/%d failed_checks=%d"), bPass, bSaved, RouteResults.Num(), Routes.Num(), FailedChecks);
        Enter(EPhase::Done);
        // This is an explicitly requested standalone validation run. SaveStringToFile
        // has closed its file above. UE's graceful Windows exit can lose a nonzero
        // PostQuitMessage status in the -game main loop; force preserves the real
        // result via TerminateProcess and FWindowsPlatformMisc flushes GLog first.
        FPlatformMisc::RequestExitWithStatus(true, bPass && bSaved ? 0 : 1, TEXT("AstraCaveTest finished and report saved"));
    }

    bool LoadRoutes(FString& Error)
    {
        FString Text;
        TSharedPtr<FJsonObject> Root;
        if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectDir() / TEXT("ArtSource/Layout/CrystalCave/cave_routes.json")))
            || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
        { Error = TEXT("Missing or invalid cave_routes.json"); return false; }
        int32 Version = 0;
        if (!Root->TryGetNumberField(TEXT("schema_version"), Version) || Version != 1)
        { Error = TEXT("Expected cave route schema_version 1"); return false; }
        Root->TryGetNumberField(TEXT("waypoint_tolerance_cm"), Tolerance);
        Root->TryGetNumberField(TEXT("walk_speed_cm_s"), WalkSpeed);
        Root->TryGetNumberField(TEXT("max_segment_seconds"), MinimumSegmentSeconds);
        if (!FMath::IsFinite(Tolerance) || Tolerance < 20 || Tolerance > 80
            || !FMath::IsFinite(WalkSpeed) || WalkSpeed < 100 || WalkSpeed > 340
            || !FMath::IsFinite(MinimumSegmentSeconds) || MinimumSegmentSeconds < 5 || MinimumSegmentSeconds > 60)
        { Error = TEXT("Invalid tolerance, walk speed, or segment timeout"); return false; }
        const TSharedPtr<FJsonObject>* Bounds = nullptr;
        if (Root->TryGetObjectField(TEXT("bounds_cm"), Bounds))
        {
            if (!(*Bounds)->TryGetNumberField(TEXT("min_x"), MinX) || !(*Bounds)->TryGetNumberField(TEXT("max_x"), MaxX)
                || !(*Bounds)->TryGetNumberField(TEXT("min_y"), MinY) || !(*Bounds)->TryGetNumberField(TEXT("max_y"), MaxY)
                || !FMath::IsFinite(MinX) || !FMath::IsFinite(MaxX) || !FMath::IsFinite(MinY) || !FMath::IsFinite(MaxY)
                || MinX >= MaxX || MinY >= MaxY || MinX < -1500 || MaxX > 1500 || MinY < -2500 || MaxY > 2500)
            { Error = TEXT("Invalid cave footprint bounds"); return false; }
        }
        const TArray<TSharedPtr<FJsonValue>>* InputRoutes = nullptr;
        if (!Root->TryGetArrayField(TEXT("routes"), InputRoutes) || InputRoutes->Num() < 7 || InputRoutes->Num() > 40)
        { Error = TEXT("Expected four branches, full traversal and two collision probes"); return false; }
        TSet<FString> Names;
        bool bIslandProbe = false;
        bool bBoundaryProbe = false;
        for (const TSharedPtr<FJsonValue>& Value : *InputRoutes)
        {
            const TSharedPtr<FJsonObject>* Object = nullptr;
            if (!Value->TryGetObject(Object)) { Error = TEXT("Route must be an object"); return false; }
            FCaveRoute Route;
            FString BlockerTag;
            const TArray<TSharedPtr<FJsonValue>>* Points = nullptr;
            if (!(*Object)->TryGetStringField(TEXT("name"), Route.Name) || Route.Name.IsEmpty() || Names.Contains(Route.Name)
                || !(*Object)->TryGetStringField(TEXT("kind"), Route.Kind) || (Route.Kind != TEXT("walk") && Route.Kind != TEXT("collision"))
                || !(*Object)->TryGetArrayField(TEXT("waypoints"), Points) || Points->Num() < 2 || Points->Num() > 100)
            { Error = TEXT("Invalid or duplicate route metadata"); return false; }
            for (const TSharedPtr<FJsonValue>& Point : *Points)
            {
                const TArray<TSharedPtr<FJsonValue>>* XY = nullptr;
                double X = 0, Y = 0;
                if (!Point->TryGetArray(XY) || XY->Num() != 2 || !(*XY)[0]->TryGetNumber(X) || !(*XY)[1]->TryGetNumber(Y)
                    || !FMath::IsFinite(X) || !FMath::IsFinite(Y) || FMath::Abs(X) > 2500 || FMath::Abs(Y) > 3500)
                { Error = TEXT("Waypoints must be finite [X,Y] centimetres near the cave"); return false; }
                if (Route.Kind == TEXT("walk") && (X < MinX || X > MaxX || Y < MinY || Y > MaxY))
                { Error = TEXT("Walk waypoint lies outside cave bounds"); return false; }
                Route.Waypoints.Add(FVector(X, Y, 0));
            }
            if (Route.Kind == TEXT("collision"))
            {
                const FVector Difference = Route.Waypoints.Last() - Route.Waypoints[0];
                if (Route.Waypoints.Num() != 2 || !(*Object)->TryGetStringField(TEXT("expected_blocker_tag"), BlockerTag) || BlockerTag.IsEmpty()
                    || Difference.Size2D() < 100 || (FMath::Abs(Difference.X) > 1 && FMath::Abs(Difference.Y) > 1))
                { Error = TEXT("Collision probe requires two axis-aligned points at least 100cm apart and expected_blocker_tag"); return false; }
                Route.ExpectedBlockerTag = FName(*BlockerTag);
                bIslandProbe |= BlockerTag == TEXT("CaveIsland");
                bBoundaryProbe |= BlockerTag == TEXT("CaveBoundary");
            }
            Names.Add(Route.Name);
            Routes.Add(MoveTemp(Route));
        }
        for (const TCHAR* Required : { TEXT("fork1_left"), TEXT("fork1_right"), TEXT("fork2_left"), TEXT("fork2_right"), TEXT("full_traversal") })
        {
            const FCaveRoute* Route = Routes.FindByPredicate([Required](const FCaveRoute& Candidate) { return Candidate.Name == Required && Candidate.Kind == TEXT("walk"); });
            if (!Route) { Error = FString(TEXT("Missing required walking route: ")) + Required; return false; }
            if (Route->Name == TEXT("full_traversal") && (FVector::Dist2D(Route->Waypoints[0], FVector(0,-2100,0)) > 100
                || FVector::Dist2D(Route->Waypoints.Last(), FVector(0,2100,0)) > 100))
            { Error = TEXT("Full traversal must connect cave entry [0,-2100] to terminus [0,2100]"); return false; }
        }
        if (!bIslandProbe || !bBoundaryProbe) { Error = TEXT("CaveIsland and CaveBoundary collision probes are mandatory"); return false; }
        if (Routes[0].Kind != TEXT("walk")) { Error = TEXT("First route must be a walk with a clear initial smoke-test area"); return false; }
        return true;
    }

    bool PlaceAtRouteStart(const FVector& XY)
    {
        AAstraCat* Player = Cat();
        ReleaseKeys();
        FVector Start = XY;
        bool bFoundLandscape = false;
        for (TActorIterator<ALandscape> It(Controller.GetWorld()); It; ++It)
        {
            const TOptional<float> Height = It->GetHeightAtLocation(Start);
            if (Height.IsSet()) { Start.Z = Height.GetValue() + Player->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 6.f; bFoundLandscape = true; break; }
        }
        if (!bFoundLandscape) return false;
        Player->GetCharacterMovement()->StopMovementImmediately();
        Player->SetActorLocation(Start, false, nullptr, ETeleportType::TeleportPhysics);
        Player->GetCharacterMovement()->SetMovementMode(MOVE_Falling);
        Controller.SetViewTarget(Player);
        LastPosition = Start;
        return true;
    }

    void BeginRoute()
    {
        ++RouteIndex;
        if (RouteIndex == Routes.Num()) { Finish(); return; }
        const FCaveRoute& Route = Routes[RouteIndex];
        if (!PlaceAtRouteStart(Route.Waypoints[0])) { Finish(TEXT("No Landscape support at route start: ") + Route.Name); return; }
        CurrentResult = MakeShared<FJsonObject>();
        CurrentResult->SetStringField(TEXT("name"), Route.Name);
        CurrentResult->SetStringField(TEXT("kind"), Route.Kind);
        Samples.Reset();
        ReachedWaypoints.Reset();
        WaypointIndex = 1;
        Travel = UnsupportedSeconds = MaximumUnsupportedSeconds = StationarySeconds = 0;
        DiscontinuousMoves = 0;
        bRouteCameraFixed = bWithinBounds = true;
        RouteStarted = Elapsed;
        LastSampleTime = -1;
        UE_LOG(LogTemp, Display, TEXT("ASTRA CAVE route %s starting (%d/%d)"), *Route.Name, RouteIndex + 1, Routes.Num());
        Enter(EPhase::RouteSettle);
    }

    void StartSegment()
    {
        SegmentStarted = Elapsed;
        // A deadline per segment makes low frame rates and unequal path lengths harmless.
        SegmentDeadline = FMath::Max(MinimumSegmentSeconds,
            static_cast<float>(FVector::Dist2D(Cat()->GetActorLocation(), Routes[RouteIndex].Waypoints[WaypointIndex])) / WalkSpeed * 2.5f + 5.f);
    }

    void Sample(float Dt)
    {
        const FVector Position = Cat()->GetActorLocation();
        const float Moved = static_cast<float>(FVector::Dist2D(Position, LastPosition));
        Travel += Moved;
        if (FVector::Dist(Position, LastPosition) > WalkSpeed * Dt * 2.f + 50.f) ++DiscontinuousMoves;
        LastPosition = Position;
        UnsupportedSeconds = Grounded() ? 0.f : UnsupportedSeconds + Dt;
        MaximumUnsupportedSeconds = FMath::Max(MaximumUnsupportedSeconds, UnsupportedSeconds);
        bRouteCameraFixed &= FixedCamera();
        bWithinBounds &= Position.X >= MinX && Position.X <= MaxX && Position.Y >= MinY && Position.Y <= MaxY && Position.Z > -100.f;
        if (Elapsed - LastSampleTime >= .2f)
        {
            LastSampleTime = Elapsed;
            TSharedPtr<FJsonObject> Point = MakeShared<FJsonObject>();
            Point->SetNumberField(TEXT("seconds"), Elapsed - RouteStarted);
            Point->SetArrayField(TEXT("position_cm"), JsonPosition(Position));
            Point->SetBoolField(TEXT("grounded"), Grounded());
            Point->SetBoolField(TEXT("fixed_camera"), FixedCamera());
            Point->SetNumberField(TEXT("foot_z_cm"), Position.Z - Cat()->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
            Point->SetNumberField(TEXT("speed_cm_s"), Cat()->GetVelocity().Size2D());
            Samples.Add(MakeShared<FJsonValueObject>(Point));
        }
    }

    void EndRoute(bool bReached, const FString& Detail)
    {
        ReleaseKeys();
        const bool bPass = bReached && MaximumUnsupportedSeconds <= .2f && bRouteCameraFixed && bWithinBounds && DiscontinuousMoves == 0 && Grounded();
        CurrentResult->SetBoolField(TEXT("passed"), bPass);
        CurrentResult->SetBoolField(TEXT("reached_objective"), bReached);
        CurrentResult->SetStringField(TEXT("detail"), Detail);
        CurrentResult->SetNumberField(TEXT("seconds"), Elapsed - RouteStarted);
        CurrentResult->SetNumberField(TEXT("travel_cm"), Travel);
        CurrentResult->SetNumberField(TEXT("max_unsupported_seconds"), MaximumUnsupportedSeconds);
        CurrentResult->SetNumberField(TEXT("discontinuous_moves"), DiscontinuousMoves);
        CurrentResult->SetBoolField(TEXT("fixed_camera"), bRouteCameraFixed);
        CurrentResult->SetBoolField(TEXT("within_cave_bounds"), bWithinBounds);
        CurrentResult->SetBoolField(TEXT("final_grounded"), Grounded());
        CurrentResult->SetArrayField(TEXT("final_position_cm"), JsonPosition(Cat()->GetActorLocation()));
        CurrentResult->SetArrayField(TEXT("reached_waypoints"), ReachedWaypoints);
        CurrentResult->SetArrayField(TEXT("samples"), Samples);
        RouteResults.Add(MakeShared<FJsonValueObject>(CurrentResult));
        Check(Routes[RouteIndex].Name, bPass, Detail);
        BeginRoute();
    }

    bool StartCollisionProbe()
    {
        const FCaveRoute& Route = Routes[RouteIndex];
        ProbeStart = Cat()->GetActorLocation();
        const FVector Target(Route.Waypoints.Last().X, Route.Waypoints.Last().Y, ProbeStart.Z);
        ProbeDirection = (Target - ProbeStart).GetSafeNormal2D();
        FHitResult Hit;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(CaveCollisionProbe), false, Cat());
        // Lift the probe's bottom 12cm above Landscape to isolate the wall from walkable slopes.
        const FCollisionShape Shape = FCollisionShape::MakeCapsule(Cat()->GetCapsuleComponent()->GetScaledCapsuleRadius(),
            Cat()->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() - 6.f);
        const bool bHit = Controller.GetWorld()->SweepSingleByChannel(Hit, ProbeStart + FVector(0,0,6), Target + FVector(0,0,6),
            FQuat::Identity, ECC_Pawn, Shape, Params);
        const bool bExpectedActor = bHit && Hit.GetActor() && Hit.GetActor()->ActorHasTag(Route.ExpectedBlockerTag);
        CurrentResult->SetBoolField(TEXT("initial_sweep_hit"), bHit);
        CurrentResult->SetBoolField(TEXT("expected_blocker_tag_matched"), bExpectedActor);
        CurrentResult->SetStringField(TEXT("expected_blocker_tag"), Route.ExpectedBlockerTag.ToString());
        CurrentResult->SetStringField(TEXT("blocking_actor"), Hit.GetActor() ? Hit.GetActor()->GetName() : TEXT("none"));
        CurrentResult->SetBoolField(TEXT("initial_penetration"), Hit.bStartPenetrating);
        if (!bHit || !bExpectedActor || Hit.bStartPenetrating || Hit.Distance < 30.f)
        { EndRoute(false, TEXT("Initial capsule sweep did not find the tagged wall ahead from a clear starting position")); return false; }
        ExpectedCollisionTravel = Hit.Distance;
        ExpectedStop = ProbeStart + ProbeDirection * Hit.Distance;
        CurrentResult->SetNumberField(TEXT("expected_stop_distance_cm"), Hit.Distance);
        CurrentResult->SetArrayField(TEXT("expected_stop_cm"), JsonPosition(ExpectedStop));
        StationarySeconds = 0;
        StartSegment();
        Enter(EPhase::Collision);
        return true;
    }

    void Tick(float Dt)
    {
        if (Phase == EPhase::Done) return;
        Elapsed += Dt;
        if (Elapsed > 900.f) { Finish(TEXT("Global test deadline exceeded")); return; }
        AAstraCat* Player = Cat();
        if (!Player)
        {
            if (Elapsed > 10.f) Finish(TEXT("Calico pawn was not possessed"));
            return;
        }
        if (Phase == EPhase::Waiting)
        {
            if (Elapsed < 1.f) return;
            // Generic forest review validation has its own exit timer; never mix it with cave movement tests.
            FString Review;
            if (FParse::Value(FCommandLine::Get(), TEXT("AstraReview="), Review)
                || FParse::Param(FCommandLine::Get(), TEXT("AstraSmokeTest"))
                || FParse::Param(FCommandLine::Get(), TEXT("AstraDemoTest")))
            { Finish(TEXT("Run -AstraCaveTest alone, without forest test or AstraReview flags")); return; }
            FString Error;
            if (!LoadRoutes(Error)) { Finish(Error); return; }
            Player->GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
            Check(TEXT("cave_controller_and_camera"), FixedCamera(), TEXT("Calico, pitch -58 yaw 0, orthographic width 2300cm"));
            const bool bPBound = Controller.InputComponent && Controller.InputComponent->KeyBindings.ContainsByPredicate(
                [](const FInputKeyBinding& Binding) { return Binding.Chord.Key == EKeys::P; });
            Check(TEXT("forest_demo_unbound"), !bPBound, TEXT("P has no binding in the cave controller"));
            if (!PlaceAtRouteStart(Routes[0].Waypoints[0])) { Finish(TEXT("No Landscape at input smoke start")); return; }
            Enter(EPhase::SmokeSettle);
            return;
        }
        if (Phase == EPhase::SmokeSettle)
        {
            if (Elapsed - PhaseStarted > 4.f) { Finish(TEXT("Input smoke start did not settle onto Landscape")); return; }
            if (Elapsed - PhaseStarted < .4f || !Grounded()) return;
            SmokeStart = Player->GetActorLocation();
            Key(SmokeIndex, true);
            Enter(EPhase::SmokePress);
            return;
        }
        if (Phase == EPhase::SmokePress)
        {
            if (Elapsed - PhaseStarted < .4f) return;
            ReleaseKeys();
            Enter(EPhase::SmokeRelease);
            return;
        }
        if (Phase == EPhase::SmokeRelease)
        {
            if (Elapsed - PhaseStarted < .3f) return;
            const FVector Delta = Player->GetActorLocation() - SmokeStart;
            const float Forward = static_cast<float>(FVector::DotProduct(Delta, CaveDirections[SmokeIndex]));
            const float Lateral = static_cast<float>((Delta - CaveDirections[SmokeIndex] * Forward).Size2D());
            Check(FString(TEXT("input_")) + CaveKeys[SmokeIndex].ToString(), Forward > 40.f && Lateral < 25.f && Grounded() && FixedCamera(),
                FString::Printf(TEXT("travel_cm=%.2f lateral_cm=%.2f delta=%s grounded=%d camera_fixed=%d"), Forward, Lateral, *Delta.ToString(), Grounded(), FixedCamera()));
            ++SmokeIndex;
            if (SmokeIndex == 4) BeginRoute();
            else Enter(EPhase::SmokeSettle);
            return;
        }
        if (Phase == EPhase::RouteSettle)
        {
            if (Elapsed - PhaseStarted > 4.f) { EndRoute(false, TEXT("Route start did not settle onto walkable floor")); return; }
            if (Elapsed - PhaseStarted < .4f || !Grounded()) return;
            LastPosition = Player->GetActorLocation();
            CurrentResult->SetArrayField(TEXT("initial_position_cm"), JsonPosition(LastPosition));
            if (Routes[RouteIndex].Kind == TEXT("collision")) StartCollisionProbe();
            else { StartSegment(); Enter(EPhase::Walking); }
            return;
        }
        Sample(Dt);
        if (MaximumUnsupportedSeconds > .2f || !bWithinBounds || DiscontinuousMoves > 0)
        { EndRoute(false, TEXT("Lost ground support, left cave bounds, or detected an in-route position discontinuity")); return; }
        if (Elapsed - SegmentStarted > SegmentDeadline)
        { EndRoute(false, FString::Printf(TEXT("Waypoint/probe %d timed out after %.1f seconds"), WaypointIndex, SegmentDeadline)); return; }
        if (Phase == EPhase::Walking)
        {
            const FVector Difference = Routes[RouteIndex].Waypoints[WaypointIndex] - Player->GetActorLocation();
            if (Difference.Size2D() <= Tolerance)
            {
                TSharedPtr<FJsonObject> Reached = MakeShared<FJsonObject>();
                Reached->SetNumberField(TEXT("index"), WaypointIndex);
                Reached->SetNumberField(TEXT("error_cm"), Difference.Size2D());
                Reached->SetNumberField(TEXT("seconds"), Elapsed - RouteStarted);
                Reached->SetBoolField(TEXT("grounded"), Grounded());
                Reached->SetArrayField(TEXT("position_cm"), JsonPosition(Player->GetActorLocation()));
                ReachedWaypoints.Add(MakeShared<FJsonValueObject>(Reached));
                ++WaypointIndex;
                if (WaypointIndex == Routes[RouteIndex].Waypoints.Num()) { EndRoute(true, TEXT("Every waypoint reached by actual WASD with continuous supported movement")); return; }
                StartSegment();
            }
            Steer(Routes[RouteIndex].Waypoints[WaypointIndex] - Player->GetActorLocation(), Tolerance * .35f);
        }
        else if (Phase == EPhase::Collision)
        {
            Steer(ProbeDirection * 100.f, 1.f);
            const FVector Delta = Player->GetActorLocation() - ProbeStart;
            const float Forward = static_cast<float>(FVector::DotProduct(Delta, ProbeDirection));
            const float Lateral = static_cast<float>((Delta - ProbeDirection * Forward).Size2D());
            const bool bAtWall = FMath::Abs(Forward - ExpectedCollisionTravel) < 55.f && Lateral < 40.f;
            StationarySeconds = bAtWall && Player->GetVelocity().Size2D() < 8.f ? StationarySeconds + Dt : 0.f;
            if (Forward > ExpectedCollisionTravel + 55.f)
            { EndRoute(false, TEXT("Pawn crossed the capsule sweep's expected blocking wall")); return; }
            if (StationarySeconds >= 1.2f)
            {
                CurrentResult->SetNumberField(TEXT("actual_forward_travel_cm"), Forward);
                CurrentResult->SetNumberField(TEXT("lateral_error_cm"), Lateral);
                CurrentResult->SetNumberField(TEXT("held_against_wall_seconds"), StationarySeconds);
                CurrentResult->SetNumberField(TEXT("stop_error_cm"), FMath::Abs(Forward - ExpectedCollisionTravel));
                EndRoute(Forward > 20.f && bAtWall, TEXT("Held WASD into the tagged barrier for 1.2 seconds; capsule stopped at expected collision surface"));
            }
        }
    }
};

AAstraCrystalCaveController::AAstraCrystalCaveController() = default;
AAstraCrystalCaveController::~AAstraCrystalCaveController() = default;

void AAstraCrystalCaveController::BeginPlay()
{
    Super::BeginPlay();
    if (FParse::Param(FCommandLine::Get(), TEXT("AstraCaveLightsOff")))
    {
        int32 DisabledLights = 0;
        for (TActorIterator<APointLight> It(GetWorld()); It; ++It)
        {
            if (!It->ActorHasTag(TEXT("CaveCrystalLight"))) continue;
            It->GetLightComponent()->SetIntensity(0.f);
            ++DisabledLights;
        }
        UE_LOG(LogTemp, Display, TEXT("ASTRA CAVE LIGHT A/B: disabled %d tagged crystal point lights; emissive materials preserved"), DisabledLights);
    }
    if (FParse::Param(FCommandLine::Get(), TEXT("AstraCaveTest"))) CaveValidation = MakeShared<FAstraCaveValidation>(*this);
}

void AAstraCrystalCaveController::SetupInputComponent()
{
    Super::SetupInputComponent();
    // The inherited forest tour has hard-coded coordinates belonging to another level.
    InputComponent->KeyBindings.RemoveAll([](const FInputKeyBinding& Binding) { return Binding.Chord.Key == EKeys::P; });
}

void AAstraCrystalCaveController::OnPossess(APawn* InPawn)
{
    Super::OnPossess(InPawn);
    if (AAstraCat* CaveCat = Cast<AAstraCat>(InPawn))
    {
        CaveCat->CameraBoom->SetUsingAbsoluteRotation(true);
        CaveCat->CameraBoom->SetWorldRotation(FRotator(-58,0,0));
        CaveCat->CameraBoom->bDoCollisionTest = false;
        CaveCat->TopDownCamera->OrthoWidth = 2300.f;
    }
}

void AAstraCrystalCaveController::PlayerTick(float DeltaTime)
{
    if (CaveValidation) CaveValidation->Tick(DeltaTime);
    Super::PlayerTick(DeltaTime);
}

AAstraCrystalCaveGameMode::AAstraCrystalCaveGameMode()
{
    PlayerControllerClass = AAstraCrystalCaveController::StaticClass();
}

AActor* UAstraCrystalCaveLibrary::CreateCaveTerrain(UMaterialInterface* Material)
{
#if WITH_EDITOR
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World) return nullptr;
    const FString Filename = FPaths::ProjectDir() / TEXT("ArtSource/Layout/CrystalCave/cave_height.r16");
    TArray<uint8> Raw;
    constexpr int32 SizeX = 127, SizeY = 64;
    if (!FFileHelper::LoadFileToArray(Raw, *Filename) || Raw.Num() != SizeX * SizeY * 2)
    {
        UE_LOG(LogTemp, Error, TEXT("Missing or invalid Blender cave R16 heightmap (expected 127 x 64): %s"), *Filename);
        return nullptr;
    }
    FActorSpawnParameters Parameters;
    Parameters.ObjectFlags |= RF_Transactional;
    ALandscape* Terrain = World->SpawnActor<ALandscape>(ALandscape::StaticClass(), FVector(-1500,-2500,0), FRotator::ZeroRotator, Parameters);
    if (!Terrain) return nullptr;
    Terrain->SetActorScale3D(FVector(3000.f / 126.f, 5000.f / 63.f, 100.f));
    Terrain->LandscapeMaterial = Material;
    TArray<uint16> Heights;
    Heights.SetNumUninitialized(SizeX * SizeY);
    FMemory::Memcpy(Heights.GetData(), Raw.GetData(), Raw.Num());
    TMap<FGuid,TArray<uint16>> HeightLayers;
    HeightLayers.Add(FGuid(), MoveTemp(Heights));
    TMap<FGuid,TArray<FLandscapeImportLayerInfo>> MaterialLayers;
    MaterialLayers.Add(FGuid(), {});
    Terrain->Import(FGuid::NewGuid(), 0, 0, 126, 63, 1, 63, HeightLayers, TEXT(""), MaterialLayers,
        ELandscapeImportAlphamapType::Additive, TArrayView<const FLandscapeLayer>());
    Terrain->CreateLandscapeInfo();
    Terrain->SetActorLabel(TEXT("Landscape_30x50m_CrystalCave"));
    Terrain->Tags.Add(TEXT("CrystalCave"));
    Terrain->PostEditChange();
    Terrain->MarkPackageDirty();
    return Terrain;
#else
    return nullptr;
#endif
}
