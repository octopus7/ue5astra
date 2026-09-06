#include "AstraWorld.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "Landscape.h"
#include "LandscapeInfo.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "InputKeyEventArgs.h"
#include "Camera/CameraActor.h"
#include "EngineUtils.h"
#include "Engine/GameViewportClient.h"
#if WITH_EDITOR
#include "Editor.h"
#include "LandscapeEdit.h"
#include "LandscapeEditLayer.h"
#endif

UStaticMeshComponent* AAstraCat::Box(const TCHAR* Name, FVector Position, FVector Dimensions, const TCHAR* MaterialName, USceneComponent* Parent)
{
    UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Name);
    Part->SetupAttachment(Parent ? Parent : CatRoot.Get());
    Part->SetRelativeLocation(Position);
    Part->SetRelativeScale3D(Dimensions / 100.f);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    Part->SetStaticMesh(Cube.Object);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    const FString Path = FString::Printf(TEXT("/Game/Astra/Materials/%s.%s"), MaterialName, MaterialName);
    if (UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr, *Path)) Part->SetMaterial(0, Mat);
    return Part;
}

AAstraCat::AAstraCat()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(30, 88);
    bUseControllerRotationYaw = false;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->RotationRate = FRotator(0, 680, 0);
    GetCharacterMovement()->MaxWalkSpeed = 340;
    GetCharacterMovement()->MaxAcceleration = 1600;
    GetCharacterMovement()->BrakingDecelerationWalking = 2000;
    GetCharacterMovement()->MaxStepHeight = 40;
    GetCharacterMovement()->SetWalkableFloorAngle(45);
    CatRoot = CreateDefaultSubobject<USceneComponent>(TEXT("CalicoVisual"));
    CatRoot->SetupAttachment(GetCapsuleComponent());
    CatRoot->SetRelativeLocation(FVector(0,0,-88));
    Box(TEXT("Body"), FVector(0,0,78), FVector(34,42,52), TEXT("M_CatCream"));
    Box(TEXT("BackOrange"), FVector(-18,8,84), FVector(3,25,32), TEXT("M_CatOrange"));
    Box(TEXT("BackBlack"), FVector(-18,-14,68), FVector(3,15,24), TEXT("M_CatBlack"));
    Box(TEXT("SideOrange"), FVector(1,22,78), FVector(30,3,36), TEXT("M_CatOrange"));
    Box(TEXT("Head"), FVector(3,0,130), FVector(54,62,48), TEXT("M_CatCream"));
    Box(TEXT("HeadOrange"), FVector(5,17,143), FVector(53,29,24), TEXT("M_CatOrange"));
    Box(TEXT("HeadBlack"), FVector(-11,-19,145), FVector(30,25,20), TEXT("M_CatBlack"));
    Box(TEXT("ForeheadBlack"), FVector(30,-19,143), FVector(2,18,21), TEXT("M_CatBlack"));
    Box(TEXT("Muzzle"), FVector(33,0,119), FVector(12,35,20), TEXT("M_CatCream"));
    Box(TEXT("EyeLeft"), FVector(31,-16,132), FVector(3,8,10), TEXT("M_CatBlack"));
    Box(TEXT("EyeRight"), FVector(33,16,132), FVector(3,8,10), TEXT("M_CatBlack"));
    Box(TEXT("EyeGlintLeft"), FVector(33,-17,134), FVector(1.5,3,4), TEXT("M_CatCream"));
    Box(TEXT("EyeGlintRight"), FVector(35,15,134), FVector(1.5,3,4), TEXT("M_CatCream"));
    Box(TEXT("Nose"), FVector(40,0,124), FVector(3,8,5), TEXT("M_CatPink"));
    Box(TEXT("Mouth"), FVector(40,0,117), FVector(2,3,4), TEXT("M_CatBlack"));
    Box(TEXT("EarLeft"), FVector(1,-23,164), FVector(25,18,26), TEXT("M_CatBlack"));
    Box(TEXT("EarRight"), FVector(1,23,164), FVector(25,18,26), TEXT("M_CatOrange"));
    Box(TEXT("InnerEarLeft"), FVector(14,-23,166), FVector(2,10,14), TEXT("M_CatPink"));
    Box(TEXT("InnerEarRight"), FVector(14,23,166), FVector(2,10,14), TEXT("M_CatPink"));
    LeftLeg = CreateDefaultSubobject<USceneComponent>(TEXT("LeftLegPivot"));
    LeftLeg->SetupAttachment(CatRoot); LeftLeg->SetRelativeLocation(FVector(0,-13,52));
    RightLeg = CreateDefaultSubobject<USceneComponent>(TEXT("RightLegPivot"));
    RightLeg->SetupAttachment(CatRoot); RightLeg->SetRelativeLocation(FVector(0,13,52));
    Box(TEXT("LeftLeg"), FVector(0,0,-22), FVector(18,18,42), TEXT("M_CatOrange"), LeftLeg);
    Box(TEXT("LeftPaw"), FVector(5,0,-43), FVector(28,20,14), TEXT("M_CatCream"), LeftLeg);
    Box(TEXT("RightLeg"), FVector(0,0,-22), FVector(18,18,42), TEXT("M_CatBlack"), RightLeg);
    Box(TEXT("RightPaw"), FVector(5,0,-43), FVector(28,20,14), TEXT("M_CatCream"), RightLeg);
    LeftArm = CreateDefaultSubobject<USceneComponent>(TEXT("LeftArmPivot"));
    LeftArm->SetupAttachment(CatRoot); LeftArm->SetRelativeLocation(FVector(0,-30,96));
    RightArm = CreateDefaultSubobject<USceneComponent>(TEXT("RightArmPivot"));
    RightArm->SetupAttachment(CatRoot); RightArm->SetRelativeLocation(FVector(0,30,96));
    Box(TEXT("LeftArm"), FVector(0,0,-17), FVector(17,16,34), TEXT("M_CatCream"), LeftArm);
    Box(TEXT("RightArm"), FVector(0,0,-17), FVector(17,16,34), TEXT("M_CatOrange"), RightArm);
    Box(TEXT("RightHand"), FVector(0,0,-36), FVector(18,17,12), TEXT("M_CatCream"), RightArm);
    Tail = CreateDefaultSubobject<USceneComponent>(TEXT("TailPivot"));
    Tail->SetupAttachment(CatRoot); Tail->SetRelativeLocation(FVector(-20,0,59));
    Box(TEXT("TailBase"), FVector(-15,0,0), FVector(32,15,15), TEXT("M_CatOrange"), Tail);
    Box(TEXT("TailBlackBand"), FVector(-34,0,8), FVector(15,15,27), TEXT("M_CatBlack"), Tail);
    Box(TEXT("TailTip"), FVector(-34,0,29), FVector(15,15,17), TEXT("M_CatCream"), Tail);
    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("FixedCameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->SetUsingAbsoluteRotation(true);
    CameraBoom->SetRelativeRotation(FRotator(-58,0,0));
    CameraBoom->TargetArmLength = 2700;
    CameraBoom->bDoCollisionTest = false;
    CameraBoom->bEnableCameraLag = true;
    CameraBoom->CameraLagSpeed = 7;
    CameraBoom->bUsePawnControlRotation = false;
    TopDownCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("TopDownCamera"));
    TopDownCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    TopDownCamera->ProjectionMode = ECameraProjectionMode::Orthographic;
    TopDownCamera->OrthoWidth = 3000;
    TopDownCamera->bUsePawnControlRotation = false;
    TopDownCamera->bConstrainAspectRatio = false;
}

