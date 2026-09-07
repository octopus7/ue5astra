#include "AstraNiagaraLibrary.h"
#include "Editor.h"
#include "LevelEditorViewport.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Dom/JsonObject.h"
#include "Engine/StaticMesh.h"
#include "JsonObjectConverter.h"
#include "Materials/MaterialInterface.h"
#include "Misc/PackageName.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraMeshRendererProperties.h"
#include "NiagaraSpriteRendererProperties.h"
#include "NiagaraSystem.h"
#include "NiagaraSystemEmitterState.h"
#include "Serialization/JsonSerializer.h"
#include "Stateless/NiagaraStatelessEmitter.h"
#include "Stateless/Modules/NiagaraStatelessModule_AddVelocity.h"
#include "Stateless/Modules/NiagaraStatelessModule_Drag.h"
#include "Stateless/Modules/NiagaraStatelessModule_GravityForce.h"
#include "Stateless/Modules/NiagaraStatelessModule_InitialMeshOrientation.h"
#include "Stateless/Modules/NiagaraStatelessModule_InitializeParticle.h"
#include "Stateless/Modules/NiagaraStatelessModule_MeshRotationRate.h"
#include "Stateless/Modules/NiagaraStatelessModule_ScaleColor.h"
#include "Stateless/Modules/NiagaraStatelessModule_ScaleSpriteSize.h"
#include "Stateless/Modules/NiagaraStatelessModule_ShapeLocation.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

DEFINE_LOG_CATEGORY_STATIC(LogAstraNiagara, Log, All);

void UAstraNiagaraLibrary::EnableViewportRealtime()
{
    if (GEditor)
    {
        for (FLevelEditorViewportClient* Client : GEditor->GetLevelViewportClients())
        {
            if (Client) { Client->SetRealtime(true); }
        }
    }
}

namespace AstraNiagara
{
    constexpr const TCHAR* TemplatePath = TEXT("/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight");
    const FBox EffectBounds(FVector(-49.0), FVector(49.0));

    template<typename T>
    T* GetModule(UNiagaraStatelessEmitter* Emitter)
    {
        T* Module = Cast<T>(Emitter->GetModule(T::StaticClass()));
        if (Module) { Module->SetIsModuleEnabled(true); }
        return Module;
    }

    template<typename T>
    T* StructProperty(UObject* Object, FName Name)
    {
        FStructProperty* Property = FindFProperty<FStructProperty>(Object->GetClass(), Name);
        return Property ? Property->ContainerPtrToValuePtr<T>(Object) : nullptr;
    }

    void VectorRange(FNiagaraDistributionRangeVector3& Distribution, const FVector3f& Min, const FVector3f& Max)
    {
        Distribution.Mode = ENiagaraDistributionMode::NonUniformRange;
        Distribution.Min = Min;
        Distribution.Max = Max;
        Distribution.ChannelConstantsAndRanges = { Min.X, Min.Y, Min.Z, Max.X, Max.Y, Max.Z };
        Distribution.ChannelCurves.Reset();
    }

    void SpriteRange(FNiagaraDistributionRangeVector2& Distribution, float Min, float Max)
    {
        Distribution.Mode = ENiagaraDistributionMode::UniformRange;
        Distribution.Min = FVector2f(Min);
        Distribution.Max = FVector2f(Max);
        Distribution.ChannelConstantsAndRanges = { Min, Max };
        Distribution.ChannelCurves.Reset();
    }

    void AddKey(FRichCurve& Curve, float Time, float Value)
    {
        const FKeyHandle Key = Curve.AddKey(Time, Value);
        Curve.SetKeyInterpMode(Key, RCIM_Linear);
    }

    void ColorCurve(FNiagaraDistributionColor& Distribution, float FadeIn, float HoldUntil)
    {
        Distribution.Mode = ENiagaraDistributionMode::NonUniformCurve;
        Distribution.LookupValueMode = uint8(ENiagaraDistributionLookupValueMode::ParticlesNormalizedAge);
        Distribution.ChannelCurves.SetNum(4);
        for (FRichCurve& Curve : Distribution.ChannelCurves) { Curve.Reset(); }
        for (int32 Channel = 0; Channel < 3; ++Channel)
        {
            AddKey(Distribution.ChannelCurves[Channel], 0.0f, 1.0f);
            AddKey(Distribution.ChannelCurves[Channel], 1.0f, 1.0f);
        }
        FRichCurve& Alpha = Distribution.ChannelCurves[3];
        AddKey(Alpha, 0.0f, FadeIn > 0.0f ? 0.0f : 1.0f);
        if (FadeIn > 0.0f) { AddKey(Alpha, FadeIn, 1.0f); }
        AddKey(Alpha, HoldUntil, 1.0f);
        AddKey(Alpha, 1.0f, 0.0f);
        Distribution.UpdateValuesFromDistribution();
    }

