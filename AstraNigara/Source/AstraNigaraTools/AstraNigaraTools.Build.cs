using System.IO;
using UnrealBuildTool;

public class AstraNigaraTools : ModuleRules
{
    public AstraNigaraTools(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "Niagara" });
        PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "AssetRegistry", "Json", "JsonUtilities", "NiagaraShader", "RenderCore", "RHI" });
        string NiagaraSource = Path.Combine(EngineDirectory, "Plugins", "FX", "Niagara", "Source");
        PrivateIncludePaths.Add(Path.Combine(NiagaraSource, "Niagara", "Internal"));
        PrivateIncludePaths.Add(Path.Combine(NiagaraSource, "NiagaraShader", "Internal"));
    }
}
