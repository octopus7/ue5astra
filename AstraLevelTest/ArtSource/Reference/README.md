# Astra art direction

Generated with the built-in image generation tool; these are target references, not Unreal screenshots.

- `Astra_TargetGameplay.png`: a fixed 58-degree orthographic gameplay view, upright box-built white/orange/charcoal calico cat, warm ochre trail, olive and sage low-poly woodland, mossy angular rocks, warm afternoon light.
- `Astra_TargetOverview.png`: expanded approximately 100 x 100 metre layout with a central clearing, woodland paths, a jade lake with lotus and reeds, an outflow stream, an intact wooden bridge, a separate collapsed bridge, and a ruined timber cabin.

Implementation workflow: build mesh assets and arrange the scene in Blender; export FBX assets, JSON object transforms, and the terrain height data; reconstruct the terrain as a native Unreal Landscape and apply the extracted arrangement. Configure water, lighting, collision, WASD movement, and a fixed camera in Unreal Engine 5.7.

Large readable shapes and restrained painted textures take precedence over close-up detail. The two reference images establish direction; the final interactive level will have its own real-time rendering.

Individual modeling references are saved as `Ref_Oak`, `Ref_Fir`, `Ref_MossRock`, `Ref_Lotus`, `Ref_Reeds`, `Ref_BridgeIntact`, `Ref_BridgeBroken`, `Ref_CabinRuin`, and `Ref_CalicoCat` PNG files. The generation prompt set is recorded in `GENERATION_PROMPTS.md`.

Generated production textures are saved in `../Textures/T_ForestFloor.png` and `../Textures/T_AnimeSkyReflection.png`. The cloud image is used on the actual sky dome. The latest direction excludes sky/cloud reflections from the lake and creek and permits a dedicated reflection illusion for the small puddles.

`Ref_PinkRoofLakesideHouse.png` is the separate modeling reference for a pink-roof house on the right/eastern side of the lake, with its front door facing the game camera and a well in the front yard. The sheet includes front, side, and top views. Its prompt is saved in `PINK_HOUSE_PROMPT.md`. The Blender models have been imported and placed in Unreal; `../Previews/UE_House.png` shows the actual engine result.
