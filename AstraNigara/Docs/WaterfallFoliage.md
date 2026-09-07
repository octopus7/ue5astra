# Waterfall meadow foliage

The waterfall meadow uses three original Blender grass clumps planted with native Unreal Foliage. Existing moss, ferns, flowers and shrubs remain part of the scene.

## Art and movement

- Tuft: 8 curved blades, 80 triangles. Fan: 10 lower spreading blades, 100 triangles. Sedge: 6 taller narrow blades, 60 triangles.
- Each blade has a raised middle rib and tapered silhouette, giving broad directional facets rather than a flat grass card. A tuft's blades lean together; nearby instances share a gently changing heading.
- Vertex Color R stores the exact root-to-tip weight from 0 to 1. WPO is multiplied by `pow(R, 1.8)`, so roots remain fixed. A traveling world-space gust moves groups together, with low-amplitude per-blade flutter.
- Material color changes in coherent world-space patches between jade, olive and yellow-green. Fine per-instance and per-blade variation sits inside these larger patches. Roots darken; tips and blade ridges catch stylized highlights.
- Grass is actual geometry, without a texture alpha card. Masked material opacity is used only for Foliage distance fading.

## Placement and cost

The seeded sampler plants 855 clumps: 441 tufts, 316 fans and 98 sedges. All instances visible at once total 72,760 source triangles. They use three `FoliageType_InstancedStaticMesh` assets and native `InstancedFoliageActor` instances, rather than individual actors.

Placement follows the irregular ground island, excluding the pool and bank rocks with a 224 × 187 cm ellipse centered at `(0, 50)`. The central cliff footprint is also excluded. Roots sit at the ground height of −13 cm, at least 7.2 cm apart; density and headings vary smoothly by location. Foreground blades are shorter to preserve the pool silhouette.

Foliage fades between 1,300 and 2,200 cm, with WPO disabled beyond 2,000 cm. The showcase camera is roughly 1,000 cm away, so nearby grass retains its full silhouette. Collision and shadow casting are disabled to match the existing unlit anime scene. Mesh bounds include the approximately 4 cm wind displacement.

## Rebuilding

1. Run Blender 4.5 with `--background --factory-startup --python Scripts/build_waterfall_foliage_blender.py`.
2. Open `/Game/Maps/L_AnimeWaterfall` in UE 5.7.
3. Run `py "D:/github/ue5astra/AstraNigara/Scripts/build_waterfall_foliage.py"` in the UE console.

The editor script replaces only its three owned FoliageTypes, preserving other foliage. It imports FBX vertex colors, creates `/Game/VFX/Waterfall/Foliage/M_WF_GrassWind`, and saves the level. `WindStrengthCm` (3.8) and `WindSpeed` (1.1) are material parameters.

`Saved/waterfall_foliage_report.json` records actual component instance counts, asset paths and triangle totals after successful editor verification. Blender source dimensions, UV and wind-channel checks are in `ArtSource/WaterfallFoliage/foliage_manifest.json`. The Blender preview is `ArtSource/WaterfallFoliage/GrassClumps.png`.

Native API evidence for the UE 5.7 implementation is in `Engine/Source/Runtime/Foliage/Public/InstancedFoliageActor.h`: `AddInstances` and `RemoveAllInstances` are editor-only `BlueprintCallable` functions. `FoliageType.h` exposes culling and WPO settings, and `FoliageEdit/Private/FoliageTypeFactory.h` provides the instanced static mesh FoliageType asset factory.
