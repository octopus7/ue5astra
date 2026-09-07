# BeastCrossing

UE 5.7 Blueprint/content-only project. Open `BeastCrossing.uproject`.
Default editor and game map: `/Game/Maps/L_Main`.

Pending work: [Ocean-based realistic sea, an island-crossing creek and generated textures](Docs/PENDING_WORK.md).
Status: waiting for the user's instruction to resume; documentation only for now.

The main level now contains the first modeled island environment: sand beach,
grass, layered northern plateau, paths/plaza/stairs, three cottages, a dock,
fences/benches/mailboxes, trees/flowers/rocks, ocean and daylight.
The default GameModeBase provides the engine's flying default pawn for basic
preview from the plaza. Character controls and interaction systems are not built.

Art direction: an original cozy Animal Crossing-inspired island modeled in Blender.
Image generation is permitted for both references and production textures;
the previous reference-only restriction has been superseded by the user's instruction.
Texture generation and application are pending, as recorded above. Three parallel agents authored
the terrain, village and nature modules. All in-game models are real meshes with
solid-color materials in the current first pass. The ocean material uses procedural world-space waves.

Editable sources: `Art/Blender/terrain.blend`, `village.blend`, `nature.blend`.
Combined Blender scene: `Art/Blender/BeastCrossing_Island.blend`.
Actual model previews and engine validation: `Art/Previews/`.
Reference and exact image prompt: `Art/References/`.

The first pass imports three mesh assemblies into `/Game/Island/Meshes`, with
material slots preserved. For object-level changes, edit the modular Blender
sources and re-export. Collision uses the triangles of the static environment;
production LODs, instancing and simplified collision remain a later optimization.

Rebuild with Blender 4.5 background mode: run `Scripts/Blender/build_terrain.py`,
`build_village.py`, and `build_nature.py`, then `assemble_island.py`.
Run `Scripts/import_island.py` through UE's Python commandlet to update `L_Main`;
run `Scripts/verify_island.py` to reload and check saved mesh scale/materials.
`Scripts/capture_island.py` runs in a rendering editor process to capture the level.
For sandboxed commandlets or rendering, use `-ddc=BeastLocalDDC`; this optional
profile reads the bundled engine cache and writes cache data inside this project.

`Scripts/create_main_level.py` is the original one-time bootstrap; it refuses to
overwrite an existing map. The initial map backup and generated engine files are
under `Saved` and ignored by Git. No external textures or asset downloads are needed.
