#include "SoftbodyCharacter.h"

#include "SoftBodyBall.h"
#include "SoftBodySolver.h"
#include "Animation/AnimInstance.h"
#include "Camera/CameraComponent.h"
#include "Camera/CameraTypes.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/InputSettings.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
    const FName HandBone(TEXT("hand_r"));
    const FName MiddleBase(TEXT("middle_01_r"));
    const TCHAR* DigitNames[] = { TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("pinky"), TEXT("thumb") };

    FName DigitBone(int32 Finger, int32 Joint)
    {
        return FName(*FString::Printf(TEXT("%s_%02d_r"), DigitNames[Finger], Joint));
    }
}

ASoftbodyCharacter::ASoftbodyCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PrePhysics;
    GetCapsuleComponent()->InitCapsuleSize(22.f, 96.f);
    bUseControllerRotationPitch = false;
    bUseControllerRotationYaw = false;
    bUseControllerRotationRoll = false;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->RotationRate = FRotator(0.f, 500.f, 0.f);
    GetCharacterMovement()->MaxWalkSpeed = 350.f;
    GetCharacterMovement()->JumpZVelocity = 500.f;
    GetCharacterMovement()->AirControl = 0.35f;
    GetCharacterMovement()->BrakingDecelerationWalking = 2000.f;
    GetCharacterMovement()->InitialPushForceFactor = 100.f;
    GetCharacterMovement()->PushForceFactor = 8000.f;
    GetCharacterMovement()->bPushForceScaledToMass = false;
    GetCharacterMovement()->TouchForceFactor = 1.f;

    GetMesh()->SetRelativeLocationAndRotation(FVector(0.f, 0.f, -96.f), FRotator(0.f, -90.f, 0.f));
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    GetMesh()->SetForcedLOD(1);

    static ConstructorHelpers::FObjectFinder<USkeletalMesh> Manny(TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
    if (Manny.Succeeded())
    {
        GetMesh()->SetSkeletalMesh(Manny.Object);
    }
    static ConstructorHelpers::FClassFinder<UAnimInstance> AnimBP(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"));
    if (AnimBP.Succeeded())
    {
        GetMesh()->SetAnimInstanceClass(AnimBP.Class);
    }

    InteractionMesh = CreateDefaultSubobject<UPoseableMeshComponent>(TEXT("InteractionPose"));
    InteractionMesh->SetupAttachment(GetCapsuleComponent());
    InteractionMesh->SetRelativeTransform(GetMesh()->GetRelativeTransform());
    InteractionMesh->SetSkinnedAssetAndUpdate(Manny.Object);
    InteractionMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    InteractionMesh->SetVisibility(false);
    InteractionMesh->SetForcedLOD(1);
    InteractionMesh->PrimaryComponentTick.bCanEverTick = false;

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 320.f;
    CameraBoom->SocketOffset = FVector(0.f, 45.f, 55.f);
    CameraBoom->bUsePawnControlRotation = true;
    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;
    FollowCamera->FieldOfView = 70.f;
}

void ASoftbodyCharacter::BeginPlay()
{
    Super::BeginPlay();
    // Read animation before copying it; solve the soft body only after the hand is posed.
    AddTickPrerequisiteComponent(GetMesh());
    CacheReferencePose();
    SelectNearestBall();
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        PC->SetControlRotation(FRotator(-12.f, 0.f, 0.f));
        PC->SetInputMode(FInputModeGameOnly());
        PC->bShowMouseCursor = false;
    }
}

