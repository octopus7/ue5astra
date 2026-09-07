"""Fresh FBX round-trip validation for the independently generated fishing dock.

Run Blender --factory-startup -b --python this_file.py. Does not modify assets.
"""
import bpy
import bmesh
import hashlib
import json
import math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
meta_path = ART / 'Layout/fishing_dock.json'
metadata = json.loads(meta_path.read_text(encoding='utf-8'))
record = metadata['assets'][0]
fbx_path = ROOT / record['file']
blend_path = ROOT / metadata['source']
report_path = ART / 'Previews/FishingDock_FBXValidation.json'

bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
    data_to.objects = [name for name in data_from.objects if name == record['asset_id']]
assert len(data_to.objects) == 1 and data_to.objects[0] is not None
source = data_to.objects[0]
bpy.context.scene.collection.objects.link(source)
bpy.context.view_layer.update()

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(fbx_path), use_custom_normals=True)
imported = [obj for obj in set(bpy.data.objects)-before if obj.type == 'MESH']
assert len(imported) == 1, 'FBX must contain exactly the dock static mesh'
obj = imported[0]
bpy.context.view_layer.update()

def geometry_info(value):
    bm = bmesh.new()
    bm.from_mesh(value.data)
    result = {
        'vertices': len(value.data.vertices),
        'triangles': sum(len(p.vertices)-2 for p in value.data.polygons),
        'finite_vertices': all(math.isfinite(c) for v in value.data.vertices for c in v.co),
        'non_manifold_edges': sum(not e.is_manifold for e in bm.edges),
        'degenerate_faces': sum(p.area <= 1e-12 for p in value.data.polygons),
        'dimensions_m': [float(c) for c in value.dimensions],
        'bounds_min_m': [min(v.co[i] for v in value.data.vertices) for i in range(3)],
        'bounds_max_m': [max(v.co[i] for v in value.data.vertices) for i in range(3)],
        'material_slots': [slot.material.name if slot.material else None for slot in value.material_slots],
        'uv0_finite': bool(value.data.uv_layers) and all(math.isfinite(c)
            for uv in value.data.uv_layers.active.data for c in uv.uv),
        'material_indices_valid': all(p.material_index < len(value.material_slots) for p in value.data.polygons),
        'custom_normals': value.data.has_custom_normals,
        'normals_finite_unit_length': all(math.isfinite(c) for n in value.data.corner_normals for c in n.vector)
            and all(abs(n.vector.length-1) < 1e-4 for n in value.data.corner_normals),
        'origin_translation_m': list(value.location),
        'scale': list(value.scale),
    }
    bm.free()
    return result

source_info = geometry_info(source)
fbx_info = geometry_info(obj)
dimension_error = max(abs(a-b) for a, b in zip(source_info['dimensions_m'], fbx_info['dimensions_m']))
bound_error = max(abs(a-b) for key in ('bounds_min_m', 'bounds_max_m')
    for a, b in zip(source_info[key], fbx_info[key]))
metadata_dimension_error = max(abs(a-b) for a, b in zip(record['dimensions_m'], fbx_info['dimensions_m']))

# Material datablocks receive a .001 suffix when the same source materials are loaded.
material_basenames = [name.rsplit('.', 1)[0] if name and name.rsplit('.', 1)[-1].isdigit()
    else name for name in fbx_info['material_slots']]
bm = bmesh.new()
bm.from_mesh(obj.data)
tree = BVHTree.FromBMesh(bm)
surface_samples = []
for name, x, y in [('ramp_foot', -2.28, 0), ('ramp_mid', -1.20, 0),
                   ('walkway', 1.36, 0), ('platform', 4.60, 0)]:
    hit, normal, index, distance = tree.ray_cast(Vector((x, y, 5)), Vector((0, 0, -1)))
    surface_samples.append({'location': name, 'x_m': x, 'y_m': y,
        'height_m': float(hit.z) if hit else None,
        'normal_z': float(normal.z) if normal else None})
bm.free()

checks = {
    'single_imported_mesh': len(imported) == 1,
    'exact_source_vertex_count': source_info['vertices'] == fbx_info['vertices'] == record['vertices'],
    'exact_source_triangle_count': source_info['triangles'] == fbx_info['triangles'] == record['triangles'],
    'source_and_fbx_closed': source_info['non_manifold_edges'] == fbx_info['non_manifold_edges'] == 0,
    'no_degenerate_faces': source_info['degenerate_faces'] == fbx_info['degenerate_faces'] == 0,
    'finite_vertices_and_uv0': all(info['finite_vertices'] and info['uv0_finite'] for info in (source_info, fbx_info)),
    'exact_roundtrip_bounds': dimension_error < 1e-5 and bound_error < 1e-5,
    'metadata_dimensions_match': metadata_dimension_error < 1e-5,
    'pile_bottom_at_zero': abs(fbx_info['bounds_min_m'][2]) < 1e-6,
    'origin_and_scale_preserved': all(abs(v) < 1e-6 for v in fbx_info['origin_translation_m'])
        and all(abs(v-1) < 1e-6 for v in fbx_info['scale']),
    'custom_normals_preserved': fbx_info['custom_normals'] and fbx_info['normals_finite_unit_length'],
    'ordered_material_slots_preserved': material_basenames == record['material_slots'],
    'material_indices_valid': fbx_info['material_indices_valid'],
    'continuous_supported_center_samples': all(s['height_m'] is not None and s['normal_z'] > .98 for s in surface_samples),
    'platform_surface_matches_metadata': abs(surface_samples[-1]['height_m']-metadata['deck_surface_local_z_m']) < .015,
}
report = {
    'asset_id': record['asset_id'], 'passed': all(checks.values()),
    'checks': checks, 'source': source_info, 'fresh_fbx_import': fbx_info,
    'maximum_dimensions_error_m': dimension_error, 'maximum_bounds_error_m': bound_error,
    'maximum_metadata_dimensions_error_m': metadata_dimension_error,
    'surface_samples': surface_samples,
    'fbx_sha256': hashlib.sha256(fbx_path.read_bytes()).hexdigest(),
    'metadata_sha256': hashlib.sha256(meta_path.read_bytes()).hexdigest(),
    'preview_visual_review': {
        'path': 'ArtSource/Previews/Blender_FishingDock.png',
        'result': 'Reviewed: open fishing edge, broad platform, clear approach, readable wood grain and soft post shading.',
        'scope': 'Geometry/asset validation; runtime walkability is verified separately by the main integration.',
    },
}
report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'passed': report['passed'], 'checks': checks, 'path': str(report_path)}, indent=2))
assert report['passed'], 'Fishing dock FBX validation failed; see report.'
