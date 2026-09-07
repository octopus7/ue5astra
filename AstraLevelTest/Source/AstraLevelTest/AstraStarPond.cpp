#include "AstraStarPond.h"
#include "AstraWorld.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/SkeletalMeshActor.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "InputKeyEventArgs.h"

AAstraStarPond::AAstraStarPond()
{
    PrimaryActorTick.bCanEverTick=true;
    SetActorHiddenInGame(true);
}

void AAstraStarPond::BeginPlay()
{
    Super::BeginPlay();
    if(WaterActor) WaterMaterial=WaterActor->GetStaticMeshComponent()->CreateDynamicMaterialInstance(0);
    bValidate=FParse::Param(FCommandLine::Get(),TEXT("AstraStarPondTest"));
    for(TActorIterator<ASkeletalMeshActor> It(GetWorld());It;++It)
        if(It->GetSkeletalMeshComponent()->GetSkeletalMeshAsset()
            && It->GetSkeletalMeshComponent()->GetSkeletalMeshAsset()->GetName().Contains(TEXT("UnicornElephant")))
            Guardian=It->GetSkeletalMeshComponent();
}

void AAstraStarPond::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(const APawn* Pawn=UGameplayStatics::GetPlayerPawn(this,0))
    {
        const float Distance=FVector::Dist2D(Pawn->GetActorLocation(),Observatory);
        const float T=FMath::Clamp((Distance-140.f)/230.f,0.f,1.f);
        const float Target=1.f-T*T*(3.f-2.f*T);
        Alignment=FMath::FInterpTo(Alignment,Target,DeltaSeconds,3.f);
        if(WaterMaterial) WaterMaterial->SetScalarParameterValue(TEXT("Alignment"),Alignment);
    }
    if(bValidate && !bFinished) Validate(DeltaSeconds);
}

void AAstraStarPond::Check(const FString& Name,bool Passed,const FString& Detail)
{
    if(!Passed) ++Failures;
    FString Safe=Detail;Safe.ReplaceInline(TEXT("\\"),TEXT("/"));Safe.ReplaceInline(TEXT("\""),TEXT("'"));
    Checks.Add(FString::Printf(TEXT("{\"name\":\"%s\",\"passed\":%s,\"detail\":\"%s\"}"),*Name,Passed?TEXT("true"):TEXT("false"),*Safe));
    UE_LOG(LogTemp,Display,TEXT("STAR POND TEST %s %s %s"),*Name,Passed?TEXT("PASS"):TEXT("FAIL"),*Safe);
}

