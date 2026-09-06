"""Build an independent shoreline mesh kit; never opens or rewrites the game map.

Blender 4.5: blender -b --factory-startup --python build_shoreline_kit.py
Use -- --skip-render for a geometry/export-only rebuild.
Source metres, FBX unit conversion matches build_blender_scene.py.
"""
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / 'Saved' / 'Shoreline'
PALETTE = {
    'M_ShoreSand': 'C6B88D', 'M_ShoreSandLight': 'D2C59A',
    'M_ShoreSandDark': 'B4A681', 'M_ShoreEarth': 'A68B60',
    'M_ShoreEarthLight': 'B69A6A', 'M_ShoreEarthDark': '8E7755',
    'M_ShoreGrass': 'A0AC64', 'M_ShoreGrassLight': 'AFB96D',
    'M_SubmergedStone': 'AAA99A', 'M_SubmergedStoneLight': 'BFBEAE',
    'M_SubmergedStoneDark': '94998E', 'M_ShoreMoss': '8E9F6C',
}


def linear(hex_color):
    def channel(c):
        c = int(c, 16) / 255.0
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    return tuple(channel(hex_color[i:i + 2]) for i in (0, 2, 4))


def make_material(name, hex_color, roughness=.88):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    rgba = (*linear(hex_color), 1)
    mat.diffuse_color = rgba
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = rgba
    bsdf.inputs['Roughness'].default_value = roughness
    return mat


def new_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def move_to(obj, collection):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    collection.objects.link(obj)


def bounds(obj):
    points = [v.co for v in obj.data.vertices]
    minimum = [min(v[i] for v in points) for i in range(3)]
    maximum = [max(v[i] for v in points) for i in range(3)]
    return minimum, maximum


def audit_mesh(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bad_edges = sum(not e.is_manifold for e in bm.edges)
    bad_faces = sum(f.calc_area() < 1e-10 for f in bm.faces)
    volume = bm.calc_volume(signed=True)
    bm.free()
    uv = mesh.uv_layers.get('UVMap')
    degenerate_uv = 0
    if uv:
        for tri in mesh.loop_triangles:
            a, b, c = [uv.data[i].uv for i in tri.loops]
            if abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)) < 1e-10:
                degenerate_uv += 1
    attr = mesh.color_attributes.get('ShoreData')
    minimum, maximum = bounds(obj)
    errors = []
    if bad_edges: errors.append(f'{bad_edges} non-manifold edges')
    if bad_faces: errors.append(f'{bad_faces} zero-area faces')
    if volume <= 0: errors.append('nonpositive signed volume / inverted normals')
    if uv is None: errors.append('missing UVMap')
    if degenerate_uv: errors.append(f'{degenerate_uv} degenerate UV triangles')
    if attr is None: errors.append('missing ShoreData')
    if attr and (attr.domain != 'POINT' or len(attr.data) != len(mesh.vertices)):
        errors.append('invalid ShoreData point count')
    if any(abs(c-1) > 1e-6 for c in obj.scale): errors.append('unapplied scale')
    if any(abs(c) > 1e-6 for c in obj.rotation_euler): errors.append('unapplied rotation')
    if any(abs(c) > 1e-6 for c in obj.location): errors.append('nonzero source location')
    if not all(math.isfinite(c) for v in mesh.vertices for c in v.co):
        errors.append('nonfinite vertex coordinates')
    result = {
        'vertices': len(mesh.vertices), 'triangles': len(mesh.loop_triangles),
        'polygons': len(mesh.polygons), 'material_slots': len(mesh.materials),
        'bounds_min_m': minimum, 'bounds_max_m': maximum,
        'dimensions_m': [b-a for a, b in zip(minimum, maximum)],
        'non_manifold_edges': bad_edges, 'zero_area_faces': bad_faces,
        'degenerate_uv_triangles': degenerate_uv, 'signed_volume_m3': volume,
        'uv_layer': uv.name if uv else None,
        'vertex_color': attr.name if attr else None, 'errors': errors,
    }
    if errors:
        raise RuntimeError(f'{obj.name}: {errors}')
    return result


def export_asset(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = ART / 'Meshes' / 'Shoreline' / f'{obj.name}.fbx'
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y', axis_up='Z', bake_anim=False, add_leaf_bones=False,
        mesh_smooth_type='FACE', use_mesh_modifiers=True, use_custom_props=True,
        colors_type='LINEAR', prioritize_active_color=True,
    )
    return path