void ASoftbodyCharacter::CacheReferencePose()
{
    USkeletalMesh* MeshAsset = GetMesh()->GetSkeletalMeshAsset();
    if (!MeshAsset)
    {
        return;
    }
    const FReferenceSkeleton& Skeleton = MeshAsset->GetRefSkeleton();
    ReferenceComponentPose = Skeleton.GetRefBonePose();
    for (int32 BoneIndex = 1; BoneIndex < ReferenceComponentPose.Num(); ++BoneIndex)
    {
        ReferenceComponentPose[BoneIndex] *= ReferenceComponentPose[ Skeleton.GetParentIndex(BoneIndex) ];
    }
    if (Skeleton.FindBoneIndex(HandBone) == INDEX_NONE || Skeleton.FindBoneIndex(MiddleBase) == INDEX_NONE)
    {
        UE_LOG(LogTemp, Error, TEXT("Softbody: mannequin has no required right-hand bones."));
        return;
    }
    const FVector Wrist = ReferenceBone(HandBone).GetLocation();
    const FVector Middle = ReferenceBone(MiddleBase).GetLocation();
    const FVector Forward = (Middle - Wrist).GetSafeNormal();
    const FVector Across = (ReferenceBone(TEXT("index_01_r")).GetLocation() - ReferenceBone(TEXT("pinky_01_r")).GetLocation()).GetSafeNormal();
    ReferenceHandFrame = FRotationMatrix::MakeFromXY(Forward, Across).ToQuat();
    ReferencePalmNormal = FVector::CrossProduct(Forward, Across).GetSafeNormal();
    ReferencePalmCenter = FMath::Lerp(Wrist, Middle, 0.55f);
    bReferenceReady = true;
    UE_LOG(LogTemp, Display, TEXT("Softbody mannequin: upper arm %.2f cm, forearm %.2f cm, palm %.2f cm; %d bones."),
        FVector::Distance(ReferenceBone(TEXT("upperarm_r")).GetLocation(), ReferenceBone(TEXT("lowerarm_r")).GetLocation()),
        FVector::Distance(ReferenceBone(TEXT("lowerarm_r")).GetLocation(), Wrist),
        FVector::Distance(Wrist, Middle), ReferenceComponentPose.Num());
}

FTransform ASoftbodyCharacter::ReferenceBone(FName BoneName) const
{
    const int32 Index = GetMesh()->GetBoneIndex(BoneName);
    return ReferenceComponentPose.IsValidIndex(Index) ? ReferenceComponentPose[Index] : FTransform::Identity;
}

void ASoftbodyCharacter::SelectNearestBall()
{
    ASoftBodyBall* Nearest = nullptr;
    double BestDistance = TNumericLimits<double>::Max();
    for (TActorIterator<ASoftBodyBall> It(GetWorld()); It; ++It)
    {
        if (!It->bHandInteractable)
        {
            continue;
        }
        const double Distance = FVector::DistSquared2D(GetActorLocation(), It->GetActorLocation());
        if (Distance < BestDistance)
        {
            BestDistance = Distance;
            Nearest = *It;
        }
    }
    if (Ball != Nearest)
    {
        if (Ball)
        {
            Ball->SetHandContacts({});
            Ball->RemoveTickPrerequisiteActor(this);
        }
        Ball = Nearest;
        if (Ball)
        {
            Ball->AddTickPrerequisiteActor(this);
        }
    }
}

void ASoftbodyCharacter::BeginInteraction()
{
    if (bInteracting)
    {
        return;
    }
    SelectNearestBall();
    if (!Ball || !bReferenceReady || FVector::Dist2D(GetActorLocation(), Ball->GetActorLocation()) > 230.f)
    {
        return;
    }
    const float SizeBlend = FMath::Clamp((Ball->BallRadius - 3.35f) / 3.35f, 0.f, 1.f);
    FVector Station = Ball->GetActorLocation() + FVector(FMath::Lerp(-35.f, -44.f, SizeBlend), -18.f, 0.f);
    Station.Z = GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    GetCharacterMovement()->StopMovementImmediately();
    GetCharacterMovement()->DisableMovement();
    SetActorLocationAndRotation(Station, FRotator::ZeroRotator, false, nullptr, ETeleportType::TeleportPhysics);
    bInteracting = true;
    ResetHandControls();
    FMinimalViewInfo InteractionView;
    CalcCamera(0.f, InteractionView);
    HandSlideDirection = FRotationMatrix(InteractionView.Rotation).GetUnitAxis(EAxis::Y).GetSafeNormal2D();
    GetMesh()->SetVisibility(false);
    InteractionMesh->SetVisibility(true);
    UpdateHandPose();
    UpdateHandContacts();
}

