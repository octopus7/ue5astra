"""Fresh-process FBX round trip for the four terrain-fitted shoreline assets.

blender -b --factory-startup --python-exit-code 1 --python this_file.py
Reads the saved review library as the exact vertex/UV/colour reference. Never
regenerates assets, writes FBX, or saves any Blender scene.
"""
import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
REPORT = ART / 'Previews' / 'ShorelineSite_FBXValidation.json'


def snapshot(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    points = [tuple(obj.matrix_world @ v.co) for v in mesh.vertices]
    attr = mesh.color_attributes['ShoreData']
    uv = mesh.uv_layers['UVMap']
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    triangles = {}
    for tri in mesh.loop_triangles:
        key = tuple(sorted(tri.vertices))
        triangles[key] = {}
        for loop_index in tri.loops:
            vertex_index = mesh.loops[loop_index].vertex_index
            colour_index = vertex_index if attr.domain == 'POINT' else loop_index
            triangles[key][vertex_index] = {
                'uv': tuple(uv.data[loop_index].uv),
                'colour': tuple(attr.data[colour_index].color),
                'normal': tuple((normal_matrix @ mesh.corner_normals[loop_index].vector).normalized())}
    return {'points': points, 'triangles': triangles,
            'materials': [m.name for m in mesh.materials],
            'smooth_face_count': sum(face.use_smooth for face in mesh.polygons),
            'bounds_min': [min(v[a] for v in points) for a in range(3)],
            'bounds_max': [max(v[a] for v in points) for a in range(3)]}


def verify_asset(name, spec, source):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    bpy.ops.import_scene.fbx(filepath=str(ART/spec['file']), use_anim=False, colors_type='LINEAR')
    objects = [obj for obj in scene.objects if obj.type == 'MESH']
    assert len(objects) == 1, f'Expected one mesh, got {len(objects)}'
    obj = objects[0]
    mesh = obj.data
    mesh.calc_loop_triangles()
    points = [tuple(obj.matrix_world @ v.co) for v in mesh.vertices]
    actual_min = [min(v[a] for v in points) for a in range(3)]
    actual_max = [max(v[a] for v in points) for a in range(3)]
    dimensions = [b-a for a, b in zip(actual_min, actual_max)]
    dimensions_error = max(abs(a-b) for a, b in zip(dimensions, spec['dimensions_m']))
    bounds_error = max(abs(a-b) for actual, expected in (
        (actual_min, source['bounds_min']), (actual_max, source['bounds_max']))
        for a, b in zip(actual, expected))
    assert dimensions_error < .0002, f'Dimension/units drift {dimensions_error} m'
    assert bounds_error < .0002, f'Axis/pivot bounds drift {bounds_error} m'
    assert len(mesh.loop_triangles) == spec['validation']['triangles'], 'Triangle count changed'
    materials = [m.name for m in mesh.materials]
    assert materials == spec['materials'] == source['materials'], 'Material slots changed'
    attr = mesh.color_attributes.get('ShoreData')
    assert attr is not None, 'ShoreData lost'
    uv = mesh.uv_layers.get('UVMap')
    assert uv is not None, 'UVMap lost'

    # FBX can duplicate a geometric vertex at a UV/normal seam. Match each
    # imported world-space point to the saved local/pivot-space source point.
    nearest = []
    vertex_error = 0.0
    for point in points:
        index, squared = min(((i, sum((a-b)**2 for a, b in zip(point, original)))
                              for i, original in enumerate(source['points'])), key=lambda item: item[1])
        nearest.append(index)
        vertex_error = max(vertex_error, squared**.5)
    assert vertex_error < .0002, f'Vertex/axis/unit drift {vertex_error} m'
    uv_error = colour_error = normal_angle_error = 0.0
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    bad_uv = 0
    for tri in mesh.loop_triangles:
        source_triangle = tuple(sorted(nearest[index] for index in tri.vertices))
        assert source_triangle in source['triangles'], 'Triangle topology changed'
        a, b, c = [uv.data[i].uv for i in tri.loops]
        bad_uv += abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)) < 1e-10
        for loop_index in tri.loops:
            vertex_index = mesh.loops[loop_index].vertex_index
            expected = source['triangles'][source_triangle][nearest[vertex_index]]
            uv_error = max(uv_error, max(abs(a-b) for a, b in zip(uv.data[loop_index].uv, expected['uv'])))
            colour_index = vertex_index if attr.domain == 'POINT' else loop_index
            colour_error = max(colour_error, max(abs(a-b) for a, b in zip(attr.data[colour_index].color, expected['colour'])))
            actual_normal = (normal_matrix @ mesh.corner_normals[loop_index].vector).normalized()
            dot = sum(a*b for a,b in zip(actual_normal, expected['normal']))
            normal_angle_error = max(normal_angle_error, math.degrees(math.acos(max(-1.0,min(1.0,dot)))))
    assert bad_uv == 0, f'Degenerate UV triangles: {bad_uv}'
    assert uv_error < .0002, f'UV data changed: {uv_error}'
    assert colour_error < .004, f'Colour data changed: {colour_error}'
    assert normal_angle_error < .15, f'Authored corner normals changed: {normal_angle_error} degrees'
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(obj.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    bad_edges = sum(not e.is_manifold for e in bm.edges)
    bad_faces = sum(f.calc_area() < 1e-10 for f in bm.faces)
    volume = bm.calc_volume(signed=True)
    bm.free()
    assert bad_edges == bad_faces == 0, f'Invalid topology: edges={bad_edges}, faces={bad_faces}'
    assert volume > 0, f'Inverted/zero signed volume: {volume}'
    volume_error = abs(volume-spec['validation']['signed_volume_m3'])
    assert volume_error < max(1e-5, volume*1e-5), f'Volume changed: {volume_error}'
    blue_values = [entry.color[2] for entry in attr.data]
    return {'passed': True, 'file': spec['file'],
            'fbx_sha256': hashlib.sha256((ART/spec['file']).read_bytes()).hexdigest(),
            'dimensions_m': dimensions, 'max_dimensions_error_m': dimensions_error,
            'bounds_min_m': actual_min, 'bounds_max_m': actual_max,
            'max_bounds_error_m': bounds_error, 'max_vertex_position_error_m': vertex_error,
            'triangles': len(mesh.loop_triangles), 'materials': materials,
            'uv_layer': uv.name, 'max_uv_error': uv_error, 'degenerate_uv_triangles': bad_uv,
            'vertex_color': attr.name, 'vertex_color_domain': attr.domain,
            'vertex_color_type': attr.data_type, 'max_vertex_color_error': colour_error,
            'blue_channel_range': [min(blue_values),max(blue_values)],
            'blue_intermediate_corner_count': sum(0.0<b<1.0 for b in blue_values),
            'blue_distinct_values_6dp': len({round(b,6) for b in blue_values}),
            'source_smooth_face_count': source['smooth_face_count'],
            'imported_smooth_face_count': sum(face.use_smooth for face in mesh.polygons),
            'max_loop_normal_angle_error_deg': normal_angle_error,
            'imported_has_custom_normals': mesh.has_custom_normals,
            'non_manifold_edges_after_seam_weld': bad_edges, 'zero_area_faces': bad_faces,
            'signed_volume_m3': volume, 'volume_error_m3': volume_error}


def main():
    manifest_path = ART/'Layout'/'shoreline_site.json'
    blend_path = ART/'Blender'/'AstraLakeshoreReview.blend'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    specs = {name: spec for name, spec in manifest['assets'].items()
             if spec['file'].startswith('Meshes/ShorelineSite/')}
    assert len(specs) == 4, f'Expected four site FBX assets, got {len(specs)}'
    protected = [manifest_path, blend_path]+[ART/spec['file'] for spec in specs.values()]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(blend_path), link=False) as (src, dst):
        assert all(name in src.objects for name in specs), 'Review blend missing source asset'
        dst.objects = list(specs)
    sources = {obj.name: snapshot(obj) for obj in dst.objects}
    results = {}
    for name, spec in specs.items():
        try:
            results[name] = verify_asset(name, spec, sources[name])
        except Exception as exc:
            results[name] = {'passed': False, 'error': str(exc)}
    unchanged = all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p)] for p in protected)
    report = {'passed': unchanged and all(r['passed'] for r in results.values()),
              'blender': bpy.app.version_string,
              'scope': 'Fresh Blender FBX import; compare exact saved review geometry, dimensions, pivot/axes/units, triangle topology, material slots, loop UVs, ShoreData, authored loop normals and smooth-face counts, welded manifold topology and positive signed volume. UE validation is separate.',
              'reference_blend': blend_path.relative_to(ART).as_posix(),
              'source_files_unchanged': unchanged, 'assets': results}
    REPORT.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('SHORELINE_SITE_FBX_ROUNDTRIP '+json.dumps(report))
    if not report['passed']:
        raise RuntimeError('Site FBX validation failed; see '+str(REPORT))


if __name__ == '__main__':
    main()