    void SizeCurve(FNiagaraDistributionVector2& Distribution, float Start, float Peak, float End)
    {
        Distribution.Mode = ENiagaraDistributionMode::UniformCurve;
        Distribution.LookupValueMode = uint8(ENiagaraDistributionLookupValueMode::ParticlesNormalizedAge);
        Distribution.ChannelCurves.SetNum(1);
        Distribution.ChannelCurves[0].Reset();
        AddKey(Distribution.ChannelCurves[0], 0.0f, Start);
        AddKey(Distribution.ChannelCurves[0], 0.35f, Peak);
        AddKey(Distribution.ChannelCurves[0], 1.0f, End);
        Distribution.UpdateValuesFromDistribution();
    }

    bool ConfigureEmitter(UNiagaraStatelessEmitter* Emitter, int32 Index, UMaterialInterface* Material, bool bLooping)
    {
        Emitter->Modify();
        for (UNiagaraStatelessModule* Module : Emitter->GetModules())
        {
            if (Module && Module->CanDisableModule()) { Module->SetIsModuleEnabled(false); }
        }
        auto* Initialize = GetModule<UNiagaraStatelessModule_InitializeParticle>(Emitter);
        auto* Velocity = GetModule<UNiagaraStatelessModule_AddVelocity>(Emitter);
        auto* Shape = GetModule<UNiagaraStatelessModule_ShapeLocation>(Emitter);
        auto* Color = GetModule<UNiagaraStatelessModule_ScaleColor>(Emitter);
        auto* Size = GetModule<UNiagaraStatelessModule_ScaleSpriteSize>(Emitter);
        auto* State = StructProperty<FNiagaraEmitterStateData>(Emitter, TEXT("EmitterState"));
        auto* Bounds = StructProperty<FBox>(Emitter, TEXT("FixedBounds"));
        if (!Initialize || !Velocity || !Shape || !Color || !Size || !State || !Bounds)
        {
            UE_LOG(LogAstraNiagara, Error, TEXT("FountainLightweight is missing required modules/properties"));
            return false;
        }
        *Bounds = EffectBounds;
        *State = FNiagaraEmitterStateData();
        State->LoopBehavior = bLooping ? ENiagaraLoopBehavior::Infinite : ENiagaraLoopBehavior::Once;
        State->LoopDurationMode = ENiagaraLoopDurationMode::Fixed;
        State->LoopDuration.InitConstant(2.0f);
        State->InactiveResponse = ENiagaraEmitterInactiveResponse::Complete;

        while (Emitter->GetNumSpawnInfos() > 0)
        {
            FGuid SourceId = Emitter->GetSpawnInfoByIndex(0)->SourceId;
            Emitter->RemoveSpawnInfoBySourceId(SourceId);
        }
        const int32 Counts[] = { 14, 9, 11, 2 };
        const float StartTimes[] = { 0.0f, 0.0f, 0.045f, 0.0f };
        FNiagaraStatelessSpawnInfo& Spawn = Emitter->AddSpawnInfo();
        Spawn.Type = ENiagaraStatelessSpawnInfoType::Burst;
        Spawn.SpawnTime = StartTimes[Index];
        Spawn.Amount.InitConstant(Counts[Index]);
        Spawn.bEnabled = true;
        Spawn.bLoopCountLimitEnabled = false;
        Spawn.bSpawnProbabilityEnabled = false;

        Initialize->MassDistribution.InitConstant(1.0f);
        Initialize->InitialPositionDistribution.InitConstant(FVector3f::ZeroVector);
        Initialize->SpriteRotationDistribution.InitRange(0.0f, 360.0f);
        Velocity->VelocityType = ENSM_VelocityType::Linear;
        Velocity->CoordinateSpace = ENiagaraCoordinateSpace::Local;
        Velocity->LinearVelocityScale.InitConstant(1.0f);
        Shape->ShapePrimitive = ENSM_ShapePrimitive::Sphere;
        Shape->SphereRadius.InitConstant(Index == 3 ? 1.0f : 5.0f);
        Shape->ShapeScale.InitConstant(FVector3f(1.0f));
        Shape->CoordinateSpace = ENiagaraCoordinateSpace::Local;

        if (Index == 0)
        {
            Initialize->LifetimeDistribution.InitRange(0.38f, 0.48f);
            Initialize->ColorDistribution.InitConstant(FLinearColor(0.35f, 0.30f, 0.24f, 1.0f));
            VectorRange(Initialize->MeshScaleDistribution, FVector3f(0.014f, 0.018f, 0.012f), FVector3f(0.033f, 0.028f, 0.025f));
            VectorRange(Velocity->LinearVelocityDistribution, FVector3f(-45.0f, -45.0f, 110.0f), FVector3f(45.0f, 45.0f, 160.0f));
            auto* Gravity = GetModule<UNiagaraStatelessModule_GravityForce>(Emitter);
            auto* Orientation = GetModule<UNiagaraStatelessModule_InitialMeshOrientation>(Emitter);
            auto* Rotation = GetModule<UNiagaraStatelessModule_MeshRotationRate>(Emitter);
            if (!Gravity || !Orientation || !Rotation) { return false; }
            Gravity->GravityDistribution.InitConstant(FVector3f(0.0f, 0.0f, -700.0f));
            Orientation->MeshOrientationMode = ENSMInitialMeshOrientationMode::Random;
            Rotation->bUseRateScale = false;
            VectorRange(Rotation->RotationRateDistribution, FVector3f(-300.0f), FVector3f(300.0f));
            ColorCurve(Color->ScaleDistribution, 0.0f, 0.65f);
            Size->SetIsModuleEnabled(false);
        }
        else if (Index == 1)
        {
            Initialize->LifetimeDistribution.InitRange(0.16f, 0.28f);
            Initialize->ColorDistribution.InitConstant(FLinearColor(4.5f, 1.15f, 0.12f, 1.0f));
            SpriteRange(Initialize->SpriteSizeDistribution, 13.0f, 22.0f);
            VectorRange(Velocity->LinearVelocityDistribution, FVector3f(-23.0f, -23.0f, 5.0f), FVector3f(23.0f, 23.0f, 35.0f));
            ColorCurve(Color->ScaleDistribution, 0.0f, 0.12f);
            SizeCurve(Size->ScaleDistribution, 0.45f, 1.25f, 0.55f);
        }
        else if (Index == 2)
        {
            Initialize->LifetimeDistribution.InitRange(0.75f, 1.05f);
            Initialize->ColorDistribution.InitConstant(FLinearColor(0.11f, 0.10f, 0.09f, 0.68f));
            SpriteRange(Initialize->SpriteSizeDistribution, 18.0f, 28.0f);
            VectorRange(Velocity->LinearVelocityDistribution, FVector3f(-10.0f, -10.0f, 10.0f), FVector3f(10.0f, 10.0f, 18.0f));
            auto* Drag = GetModule<UNiagaraStatelessModule_Drag>(Emitter);
            if (Drag) { Drag->DragDistribution.InitConstant(0.75f); }
            ColorCurve(Color->ScaleDistribution, 0.12f, 0.30f);
            SizeCurve(Size->ScaleDistribution, 0.50f, 1.10f, 1.45f);
        }
        else
        {
            Initialize->LifetimeDistribution.InitRange(0.20f, 0.32f);
            Initialize->ColorDistribution.InitConstant(FLinearColor::White);
            SpriteRange(Initialize->SpriteSizeDistribution, 30.0f, 40.0f);
            Velocity->LinearVelocityDistribution.InitConstant(FVector3f(0.0f, 0.0f, 3.0f));
            ColorCurve(Color->ScaleDistribution, 0.0f, 0.05f);
            SizeCurve(Size->ScaleDistribution, 0.40f, 1.00f, 1.15f);
        }

        const TArray<UNiagaraRendererProperties*> PreviousRenderers = Emitter->GetRenderers();
        for (UNiagaraRendererProperties* Renderer : PreviousRenderers) { Emitter->RemoveRenderer(Renderer, FGuid()); }
        if (Index == 0)
        {
            auto* Renderer = NewObject<UNiagaraMeshRendererProperties>(Emitter, NAME_None, RF_Transactional);
            Renderer->Meshes.SetNum(1);
            Renderer->Meshes[0].Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
            if (!Renderer->Meshes[0].Mesh) { return false; }
            Renderer->FacingMode = ENiagaraMeshFacingMode::Default;
            Renderer->bOverrideMaterials = true;
            Renderer->OverrideMaterials.SetNum(1);
            Renderer->OverrideMaterials[0].ExplicitMat = Material;
            Emitter->AddRenderer(Renderer, FGuid());
        }
        else
        {
            auto* Renderer = NewObject<UNiagaraSpriteRendererProperties>(Emitter, NAME_None, RF_Transactional);
            Renderer->Material = Material;
            Emitter->AddRenderer(Renderer, FGuid());
        }
        Emitter->PostEditChange();
        return true;
    }
}

