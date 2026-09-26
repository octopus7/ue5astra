#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "SoftbodyCharacter.generated.h"

class ASoftBodyBall;
class UCameraComponent;
class UPoseableMeshComponent;
class USpringArmComponent;

/** The template mannequin, with a bone-driven overhead soft-ball interaction. */
UCLASS()
class SOFTBODY_API ASoftbodyCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    ASoftbodyCharacter();
    virtual void Tick(float DeltaSeconds) override;
    virtual void CalcCamera(float DeltaTime, FMinimalViewInfo& OutResult) override;

    UPROPERTY(BlueprintReadOnly, Category="Grip")
    float GripAmount = 0.f;

    UPROPERTY(BlueprintReadOnly, Category="Grip")
    bool bInteracting = false;

    UPROPERTY(BlueprintReadOnly, Category="Grip")
    bool bAutoDemo = false;

    UFUNCTION(BlueprintCallable, Category="Grip")
    void BeginInteraction();

    UFUNCTION(BlueprintCallable, Category="Grip")
    void EndInteraction();

    UFUNCTION(BlueprintCallable, Category="Grip")
    void SetAutoDemo(bool bEnabled);

    UFUNCTION(BlueprintCallable, Category="Grip")
    void SetGripInput(float Amount);

    UFUNCTION(BlueprintPure, Category="Grip")
    ASoftBodyBall* GetBall() const { return Ball; }

    UFUNCTION(BlueprintPure, Category="Grip")
    float GetHandContactError() const { return HandContactError; }

    UFUNCTION(BlueprintPure, Category="Grip")
    float GetPalmDownAlignment() const { return PalmDownAlignment; }

    UFUNCTION(BlueprintPure, Category="Grip")
    int32 GetHandContactCount() const { return HandContactCount; }

protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

private:
    UPROPERTY(VisibleAnywhere)
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UCameraComponent> FollowCamera;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UPoseableMeshComponent> InteractionMesh;

    UPROPERTY()
    TObjectPtr<ASoftBodyBall> Ball;

    TArray<FTransform> ReferenceComponentPose;
    FQuat ReferenceHandFrame = FQuat::Identity;
    FVector ReferencePalmCenter = FVector::ZeroVector;
    FVector ReferencePalmNormal = FVector::UpVector;
    FVector DesiredWrist = FVector::ZeroVector;
    float GripInput = 0.f;
    float DemoTime = 0.f;
    float HandContactError = 0.f;
    float PalmDownAlignment = 0.f;
    int32 HandContactCount = 0;
    bool bCloseCamera = true;
    bool bReferenceReady = false;

    void SelectNearestBall();
    void CacheReferencePose();
    void UpdateHandPose();
    void UpdateHandContacts();
    void ToggleInteraction();
    void ToggleCamera();
    void ToggleAutoDemo();
    void GripPressed();
    void GripReleased();
    void ResetSelectedBall();
    void MoveForward(float Value);
    void MoveRight(float Value);
    void Turn(float Value);
    void LookUp(float Value);
    void StartJump();
    FTransform ReferenceBone(FName BoneName) const;
    void SetWorldBoneRotation(FName BoneName, const FQuat& Rotation);
    void PointBoneAt(FName BoneName, FName ChildName, const FVector& Direction);
};
