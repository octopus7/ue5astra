#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "AstraWorld.generated.h"

class UStaticMeshComponent;
class USpringArmComponent;
class UCameraComponent;
class UMaterialInterface;

UCLASS()
class ASTRALEVELTEST_API AAstraCat : public ACharacter
{
    GENERATED_BODY()
public:
    AAstraCat();
    virtual void Tick(float DeltaSeconds) override;
    virtual void BeginPlay() override;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USceneComponent> CatRoot;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UCameraComponent> TopDownCamera;
private:
    UStaticMeshComponent* Box(const TCHAR* Name, FVector Position, FVector Dimensions, const TCHAR* MaterialName, USceneComponent* Parent = nullptr);
    UPROPERTY() TObjectPtr<USceneComponent> LeftLeg;
    UPROPERTY() TObjectPtr<USceneComponent> RightLeg;
    UPROPERTY() TObjectPtr<USceneComponent> LeftArm;
    UPROPERTY() TObjectPtr<USceneComponent> RightArm;
    UPROPERTY() TObjectPtr<USceneComponent> Tail;
    float Gait = 0;
    FVector SafeLocation;
};

UCLASS()
class ASTRALEVELTEST_API AAstraController : public APlayerController
{
    GENERATED_BODY()
public:
    AAstraController();
    virtual void BeginPlay() override;
    virtual void PlayerTick(float DeltaTime) override;
private:
    void TickValidation(float DeltaTime);
    bool bSmokeTest = false;
    bool bBridgeTest = false;
    bool bCampTest = false;
    bool bBridgeMidpointSupported = false;
    bool bReviewSelected = false;
    bool bCaptured = false;
    bool bTestPressed = false;
    bool bTestsPassed = true;
    int32 TestStage = 0;
    float ValidationTime = 0;
    float ReviewCaptureTime = 13.f;
    FVector TestStart;
    FRotator TestCameraRotation;
    FString ReviewCamera;
    TArray<FString> TestResults;
};

UCLASS()
class ASTRALEVELTEST_API AAstraGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AAstraGameMode();
};

UCLASS()
class ASTRALEVELTEST_API UAstraSceneLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Astra|Terrain") static float TerrainHeight(float X, float Y);
    UFUNCTION(BlueprintCallable, Category="Astra|Terrain") static float StreamCenter(float X);
    UFUNCTION(BlueprintCallable, Category="Astra|Editor") static AActor* CreateTerrain(UMaterialInterface* Material);
    UFUNCTION(BlueprintCallable, Category="Astra|Editor") static bool UpdateTerrainHeights(AActor* Terrain);
    UFUNCTION(BlueprintCallable, Category="Astra|Terrain") static float LandscapeHeightAt(AActor* Terrain, FVector Location);
};