void ASoftbodyCharacter::EndInteraction()
{
    bInteracting = false;
    ResetHandControls();
    HandContactCount = 0;
    if (Ball)
    {
        Ball->SetHandContacts({});
    }
    InteractionMesh->SetVisibility(false);
    GetMesh()->SetVisibility(true);
    GetCharacterMovement()->SetMovementMode(MOVE_Walking);
}

void ASoftbodyCharacter::SetAutoDemo(bool bEnabled)
{
    if (bEnabled && !bInteracting)
    {
        BeginInteraction();
    }
    GripInput = GripAmount;
    bGripOverride = false;
    bAutoDemo = bEnabled && bInteracting;
    DemoTime = 0.f;
    if (bAutoDemo)
    {
        PressureInput = 0.f;
        HandOffsetInput = 0.f;
    }
}

void ASoftbodyCharacter::SetGripInput(float Amount)
{
    bAutoDemo = false;
    bGripOverride = false;
    GripInput = FMath::Clamp(Amount, 0.f, 1.f);
}

void ASoftbodyCharacter::ResetHandControls()
{
    bAutoDemo = false;
    bGripOverride = false;
    GripInput = GripAmount = 0.f;
    PressureInput = PressureAmount = 0.f;
    HandOffsetInput = HandOffsetAmount = 0.f;
    DemoTime = 0.f;
}

void ASoftbodyCharacter::TakeOverManualControl()
{
    if (bAutoDemo)
    {
        // Continue from the displayed pose instead of jumping to the demo target.
        GripInput = GripAmount;
        PressureInput = PressureAmount;
        HandOffsetInput = HandOffsetAmount;
        bAutoDemo = false;
    }
}

float ASoftbodyCharacter::HandMouseDelta(float Value) const
{
    // Legacy mouse axes include camera FOV scaling. Hand travel should stay the
    // same when C changes inspection distance; retain the user's axis sensitivity.
    const UInputSettings* Settings = GetDefault<UInputSettings>();
    const APlayerController* PC = Cast<APlayerController>(GetController());
    if (Settings->bEnableFOVScaling && PC && PC->PlayerCameraManager)
    {
        Value /= FMath::Max(.01f, Settings->FOVScale * PC->PlayerCameraManager->GetFOVAngle());
    }
    return Value * .075f;
}

void ASoftbodyCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bInteracting)
    {
        SelectNearestBall();
        return;
    }
    if (!IsValid(Ball))
    {
        EndInteraction();
        return;
    }
    if (bAutoDemo)
    {
        DemoTime = FMath::Fmod(DemoTime + DeltaSeconds, 8.f);
        if (DemoTime < 1.0f) GripInput = 0.f;
        else if (DemoTime < 2.5f) GripInput = (DemoTime - 1.f) / 1.5f;
        else if (DemoTime < 4.f) GripInput = 1.f;
        else if (DemoTime < 5.5f) GripInput = 1.f - (DemoTime - 4.f) / 1.5f;
        else GripInput = 0.f;
    }
    const float PreviousGrip = GripAmount;
    GripAmount = FMath::FInterpTo(GripAmount, bGripOverride ? 1.f : GripInput, DeltaSeconds, 5.f);
    PressureAmount = FMath::FInterpTo(PressureAmount, PressureInput, DeltaSeconds, 12.f);
    HandOffsetAmount = FMath::FInterpTo(HandOffsetAmount, HandOffsetInput, DeltaSeconds, 12.f);
    UpdateHandPose();
    UpdateHandContacts();
    if (PreviousGrip < 0.97f && GripAmount >= 0.97f)
    {
        UE_LOG(LogTemp, Display, TEXT("Softbody grip: radius %.2f, wrist error %.3f cm, palm down %.3f, %d phalanx/palm colliders."),
            Ball->BallRadius, HandContactError, PalmDownAlignment, HandContactCount);
        for (int32 Finger = 0; Finger < 5; ++Finger)
        {
            const FVector TipBone = InteractionMesh->GetBoneLocationByName(DigitBone(Finger, 3), EBoneSpaces::WorldSpace);
            const FVector Local = Ball->GetActorTransform().InverseTransformPosition(TipBone);
            UE_LOG(LogTemp, Display, TEXT("Softbody %s distal bone relative to ball: %s"), DigitNames[Finger], *Local.ToCompactString());
        }
    }
}

