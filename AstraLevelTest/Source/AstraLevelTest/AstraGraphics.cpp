#include "AstraGraphics.h"

#include "Async/Async.h"
#include "Containers/Ticker.h"
#include "DLSSLibrary.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "FXRenderingUtils.h"
#include "GameFramework/GameUserSettings.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "SceneView.h"
#include "SceneViewExtension.h"
#include "Serialization/JsonSerializer.h"
#include "TemporalUpscaler.h"
#include "UnrealClient.h"

DEFINE_LOG_CATEGORY_STATIC(LogAstraGraphics, Log, All);

namespace
{
    struct FGraphicsProfile
    {
        FString Requested = TEXT("DLSS4K");
        FString Actual = TEXT("DLSS4K");
        FString Support;
        FString FallbackReason;
        FIntPoint Output = FIntPoint(3840, 2160);
        float ScreenPercentage = 100.f;
        bool bDLSSEnabled = false;
        bool bDLSSSupported = false;
        bool bPerformanceSupported = false;
        bool bCommandLineResolution = false;
        bool bValidProfile = true;
    };

    FString SavedPath(const TCHAR* FileName)
    {
        return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), FileName));
    }

    bool SaveJson(const TCHAR* FileName, const TSharedRef<FJsonObject>& Object)
    {
        IFileManager::Get().MakeDirectory(*FPaths::ProjectSavedDir(), true);
        FString Text;
        const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
        return FJsonSerializer::Serialize(Object, Writer)
            && FFileHelper::SaveStringToFile(Text, *SavedPath(FileName), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    }

    TSharedRef<FJsonObject> ProfileJson(const FGraphicsProfile& Profile)
    {
        TSharedRef<FJsonObject> Json = MakeShared<FJsonObject>();
        Json->SetStringField(TEXT("requestedProfile"), Profile.Requested);
        Json->SetStringField(TEXT("actualProfile"), Profile.Actual);
        Json->SetStringField(TEXT("dlssSupport"), Profile.Support);
        Json->SetStringField(TEXT("fallbackReason"), Profile.FallbackReason);
        Json->SetBoolField(TEXT("dlssSupported"), Profile.bDLSSSupported);
        Json->SetBoolField(TEXT("performanceModeSupported"), Profile.bPerformanceSupported);
        Json->SetBoolField(TEXT("dlssEnabled"), Profile.bDLSSEnabled);
        Json->SetBoolField(TEXT("commandLineResolutionOverride"), Profile.bCommandLineResolution);
        Json->SetBoolField(TEXT("validRequestedProfile"), Profile.bValidProfile);
        Json->SetNumberField(TEXT("outputWidth"), Profile.Output.X);
        Json->SetNumberField(TEXT("outputHeight"), Profile.Output.Y);
        Json->SetNumberField(TEXT("screenPercentage"), Profile.ScreenPercentage);
        Json->SetNumberField(TEXT("expectedInternalWidth"), FMath::RoundToInt(Profile.Output.X * Profile.ScreenPercentage / 100.f));
        Json->SetNumberField(TEXT("expectedInternalHeight"), FMath::RoundToInt(Profile.Output.Y * Profile.ScreenPercentage / 100.f));
        return Json;
    }

    void SetConsoleInt(const TCHAR* Name, int32 Value)
    {
        if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Name))
            Variable->Set(Value, ECVF_SetByCode);
    }

    struct FRenderedFrame
    {
        FString Upscaler;
        FIntPoint Output = FIntPoint::ZeroValue;
        FIntPoint Internal = FIntPoint::ZeroValue;
    };

    struct FGraphicsTest;

    class FGraphicsViewObserver final : public FWorldSceneViewExtension
    {
    public:
        FGraphicsViewObserver(const FAutoRegister& AutoRegister, UWorld* World,
            TWeakPtr<FGraphicsTest, ESPMode::ThreadSafe> InTest)
            : FWorldSceneViewExtension(AutoRegister, World), Test(InTest) {}

        virtual void PostRenderViewFamily_RenderThread(FRDGBuilder& GraphBuilder, FSceneViewFamily& Family) override;

    private:
        TWeakPtr<FGraphicsTest, ESPMode::ThreadSafe> Test;
    };

    struct FGraphicsTest : public TSharedFromThis<FGraphicsTest, ESPMode::ThreadSafe>
    {
        FGraphicsProfile Profile;
        TWeakObjectPtr<UWorld> World;
        TSharedPtr<FGraphicsViewObserver, ESPMode::ThreadSafe> Observer;
        FDelegateHandle ScreenshotHandle;
        FRenderedFrame Frame;
        double Started = FPlatformTime::Seconds();
        int32 ObservedFrames = 0;
        FIntPoint ScreenshotSize = FIntPoint::ZeroValue;
        bool bRequestedScreenshot = false;
        bool bScreenshotSaved = false;
        bool bScreenshotHasDetail = false;
        bool bFinished = false;

        ~FGraphicsTest()
        {
            // The ticker owns the final strong reference on the game thread.
            UGameViewportClient::OnScreenshotCaptured().Remove(ScreenshotHandle);
        }

        void ReceiveFrame(FRenderedFrame InFrame)
        {
            if (bFinished) return;
            Frame = MoveTemp(InFrame);
            ++ObservedFrames;
        }

        void CaptureScreenshot(int32 Width, int32 Height, const TArray<FColor>& Pixels)
        {
            if (bFinished || !bRequestedScreenshot) return;
            ScreenshotSize = FIntPoint(Width, Height);
            if (Pixels.Num() == int64(Width) * Height && Pixels.Num() > 0)
            {
                const FColor First = Pixels[0];
                for (int32 Index = 1; Index < Pixels.Num(); Index += 97)
                {
                    if (Pixels[Index] != First) { bScreenshotHasDetail = true; break; }
                }
                TArray64<uint8> Png;
                FImageUtils::PNGCompressImageArray(Width, Height,
                    TArrayView64<const FColor>(Pixels.GetData(), Pixels.Num()), Png);
                bScreenshotSaved = Png.Num() > 0
                    && FFileHelper::SaveArrayToFile(Png, *SavedPath(TEXT("GraphicsValidation.png")));
            }
            UGameViewportClient::OnScreenshotCaptured().Remove(ScreenshotHandle);
            ScreenshotHandle.Reset();
        }

        bool Tick(float DeltaSeconds)
        {
            if (bFinished) return false;
            const double Elapsed = FPlatformTime::Seconds() - Started;
            if (!World.IsValid()) return Finish(TEXT("Game world was destroyed"));
            if (Elapsed >= 6.0 && !bRequestedScreenshot)
            {
                bRequestedScreenshot = true;
                // This callback and PNG encoding work in Shipping without console commands.
                SetConsoleInt(TEXT("r.ScreenshotDelegate"), 1);
                FScreenshotRequest::RequestScreenshot(SavedPath(TEXT("GraphicsValidation.png")), false, false);
                return true; // Allow a rendered frame even after a long first-frame shader stall.
            }
            if (Elapsed >= 8.0 && (bScreenshotSaved || Elapsed >= 20.0)) return Finish(TEXT(""));
            return true;
        }

        bool Finish(const FString& Failure)
        {
            bFinished = true;
            UGameViewportClient::OnScreenshotCaptured().Remove(ScreenshotHandle);
            ScreenshotHandle.Reset();
            Observer.Reset();

            const FIntPoint ExpectedInternal(
                FMath::RoundToInt(Profile.Output.X * Profile.ScreenPercentage / 100.f),
                FMath::RoundToInt(Profile.Output.Y * Profile.ScreenPercentage / 100.f));
            const bool bActualDLSS = Frame.Upscaler.Contains(TEXT("DLSS"), ESearchCase::IgnoreCase);
            const bool bResolutionPass = Frame.Output == Profile.Output && Frame.Internal == ExpectedInternal;
            const bool bUpscalerPass = bActualDLSS == Profile.bDLSSEnabled;
            const bool bPassed = Failure.IsEmpty() && Profile.bValidProfile && ObservedFrames >= 3
                && bResolutionPass && bUpscalerPass && bScreenshotSaved && bScreenshotHasDetail
                && ScreenshotSize == Profile.Output;

            TArray<FString> Failures;
            if (!Failure.IsEmpty()) Failures.Add(Failure);
            if (!Profile.bValidProfile) Failures.Add(TEXT("Unknown requested render profile"));
            if (ObservedFrames < 3) Failures.Add(TEXT("Fewer than three actual render frames observed"));
            if (!bResolutionPass) Failures.Add(TEXT("Actual output or internal render resolution did not match"));
            if (!bUpscalerPass) Failures.Add(TEXT("Actual temporal upscaler did not match the selected profile"));
            if (!bScreenshotSaved || !bScreenshotHasDetail) Failures.Add(TEXT("Detailed screenshot was not saved"));
            if (ScreenshotSize != Profile.Output) Failures.Add(TEXT("Screenshot resolution did not match"));

            TSharedRef<FJsonObject> Json = ProfileJson(Profile);
            Json->SetBoolField(TEXT("passed"), bPassed);
            Json->SetStringField(TEXT("failure"), FString::Join(Failures, TEXT("; ")));
            Json->SetNumberField(TEXT("elapsedSeconds"), FPlatformTime::Seconds() - Started);
            Json->SetNumberField(TEXT("observedFrames"), ObservedFrames);
            Json->SetStringField(TEXT("actualTemporalUpscaler"), Frame.Upscaler);
            Json->SetBoolField(TEXT("actualDLSSEnabled"), bActualDLSS);
            Json->SetBoolField(TEXT("resolutionPass"), bResolutionPass);
            Json->SetBoolField(TEXT("upscalerPass"), bUpscalerPass);
            Json->SetNumberField(TEXT("actualOutputWidth"), Frame.Output.X);
            Json->SetNumberField(TEXT("actualOutputHeight"), Frame.Output.Y);
            Json->SetNumberField(TEXT("actualInternalWidth"), Frame.Internal.X);
            Json->SetNumberField(TEXT("actualInternalHeight"), Frame.Internal.Y);
            Json->SetBoolField(TEXT("screenshotSaved"), bScreenshotSaved);
            Json->SetBoolField(TEXT("screenshotHasDetail"), bScreenshotHasDetail);
            Json->SetNumberField(TEXT("screenshotWidth"), ScreenshotSize.X);
            Json->SetNumberField(TEXT("screenshotHeight"), ScreenshotSize.Y);
            const bool bReportSaved = SaveJson(TEXT("GraphicsValidation.json"), Json);
            UE_LOG(LogAstraGraphics, Display, TEXT("Graphics validation %s: %s, %dx%d -> %dx%d, report=%d"),
                bPassed ? TEXT("PASS") : TEXT("FAIL"), *Frame.Upscaler,
                Frame.Internal.X, Frame.Internal.Y, Frame.Output.X, Frame.Output.Y, bReportSaved);
            FPlatformMisc::RequestExitWithStatus(false, (bPassed && bReportSaved) ? 0 : 1);
            return false;
        }
    };

    void FGraphicsViewObserver::PostRenderViewFamily_RenderThread(FRDGBuilder& GraphBuilder, FSceneViewFamily& Family)
    {
        if (Family.Views.Num() != 1) return;
        const FSceneView* View = Family.Views[0];
        if (!View || !View->bIsViewInfo || View->bIsSceneCapture) return;
        FRenderedFrame Frame;
        Frame.Output = View->UnscaledViewRect.Size();
        // The render callback supplies FViewInfo; this public accessor reads its actual ViewRect.
        Frame.Internal = UE::FXRenderingUtils::GetRawViewRectUnsafe(*View).Size();
        const UE::Renderer::Private::ITemporalUpscaler* Upscaler = Family.GetTemporalUpscalerInterface();
        Frame.Upscaler = Upscaler ? Upscaler->GetDebugName() : TEXT("EngineTemporalUpscaler");
        const TWeakPtr<FGraphicsTest, ESPMode::ThreadSafe> WeakTest = Test;
        AsyncTask(ENamedThreads::GameThread, [WeakTest, Frame = MoveTemp(Frame)]() mutable
        {
            if (const TSharedPtr<FGraphicsTest, ESPMode::ThreadSafe> Pinned = WeakTest.Pin())
                Pinned->ReceiveFrame(MoveTemp(Frame));
        });
    }
}

