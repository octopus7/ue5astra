using UnrealBuildTool;
public class AstraLevelTestEditorTarget : TargetRules
{
    public AstraLevelTestEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("AstraLevelTest");
    }
}
