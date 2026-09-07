#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AstraDemoPlayback.h"
#include "AstraLevelConfig.generated.h"

/** Saved, level-local tour data. Maps without this actor keep the original woodland tour. */
UCLASS(BlueprintType)
class ASTRALEVELTEST_API AAstraLevelConfig : public AActor
{
    GENERATED_BODY()

public:
    AAstraLevelConfig();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Astra|Demo")
    TArray<FAstraDemoShot> DemoShots;

    // A short filename prefix keeps each level's validation result separate.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Astra|Demo")
    FString ValidationPrefix = TEXT("SF");

    static const AAstraLevelConfig* FindForWorld(UWorld* World);
    FString GetSafeValidationPrefix() const;
};