void AAstraCat::BeginPlay()
{
    Super::BeginPlay();
    SafeLocation = GetActorLocation();
}

void AAstraCat::Tick(float Dt)
{
    Super::Tick(Dt);
    const float Speed = GetVelocity().Size2D();
    Gait += Dt * FMath::Clamp(Speed / 24.f, 0.f, 15.f);
    const float Stride = FMath::Sin(Gait) * FMath::Clamp(Speed / 340.f, 0.f, 1.f) * 30.f;
    LeftLeg->SetRelativeRotation(FRotator(Stride,0,0));
    RightLeg->SetRelativeRotation(FRotator(-Stride,0,0));
    LeftArm->SetRelativeRotation(FRotator(-Stride*.7f,0,-7));
    RightArm->SetRelativeRotation(FRotator(Stride*.7f,0,7));
    Tail->SetRelativeRotation(FRotator(0,FMath::Sin(GetWorld()->GetTimeSeconds()*2.f)*12,0));
    CatRoot->SetRelativeLocation(FVector(0,0,-88 + FMath::Abs(FMath::Sin(Gait))*FMath::Min(Speed/100.f,3.f)));
    const FVector P = GetActorLocation();
    if (P.Z > 65 && FMath::Abs(P.X)<4980 && FMath::Abs(P.Y)<4980 && GetCharacterMovement()->IsMovingOnGround()) SafeLocation = P;
    if (P.Z < -180 || FMath::Abs(P.X)>4980 || FMath::Abs(P.Y)>4980)
    {
        SetActorLocation(SafeLocation); GetCharacterMovement()->StopMovementImmediately();
    }
}