void FAstraGraphics::Apply(UWorld* World)
{
    if (!World || !World->IsGameWorld() || World->IsPlayInEditor() || IsRunningDedicatedServer()) return;
    // Avoid affecting ordinary editor sessions, including their globally shared rendering CVars.
    if (GIsEditor) return;

    FGraphicsProfile Profile;
    FParse::Value(FCommandLine::Get(), TEXT("AstraRenderProfile="), Profile.Requested);
    if (Profile.Requested.Equals(TEXT("DLSS4K"), ESearchCase::IgnoreCase)) Profile.Actual = TEXT("DLSS4K");
    else if (Profile.Requested.Equals(TEXT("Native1080"), ESearchCase::IgnoreCase)) Profile.Actual = TEXT("Native1080");
    else if (Profile.Requested.Equals(TEXT("Native4K"), ESearchCase::IgnoreCase)) Profile.Actual = TEXT("Native4K");
    else
    {
        Profile.bValidProfile = false;
        Profile.Actual = TEXT("Native1080");
        Profile.FallbackReason = TEXT("Unknown render profile");
    }

    const UDLSSSupport Support = UDLSSLibrary::QueryDLSSSupport();
    Profile.Support = StaticEnum<UDLSSSupport>()->GetNameStringByValue(static_cast<int64>(Support));
    Profile.bDLSSSupported = UDLSSLibrary::IsDLSSSupported();
    float OptimalPercentage = 100.f;
    if (Profile.bDLSSSupported)
    {
        bool bFixed = false;
        float MinPercentage = 100.f, MaxPercentage = 100.f, DeprecatedSharpness = 0.f;
        UDLSSLibrary::GetDLSSModeInformation(UDLSSMode::Performance, FVector2D(3840, 2160),
            Profile.bPerformanceSupported, OptimalPercentage, bFixed,
            MinPercentage, MaxPercentage, DeprecatedSharpness);
    }
    if (Profile.Actual == TEXT("DLSS4K"))
    {
        if (Profile.bDLSSSupported && Profile.bPerformanceSupported && FMath::IsNearlyEqual(OptimalPercentage, 50.f, .01f))
        {
            Profile.bDLSSEnabled = true;
            Profile.ScreenPercentage = OptimalPercentage;
        }
        else
        {
            Profile.Actual = TEXT("Native1080");
            Profile.FallbackReason = TEXT("DLSS Performance at 50 percent is unavailable");
        }
    }
    UDLSSLibrary::EnableDLSS(Profile.bDLSSEnabled);
    if (Profile.bDLSSEnabled && !UDLSSLibrary::IsDLSSEnabled())
    {
        Profile.bDLSSEnabled = false;
        Profile.ScreenPercentage = 100.f;
        Profile.Actual = TEXT("Native1080");
        Profile.FallbackReason = TEXT("DLSS activation failed");
    }
    Profile.Output = Profile.Actual == TEXT("Native1080") ? FIntPoint(1920, 1080) : FIntPoint(3840, 2160);
    int32 ResolutionOverride = 0;
    if (FParse::Value(FCommandLine::Get(), TEXT("ResX="), ResolutionOverride) && ResolutionOverride > 0)
    {
        Profile.Output.X = ResolutionOverride;
        Profile.bCommandLineResolution = true;
    }
    if (FParse::Value(FCommandLine::Get(), TEXT("ResY="), ResolutionOverride) && ResolutionOverride > 0)
    {
        Profile.Output.Y = ResolutionOverride;
        Profile.bCommandLineResolution = true;
    }

    if (UGameUserSettings* Settings = GEngine ? GEngine->GetGameUserSettings() : nullptr)
    {
        Settings->SetScreenResolution(Profile.Output);
        Settings->SetFullscreenMode(FParse::Param(FCommandLine::Get(), TEXT("windowed"))
            ? EWindowMode::Windowed : EWindowMode::Fullscreen);
        Settings->SetDynamicResolutionEnabled(false);
        Settings->ApplyResolutionSettings(true);
        Settings->SaveSettings();
    }
    SetConsoleInt(TEXT("r.DynamicRes.OperationMode"), 0);
    // Keep output pixels tied to the requested resolution even on a high DPI desktop.
    if (IConsoleVariable* Secondary = IConsoleManager::Get().FindConsoleVariable(TEXT("r.SecondaryScreenPercentage.GameViewport")))
        Secondary->Set(100.f, ECVF_SetByCode);
    if (IConsoleVariable* Percentage = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage")))
        Percentage->Set(Profile.ScreenPercentage, ECVF_SetByCode);

    const bool bSettingsSaved = SaveJson(TEXT("GraphicsSettings.json"), ProfileJson(Profile));
    UE_LOG(LogAstraGraphics, Display, TEXT("Requested=%s actual=%s support=%s DLSS=%d output=%dx%d screenPercentage=%.2f fallback=%s settingsSaved=%d"),
        *Profile.Requested, *Profile.Actual, *Profile.Support, Profile.bDLSSEnabled,
        Profile.Output.X, Profile.Output.Y, Profile.ScreenPercentage, *Profile.FallbackReason, bSettingsSaved);

    if (FParse::Param(FCommandLine::Get(), TEXT("AstraGraphicsTest")))
    {
        IFileManager::Get().Delete(*SavedPath(TEXT("GraphicsValidation.json")));
        IFileManager::Get().Delete(*SavedPath(TEXT("GraphicsValidation.png")));
        TSharedRef<FGraphicsTest, ESPMode::ThreadSafe> Test = MakeShared<FGraphicsTest, ESPMode::ThreadSafe>();
        Test->Profile = Profile;
        Test->World = World;
        Test->Observer = FSceneViewExtensions::NewExtension<FGraphicsViewObserver>(World,
            TWeakPtr<FGraphicsTest, ESPMode::ThreadSafe>(Test));
        Test->ScreenshotHandle = UGameViewportClient::OnScreenshotCaptured().AddSP(Test, &FGraphicsTest::CaptureScreenshot);
        FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Test](float DeltaSeconds)
        {
            return Test->Tick(DeltaSeconds);
        }));
    }
}