void AAstraStarPond::Validate(float DeltaSeconds)
{
    Elapsed+=DeltaSeconds;
    AAstraController* PC=Cast<AAstraController>(UGameplayStatics::GetPlayerController(this,0));
    AAstraCat* Cat=PC?Cast<AAstraCat>(PC->GetPawn()):nullptr;
    if(Elapsed>45.f){Check(TEXT("timeout"),false);FinishValidation();return;}
    if(!Cat) return;
    auto* Movement=Cat->GetCharacterMovement();
    const FKey Keys[]={EKeys::W,EKeys::D,EKeys::S,EKeys::A};
    const auto Input=[PC](FKey Key,bool Down){PC->InputKey(FInputKeyEventArgs::CreateSimulated(Key,Down?IE_Pressed:IE_Released,Down?1.f:0.f));};
    const auto Enter=[this](int32 Stage){TestStage=Stage;StageStart=Elapsed;};
    if(Guardian && InitialBones.Num())
    {
        for(const auto& Pair:InitialBones)
        {
            const FTransform Current=Guardian->GetSocketTransform(Pair.Key,RTS_Component);
            const float Distance=FVector::Distance(Current.GetLocation(),Pair.Value.GetLocation());
            if(Pair.Key.ToString().Contains(TEXT("foot"),ESearchCase::IgnoreCase)) MaxFootDrift=FMath::Max(MaxFootDrift,Distance);
            else MaxMovingBoneDelta=FMath::Max(MaxMovingBoneDelta,Distance+FMath::RadiansToDegrees(Current.GetRotation().AngularDistance(Pair.Value.GetRotation())));
        }
    }
    const float Age=Elapsed-StageStart;
    if(TestStage==0)
    {
        if(Elapsed<2.f || !Movement->IsMovingOnGround()) return;
        Check(TEXT("spawn_grounded"),true);
        Check(TEXT("water_dynamic_material"),WaterMaterial!=nullptr);
        Check(TEXT("guardian_skeletal_mesh"),Guardian && Guardian->GetNumBones()>=10);
        if(Guardian)
        {
            GuardianStart=Guardian->GetComponentLocation();
            TArray<FName> Names;Guardian->GetBoneNames(Names);
            for(FName Name:Names) InitialBones.Add(Name,Guardian->GetSocketTransform(Name,RTS_Component));
            const auto* Anim=Guardian->GetSingleNodeInstance();
            Check(TEXT("guardian_looping_idle"),Anim && Anim->IsPlaying() && Anim->IsLooping());
        }
        Cat->SetActorLocation(FVector(-2600,0,240));Movement->StopMovementImmediately();Enter(1);return;
    }
    if(TestStage>=1 && TestStage<=8)
    {
        const int32 Index=(TestStage-1)/2;
        if(TestStage%2==1)
        {
            if(Age<.6f || !Movement->IsMovingOnGround())return;
            MovementStart=Cat->GetActorLocation();Input(Keys[Index],true);Enter(TestStage+1);
        }
        else if(Age>.55f)
        {
            Input(Keys[Index],false);
            const float Travel=FVector::Dist2D(MovementStart,Cat->GetActorLocation());
            Check(TEXT("WASD_")+Keys[Index].ToString(),Travel>60.f && Movement->IsMovingOnGround(),FString::Printf(TEXT("travel_cm=%.2f"),Travel));
            Cat->SetActorLocation(FVector(-2600,0,240));Movement->StopMovementImmediately();Enter(TestStage+1);
        }
        return;
    }
    if(TestStage==9){Cat->SetActorLocation(FVector(-1600,0,248));Movement->StopMovementImmediately();Enter(10);return;}
    if(TestStage==10 && Age>1.6f)
    {
        Check(TEXT("constellation_reveals_at_dais"),Alignment>.98f && Movement->IsMovingOnGround(),FString::Printf(TEXT("alignment=%.4f"),Alignment));
        Cat->SetActorLocation(FVector(-2500,0,240));Movement->StopMovementImmediately();Enter(11);return;
    }
    if(TestStage==11 && Age>1.6f)
    {
        Check(TEXT("constellation_fades_away"),Alignment<.02f,FString::Printf(TEXT("alignment=%.4f"),Alignment));
        Cat->SetActorLocation(FVector(-1580,0,248));Movement->StopMovementImmediately();Enter(12);return;
    }
    if(TestStage==12 && Age>.7f){Input(EKeys::W,true);Enter(13);return;}
    if(TestStage==13 && Age>3.f)
    {
        Input(EKeys::W,false);
        const FVector P=Cat->GetActorLocation();
        Check(TEXT("pond_edge_blocks_deep_water"),P.X<-1080.f && P.X>-1500.f && Movement->IsMovingOnGround(),P.ToString());
        Enter(14);return;
    }
    if(TestStage==14 && Age>1.f)
    {
        Check(TEXT("guardian_real_bones_animate"),MaxMovingBoneDelta>.5f,FString::Printf(TEXT("max_bone_delta=%.4f"),MaxMovingBoneDelta));
        Check(TEXT("guardian_feet_planted"),MaxFootDrift<.2f,FString::Printf(TEXT("max_foot_drift_cm=%.5f"),MaxFootDrift));
        Check(TEXT("guardian_root_in_place"),Guardian && FVector::Distance(Guardian->GetComponentLocation(),GuardianStart)<.01f);
        FinishValidation();
    }
}

void AAstraStarPond::FinishValidation()
{
    bFinished=true;
    const FString File=FPaths::ProjectDir()/TEXT("ArtSource/Previews/UE_StarPondRuntimeValidation.json");
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(File),true);
    const FString Json=FString::Printf(TEXT("{\"passed\":%s,\"world_seconds\":%.4f,\"checks\":[%s]}"),Failures?TEXT("false"):TEXT("true"),Elapsed,*FString::Join(Checks,TEXT(",")));
    FFileHelper::SaveStringToFile(Json,*File);
    FPlatformMisc::RequestExitWithStatus(false,Failures?1:0);
}