void ASoftbodyCharacter::SetWorldBoneRotation(FName BoneName, const FQuat& Rotation)
{
    FTransform Transform = InteractionMesh->GetBoneTransformByName(BoneName, EBoneSpaces::WorldSpace);
    Transform.SetRotation(Rotation.GetNormalized());
    InteractionMesh->SetBoneTransformByName(BoneName, Transform, EBoneSpaces::WorldSpace);
}

void ASoftbodyCharacter::PointBoneAt(FName BoneName, FName ChildName, const FVector& Direction)
{
    const FTransform Bone = InteractionMesh->GetBoneTransformByName(BoneName, EBoneSpaces::WorldSpace);
    const FVector Child = InteractionMesh->GetBoneLocationByName(ChildName, EBoneSpaces::WorldSpace);
    const FQuat Delta = FQuat::FindBetweenNormals((Child - Bone.GetLocation()).GetSafeNormal(), Direction.GetSafeNormal());
    SetWorldBoneRotation(BoneName, Delta * Bone.GetRotation());
}

void ASoftbodyCharacter::UpdateHandPose(float SupportLift)
{
    if (!Ball || !bReferenceReady)
    {
        return;
    }
    InteractionMesh->CopyPoseFromSkeletalComponent(GetMesh());
    // +X is finger-forward, -Y is the thumb side of this right hand: their
    // cross product points down. Reference-pose measurements avoid Euler-axis guesses.
    const FQuat DownwardFrame = FRotationMatrix::MakeFromXY(FVector::ForwardVector, -FVector::RightVector).ToQuat();
    const FQuat HandDelta = DownwardFrame * ReferenceHandFrame.Inverse();
    const FQuat HandRotation = HandDelta * ReferenceBone(HandBone).GetRotation();
    const float SizeBlend = FMath::Clamp((Ball->BallRadius - 3.35f) / 3.35f, 0.f, 1.f);
    const float PalmX = FMath::Lerp(-2.8f, -2.5f, SizeBlend);
    const FVector ContactCenter = Ball->GetActorLocation() + HandSlideDirection * (HandOffsetAmount * Ball->BallRadius * .45f);
    const float PalmHeight = Ball->BallRadius + 2.f - PressureAmount * Ball->BallRadius * .3f + SupportLift;
    const FVector PalmTarget = ContactCenter + FVector(PalmX, 0.f, PalmHeight);
    DesiredWrist = PalmTarget - HandDelta.RotateVector(ReferencePalmCenter - ReferenceBone(HandBone).GetLocation());

    const FVector Shoulder = InteractionMesh->GetBoneLocationByName(TEXT("upperarm_r"), EBoneSpaces::WorldSpace);
    const FVector OldElbow = InteractionMesh->GetBoneLocationByName(TEXT("lowerarm_r"), EBoneSpaces::WorldSpace);
    const FVector OldWrist = InteractionMesh->GetBoneLocationByName(HandBone, EBoneSpaces::WorldSpace);
    const float UpperLength = FVector::Distance(Shoulder, OldElbow);
    const float LowerLength = FVector::Distance(OldElbow, OldWrist);
    const FVector ReachDirection = (DesiredWrist - Shoulder).GetSafeNormal();
    const float Reach = FMath::Clamp(static_cast<float>(FVector::Distance(DesiredWrist, Shoulder)),
        FMath::Abs(UpperLength - LowerLength) + 0.1f, UpperLength + LowerLength - 0.2f);
    const float Along = (UpperLength * UpperLength - LowerLength * LowerLength + Reach * Reach) / (2.f * Reach);
    const float Out = FMath::Sqrt(FMath::Max(0.f, UpperLength * UpperLength - Along * Along));
    const FVector Pole(0.f, 1.f, -0.2f);
    const FVector BendDirection = (Pole - ReachDirection * FVector::DotProduct(Pole, ReachDirection)).GetSafeNormal();
    const FVector ElbowTarget = Shoulder + ReachDirection * Along + BendDirection * Out;
    PointBoneAt(TEXT("upperarm_r"), TEXT("lowerarm_r"), ElbowTarget - Shoulder);
    const FVector Elbow = InteractionMesh->GetBoneLocationByName(TEXT("lowerarm_r"), EBoneSpaces::WorldSpace);
    const FVector ForearmReference = ReferenceBone(HandBone).GetLocation() - ReferenceBone(TEXT("lowerarm_r")).GetLocation();
    const FQuat ForearmSwing = FQuat::FindBetweenNormals(HandDelta.RotateVector(ForearmReference).GetSafeNormal(), (DesiredWrist - Elbow).GetSafeNormal());
    SetWorldBoneRotation(TEXT("lowerarm_r"), ForearmSwing * HandDelta * ReferenceBone(TEXT("lowerarm_r")).GetRotation());
    SetWorldBoneRotation(HandBone, HandRotation);

    const float ClosedAngles[3] = {
        FMath::Lerp(55.f, 38.f, SizeBlend),
        FMath::Lerp(115.f, 88.f, SizeBlend),
        FMath::Lerp(150.f, 130.f, SizeBlend)
    };
    const float OpenAngles[3] = { -5.f, 3.f, 10.f };
    for (int32 Finger = 0; Finger < 5; ++Finger)
    {
        const bool bThumb = Finger == 4;
        const FVector Base = InteractionMesh->GetBoneLocationByName(DigitBone(Finger, 1), EBoneSpaces::WorldSpace);
        FVector Horizontal;
        if (bThumb)
        {
            // Opposition brings the thumb toward the other side of the sphere.
            Horizontal = FVector(0.4f, -1.f, 0.f).GetSafeNormal();
        }
        else
        {
            const float Inward = -(Base.Y - ContactCenter.Y) * FMath::Lerp(0.14f, 0.05f, SizeBlend) * GripAmount;
            Horizontal = FVector(1.f, Inward, 0.f).GetSafeNormal();
        }
        for (int32 Joint = 1; Joint <= 3; ++Joint)
        {
            const FName Name = DigitBone(Finger, Joint);
            if (InteractionMesh->GetBoneIndex(Name) == INDEX_NONE)
            {
                continue;
            }
            const FTransform Reference = ReferenceBone(Name);
            FVector RefDirection;
            if (Joint < 3)
            {
                RefDirection = ReferenceBone(DigitBone(Finger, Joint + 1)).GetLocation() - Reference.GetLocation();
            }
            else
            {
                RefDirection = Reference.GetLocation() - ReferenceBone(DigitBone(Finger, 2)).GetLocation();
            }
            float ClosedAngle = ClosedAngles[Joint - 1];
            float OpenAngle = OpenAngles[Joint - 1];
            if (bThumb)
            {
                // Oppose from the wrist toward +X and wrap around the -Y side.
                // The old shared curl plane pulled the thumb back behind the ball.
                const float SmallAngles[3] = { 30.f, 30.f, 65.f };
                const float LargeAngles[3] = { 35.f, 45.f, 70.f };
                const FVector SmallDirections[3] = { FVector(1.f, -.28f, 0.f), FVector(1.f, .10f, 0.f), FVector(1.f, .25f, 0.f) };
                const FVector LargeDirections[3] = { FVector(1.f, -.70f, 0.f), FVector(.10f, -1.f, 0.f), FVector(1.f, .10f, 0.f) };
                ClosedAngle = FMath::Lerp(SmallAngles[Joint - 1], LargeAngles[Joint - 1], SizeBlend);
                OpenAngle = 5.f + Joint * 5.f;
                const FVector ClosedDirection = FMath::Lerp(SmallDirections[Joint - 1], LargeDirections[Joint - 1], SizeBlend).GetSafeNormal();
                Horizontal = FMath::Lerp(FVector(.4f, -1.f, 0.f).GetSafeNormal(), ClosedDirection, GripAmount).GetSafeNormal();
            }
            else
            {
                ClosedAngle += (Finger - 1.f) * 2.5f;
            }
            const float Angle = FMath::DegreesToRadians(FMath::Lerp(OpenAngle, ClosedAngle, GripAmount));
            const FVector DesiredDirection = Horizontal * FMath::Cos(Angle) - FVector::UpVector * FMath::Sin(Angle);
            const FQuat Swing = FQuat::FindBetweenNormals(HandDelta.RotateVector(RefDirection).GetSafeNormal(), DesiredDirection);
            SetWorldBoneRotation(Name, Swing * HandDelta * Reference.GetRotation());
        }
    }
    InteractionMesh->RefreshBoneTransforms();
    const FTransform ActualHand = InteractionMesh->GetBoneTransformByName(HandBone, EBoneSpaces::WorldSpace);
    HandContactError = FVector::Distance(ActualHand.GetLocation(), DesiredWrist);
    const FVector NormalInHand = ReferenceBone(HandBone).GetRotation().UnrotateVector(ReferencePalmNormal);
    PalmDownAlignment = FVector::DotProduct(ActualHand.GetRotation().RotateVector(NormalInHand), -FVector::UpVector);
}

