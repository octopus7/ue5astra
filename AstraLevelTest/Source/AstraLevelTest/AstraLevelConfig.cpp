#include "AstraLevelConfig.h"

#include "EngineUtils.h"

AAstraLevelConfig::AAstraLevelConfig()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorHiddenInGame(true);
    SetCanBeDamaged(false);
}

const AAstraLevelConfig* AAstraLevelConfig::FindForWorld(UWorld* World)
{
    if (!World) return nullptr;
    for (TActorIterator<AAstraLevelConfig> It(World); It; ++It)
    {
        if (IsValid(*It) && !It->DemoShots.IsEmpty()) return *It;
    }
    return nullptr;
}

FString AAstraLevelConfig::GetSafeValidationPrefix() const
{
    FString SafePrefix;
    for (const TCHAR Character : ValidationPrefix)
    {
        if (FChar::IsAlnum(Character) || Character == TEXT('_')) SafePrefix.AppendChar(Character);
    }
    // Even an accidentally blank or punctuation-only prefix must not overwrite the main map's result.
    return SafePrefix.IsEmpty() ? TEXT("Level") : SafePrefix;
}
