using UnrealBuildTool;
public class SoftbodyEditorTarget : TargetRules
{
    public SoftbodyEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("Softbody");
    }
}
