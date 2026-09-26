using UnrealBuildTool;
public class SoftbodyTarget : TargetRules
{
    public SoftbodyTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("Softbody");
    }
}
