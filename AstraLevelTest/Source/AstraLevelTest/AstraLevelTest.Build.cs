using UnrealBuildTool;
public class AstraLevelTest : ModuleRules
{
    public AstraLevelTest(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] {"Core", "CoreUObject", "Engine", "InputCore", "Landscape"});
        PrivateDependencyModuleNames.AddRange(new [] {"DLSSBlueprint", "RenderCore", "RHI", "Renderer", "Json"});
        if (Target.bBuildEditor)
            PrivateDependencyModuleNames.AddRange(new [] {"UnrealEd", "LandscapeEditor", "Foliage"});
    }
}
