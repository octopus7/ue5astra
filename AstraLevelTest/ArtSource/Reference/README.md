# Astra art direction

Generated with the built-in image generation tool; these are target references, not Unreal screenshots.

- `Astra_TargetGameplay.png`: a fixed 58-degree orthographic gameplay view, upright box-built white/orange/charcoal calico cat, warm ochre trail, olive and sage low-poly woodland, mossy angular rocks, warm afternoon light.
- `Astra_TargetOverview.png`: expanded approximately 100 x 100 metre layout with a central clearing, woodland paths, a jade lake with lotus and reeds, an outflow stream, an intact wooden bridge, a separate collapsed bridge, and a ruined timber cabin.

Implementation workflow: build mesh assets and arrange the scene in Blender; export FBX assets, JSON object transforms, and the terrain height data; reconstruct the terrain as a native Unreal Landscape and apply the extracted arrangement. Configure water, lighting, collision, WASD movement, and a fixed camera in Unreal Engine 5.7.

Large readable shapes and restrained painted textures take precedence over close-up detail. The two reference images establish direction; the final interactive level will have its own real-time rendering.