void ASoftbodyCharacter::UpdateHandContacts()
{
    if (!Ball || !bReferenceReady)
    {
        return;
    }
    float LowestPoint = 0.f;
    TArray<FSoftBodyContact> Contacts = GatherHandContacts(LowestPoint);
    const float TableTop = Ball->GetActorLocation().Z - Ball->BallRadius;
    const float SupportLift = FMath::Max(0.f, TableTop + .05f - LowestPoint);
    if (SupportLift > 0.f)
    {
        // The table limits actual travel without changing the user's three inputs.
        // Repose the visible hand before rebuilding its matching contact spheres.
        UpdateHandPose(SupportLift);
        Contacts = GatherHandContacts(LowestPoint);
    }
    HandContactCount = Contacts.Num();
    Ball->SetHandContacts(Contacts);
}

TArray<FSoftBodyContact> ASoftbodyCharacter::GatherHandContacts(float& LowestPoint) const
{
    TArray<FSoftBodyContact> Contacts;
    Contacts.Reserve(50);
    LowestPoint = TNumericLimits<float>::Max();
    const FTransform BallWorld = Ball->GetActorTransform();
    auto AddContact = [&Contacts, &BallWorld, &LowestPoint](const FVector& WorldCenter, float Radius)
    {
        FSoftBodyContact Contact;
        Contact.Center = BallWorld.InverseTransformPosition(WorldCenter);
        Contact.Radius = Radius;
        Contacts.Add(Contact);
        LowestPoint = FMath::Min(LowestPoint, static_cast<float>(WorldCenter.Z) - Radius);
    };
    const FTransform HandWorld = InteractionMesh->GetBoneTransformByName(HandBone, EBoneSpaces::WorldSpace);
    const FVector PalmLocal = ReferenceBone(HandBone).InverseTransformPosition(ReferencePalmCenter);
    AddContact(HandWorld.TransformPosition(PalmLocal), 2.8f);
    const FVector DistalPalm = FMath::Lerp(ReferenceBone(HandBone).GetLocation(), ReferenceBone(MiddleBase).GetLocation(), 0.9f);
    AddContact(HandWorld.TransformPosition(ReferenceBone(HandBone).InverseTransformPosition(DistalPalm)), 2.4f);

    for (int32 Finger = 0; Finger < 5; ++Finger)
    {
        for (int32 Joint = 1; Joint <= 3; ++Joint)
        {
            const FName Name = DigitBone(Finger, Joint);
            if (InteractionMesh->GetBoneIndex(Name) == INDEX_NONE)
            {
                continue;
            }
            const FTransform Segment = InteractionMesh->GetBoneTransformByName(Name, EBoneSpaces::WorldSpace);
            const FVector Start = Segment.GetLocation();
            FVector End;
            if (Joint < 3)
            {
                End = InteractionMesh->GetBoneLocationByName(DigitBone(Finger, Joint + 1), EBoneSpaces::WorldSpace);
            }
            else
            {
                // The visible terminal phalanx extends beyond bone_03. Carry its
                // measured predecessor direction through the actual posed transform.
                const FTransform Reference = ReferenceBone(Name);
                const FVector ReferenceTip = Reference.GetLocation() +
                    (Reference.GetLocation() - ReferenceBone(DigitBone(Finger, 2)).GetLocation()) * 0.80f;
                End = Segment.TransformPosition(Reference.InverseTransformPosition(ReferenceTip));
            }
            const float Radius = Finger == 4 ? 1.15f : (Finger == 3 ? 0.85f : 1.0f);
            // Include the actual segment endpoints, not only the inner samples.
            LowestPoint = FMath::Min(LowestPoint, static_cast<float>(FMath::Min(Start.Z, End.Z)) - Radius);
            for (int32 Sample = 0; Sample < 3; ++Sample)
            {
                AddContact(FMath::Lerp(Start, End, (Sample + 0.5f) / 3.f), Radius);
            }
        }
    }
    return Contacts;
}

