# Mechanical debris source

Six original low-poly parts generated for the small destruction Niagara effect:
hex bolt, hex nut, compression spring, spur gear, washer, and split shaft coupler.
The source scene contains centered export meshes and a separate presentation
collection. The meshes have one material slot and a UV channel. The bolt thread,
nut thread, and gear teeth are simplified for a small VFX particle footprint.
These FBX files are the economical LOD0 meshes; the UE import pipeline generates
the lower distance LODs. Lower tessellation retains the silhouette and bore holes.

| Mesh | LOD0 triangles | Original triangles |
| --- | ---: | ---: |
| Hex bolt | 570 | 1,348 |
| Hex nut | 480 | 1,152 |
| Coil spring | 872 | 2,316 |
| Spur gear | 576 | 1,344 |
| Washer | 192 | 512 |
| Shaft coupler | 540 | 1,052 |
| Total | 3,230 | 7,724 |

The source triangle count is reduced by 58.2%. The bolt has six coarse thread
turns, the nut has a simplified interior groove, and the spring retains six
helical turns with a six-sided wire cross-section. The gear has twelve teeth.
The original maximum dimensions are unchanged. Per-part triangle budgets,
counts, and reductions are recorded in the generated report and checked by the
generator.

Run from the repository root with Blender 4.5:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe' --background --factory-startup --python-exit-code 1 --python AstraNigara\Scripts\build_mechanical_parts.py
```

The script writes `MechanicalParts.blend`, six individual `FBX/SM_*.fbx` files,
`mechanical_parts_report.json`, and `../../Docs/Previews/MechanicalParts_Lineup.png`.
The report records actual geometry dimensions, triangle counts, centered pivots,
material and UV counts. It also validates each exported FBX's unit metadata and
vertex bounds before rendering the preview.

Coordinates are centimeters: Blender's metric scene uses `scale_length=0.01`.
The FBX exporter uses `global_scale=1`, `apply_unit_scale=True`, and
`apply_scale_options='FBX_SCALE_UNITS'`; each FBX reports `UnitScaleFactor=1.0`
(one FBX unit is one centimeter). UE should import with uniform scale **1.0**
and scene unit conversion enabled. Do not add a 100x correction. The meshes use
Z up, and all object rotations/scales are applied before export.

Dimensions range from the 1.7 cm washer to the 3.5 cm bolt. The spring is about
3.4 cm tall. They are visual debris meshes without authored collision hulls or
engineering tolerances. Holes in the nut, washer, gear and coupler are geometry.

![Six mechanical parts](../../Docs/Previews/MechanicalParts_Lineup.png)
