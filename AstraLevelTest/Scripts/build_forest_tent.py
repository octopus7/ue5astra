"""Build standalone forest tent, bedroll and satchel; metres, front -X.

Run Blender --background --factory-startup --python this_file.py.
Writes only the independent ForestTent source, three FBXs, metadata and preview.
"""
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
for folder in ('Blender', 'Meshes', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_ForestTentMeshLibrary')
presentation = bpy.data.collections.new('02_AssetPresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)

PALETTE = {
    'M_TentCanvas': 'E4D5AC', 'M_TentCanvasLight': 'EEE0BC',
    'M_TentCanvasFold': 'CBBD98', 'M_TentSage': '929B75',
    'M_TentSageLight': 'A5AB85', 'M_TentOchre': 'B48B48',
    'M_TentWood': '806342', 'M_TentWoodDark': '5E4D3C',
    'M_TentRope': 'C1AA7D', 'M_TentInside': '4F6777',
    'M_CampLeather': '84613E', 'M_CampLeatherLight': 'A27A4D',
    'M_CampBuckle': 'B4AA83', 'M_CampRollDark': '657758',
}

def linear(v):
    return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4

materials = {}
for name, value in PALETTE.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    color = tuple(linear(int(value[i:i+2], 16)/255) for i in (0, 2, 4))
    mat.diffuse_color = (*color, 1)
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .84
    if name == 'M_CampBuckle':
        shader.inputs['Roughness'].default_value = .48
        shader.inputs['Metallic'].default_value = .25
    materials[name] = mat

def finish(obj, material):
    obj.data.materials.append(materials[material])
    return obj

def mesh(name, vertices, faces, material):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return finish(obj, material)

def cube(name, center, size, material, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('BroadFacetedCorners', 'BEVEL')
        mod.width = min(bevel, min(size)*.42)
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(obj, material)

def cylinder(name, a, b, radius, material, vertices=8):
    direction = Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
        depth=direction.length, location=(Vector(a)+Vector(b))/2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return finish(obj, material)

def solid_grid(name, rows, offset, material, side_material=None):
    """Close a rectangular curved cloth grid with a matching inner surface."""
    height, width = len(rows), len(rows[0])
    top = [point for row in rows for point in row]
    n = len(top)
    vertices = top + [tuple(Vector(point)+Vector(offset)) for point in top]
    faces = []
    for r in range(height-1):
        for c in range(width-1):
            a = r*width+c
            faces.append((a, a+1, a+width+1, a+width))
    top_count = len(faces)
    faces += [tuple(index+n for index in reversed(face)) for face in list(faces)]
    boundary = list(range(width)) + [r*width+width-1 for r in range(1, height)]
    boundary += list(range((height-1)*width+width-2, (height-1)*width-1, -1))
    boundary += [r*width for r in range(height-2, 0, -1)]
    for a, b in zip(boundary, boundary[1:]+boundary[:1]):
        faces.append((a, b, b+n, a+n))
    obj = mesh(name, vertices, faces, material)
    if side_material:
        obj.data.materials.append(materials[side_material])
        for face in obj.data.polygons[top_count:]:
            face.material_index = 1
    return obj

def torus(name, center, major, minor, material, rotation=(0, 0, 0), major_segments=16):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
        major_segments=major_segments, minor_segments=6, location=center, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    return finish(obj, material)

def asset(name, parts):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    minimum_z = min(vertex.co.z for vertex in obj.data.vertices)
    for vertex in obj.data.vertices:
        vertex.co.z -= minimum_z
    obj.data.update()
    # A proper UV map is retained for lightmap generation and future fabric treatments.
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.025)
    bpy.ops.object.mode_set(mode='OBJECT')
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    library.objects.link(obj)
    obj['asset_id'] = name
    obj['collision'] = 'complex'
    obj['front_axis'] = '-X'
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{name}.fbx'),
        use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
        bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE', use_mesh_modifiers=True)
    obj.hide_render = True
    obj.hide_set(True)
    return obj

# The roof is one thick curved sheet per side, each with broad fabric color panels.
parts = []
for sign in (-1, 1):
    rows = []
    for t in (0, .10, .53, .94, 1):
        row = []
        for x in (-1.75, -1.43, 0, 1.43, 1.75):
            sag = .09*(1-abs(x)/1.75)*math.sin(math.pi*t)
            row.append((x, sign*(1.5*t), 2.4*(1-t)+.10*t-sag))
        rows.append(row)
    obj = solid_grid('CanvasRoof', rows, (0, 0, -.035), 'M_TentCanvas', 'M_TentInside')
    for mat in ('M_TentSage', 'M_TentOchre', 'M_TentCanvasLight', 'M_TentCanvasFold'):
        obj.data.materials.append(materials[mat])
    for r in range(4):
        for c in range(4):
            obj.data.polygons[r*4+c].material_index = 3 if r == 3 else (2 if c in (0, 3) else (4 if (r+c)%3 == 0 else 0))
    parts.append(obj)

# Closed triangular rear end, and a blue cloth floor visible through the open entrance.
rear = [(1.72, -1.47, .095), (1.72, 1.47, .095), (1.72, 0, 2.37)]
parts.append(mesh('ClosedRearCanvas', rear+[(x-.035, y, z) for x, y, z in rear],
    [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], 'M_TentSage'))
parts.append(cube('Groundsheet', (0, 0, .03), (3.38, 2.80, .06), 'M_TentInside', .018))
for sign in (-1, 1):
    # Gathered open flaps, with generous clearance at the bottom and gentle broad folds.
    rows = []
    for z, outer, inner, bulge in ((.105, 1.46, .89, .01), (.71, 1.06, .77, .095),
                                 (1.39, .62, .30, .12), (2.25, .082, .018, .01)):
        rows.append([(-1.77, sign*outer, z), (-1.85-bulge, sign*(outer+inner)/2, z),
                     (-1.80, sign*inner, z)])
    flap = solid_grid('TiedOpenEntranceFlap', rows, (.033, 0, 0), 'M_TentCanvasLight', 'M_TentCanvasFold')
    parts.append(flap)
    # Soft ochre hem at the flap foot, actual thickness so no two-sided collision surfaces.
    parts.append(solid_grid('DoorHem', [rows[0], [(x, y, z+.105) for x, y, z in rows[0]]],
        (.020, 0, 0), 'M_TentOchre'))
    parts.append(cylinder('FlapTie', (-1.985, sign*.745, .72), (-1.90, sign*1.065, .73), .030, 'M_TentRope'))

# A-frame poles run along the entrance sides and leave its center open.
for x in (-1.79, 1.79):
    for sign in (-1, 1):
        parts.append(cylinder('WoodenAFrame', (x, sign*1.48, .068), (x, -sign*.085, 2.52), .067, 'M_TentWood'))
    parts.append(torus('RidgeLashing', (x, 0, 2.397), .109, .026, 'M_TentRope', (0, math.pi/2, 0), 12))
parts.append(cylinder('WoodenRidgePole', (-1.96, 0, 2.415), (1.96, 0, 2.415), .092, 'M_TentWoodDark', 10))
for sign in (-1, 1):
    parts.append(cylinder('LowerCanvasHem', (-1.76, sign*1.50, .087), (1.76, sign*1.50, .087), .035, 'M_TentOchre'))
    for end in (-1, 1):
        stake = (end*2.18, sign*2.05, .13)
        parts.append(cylinder('GroundPeg', (stake[0]-.035*end, stake[1], .045),
            (stake[0]+.04*end, stake[1], .36), .055, 'M_TentWood', 7))
        parts.append(cylinder('CornerGuyRope', (end*1.72, sign*1.46, .15), stake, .018, 'M_TentRope', 6))
        parts.append(cylinder('UpperGuyRope', (end*1.76, sign*.66, 1.40),
            (stake[0], stake[1], .26), .017, 'M_TentRope', 6))
        parts.append(torus('PegRopeLoop', (stake[0]+.016*end, stake[1], .25), .060, .017, 'M_TentRope', major_segments=10))
tent = asset('SM_ForestTent', parts)

# Bedroll: low-sided cylinder, closed end rings and substantial straps/handle.
parts = [cylinder('RolledBlanket', (0, -.53, .31), (0, .53, .31), .31, 'M_TentSage', 14)]
for sign in (-1, 1):
    for radius in (.24, .15, .060):
        parts.append(torus('RolledClothEnd', (0, sign*.537, .31), radius, .025,
                           'M_CampRollDark', (math.pi/2, 0, 0), 14))
    parts.append(torus('BedrollLeatherStrap', (0, sign*.345, .31), .313, .035,
                       'M_CampLeather', (math.pi/2, 0, 0), 14))
    parts.append(cube('BedrollStrapBuckle', (-.27, sign*.345, .50), (.060, .145, .105), 'M_CampBuckle', .012))
    parts.append(cube('BedrollBuckleTongue', (-.309, sign*.345, .50), (.022, .065, .066), 'M_CampLeather'))
parts += [cube('BedrollHandleSide', (0, y, .67), (.075, .075, .18), 'M_CampLeather', .016) for y in (-.23, .23)]
parts.append(cube('BedrollCarryHandle', (0, 0, .75), (.078, .52, .080), 'M_CampLeatherLight', .022))
bedroll = asset('SM_CampBedroll', parts)

# Satchel: broad faceted fabric body, folded cream flap and two substantial front straps.
parts = [cube('SatchelBody', (0, 0, .38), (.44, .75, .76), 'M_TentSage', .075),
         cube('SatchelLid', (-.08, 0, .72), (.40, .77, .22), 'M_TentCanvas', .075),
         cube('SatchelFoldedFlap', (-.228, 0, .57), (.082, .68, .39), 'M_TentCanvasLight', .055)]
for sign in (-1, 1):
    parts.append(cube('SatchelBottomCorner', (-.172, sign*.30, .11), (.17, .13, .19), 'M_TentOchre', .027))
    parts.append(cube('SatchelFrontStrap', (-.288, sign*.236, .41), (.039, .068, .60), 'M_CampLeather', .010))
    parts.append(cube('SatchelStrapTop', (-.013, sign*.236, .821), (.50, .065, .023), 'M_CampLeather'))
    parts.append(cube('SatchelStrapBuckle', (-.319, sign*.236, .45), (.037, .121, .13), 'M_CampBuckle', .009))
    parts.append(cube('SatchelBuckleCenter', (-.344, sign*.236, .45), (.020, .065, .078), 'M_CampLeather'))
    parts.append(cylinder('SatchelHandleArm', (.025, sign*.15, .80), (.025, sign*.15, .94), .030, 'M_CampLeather', 7))
parts.append(cylinder('SatchelCarryHandle', (.025, -.15, .94), (.025, .15, .94), .037, 'M_CampLeatherLight', 8))
# Rear strap connects as independent closed solids; all front -X views read the buckled face.
for y in (-.24, .24):
    parts.append(cube('SatchelRearStrap', (.229, y, .41), (.055, .061, .54), 'M_CampLeather', .010))
satchel = asset('SM_CampSatchel', parts)

def asset_metadata(obj):
    bounds = [Vector(corner) for corner in obj.bound_box]
    assert all(math.isfinite(value) for vertex in obj.data.vertices for value in vertex.co)
    assert min(v.z for v in bounds) >= -.00001, 'Ground-origin asset extends below ground'
    bad_faces = [(face.index, face.area, [tuple(obj.data.vertices[i].co) for i in face.vertices])
                 for face in obj.data.polygons if face.area <= 1e-9]
    assert not bad_faces, f'Degenerate mesh face {obj.name}: {bad_faces[:3]}'
    assert all(slot.material and slot.material.name in PALETTE for slot in obj.material_slots)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    open_edges = sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert open_edges == 0, 'Each solid must be closed'
    uv = obj.data.uv_layers.active
    assert uv and len(uv.data) == len(obj.data.loops)
    assert all(math.isfinite(c) for item in uv.data for c in item.uv)
    return {
        'asset_id': obj.name, 'file': f'ArtSource/Meshes/{obj.name}.fbx',
        'collision': 'complex', 'front_axis_blender': '-X', 'origin': 'ground at (0, 0, 0)',
        'dimensions_m': [round(v, 6) for v in obj.dimensions],
        'bounds_min_m': [round(min(v[i] for v in bounds), 6) for i in range(3)],
        'bounds_max_m': [round(max(v[i] for v in bounds), 6) for i in range(3)],
        'vertices': len(obj.data.vertices),
        'triangles': sum(len(face.vertices)-2 for face in obj.data.polygons),
        'material_slots': [slot.material.name for slot in obj.material_slots],
        'validation': {'finite_vertices': True, 'ground_origin': True,
            'degenerate_faces': 0, 'non_manifold_edges': open_edges, 'uv_layers': len(obj.data.uv_layers),
            'finite_uvs': True},
    }

asset_objects = [tent, bedroll, satchel]
metadata = {
    'source': 'ArtSource/Blender/ForestTent.blend', 'script': 'Scripts/build_forest_tent.py',
    'reference': 'ArtSource/Reference/Ref_ForestTent.png', 'units': 'metres',
    'unreal_conversion': '(Blender X, -Blender Y, Blender Z) * 100; yaw negated',
    'palette_srgb_hex': PALETTE,
    'material_properties': {name: {'roughness': .48 if name == 'M_CampBuckle' else .84,
        'metallic': .25 if name == 'M_CampBuckle' else 0.0} for name in PALETTE},
    'assets': [asset_metadata(obj) for obj in asset_objects],
    'placement_notes': 'Front local -X faces the fixed camera. Tent body 3.5 x 3.0 m; keep 0.6 m outside full guy-rope footprint clear and preserve 1.6 m central front approach. Place fire at least 3 m from the canvas. Bedroll and satchel separate; use 1 m and 0.7 m side clearances.',
    'entry': {'front_axis': '-X', 'decorative_opening': True, 'minimum_ground_width_m': 1.78,
        'groundsheet_top_m': .06, 'note': 'Exterior gameplay prop; interior access not required.'},
    'topology': 'Cloth grids have a 0.035 m enclosed thickness; ropes/poles/accessories are closed solids. No fine surface texture.',
}
assert sum(item['triangles'] for item in metadata['assets']) < 10000

# FBX round trip catches incorrect export units, missing UVs and slot order changes.
for original, entry in zip(asset_objects, metadata['assets']):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.fbx(filepath=str(ART/'Meshes'/f'{original.name}.fbx'))
    imported = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    assert len(imported) == 1
    clone = imported[0]
    assert max(abs(clone.dimensions[i]-original.dimensions[i]) for i in range(3)) < .0001
    assert len(clone.data.uv_layers) >= 1
    assert [slot.material.name.split('.')[0] for slot in clone.material_slots] == [slot.material.name for slot in original.material_slots]
    entry['validation']['fbx_roundtrip_bounds_m'] = [round(v, 6) for v in clone.dimensions]
    entry['validation']['fbx_roundtrip_uvs'] = True
    entry['validation']['fbx_roundtrip_material_slots'] = True
    for imported_obj in list(bpy.context.selected_objects):
        bpy.data.objects.remove(imported_obj, do_unlink=True)
(ART/'Layout'/'forest_tent.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')

# Render the tent and companions with the real asset geometry, using the fixed game angle.
for original, name, location in ((tent, 'Preview_ForestTent', (.7, .5, 0)),
                                (bedroll, 'Preview_CampBedroll', (-2.2, -1.7, 0)),
                                (satchel, 'Preview_CampSatchel', (-2.1, -.15, 0))):
    obj = bpy.data.objects.new(name, original.data)
    presentation.objects.link(obj)
    obj.location = location
ground_mat = bpy.data.materials.new('TentPreviewGround')
ground_mat.diffuse_color = (.23, .30, .16, 1)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.045))
ground = bpy.context.object
ground.name = 'PreviewGround'
ground.data.materials.append(ground_mat)
for collection in list(ground.users_collection):
    collection.objects.unlink(ground)
presentation.objects.link(ground)
bpy.ops.object.light_add(type='SUN', location=(-6, -7, 12))
sun = bpy.context.object
sun.name = 'SoftSun_50deg'
sun.rotation_euler = (math.radians(24), math.radians(-20), math.radians(-35))
sun.data.energy = 2.5
sun.data.color = (1.0, .91, .79)
sun.data.angle = math.radians(50)
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.49, .66, .86, 1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .48
target = Vector((.05, .35, .66))
horizontal = Vector((-1, -.65, 0)).normalized()*8
bpy.ops.object.camera_add(location=target+horizontal+Vector((0, 0, 8*math.tan(math.radians(58)))))
camera = bpy.context.object
camera.name = 'ForestTentPreviewCamera_58deg'
camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 10.2
scene.camera = camera
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(ART/'Previews'/'Blender_ForestTent.png')
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.film_transparent = False
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'ForestTent.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA FOREST TENT ASSETS COMPLETE '+json.dumps(metadata['assets']))