void ASoftbodyCharacter::CalcCamera(float DeltaTime, FMinimalViewInfo& OutResult)
{
    if (!bInteracting || !Ball)
    {
        Super::CalcCamera(DeltaTime, OutResult);
        return;
    }
    const FVector Center = Ball->GetActorLocation();
    const FVector Target = Center + (bCloseCamera ? FVector(-5.f, 0.f, 8.f) : FVector(-25.f, -5.f, -5.f));
    OutResult.Location = Center + (bCloseCamera ? FVector(42.f, -88.f, 49.f) : FVector(180.f, -240.f, 105.f));
    OutResult.Rotation = (Target - OutResult.Location).Rotation();
    OutResult.FOV = bCloseCamera ? 42.f : 58.f;
    OutResult.bConstrainAspectRatio = false;
}

void ASoftbodyCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("MoveForward"), this, &ASoftbodyCharacter::MoveForward);
    Input->BindAxis(TEXT("MoveRight"), this, &ASoftbodyCharacter::MoveRight);
    Input->BindAxis(TEXT("Turn"), this, &ASoftbodyCharacter::Turn);
    Input->BindAxis(TEXT("LookUp"), this, &ASoftbodyCharacter::LookUp);
    Input->BindKey(EKeys::SpaceBar, IE_Pressed, this, &ASoftbodyCharacter::StartJump);
    Input->BindKey(EKeys::SpaceBar, IE_Released, this, &ACharacter::StopJumping);
    Input->BindKey(EKeys::E, IE_Pressed, this, &ASoftbodyCharacter::ToggleInteraction);
    Input->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &ASoftbodyCharacter::GripPressed);
    Input->BindKey(EKeys::LeftMouseButton, IE_Released, this, &ASoftbodyCharacter::GripReleased);
    Input->BindKey(EKeys::MouseScrollUp, IE_Pressed, this, &ASoftbodyCharacter::GripWheelUp);
    Input->BindKey(EKeys::MouseScrollDown, IE_Pressed, this, &ASoftbodyCharacter::GripWheelDown);
    Input->BindKey(EKeys::R, IE_Pressed, this, &ASoftbodyCharacter::ResetSelectedBall);
    Input->BindKey(EKeys::C, IE_Pressed, this, &ASoftbodyCharacter::ToggleCamera);
    Input->BindKey(EKeys::Tab, IE_Pressed, this, &ASoftbodyCharacter::ToggleAutoDemo);
}

