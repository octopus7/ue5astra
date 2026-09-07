#include "AstraRootBelltower.h"
#include "AstraWorld.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "InputKeyEventArgs.h"

AAstraRootBelltower::AAstraRootBelltower()
{
    PrimaryActorTick.bCanEverTick=true;
    SetActorHiddenInGame(true);
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    ChimeAudio=CreateDefaultSubobject<UAudioComponent>(TEXT("BellChime"));
    ChimeAudio->SetupAttachment(GetRootComponent());
    ChimeAudio->bAutoActivate=false;
    ChimeAudio->bOverrideAttenuation=true;
    ChimeAudio->AttenuationOverrides.bAttenuate=true;
    ChimeAudio->AttenuationOverrides.bSpatialize=true;
    ChimeAudio->AttenuationOverrides.AttenuationShapeExtents=FVector(700.f);
    ChimeAudio->AttenuationOverrides.FalloffDistance=2200.f;
    ChimeAudio->SetVolumeMultiplier(.42f);
}

void AAstraRootBelltower::BeginPlay()
{
    Super::BeginPlay();
    bValidate=FParse::Param(FCommandLine::Get(),TEXT("AstraRootBelltowerTest"));
    if(BellActor){BellRest=BellActor->GetActorTransform();ChimeAudio->SetWorldLocation(BellRest.GetLocation());}
    ChimeAudio->SetSound(ChimeSound);
    for(AStaticMeshActor* Actor:RootActors)
    {
        if(!Actor)continue;
        UStaticMeshComponent* Component=Actor->GetStaticMeshComponent();
        for(int32 Index=0;Index<Component->GetNumMaterials();++Index)
        {
            UMaterialInterface* Material=Component->GetMaterial(Index);
            if(Material && Material->GetName()==TEXT("M_RB_SapGlow"))
            {
                if(!RootGlow)RootGlow=UMaterialInstanceDynamic::Create(Material,this);
                Component->SetMaterial(Index,RootGlow);
            }
        }
    }
}

void AAstraRootBelltower::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if(bConfiguredCamera)
        if(APlayerController* PC=UGameplayStatics::GetPlayerController(this,0))
            PC->ClearAudioListenerAttenuationOverride();
    Super::EndPlay(EndPlayReason);
}

void AAstraRootBelltower::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);Elapsed+=DeltaSeconds;
    if(AAstraCat* Cat=Cast<AAstraCat>(UGameplayStatics::GetPlayerPawn(this,0)))
    {
        if(!bConfiguredCamera)
        {
            Cat->TopDownCamera->SetOrthoWidth(3200.f);
            Cat->CameraBoom->TargetOffset=FVector(400,0,250);
            // Attenuate at the cat; the elevated camera and its lag must not silence a nearby bell.
            if(APlayerController* PC=UGameplayStatics::GetPlayerController(this,0))
                PC->SetAudioListenerAttenuationOverride(Cat->GetRootComponent(),FVector::ZeroVector);
            bConfiguredCamera=true;
        }
        const float Distance=FVector::Dist2D(Cat->GetActorLocation(),ResonanceCenter);
        const float T=FMath::Clamp((Distance-280.f)/370.f,0.f,1.f);
        Resonance=FMath::FInterpTo(Resonance,1.f-T*T*(3.f-2.f*T),DeltaSeconds,4.f);
        const bool bNear=Distance<280.f;
        if(bNear && !bWasNear && Elapsed-LastChime>8.f && ChimeSound)
        {
            ChimeAudio->Play();LastChime=Elapsed;++ChimeCount;
            UE_LOG(LogTemp,Display,TEXT("ROOT BELLTOWER chime %d at %.3f seconds"),ChimeCount,Elapsed);
        }
        bWasNear=bNear;
    }
    if(RootGlow)RootGlow->SetScalarParameterValue(TEXT("Resonance"),Resonance);
    if(BellActor)
    {
        const float Swing=FMath::Sin(Elapsed*1.35f)*(1.25f+Resonance*3.f);
        BellActor->SetActorRotation(BellRest.GetRotation()*FQuat(FVector::RightVector,FMath::DegreesToRadians(Swing)));
        MaxSwing=FMath::Max(MaxSwing,FMath::Abs(Swing));
        MaxPivotDrift=FMath::Max(MaxPivotDrift,float(FVector::Distance(BellRest.GetLocation(),BellActor->GetActorLocation())));
    }
    if(bValidate && !bFinished)Validate(DeltaSeconds);
}

void AAstraRootBelltower::Check(const FString& Name,bool Passed,const FString& Detail)
{
    if(!Passed)++Failures;
    Checks.Add(FString::Printf(TEXT("{\"name\":\"%s\",\"passed\":%s,\"detail\":\"%s\"}"),*Name,Passed?TEXT("true"):TEXT("false"),*Detail));
    UE_LOG(LogTemp,Display,TEXT("ROOT BELLTOWER TEST %s %s %s"),*Name,Passed?TEXT("PASS"):TEXT("FAIL"),*Detail);
}

