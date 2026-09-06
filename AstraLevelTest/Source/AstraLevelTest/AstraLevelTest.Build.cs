using UnrealBuildTool;
public class AstraLevelTest : ModuleRules
{
    public AstraLevelTest(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] {"Core", "CoreUObject", "Engine", "InputCore", "Landscape"});
        if (Target.bBuildEditor)
            PrivateDependencyModuleNames.AddRange(new [] {"UnrealEd", "LandscapeEditor"});
    }
}