AAstraController::AAstraController()
{
    bShowMouseCursor = false;
    bEnableClickEvents = false;
    bEnableMouseOverEvents = false;
}
void AAstraController::BeginPlay()
{
    Super::BeginPlay();
    SetInputMode(FInputModeGameOnly());
    bSmokeTest = FParse::Param(FCommandLine::Get(),TEXT("AstraSmokeTest"));
    bBridgeTest = FParse::Param(FCommandLine::Get(),TEXT("AstraBridgeTest"));
    bCampTest = FParse::Param(FCommandLine::Get(),TEXT("AstraCampTest"));
    FParse::Value(FCommandLine::Get(),TEXT("AstraReview="),ReviewCamera);
    if (!ReviewCamera.IsEmpty())
    {
        FParse::Value(FCommandLine::Get(),TEXT("AstraReviewCaptureSeconds="),ReviewCaptureTime);
        ReviewCaptureTime = FMath::Clamp(ReviewCaptureTime,13.f,120.f);
    }
}
void AAstraController::PlayerTick(float Dt)
{
    Super::PlayerTick(Dt);
    if (bSmokeTest || bBridgeTest || bCampTest || !ReviewCamera.IsEmpty()) TickValidation(Dt);
    if (APawn* P = GetPawn())
    {
        FVector Direction((IsInputKeyDown(EKeys::W)?1.f:0.f)-(IsInputKeyDown(EKeys::S)?1.f:0.f),
                          (IsInputKeyDown(EKeys::D)?1.f:0.f)-(IsInputKeyDown(EKeys::A)?1.f:0.f),0);
        if (!Direction.IsNearlyZero()) P->AddMovementInput(Direction.GetSafeNormal());
    }
}

