using UnrealBuildTool;
public class Softbody : ModuleRules
{
    public Softbody(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "ProceduralMeshComponent" });
        PrivateDependencyModuleNames.AddRange(new[] { "Json", "RenderCore", "RHI" });
    }
}