void ASoftbodyCharacter::ToggleInteraction() { if (bInteracting) EndInteraction(); else BeginInteraction(); }
void ASoftbodyCharacter::ToggleCamera() { bCloseCamera = !bCloseCamera; }
void ASoftbodyCharacter::ToggleAutoDemo() { SetAutoDemo(!bAutoDemo); }
void ASoftbodyCharacter::GripPressed()
{
    if (!bInteracting) return;
    TakeOverManualControl();
    bGripOverride = true;
}
void ASoftbodyCharacter::GripReleased() { bGripOverride = false; }
void ASoftbodyCharacter::GripWheelUp() { AdjustGrip(.1f); }
void ASoftbodyCharacter::GripWheelDown() { AdjustGrip(-.1f); }
void ASoftbodyCharacter::AdjustGrip(float Delta)
{
    if (!bInteracting) return;
    TakeOverManualControl();
    GripInput = FMath::Clamp(GripInput + Delta, 0.f, 1.f);
}
void ASoftbodyCharacter::ResetSelectedBall()
{
    ResetHandControls();
    if (bInteracting)
    {
        UpdateHandPose();
        UpdateHandContacts();
        if (Ball) Ball->ResetBall();
    }
    else
    {
        for (TActorIterator<ASoftBodyBall> It(GetWorld()); It; ++It)
        {
            It->ResetBall();
        }
    }
}
void ASoftbodyCharacter::StartJump() { if (!bInteracting) Jump(); }