void AAstraController::TickValidation(float Dt)
{
    ValidationTime += Dt;
    AAstraCat* Cat = Cast<AAstraCat>(GetPawn());
    if (!Cat) return;
    if (!bReviewSelected && ValidationTime>1)
    {
        bReviewSelected=true;
        TestCameraRotation=Cat->TopDownCamera->GetComponentRotation();
        if (!ReviewCamera.IsEmpty() && ReviewCamera!=TEXT("Gameplay"))
            for(TActorIterator<ACameraActor> It(GetWorld());It;++It)
                if(It->GetName().Contains(ReviewCamera)
#if WITH_EDITOR
                    || It->GetActorLabel()==TEXT("Camera_")+ReviewCamera
#endif
                ) { SetViewTarget(*It); break; }
    }
    if(bSmokeTest && TestStage<4)
    {
        const FKey Keys[]={EKeys::W,EKeys::A,EKeys::S,EKeys::D};
        const FVector Expected[]={FVector(1,0,0),FVector(0,-1,0),FVector(-1,0,0),FVector(0,1,0)};
        const float StartTime=3.f+TestStage*2.f;
        if(!bTestPressed && ValidationTime>=StartTime)
        {
            TestStart=Cat->GetActorLocation();
            InputKey(FInputKeyEventArgs::CreateSimulated(Keys[TestStage],IE_Pressed,1.f));
            bTestPressed=true;
        }
        if(bTestPressed && ValidationTime>=StartTime+1.15f)
        {
            InputKey(FInputKeyEventArgs::CreateSimulated(Keys[TestStage],IE_Released,0.f));
            const FVector Delta=Cat->GetActorLocation()-TestStart;
            const bool Correct=FVector::DotProduct(Delta,Expected[TestStage])>150.f;
            const bool FixedCamera=Cat->TopDownCamera->GetComponentRotation().Equals(TestCameraRotation,.05f);
            const bool Grounded=Cat->GetCharacterMovement()->IsMovingOnGround();
            const bool Pass=Correct && FixedCamera && Grounded;
            bTestsPassed &= Pass;
            TestResults.Add(FString::Printf(TEXT("{\"key\":\"%s\",\"pass\":%s,\"dx\":%.2f,\"dy\":%.2f,\"dz\":%.2f,\"fixed_camera\":%s,\"grounded\":%s}"),
                *Keys[TestStage].ToString(),Pass?TEXT("true"):TEXT("false"),Delta.X,Delta.Y,Delta.Z,FixedCamera?TEXT("true"):TEXT("false"),Grounded?TEXT("true"):TEXT("false")));
            UE_LOG(LogTemp,Display,TEXT("ASTRA INPUT %s: %s delta=%s camera_fixed=%d"),*Keys[TestStage].ToString(),Pass?TEXT("PASS"):TEXT("FAIL"),*Delta.ToString(),FixedCamera);
            ++TestStage;bTestPressed=false;
        }
    }
    if(bBridgeTest)
    {
        if(TestStage==0 && ValidationTime>1)
        {
            Cat->SetActorLocation(FVector(-700,UAstraSceneLibrary::StreamCenter(-700)-480,250));
            Cat->GetCharacterMovement()->StopMovementImmediately();
            TestStage=1;
        }
        if(TestStage==1 && ValidationTime>2)
        {
            TestStart=Cat->GetActorLocation();
            InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::D,IE_Pressed,1.f));
            TestStage=2;
        }
        if(TestStage==2 && FMath::Abs(Cat->GetActorLocation().Y-UAstraSceneLibrary::StreamCenter(-700))<80)
            bBridgeMidpointSupported |= Cat->GetActorLocation().Z>120 && Cat->GetCharacterMovement()->IsMovingOnGround();
        if(TestStage==2 && ValidationTime>5.7)
        {
            InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::D,IE_Released,0.f));
            const FVector Delta=Cat->GetActorLocation()-TestStart;
            bTestsPassed=Delta.Y>950 && bBridgeMidpointSupported && Cat->GetCharacterMovement()->IsMovingOnGround();
            const FString Result=FString::Printf(TEXT("{\"passed\":%s,\"travel_cm\":%.2f,\"supported_above_stream\":%s,\"final_z\":%.2f}"),bTestsPassed?TEXT("true"):TEXT("false"),Delta.Y,bBridgeMidpointSupported?TEXT("true"):TEXT("false"),Cat->GetActorLocation().Z);
            FFileHelper::SaveStringToFile(Result,*(FPaths::ProjectDir()/TEXT("ArtSource/Previews/UE_BridgeValidation.json")));
            UE_LOG(LogTemp,Display,TEXT("ASTRA BRIDGE %s"),*Result);
            TestStage=3;
        }
    }
    if(bCampTest)
    {
        if(TestStage==0 && ValidationTime>1)
        {
            FVector Start(3300,-2000,250);
            for(TActorIterator<ALandscape> It(GetWorld());It;++It)
                Start.Z=UAstraSceneLibrary::LandscapeHeightAt(*It,Start)+110;
            Cat->SetActorLocation(Start);Cat->GetCharacterMovement()->StopMovementImmediately();TestStage=1;
        }
        if(TestStage==1 && ValidationTime>2)
        {
            TestStart=Cat->GetActorLocation();InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::D,IE_Pressed,1.f));TestStage=2;
        }
        if(TestStage==2 && ValidationTime>6.6)
        {
            InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::D,IE_Released,0.f));
            const FVector Delta=Cat->GetActorLocation()-TestStart;
            bTestsPassed=Delta.Y>1100 && Delta.Z>250 && Cat->GetCharacterMovement()->IsMovingOnGround();
            const FString Result=FString::Printf(TEXT("{\"passed\":%s,\"travel_cm\":%.2f,\"climb_cm\":%.2f,\"grounded\":%s,\"final_z\":%.2f}"),bTestsPassed?TEXT("true"):TEXT("false"),Delta.Y,Delta.Z,Cat->GetCharacterMovement()->IsMovingOnGround()?TEXT("true"):TEXT("false"),Cat->GetActorLocation().Z);
            FFileHelper::SaveStringToFile(Result,*(FPaths::ProjectDir()/TEXT("ArtSource/Previews/UE_CampMovementValidation.json")));
            UE_LOG(LogTemp,Display,TEXT("ASTRA CAMP %s"),*Result);TestStage=3;
        }
    }
    if(!bCaptured && ValidationTime>ReviewCaptureTime)
    {
        bCaptured=true;
        const FString Name=ReviewCamera.IsEmpty()?TEXT("Gameplay"):ReviewCamera;
        const FString ImagePath=FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()/TEXT("ArtSource/Previews")/(TEXT("UE_")+Name+TEXT(".png")));
        FScreenshotRequest::RequestScreenshot(ImagePath,false,false);
        UE_LOG(LogTemp,Display,TEXT("ASTRA REVIEW capture %s at world %.3fs, validation %.3fs"),*Name,GetWorld()->GetTimeSeconds(),ValidationTime);
        if(bSmokeTest)
        {
            const FString Json=FString::Printf(TEXT("{\"passed\":%s,\"checks\":[%s],\"camera_pitch\":%.2f,\"camera_yaw\":%.2f,\"ortho_width\":%.2f}"),
                bTestsPassed && TestStage==4?TEXT("true"):TEXT("false"),*FString::Join(TestResults,TEXT(",")),TestCameraRotation.Pitch,TestCameraRotation.Yaw,Cat->TopDownCamera->OrthoWidth);
            FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectDir()/TEXT("ArtSource/Previews/UE_MovementValidation.json")));
        }
    }
    if(bCaptured && ValidationTime>ReviewCaptureTime+3.f) FPlatformMisc::RequestExitWithStatus(false,bTestsPassed?0:1);
}
AAstraGameMode::AAstraGameMode()
{
    DefaultPawnClass = AAstraCat::StaticClass();
    PlayerControllerClass = AAstraController::StaticClass();
}

