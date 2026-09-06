"""Reimport the exported kit in a disposable Blender session and verify the handoff.

blender -b --factory-startup --python-exit-code 1 --python validate_shoreline_fbx.py
This does not run Unreal or open/save the source .blend.
"""
import hashlib
import json
from pathlib import Path

import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'


def main():
    manifest = json.loads((ART/'Layout'/'shoreline_assets.json').read_text(encoding='utf-8'))
    results = {}
    for name, spec in manifest['assets'].items():
        if hashlib.sha256((ART/spec['file']).read_bytes()).hexdigest() != spec['sha256']:
            raise RuntimeError(f'{name}: FBX changed since manifest generation')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = 1
        bpy.ops.import_scene.fbx(filepath=str(ART/spec['file']), use_anim=False, colors_type='LINEAR')
        objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        if len(objects) != 1: raise RuntimeError(f'{name}: expected one mesh, got {len(objects)}')
        obj = objects[0]
        mesh = obj.data
        points = [obj.matrix_world @ v.co for v in mesh.vertices]
        minimum = [min(v[i] for v in points) for i in range(3)]
        maximum = [max(v[i] for v in points) for i in range(3)]
        error = max(abs(a-b) for side, actual in [('bounds_min_m', minimum), ('bounds_max_m', maximum)]
                    for a, b in zip(actual, spec[side]))
        if error > .0002: raise RuntimeError(f'{name}: FBX units/axes/pivot bounds drift {error}m')
        mesh.calc_loop_triangles()
        if len(mesh.loop_triangles) != spec['triangles']:
            raise RuntimeError(f'{name}: changed triangle count')
        if [m.name for m in mesh.materials] != spec['materials']:
            raise RuntimeError(f'{name}: changed material slots')
        attr = mesh.color_attributes.get('ShoreData')
        if attr is None: raise RuntimeError(f'{name}: lost ShoreData')
        is_bed = spec['metadata']['shore_kind'] in ('low_bank', 'shallow_shelf')
        color_error = 0.0
        for loop in mesh.loops:
            p = points[loop.vertex_index]
            expected = (min(1, max(0, -p.z/1.5)), min(1, max(0, -p.y/4)), 0, 1) if is_bed else (0, 0, 0, 1)
            index = loop.vertex_index if attr.domain == 'POINT' else loop.index
            actual = attr.data[index].color
            color_error = max(color_error, max(abs(a-b) for a, b in zip(actual, expected)))
        if color_error > .004:
            raise RuntimeError(f'{name}: color data changed (linear/sRGB mismatch?), max error {color_error}')
        if not mesh.uv_layers: raise RuntimeError(f'{name}: lost UVs')
        uv = mesh.uv_layers.active
        bad_uv = 0
        for tri in mesh.loop_triangles:
            a, b, c = [uv.data[i].uv for i in tri.loops]
            bad_uv += abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)) < 1e-10
        if bad_uv: raise RuntimeError(f'{name}: degenerate exported UVs: {bad_uv}')
        bm = bmesh.new()
        bm.from_mesh(mesh)
        # FBX may split vertices at UV/normal seams. Weld only for the topology audit.
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
        bad_edges = sum(not e.is_manifold for e in bm.edges)
        bm.free()
        if bad_edges: raise RuntimeError(f'{name}: FBX topology has {bad_edges} non-manifold edges')
        results[name] = {
            'passed': True, 'max_bounds_error_m': error,
            'triangles': len(mesh.loop_triangles), 'materials': [m.name for m in mesh.materials],
            'vertex_color': attr.name, 'vertex_color_domain': attr.domain,
            'max_vertex_color_error': color_error,
            'uv_layer': uv.name, 'non_manifold_edges_after_seam_weld': bad_edges,
        }
    report = {
        'passed': True, 'blender': bpy.app.version_string,
        'scope': 'Fresh Blender FBX reimport: scale, axes, pivot bounds, triangles, material slots, UVs, colors, topology. Unreal import not executed.',
        'assets': results,
    }
    (ART/'Previews'/'Shoreline_FBXValidation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('SHORELINE_FBX_ROUNDTRIP_SUCCESS ' + str(len(results)))


if __name__ == '__main__':
    main()
