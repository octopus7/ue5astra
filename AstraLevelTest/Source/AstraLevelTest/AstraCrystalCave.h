#pragma once

#include "CoreMinimal.h"
#include "AstraWorld.h"
#include "AstraCrystalCave.generated.h"

struct FAstraCaveValidation;

/** The cave retains the calico and WASD controls, with its own camera framing and no forest tour. */
UCLASS()
class ASTRALEVELTEST_API AAstraCrystalCaveController : public AAstraController
{
    GENERATED_BODY()
public:
    AAstraCrystalCaveController();
    virtual ~AAstraCrystalCaveController() override;
    virtual void BeginPlay() override;
    virtual void SetupInputComponent() override;
    virtual void PlayerTick(float DeltaTime) override;
    virtual void OnPossess(APawn* InPawn) override;
private:
    // Shared ownership storage tolerates the generated UObject vtable helper constructor
    // while the non-reflected validation implementation remains private to the .cpp.
    TSharedPtr<FAstraCaveValidation> CaveValidation;
};

UCLASS()
class ASTRALEVELTEST_API AAstraCrystalCaveGameMode : public AAstraGameMode
{
    GENERATED_BODY()
public:
    AAstraCrystalCaveGameMode();
};

UCLASS()
class ASTRALEVELTEST_API UAstraCrystalCaveLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Import the preserved Blender 127 x 64 unsigned little-endian R16 height field as Landscape. */
    UFUNCTION(BlueprintCallable, Category="Astra|CrystalCave|Editor")
    static AActor* CreateCaveTerrain(UMaterialInterface* Material);
};