void ASoftbodyCharacter::MoveForward(float Value)
{
    if (Controller && !bInteracting && !FMath::IsNearlyZero(Value))
    {
        AddMovementInput(FRotationMatrix(FRotator(0.f, Controller->GetControlRotation().Yaw, 0.f)).GetUnitAxis(EAxis::X), Value);
    }
}

void ASoftbodyCharacter::MoveRight(float Value)
{
    if (Controller && !bInteracting && !FMath::IsNearlyZero(Value))
    {
        AddMovementInput(FRotationMatrix(FRotator(0.f, Controller->GetControlRotation().Yaw, 0.f)).GetUnitAxis(EAxis::Y), Value);
    }
}

void ASoftbodyCharacter::Turn(float Value)
{
    if (!bInteracting) { AddControllerYawInput(Value); return; }
    if (!FMath::IsFinite(Value) || FMath::IsNearlyZero(Value)) return;
    TakeOverManualControl();
    HandOffsetInput = FMath::Clamp(HandOffsetInput + HandMouseDelta(Value), -1.f, 1.f);
}

void ASoftbodyCharacter::LookUp(float Value)
{
    if (!bInteracting) { AddControllerPitchInput(Value); return; }
    if (!FMath::IsFinite(Value) || FMath::IsNearlyZero(Value)) return;
    TakeOverManualControl();
    // LookUp is mapped to -MouseY, so positive Value already means mouse down.
    PressureInput = FMath::Clamp(PressureInput + HandMouseDelta(Value), 0.f, 1.f);
}
