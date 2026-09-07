#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AstraNiagaraLibrary.generated.h"

class UNiagaraSystem;
class UMaterialInterface;

/** Editor-only asset authoring helpers. Generated effects use standard Niagara runtime classes. */
UCLASS()
class ASTRANIGARATOOLS_API UAstraNiagaraLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Materials must be ordered debris, flame, smoke, distortion. Returns an unsaved dirty asset. */
    UFUNCTION(BlueprintCallable, Category = "Astra Niagara")
    static UNiagaraSystem* CreateSmallDestruction(const FString& SystemPath,
        const TArray<UMaterialInterface*>& Materials, bool bLooping);

    /** Inspect the actual authored Niagara modules and renderers as JSON for validation. */
    UFUNCTION(BlueprintCallable, Category = "Astra Niagara")
    static FString DescribeSystem(UNiagaraSystem* System);

    UFUNCTION(BlueprintCallable, Category = "Astra Niagara")
    static void EnableViewportRealtime();
};