def instance(source, name, location, collection, yaw=0, scale=1):
    obj = bpy.data.objects.new(name, source.data)
    collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler.z = math.radians(yaw)
    obj.scale = (scale, scale, scale)
    obj['asset_id'] = source.name
    return obj


def box(name, location, dimensions, material, collection):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    move_to(obj, collection)
    return obj


def label(text, location, size, mat, collection):
    data = bpy.data.curves.new('ReviewLabel', 'FONT')
    data.body = text
    data.align_x = 'CENTER'
    data.size = size
    data.extrude = 0
    obj = bpy.data.objects.new('ReviewLabel_' + text[:30], data)
    collection.objects.link(obj)
    obj.location = location
    data.materials.append(mat)
    return obj


def setup_camera(name, target, width, collection, pitch=58):
    data = bpy.data.cameras.new(name)
    data.type = 'ORTHO'
    data.ortho_scale = width
    data.clip_end = 200
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    target = Vector(target)
    obj.location = target + Vector((0, -math.cos(math.radians(pitch))*35,
                                    math.sin(math.radians(pitch))*35))
    obj.rotation_euler = (target-obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def gallery(lib, audit, mats, collection, helpers):
    paper = make_material('Preview_Paper', 'E9E7DC')
    ink = make_material('Preview_Ink', '3E514D')
    box('PreviewOnly_StudioFloor', (0, 0, -.10), (22, 23, .15), paper, collection)
    slots = [
        ('SM_ShallowShelf_01', (-3.5, 6.5), (0, -.15), '01  SHALLOW SHELF'),
        ('SM_ShallowShelf_Cove_01', (3.5, 6.5), (0, -.15), '02  COVE SHELF'),
        ('SM_ShoreBank_Straight_01', (-4.8, -2.2), (0, -2.1), '03  LOW BANK'),
        ('SM_ShoreBank_Curve_01', (0, -2.2), (0, -2.1), '04  CURVED BANK'),
        ('SM_ShoreBank_Low_01', (4.8, -2.2), (0, -2.1), '05  ERODED BANK'),
        ('SM_SubmergedRock_Round_01', (-4.8, -6.5), (0, -1), '06  ROUND'),
        ('SM_SubmergedRock_Flat_01', (-1.6, -6.5), (0, -1), '07 FLAT'),
        ('SM_SubmergedRock_Small_01', (1.6, -6.5), (0, -1), '08  SMALL'),
        ('SM_SubmergedPebbles_01', (4.8, -6.5), (0, -1), '09  PEBBLES'),
    ]
    for name, (x, y), (_, offset_y), title in slots:
        z = -audit[name]['bounds_min_m'][2]
        instance(lib[name], 'Gallery_' + name, (x, y, z), collection)
        label_y = 0.8 if title.startswith(('01', '02')) else y + offset_y
        label(title, (x, label_y, .015), .23, ink, collection)
        dims = audit[name]['dimensions_m']
        info = f'{dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.2f} m  /  {audit[name]["triangles"]} tris'
        label(info, (x, label_y-.34, .015), .15, ink, collection)
    label('ASTRA  /  LAKESHORE MESH KIT', (0, 10.0, .015), .44, ink, collection)
    label('9 source meshes  -  metres  -  faceted surfaces', (0, 9.2, .015), .23, ink, collection)
    label('BLENDER GEOMETRY REVIEW  /  WATER MATERIAL NOT INCLUDED',
          (0, -9.3, .015), .22, ink, collection)
    return setup_camera('Camera_AssetGallery', (0, .0, .3), 20, helpers)


def make_demo(lib, mats, collection, helpers):
    # Isolated 12m art study; coordinates are not placements in L_AstraWoodland.
    instances = []
    for name, loc, yaw in [
        ('SM_ShallowShelf_01', (-3, 0, 0), 0),
        ('SM_ShallowShelf_Cove_01', (3, 0, 0), 0),
        ('SM_ShoreBank_Straight_01', (-3.9, .10, 0), 0),
        ('SM_ShoreBank_Curve_01', (0, .10, 0), 0),
        ('SM_ShoreBank_Straight_01', (3.9, .10, 0), 0),
    ]:
        instances.append(instance(lib[name], 'Study_' + name, loc, collection, yaw))
    # Seat each stone using a ray cast onto the assembled shelf, not guessed heights.
    bpy.context.view_layer.update()
    shelves = [o for o in instances if 'Shelf' in o.name]
    rock_specs = [
        ('SM_SubmergedRock_Round_01', -4.4, -.8, 24, .8),
        ('SM_SubmergedRock_Flat_01', -3.6, -1.45, -18, 1),
        ('SM_SubmergedPebbles_01', -1.8, -2.2, 11, 1),
        ('SM_SubmergedRock_Small_01', -.5, -.65, 62, 1),
        ('SM_SubmergedRock_Flat_01', 1.8, -1.6, 32, .9),
        ('SM_SubmergedRock_Round_01', 3.8, -1.0, -14, .65),
        ('SM_SubmergedPebbles_01', 4.4, -2.7, 34, .85),
        ('SM_SubmergedRock_Small_01', 2.9, -2.7, 67, .85),
    ]
    for i, (name, x, y, yaw, scale) in enumerate(rock_specs):
        hits = []
        for shelf in shelves:
            inverse = shelf.matrix_world.inverted()
            hit, point, _, _ = shelf.ray_cast(inverse @ Vector((x, y, 3)), Vector((0, 0, -1)))
            if hit: hits.append((shelf.matrix_world @ point).z)
        if not hits: raise RuntimeError(f'No seabed below demo stone {i}')
        z = max(hits) - .035
        instances.append(instance(lib[name], f'Study_Stone_{i:02}', (x, y, z), collection, yaw, scale))
    # Presentation-only ground fill; excluded from the asset and placement manifests.
    # Match each bank's inland back edge. A constant-height block would expose
    # a straight step behind the deliberately lower eroded bank.
    banks = [o for o in instances if 'Bank' in o.name]
    vertices, faces = [], []
    for bank in banks:
        sections = {}
        for vertex in bank.data.vertices:
            if vertex.co.z <= 0:
                continue
            key = round(vertex.co.x, 5)
            if key not in sections or vertex.co.y > sections[key].y:
                sections[key] = vertex.co.copy()
        edge = [bank.matrix_world @ sections[x] for x in sorted(sections)]
        if len(edge) < 2: raise RuntimeError('Missing bank inland top edge')
        for a, b in zip(edge, edge[1:]):
            start = len(vertices)
            vertices.extend([tuple(a), tuple(b), (b.x, 3.7, .37), (a.x, 3.7, .37)])
            faces.append(tuple(range(start, start+4)))
    fill_mesh = bpy.data.meshes.new('PreviewOnly_LandFill')
    fill_mesh.from_pydata(vertices, [], faces)
    fill_mesh.update()
    fill_mesh.materials.append(mats['M_ShoreGrass'])
    fill = bpy.data.objects.new('PreviewOnly_LandFill', fill_mesh)
    collection.objects.link(fill)
    paper = bpy.data.materials['Preview_Paper']
    ink = bpy.data.materials['Preview_Ink']
    box('PreviewOnly_DemoFloor', (0, 0, -1.65), (25, 20, .1), paper, collection)
    label('LAKESHORE  /  DRY GEOMETRY STUDY', (0, 5.35, -.01), .37, ink, collection)
    label('12 m assembly  -  waterline datum Z = 0  -  no water shader',
          (0, -5.8, -1.58), .24, ink, collection)
    records = []
    for obj in instances:
        e = obj.rotation_euler
        records.append({
            'name': obj.name, 'asset': obj['asset_id'], 'group': 'ShorelineStudy',
            'collision': 'none', 'blender_location_m': list(obj.location),
            'blender_rotation_euler_rad': list(e), 'scale': list(obj.scale),
            'ue_location_cm': [obj.location.x*100, -obj.location.y*100, obj.location.z*100],
            'ue_rotation_deg': {'pitch': -math.degrees(e.y), 'yaw': -math.degrees(e.z), 'roll': math.degrees(e.x)},
        })
    return records, setup_camera('Camera_DryShoreStudy', (0, -.2, -.35), 17, helpers)


def main():
    for path in [ART/'Meshes'/'Shoreline', ART/'Blender', ART/'Layout', ART/'Previews', OUT]:
        path.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = .7
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (*linear('B9C4CD'), 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .45
    source = new_collection('01_ShorelineMeshLibrary')
    study = new_collection('02_ShorelineDryStudy')
    display = new_collection('03_ShorelineAssetGallery')
    helpers = new_collection('04_PreviewOnly_CamerasLights')
    mats = {name: make_material(name, color) for name, color in PALETTE.items()}
    lib, audits, assets = {}, {}, {}
    for module_name in ['shoreline_shelf', 'shoreline_bank', 'shoreline_rocks']:
        module = importlib.import_module(module_name)
        for obj in module.build_assets(mats):
            if obj.name in lib: raise RuntimeError('Duplicate asset name: ' + obj.name)
            obj['asset_id'] = obj.name
            move_to(obj, source)
            audits[obj.name] = audit_mesh(obj)
            path = export_asset(obj)
            lib[obj.name] = obj
            assets[obj.name] = {
                'file': path.relative_to(ART).as_posix(), 'collision': 'none',
                'materials': [m.name for m in obj.data.materials],
                'dimensions_m': audits[obj.name]['dimensions_m'],
                'bounds_min_m': audits[obj.name]['bounds_min_m'],
                'bounds_max_m': audits[obj.name]['bounds_max_m'],
                'triangles': audits[obj.name]['triangles'],
                'metadata': {k: obj[k] for k in obj.keys() if k != '_RNA_UI'},
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    if len(lib) != 9: raise RuntimeError(f'Expected 9 meshes, got {len(lib)}')
    cam_gallery = gallery(lib, audits, mats, display, helpers)
    records, cam_study = make_demo(lib, mats, study, helpers)
    bpy.ops.object.light_add(type='SUN', location=(-4, -7, 14))
    sun = bpy.context.object
    sun.name = 'Preview_Sun_SourceAngle50'
    sun.rotation_euler = (math.radians(24), math.radians(-20), math.radians(-25))
    sun.data.energy = 2.2
    sun.data.angle = math.radians(50)
    move_to(sun, helpers)
    manifest = {
        'version': 1, 'kit': 'AstraShoreline', 'units': 'metres', 'ue_units': 'centimetres',
        'axis_mapping': 'UE=(Blender.X,-Blender.Y,Blender.Z)',
        'local_axes': 'Shore runs X; land +Y; lake -Y; bank/shelf waterline Z=0; stones pivot at bottom.',
        'reference': 'Reference/Ref_PinkRoofLakesideHouse.png',
        'palette_srgb_hex': PALETTE, 'assets': assets,
        'shoredata': {'R': 'bank/shelf: clamp(-local_z / 1.5, 0, 1)',
                      'G': 'bank/shelf: clamp(-local_y / 4, 0, 1)',
                      'B': 'reserved 0', 'A': '1',
                      'note': 'Stone RGB is zero. These are local hints, not world water depth or foam masks.'},
        'integration_status': 'Source meshes exported; not imported into Unreal or placed in the live map.',
    }
    (ART/'Layout'/'shoreline_assets.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (ART/'Layout'/'shoreline_demo_layout.json').write_text(json.dumps({
        'version': 1, 'scope': 'Isolated dry study only; not game-map placement.',
        'units': 'metres', 'axis_mapping': manifest['axis_mapping'], 'objects': records,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    validation = {'blender': bpy.app.version_string, 'passed': True, 'assets': audits,
                  'asset_count': len(lib), 'total_triangles': sum(a['triangles'] for a in audits.values()),
                  'scope': 'Blender mesh topology, UVs, transforms, FBX export. Unreal import not executed.'}
    (ART/'Previews'/'Shoreline_MeshValidation.json').write_text(json.dumps(validation, indent=2), encoding='utf-8')
    source.hide_render = True
    source.hide_viewport = True
    study.hide_render = True
    study.hide_viewport = True
    scene.camera = cam_gallery
    bpy.ops.object.select_all(action='DESELECT')
    # Store an immediately usable material-preview viewport as well as render cameras.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
    bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'AstraShorelineKit.blend'))
    if '--skip-render' not in sys.argv:
        scene.render.filepath = str(ART/'Previews'/'Blender_ShorelineKit.png')
        bpy.ops.render.render(write_still=True)
        display.hide_render = True
        study.hide_render = False
        study.hide_viewport = False
        scene.camera = cam_study
        scene.render.resolution_y = 1400
        scene.render.filepath = str(ART/'Previews'/'Blender_ShorelineDryStudy.png')
        bpy.ops.render.render(write_still=True)
    print('SHORELINE_BUILD_SUCCESS ' + json.dumps({'assets': len(lib), 'triangles': validation['total_triangles']}))


if __name__ == '__main__':
    main()
