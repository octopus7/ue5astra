using UnrealBuildTool;

public class AstraNigaraEditorTarget : TargetRules
{
    public AstraNigaraEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("AstraNigaraTools");
    }
}