float UAstraSceneLibrary::StreamCenter(float X)
{
    return .60f*X + 850.f + 190.f*FMath::Sin(X/680.f);
}
float UAstraSceneLibrary::TerrainHeight(float X, float Y)
{
    float H = 55.f + 26.f*FMath::Sin(X/760.f)*FMath::Cos(Y/920.f) + 14.f*FMath::Sin((X+Y)/360.f);
    const float Edge = FMath::Clamp((FMath::Max(FMath::Abs(X),FMath::Abs(Y))-3000.f)/2000.f,0.f,1.f);
    H += Edge*Edge*210.f;
    H += 110.f*FMath::Exp(-(FMath::Square((X-2400.f)/1400.f)+FMath::Square((Y+2800.f)/1250.f)));
    const float LakeR = FMath::Sqrt(FMath::Square((X-1900.f)/1510.f)+FMath::Square((Y-2070.f)/1240.f));
    const float LakeCut = 1.f-FMath::SmoothStep(.87f,1.19f,LakeR);
    H = FMath::Lerp(H,-135.f,LakeCut);
    if (X<1350.f)
    {
        const float Width = 158.f+24.f*FMath::Sin(X/430.f);
        const float Cut = (1.f-FMath::SmoothStep(Width*.70f,Width+140.f,FMath::Abs(Y-StreamCenter(X))))*(1.f-FMath::SmoothStep(850.f,1350.f,X));
        H = FMath::Lerp(H,-94.f,Cut);
    }
    return H;
}

