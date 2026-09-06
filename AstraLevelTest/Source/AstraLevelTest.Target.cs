using UnrealBuildTool;
public class AstraLevelTestTarget : TargetRules
{
    public AstraLevelTestTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("AstraLevelTest");
    }
}