UNiagaraSystem* UAstraNiagaraLibrary::CreateSmallDestruction(const FString& SystemPath,
    const TArray<UMaterialInterface*>& Materials, bool bLooping)
{
    if (Materials.Num() != 4 || Materials.Contains(nullptr))
    {
        UE_LOG(LogAstraNiagara, Error, TEXT("Exactly four valid materials required: debris, flame, smoke, distortion"));
        return nullptr;
    }
    FString PackageName = FPackageName::ObjectPathToPackageName(SystemPath);
    if (!PackageName.StartsWith(TEXT("/Game/")) || !FPackageName::IsValidLongPackageName(PackageName))
    {
        UE_LOG(LogAstraNiagara, Error, TEXT("SystemPath must be a valid /Game/ package path"));
        return nullptr;
    }
    UNiagaraSystem* Template = LoadObject<UNiagaraSystem>(nullptr, AstraNiagara::TemplatePath);
    if (!Template || Template->GetEmitterHandles().IsEmpty() || !Template->GetEmitterHandle(0).GetStatelessEmitter())
    {
        UE_LOG(LogAstraNiagara, Error, TEXT("FountainLightweight template not available"));
        return nullptr;
    }
    const FString AssetName = FPackageName::GetLongPackageAssetName(PackageName);
    const FString ObjectPath = PackageName + TEXT(".") + AssetName;
    UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *ObjectPath, nullptr, LOAD_NoWarn);
    if (!System)
    {
        UPackage* Package = CreatePackage(*PackageName);
        System = DuplicateObject<UNiagaraSystem>(Template, Package, *AssetName);
        if (!System) { return nullptr; }
        System->SetFlags(RF_Public | RF_Standalone | RF_Transactional);
        FAssetRegistryModule::AssetCreated(System);
    }
    System->Modify();
    const TArray<FNiagaraEmitterHandle> OldHandles = System->GetEmitterHandles();
    for (const FNiagaraEmitterHandle& Handle : OldHandles) { System->RemoveEmitterHandle(Handle); }
    const FNiagaraEmitterHandle SourceHandle = Template->GetEmitterHandle(0);
    const TCHAR* Names[] = { TEXT("Debris"), TEXT("Flame"), TEXT("Smoke"), TEXT("Distortion") };
    for (int32 Index = 0; Index < 4; ++Index)
    {
        System->DuplicateEmitterHandle(SourceHandle, FName(Names[Index]));
        FNiagaraEmitterHandle& Handle = System->GetEmitterHandles().Last();
        Handle.SetName(FName(Names[Index]), *System);
        Handle.SetIsEnabled(true, *System, false);
        if (!AstraNiagara::ConfigureEmitter(Handle.GetStatelessEmitter(), Index, Materials[Index], bLooping)) { return nullptr; }
    }
    System->bFixedBounds = true;
    System->SetFixedBounds(AstraNiagara::EffectBounds);
    System->PostEditChange();
    System->RequestCompile(true);
    System->WaitForCompilationComplete(true, false);
    System->MarkPackageDirty();
    return System;
}

