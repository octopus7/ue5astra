# Astra art direction

Generated with the built-in image generation tool; these are target references, not Unreal screenshots.

- `Astra_TargetGameplay.png`: a fixed 58-degree orthographic gameplay view, upright box-built white/orange/charcoal calico cat, warm ochre trail, olive and sage low-poly woodland, mossy angular rocks, warm afternoon light.
- `Astra_TargetOverview.png`: expanded approximately 100 x 100 metre layout with a central clearing, woodland paths, a jade lake with lotus and reeds, an outflow stream, an intact wooden bridge, a separate collapsed bridge, and a ruined timber cabin.

Implementation workflow: build mesh assets and arrange the scene in Blender; export FBX assets, JSON object transforms, and the terrain height data; reconstruct the terrain as a native Unreal Landscape and apply the extracted arrangement. Configure water, lighting, collision, WASD movement, and a fixed camera in Unreal Engine 5.7.

Large readable shapes and restrained painted textures take precedence over close-up detail. The two reference images establish direction; the final interactive level will have its own real-time rendering.

Individual modeling references are saved as `Ref_Oak`, `Ref_Fir`, `Ref_MossRock`, `Ref_Lotus`, `Ref_Reeds`, `Ref_BridgeIntact`, `Ref_BridgeBroken`, `Ref_CabinRuin`, and `Ref_CalicoCat` PNG files. The generation prompt set is recorded in `GENERATION_PROMPTS.md`.

Generated production textures are saved in `../Textures`: `T_ForestFloor.png`, `T_AnimeSkyReflection.png`, `T_ForestCliffPaint.png`, `T_AnimeSkyPanorama.png`, `T_AnimeForestRockPaint.png`, and `T_FishingDockWood.png`. The panorama is used on the actual sky dome. The earlier cloud illustration and puddle illusion are preserved as historical work; the current puddle material reflects the actual sky and environment. The latest direction excludes sky/cloud reflections from the lake and creek.

`Ref_PinkRoofLakesideHouse.png` is the separate modeling reference for a pink-roof house on the right/eastern side of the lake, with its front door facing the game camera and a well in the front yard. The sheet includes front, side, and top views. Its prompt is saved in `PINK_HOUSE_PROMPT.md`. The Blender models have been imported and placed in Unreal; `../Previews/UE_House.png` shows the actual engine result.

`Ref_ForestCliffs.png`, `Ref_ForestTent.png`, `Ref_ForestSignpost.png`, and `Ref_ForestCooking.png` are separate forest expansion references. Each prompt is saved in its corresponding `FOREST_*_PROMPT.md`. The actual Blender asset sheets are saved in `../Previews/Blender_Forest*.png` and the placed Unreal campsite in `../Previews/UE_Camp.png`.

`SKY_PANORAMA_PROMPT.md` records the full built-in image generation prompt and the spherical mapping/compositing method for the replacement sky.

`../Textures/T_AnimeForestRockPaint.png` is the generated albedo for the smooth forest boulders. `FOREST_SMOOTH_ROCK_TEXTURE_PROMPT.md` preserves the prompt and quality notes. The native output is 1254×1254 and is saved without artificial upscaling; UE generates mipmaps through its power-of-two texture setting.

`Ref_FracturedForestRocks.png` is the later shape revision: five broad-faced, split or layered forest boulders with softly beveled edges instead of rounded pebbles. `FRACTURED_FOREST_ROCKS_PROMPT.md` preserves its full ImageGen prompt. The original painted albedo remains in use. Actual models and UE results are separate files: `../Previews/Blender_FracturedForestRocks.png` and `../Previews/UE_Rocks.png`.

## Fishing and daily-life references

Four additional built-in ImageGen reference sheets guide the 15 new assets. Each original PNG is saved in this directory; these images describe the modeling target rather than the implemented Unreal scene.

| Reference image | Contents | Saved prompt |
| --- | --- | --- |
| `Ref_FishingDock.png` | Timber pier, sloping approach, deep piles, broad platform and open fishing edge | `FISHING_DOCK_PROMPT.md` |
| `Ref_FishingProps.png` | Rod stand, fishing chair, fish bucket and open tackle box | `FISHING_PROPS_PROMPT.md` |
| `Ref_HomeLifeProps.png` | Clothesline, vegetable patch, watering tools, boots and broom, herb drying rack | `HOME_LIFE_PROPS_PROMPT.md` |
| `Ref_WoodlandLifeProps.png` | Axe and chopping stump, foraging basket, picnic blanket and meal, bridge repair supplies, wooden handcart | `WOODLAND_LIFE_PROPS_PROMPT.md` |

`../Textures/T_FishingDockWood.png` is the separately generated painted honey-oak albedo for the dock planks. `FISHING_DOCK_WOOD_PROMPT.md` records the full prompt: continuous vertical grain, restrained knots and warm variation, with no plank borders, nails or baked directional lighting. UVs align the grain with individual timbers.

The four source files are `../Blender/FishingDock.blend`, `FishingProps.blend`, `HomeLifeProps.blend` and `WoodlandLifeProps.blend`. Their matching metadata files live in `../Layout`. Actual Blender model previews use the `../Previews/Blender_FishingDock.png`, `Blender_FishingProps.png`, `Blender_HomeLifeProps.png` and `Blender_WoodlandLifeProps.png` names. In-engine presentation images are recorded separately as `UE_Fishing.png`, `UE_HomeLife.png`, `UE_Picnic.png` and `UE_Repair.png`; engine validation status is documented in the project `VALIDATION.md`.

## Starfall second level

Four new built-in ImageGen references are saved in `Starfall`: `Ref_StarfallOverview.png`, `Ref_StarfallSpaceship.png`, `Ref_StarfallTrees.png`, and `Ref_StarfallFungiSpring.png`. A fifth generated image, `../Textures/Starfall/T_SF_ShipPaint.png`, is the production hull albedo. All five exact generation prompts are preserved in [GENERATION_PROMPTS.md](Starfall/GENERATION_PROMPTS.md).

The water reflection material and sky are reused from the woodland level. New Blender source kits are `StarfallSpaceship.blend`, `StarfallTrees.blend`, and `StarfallFungiSpring.blend`; their assembled placement is `AstraStarfall.blend`. Actual engine screenshots are named `UE_SF*.png` and `UE_Demo_SF*.png`, and are distinct from these generated references. See [Starfall level documentation](../../Docs/StarfallLevel.md).
