# Small destruction

UE 5.7, 1 Unreal unit = 1cm. The one-shot asset is `/Game/VFX/SmallDestruction/NS_SmallDestruction`; its presentation variant loops every 2 seconds. Both contain four editable Lightweight Niagara emitters.

| Emitter | Burst | Lifetime | Appearance |
| --- | ---: | --- | --- |
| Debris | 14 | 0.38–0.48s | Irregularly scaled 1.2–3.3cm cube fragments, random orientation and angular velocity, gravity |
| Flame | 9 | 0.16–0.28s | Soft procedural orange/yellow additive burst, shrinking and fading |
| Smoke | 11 at 0.045s | 0.75–1.05s | Dark translucent puffs, rising, growing and fading |
| Distortion | 2 | 0.20–0.32s | Actual 2D-offset refraction, radial distortion fading with particle alpha |

The particles' configured movement and sizes keep this preset within a sub-meter region at actor scale 1.0. Fixed bounds are ±49cm on every axis; bounds alone are culling metadata and do not physically constrain particles. The showcase's gold rim is 100cm in diameter; the floor and backdrop grid spacing is 10cm. The floor lines also make heat refraction easier to inspect.

This is a visual effect preset. Debris uses short ballistic motion and has no collision, bounce, damage, or Chaos geometry fracture. Re-scaling the actor or editing spawn size/velocity can exceed the intended scale. Materials use procedural expressions, so no external image downloads are required.

The one-shot's visible particles finish by approximately 1.095 seconds and its Niagara system completes at approximately 2 seconds. The looping variant starts a new burst every 2 seconds.

`AstraNigaraTools` is an editor-only authoring module. It clones the engine's FountainLightweight system, replaces its emitters/renderers, writes explicit spawn/distribution values, and compiles Niagara. `Scripts/build_small_destruction.py` creates the materials and map; it does not rebuild the original fountain map.

The status bridge runs locally inside Unreal. `check_editor.ps1 -Screenshot -NiagaraAgeSeconds 0.15` temporarily seeks editor-world Niagara components to that age, captures the rendered viewport, then restores their update modes. This captures the viewport rather than Windows editor panels. Use 0.15 seconds for the initial burst and 0.6 seconds for smoke. Generated reports and captures are stored under `Saved/`, which is ignored by Git.

Validated with UE 5.7.4: the editor module builds, both saved systems report `valid` and `ready_to_run`, and the reloaded map references the looping system. `Scripts/validate_small_destruction.py` also checks all four emitter names, burst settings, loop behavior, mesh/material references and refraction mode. The live editor reports its current map, active Niagara component and fresh heartbeat through `Scripts/check_editor.ps1`.

Real Unreal viewport captures (1280×720), with matching [validation evidence](Previews/Validation.json):

Initial burst at 0.15 seconds:

![Small destruction burst](Previews/SmallDestruction_Burst.png)

Smoke at 0.6 seconds:

![Small destruction smoke](Previews/SmallDestruction_Smoke.png)