AActor* UAstraSceneLibrary::CreateTerrain(UMaterialInterface* Material)
{
#if WITH_EDITOR
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World) return nullptr;
    FActorSpawnParameters Params; Params.ObjectFlags |= RF_Transactional;
    ALandscape* L = World->SpawnActor<ALandscape>(ALandscape::StaticClass(),FVector(-5040,-5040,0),FRotator::ZeroRotator,Params);
    L->SetActorScale3D(FVector(80,80,100));
    L->LandscapeMaterial = Material;
    // Use the exact unsigned 16-bit height field exported from the Blender layout.
    TArray<uint8> Raw;
    const FString HeightFile = FPaths::ProjectDir() / TEXT("ArtSource/Layout/landscape_height.r16");
    if (!FFileHelper::LoadFileToArray(Raw,*HeightFile) || Raw.Num()!=127*127*2)
    {
        UE_LOG(LogTemp,Error,TEXT("Missing or invalid Blender heightmap: %s"),*HeightFile);
        L->Destroy(); return nullptr;
    }
    TArray<uint16> Heights; Heights.SetNum(127*127);
    FMemory::Memcpy(Heights.GetData(),Raw.GetData(),Raw.Num());
    TMap<FGuid,TArray<uint16>> HeightLayers; HeightLayers.Add(FGuid(),MoveTemp(Heights));
    TMap<FGuid,TArray<FLandscapeImportLayerInfo>> MaterialLayers; MaterialLayers.Add(FGuid(),{});
    L->Import(FGuid::NewGuid(),0,0,126,126,1,63,HeightLayers,TEXT(""),MaterialLayers,ELandscapeImportAlphamapType::Additive,TArrayView<const FLandscapeLayer>());
    L->CreateLandscapeInfo();
    L->SetActorLabel(TEXT("Landscape_100m_Woodland"));
    L->PostEditChange();
    L->MarkPackageDirty();
    return L;
#else
    return nullptr;
#endif
}

bool UAstraSceneLibrary::UpdateTerrainHeights(AActor* Terrain)
{
#if WITH_EDITOR
    ALandscape* Landscape = Cast<ALandscape>(Terrain);
    if (!Landscape || !Landscape->GetLandscapeInfo()) return false;
    TArray<uint8> Raw;
    if (!FFileHelper::LoadFileToArray(Raw, *(FPaths::ProjectDir() / TEXT("ArtSource/Layout/landscape_height.r16"))) || Raw.Num() != 127 * 127 * 2)
        return false;
    int32 MinX, MinY, MaxX, MaxY;
    if (!Landscape->GetLandscapeInfo()->GetLandscapeExtent(MinX, MinY, MaxX, MaxY) || MinX != 0 || MinY != 0 || MaxX != 126 || MaxY != 126)
        return false;
    TArray<uint16> Heights;
    Heights.SetNumUninitialized(127 * 127);
    FMemory::Memcpy(Heights.GetData(), Raw.GetData(), Raw.Num());
    Landscape->Modify();
    const ULandscapeEditLayerBase* BaseLayer = Landscape->GetEditLayerConst(0);
    if (!BaseLayer) return false;
    FLandscapeEditDataInterface Edit(Landscape->GetLandscapeInfo(), BaseLayer->GetGuid());
    // Update the existing terrain and collision; preserve its actor and components.
    Edit.SetHeightData(0, 0, 126, 126, Heights.GetData(), 127, true);
    Edit.Flush();
    Landscape->RequestLayersContentUpdate(ELandscapeLayerUpdateMode::Update_Heightmap_All);
    Landscape->ForceUpdateLayersContent();
    Landscape->PostEditChange();
    Landscape->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

float UAstraSceneLibrary::LandscapeHeightAt(AActor* Terrain, FVector Location)
{
    ALandscape* Landscape = Cast<ALandscape>(Terrain);
    if (!Landscape) return -99999.f;
    return Landscape->GetHeightAtLocation(Location).Get(-99999.f);
}