FString UAstraNiagaraLibrary::DescribeSystem(UNiagaraSystem* System)
{
    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    if (!System) { Root->SetStringField(TEXT("error"), TEXT("null system")); }
    else
    {
        Root->SetStringField(TEXT("asset"), System->GetPathName());
        Root->SetBoolField(TEXT("ready_to_run"), System->IsReadyToRun());
        Root->SetBoolField(TEXT("valid"), System->IsValid());
        Root->SetBoolField(TEXT("fixed_bounds_enabled"), System->bFixedBounds);
        Root->SetStringField(TEXT("bounds_cm"), System->GetFixedBounds().ToString());
        TArray<TSharedPtr<FJsonValue>> Emitters;
        for (const FNiagaraEmitterHandle& Handle : System->GetEmitterHandles())
        {
            TSharedRef<FJsonObject> Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Handle.GetName().ToString());
            Item->SetBoolField(TEXT("enabled"), Handle.GetIsEnabled());
            if (UNiagaraStatelessEmitter* Emitter = Handle.GetStatelessEmitter())
            {
                Item->SetStringField(TEXT("mode"), TEXT("Stateless"));
                if (const FBox* Bounds = AstraNiagara::StructProperty<FBox>(Emitter, TEXT("FixedBounds"))) { Item->SetStringField(TEXT("bounds_cm"), Bounds->ToString()); }
                if (const auto* State = AstraNiagara::StructProperty<FNiagaraEmitterStateData>(Emitter, TEXT("EmitterState")))
                {
                    Item->SetStringField(TEXT("loop_behavior"), State->LoopBehavior == ENiagaraLoopBehavior::Once ? TEXT("Once") : TEXT("Infinite"));
                    Item->SetNumberField(TEXT("loop_duration_seconds"), State->LoopDuration.Min);
                }
                TArray<TSharedPtr<FJsonValue>> Bursts;
                for (int32 Index = 0; Index < Emitter->GetNumSpawnInfos(); ++Index)
                {
                    const FNiagaraStatelessSpawnInfo* Spawn = Emitter->GetSpawnInfoByIndex(Index);
                    TSharedRef<FJsonObject> Burst = MakeShared<FJsonObject>();
                    Burst->SetStringField(TEXT("type"), Spawn->Type == ENiagaraStatelessSpawnInfoType::Burst ? TEXT("Burst") : TEXT("Rate"));
                    Burst->SetBoolField(TEXT("enabled"), Spawn->bEnabled);
                    Burst->SetNumberField(TEXT("time"), Spawn->SpawnTime);
                    Burst->SetNumberField(TEXT("count_min"), Spawn->Amount.Min);
                    Burst->SetNumberField(TEXT("count_max"), Spawn->Amount.Max);
                    Bursts.Add(MakeShared<FJsonValueObject>(Burst));
                }
                Item->SetArrayField(TEXT("spawns"), Bursts);
                TArray<TSharedPtr<FJsonValue>> Modules;
                for (UNiagaraStatelessModule* Module : Emitter->GetModules())
                {
                    if (!Module || !Module->IsModuleEnabled()) { continue; }
                    TSharedRef<FJsonObject> ModuleData = MakeShared<FJsonObject>();
                    ModuleData->SetStringField(TEXT("class"), Module->GetClass()->GetName());
                    TSharedRef<FJsonObject> Properties = MakeShared<FJsonObject>();
                    FJsonObjectConverter::UStructToJsonObject(Module->GetClass(), Module, Properties, 0, CPF_Transient);
                    ModuleData->SetObjectField(TEXT("properties"), Properties);
                    Modules.Add(MakeShared<FJsonValueObject>(ModuleData));
                }
                Item->SetArrayField(TEXT("modules"), Modules);
                TArray<TSharedPtr<FJsonValue>> Renderers;
                for (UNiagaraRendererProperties* Renderer : Emitter->GetRenderers())
                {
                    TSharedRef<FJsonObject> RendererData = MakeShared<FJsonObject>();
                    RendererData->SetStringField(TEXT("class"), Renderer->GetClass()->GetName());
                    RendererData->SetBoolField(TEXT("enabled"), Renderer->GetIsEnabled());
                    if (const auto* Sprite = Cast<UNiagaraSpriteRendererProperties>(Renderer)) { RendererData->SetStringField(TEXT("material"), GetPathNameSafe(Sprite->Material)); }
                    if (const auto* Mesh = Cast<UNiagaraMeshRendererProperties>(Renderer))
                    {
                        RendererData->SetStringField(TEXT("mesh"), Mesh->Meshes.IsEmpty() ? TEXT("") : GetPathNameSafe(Mesh->Meshes[0].Mesh));
                        RendererData->SetStringField(TEXT("material"), Mesh->OverrideMaterials.IsEmpty() ? TEXT("") : GetPathNameSafe(Mesh->OverrideMaterials[0].ExplicitMat));
                    }
                    Renderers.Add(MakeShared<FJsonValueObject>(RendererData));
                }
                Item->SetArrayField(TEXT("renderers"), Renderers);
            }
            Emitters.Add(MakeShared<FJsonValueObject>(Item));
        }
        Root->SetArrayField(TEXT("emitters"), Emitters);
    }
    FString Json;
    FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Json));
    return Json;
}