void AAstraRootBelltower::Validate(float DeltaSeconds)
{
    AAstraController* PC=Cast<AAstraController>(UGameplayStatics::GetPlayerController(this,0));
    AAstraCat* Cat=PC?Cast<AAstraCat>(PC->GetPawn()):nullptr;
    if(Elapsed>50.f){Check(TEXT("timeout"),false);FinishValidation();return;}
    if(!Cat)return;
    UCharacterMovementComponent* Movement=Cat->GetCharacterMovement();
    const FKey Keys[]={EKeys::W,EKeys::D,EKeys::S,EKeys::A};
    const auto Input=[PC](FKey Key,bool Down){PC->InputKey(FInputKeyEventArgs::CreateSimulated(Key,Down?IE_Pressed:IE_Released,Down?1.f:0.f));};
    const auto Enter=[this](int32 Stage){TestStage=Stage;StageStart=Elapsed;};
    const auto Place=[Cat,Movement](FVector Location){Cat->SetActorLocation(Location);Movement->StopMovementImmediately();};
    const float Age=Elapsed-StageStart;
    if(TestStage==0)
    {
        if(Elapsed<2.f || !Movement->IsMovingOnGround())return;
        Check(TEXT("spawn_grounded"),true);
        Check(TEXT("root_glow_material"),RootGlow!=nullptr);
        Check(TEXT("bell_asset_and_original_chime"),BellActor && ChimeSound && ChimeSound->GetDuration()>4.9f);
        Place(FVector(-2600,-200,280));Enter(1);return;
    }
    if(TestStage>=1 && TestStage<=8)
    {
        const int32 Index=(TestStage-1)/2;
        if(TestStage%2==1)
        {
            if(Age<.55f || !Movement->IsMovingOnGround())return;
            MovementStart=Cat->GetActorLocation();Input(Keys[Index],true);Enter(TestStage+1);
        }
        else if(Age>.6f)
        {
            Input(Keys[Index],false);
            const float Travel=FVector::Dist2D(MovementStart,Cat->GetActorLocation());
            Check(TEXT("WASD_")+Keys[Index].ToString(),Travel>80 && Movement->IsMovingOnGround(),FString::Printf(TEXT("travel_cm=%.2f"),Travel));
            Place(FVector(-2600,-200,280));Enter(TestStage+1);
        }
        return;
    }
    if(TestStage==9){Place(FVector(-600,0,290));Enter(10);return;}
    if(TestStage==10 && Age>1.4f)
    {
        Check(TEXT("courtyard_resonance"),Resonance>.98f && Movement->IsMovingOnGround(),FString::Printf(TEXT("resonance=%.4f"),Resonance));
        Check(TEXT("chime_plays_on_approach"),ChimeCount==1 && ChimeAudio->IsPlaying(),FString::Printf(TEXT("count=%d playing=%d"),ChimeCount,ChimeAudio->IsPlaying()?1:0));
        Place(FVector(-2600,-200,280));Enter(11);return;
    }
    if(TestStage==11 && Age>1.5f)
    {
        Check(TEXT("resonance_fades_away"),Resonance<.02f,FString::Printf(TEXT("resonance=%.4f"),Resonance));
        Place(FVector(-800,-1400,280));Enter(12);return;
    }
    if(TestStage==12 && Age>.6f && Movement->IsMovingOnGround())
    {MovementStart=Cat->GetActorLocation();Input(EKeys::W,true);Enter(13);return;}
    if(TestStage==13 && Age>4.6f)
    {
        Input(EKeys::W,false);const FVector P=Cat->GetActorLocation();
        Check(TEXT("walk_through_root_arch"),P.X>350.f && FMath::Abs(P.Y+1400.f)<50.f && Movement->IsMovingOnGround(),P.ToString());
        Place(FVector(-300,0,280));Enter(14);return;
    }
    if(TestStage==14 && Age>.6f && Movement->IsMovingOnGround()){Input(EKeys::W,true);Enter(15);return;}
    if(TestStage==15 && Age>3.2f)
    {
        Input(EKeys::W,false);const FVector P=Cat->GetActorLocation();
        Check(TEXT("tower_wall_blocks_player"),P.X>0 && P.X<400 && Movement->IsMovingOnGround(),P.ToString());
        Check(TEXT("bell_sways"),MaxSwing>1.f,FString::Printf(TEXT("max_swing_degrees=%.3f"),MaxSwing));
        Check(TEXT("bell_pivot_fixed"),MaxPivotDrift<.01f,FString::Printf(TEXT("max_drift_cm=%.5f"),MaxPivotDrift));
        FinishValidation();
    }
}

void AAstraRootBelltower::FinishValidation()
{
    bFinished=true;
    const FString File=FPaths::ProjectDir()/TEXT("ArtSource/Previews/UE_RootBelltowerRuntimeValidation.json");
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(File),true);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("{\"passed\":%s,\"world_seconds\":%.4f,\"checks\":[%s]}"),Failures?TEXT("false"):TEXT("true"),Elapsed,*FString::Join(Checks,TEXT(","))),*File);
    FPlatformMisc::RequestExitWithStatus(false,Failures?1:0);
}
