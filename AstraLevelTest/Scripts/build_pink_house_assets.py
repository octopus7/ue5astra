"""Build the pink lakeside cottage and separate front-yard well from the saved reference.

Run: blender --background --factory-startup --python this_file.py
Local front is -X, Z is up, metres. Unreal layout conversion is (X, -Y, Z) * 100.
Only the independent PinkHouseAssets source, two FBXs, metadata and preview are written.
"""
import bpy
import bmesh
import json
import math
import random
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
R = random.Random(718)
for folder in ('Blender', 'Meshes', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_PinkHouseMeshLibrary')
presentation = bpy.data.collections.new('02_AssetPresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)

PALETTE = {
    'M_Wood': 'A77C45', 'M_WoodLight': 'BF975B', 'M_WoodDark': '715232',
    'M_Stone': '838780', 'M_StoneLight': 'A0A293', 'M_Moss': '788747',
    'M_CottageCream': 'E8D8AC', 'M_CottageCreamLight': 'F3E6C5',
    'M_CottagePink': 'E891AE', 'M_CottagePinkLight': 'F2ABC1',
    'M_CottagePinkDark': 'C87996', 'M_CottageGlass': '689FA9',
    'M_CottageDoor': '815532', 'M_CottageRope': 'C9AE77',
    'M_WellWater': '315C63',
}


def linear(v):
    return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4


materials = {}
for name, value in PALETTE.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    color = tuple(linear(int(value[i:i+2], 16) / 255) for i in (0, 2, 4))
    mat.diffuse_color = (*color, 1)
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .86
    if name in ('M_CottageGlass', 'M_WellWater'):
        shader.inputs['Roughness'].default_value = .22
        shader.inputs['Metallic'].default_value = .2
    materials[name] = mat


def finish(obj, material):
    obj.data.materials.append(materials[material])
    return obj


def cube(name, center, size, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, material)


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


def bar(name, a, b, width, depth, material):
    direction = Vector(b) - Vector(a)
    obj = cube(name, (Vector(a) + Vector(b)) / 2,
               (width, depth, direction.length), material)
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return obj


def cylinder(name, a, b, radius, material, vertices=10):
    direction = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
        depth=direction.length, location=(Vector(a) + Vector(b)) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return finish(obj, material)


def panel(name, corners, thickness, material):
    # Closed low-poly roof panel, with its thickness extending beneath the surface.
    verts = list(corners) + [(x, y, z-thickness) for x, y, z in corners]
    return mesh(name, verts,
        [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
         (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], material)


def arch_slab(name, x, width, bottom, straight_top, peak, depth, material):
    yz = [(-width/2, bottom), (width/2, bottom),
          (width/2, straight_top), (.36*width, peak-.12),
          (0, peak), (-.36*width, peak-.12), (-width/2, straight_top)]
    n = len(yz)
    verts = [(xx, y, z) for xx in (x, x+depth) for y, z in yz]
    faces = [tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    return mesh(name, verts, faces, material)


def triangular_prism(name, face, offset, material):
    verts = list(face) + [tuple(Vector(v)+Vector(offset)) for v in face]
    return mesh(name, verts, [(0, 2, 1), (3, 4, 5),
        (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)], material)


def wedge(name, r_inner, r_outer, a, b, bottom, top, material, center=(0, 0)):
    points = [(center[0]+radius*math.cos(angle), center[1]+radius*math.sin(angle), z)
              for z in (bottom, top) for radius, angle in
              ((r_inner, a), (r_outer, a), (r_outer, b), (r_inner, b))]
    return mesh(name, points, [(0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], material)


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
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    library.objects.link(obj)
    obj['asset_id'] = name
    obj['collision'] = 'complex'
    obj['front_axis'] = '-X'
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{name}.fbx'),
        use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
        bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE',
        use_mesh_modifiers=True)
    obj.hide_render = True
    obj.hide_set(True)
    return obj


# Cottage: facade faces -X. A side-to-side main ridge supports the small front gable.
p = []
p.append(cube('Foundation', (0, 0, .28), (4.1, 5.35, .56), 'M_Stone'))
p.append(cube('CreamWalls', (0, 0, 1.965), (4.1, 5.35, 2.81), 'M_CottageCream'))
for y in (-2.68, 2.68):
    for x in (-1.63, -.81, 0, .81, 1.63):
        p.append(cube('FoundationSideStone', (x, y, .26), (.77, .16, .43),
                      'M_StoneLight' if R.random() < .38 else 'M_Stone'))
for x in (-2.06, 2.06):
    for y in (-2.25, -1.37, -.48, .48, 1.37, 2.25):
        p.append(cube('FoundationFrontStone', (x, y, .26), (.16, .82, .43),
                      'M_StoneLight' if R.random() < .38 else 'M_Stone'))
for x in (-2.10, 2.10):
    for y in (-2.68, 2.68):
        p.append(cube('CornerTimber', (x, y, 1.99), (.23, .23, 2.88), 'M_Wood'))
    p.append(cube('WallTopBeam', (x, 0, 3.33), (.23, 5.54, .22), 'M_WoodDark'))
    p.append(cube('WallBottomBeam', (x, 0, .64), (.20, 5.5, .16), 'M_Wood'))
for y in (-2.71, 2.71):
    p.append(cube('SideTopBeam', (0, y, 3.33), (4.27, .18, .22), 'M_Wood'))
    p.append(triangular_prism('SideGableCream', [(-2.15, y, 3.34), (2.15, y, 3.34),
        (0, y, 5.05)], (0, -.12 if y > 0 else .12, 0), 'M_CottageCreamLight'))
    p.append(bar('GableUpright', (0, y-.035, 3.38), (0, y-.035, 4.98), .14, .16, 'M_Wood'))
    for sign in (-1, 1):
        p.append(bar('SideGableBrace', (sign*1.64, y, 3.40), (0, y, 4.8), .12, .14, 'M_Wood'))

# Front windows and side windows: blue panes, thick surrounds and wide mullions.
for y in (-1.73, 1.73):
    p.append(cube('WindowDarkRecess', (-2.092, y, 2.02), (.12, 1.11, 1.20), 'M_WoodDark'))
    p.append(cube('WindowGlass', (-2.165, y, 2.02), (.035, .91, 1.0), 'M_CottageGlass'))
    for yy in (y-.53, y+.53):
        p.append(cube('WindowFrame', (-2.20, yy, 2.02), (.14, .12, 1.20), 'M_Wood'))
    for zz in (1.45, 2.59):
        p.append(cube('WindowFrame', (-2.20, y, zz), (.14, 1.18, .13), 'M_WoodLight'))
    p.append(cube('WindowMullion', (-2.20, y, 2.02), (.11, .075, 1.03), 'M_Wood'))
    p.append(cube('WindowMullion', (-2.20, y, 2.02), (.11, 1.02, .075), 'M_Wood'))
    p.append(cube('WindowSill', (-2.27, y, 1.40), (.33, 1.22, .12), 'M_WoodLight'))
for y in (-2.695, 2.695):
    sign = -1 if y < 0 else 1
    p.append(cube('SideWindowRecess', (.48, y, 2.00), (1.14, .11, 1.22), 'M_WoodDark'))
    p.append(cube('SideGlass', (.48, y+sign*.065, 2.0), (.94, .035, 1.02), 'M_CottageGlass'))
    for x in (-.07, 1.03):
        p.append(cube('SideFrame', (x, y+sign*.12, 2.00), (.12, .16, 1.23), 'M_Wood'))
    for z in (1.42, 2.58):
        p.append(cube('SideFrame', (.48, y+sign*.12, z), (1.23, .16, .12), 'M_WoodLight'))
    p.append(cube('SideMullion', (.48, y+sign*.12, 2.0), (.075, .12, 1.05), 'M_Wood'))
    p.append(cube('SideMullion', (.48, y+sign*.12, 2.0), (1.02, .12, .075), 'M_Wood'))

# Closed decorative door with a two-metre-plus clear visual opening.
p.append(arch_slab('DoorArchSurround', -2.20, 1.79, .56, 2.58, 3.01, .18, 'M_WoodLight'))
p.append(arch_slab('DoorRecess', -2.25, 1.50, .56, 2.52, 2.88, .08, 'M_WoodDark'))
p.append(arch_slab('DoorLeaf', -2.285, 1.36, .59, 2.48, 2.79, .07, 'M_CottageDoor'))
for y in (-.51, -.25, .02, .29, .55):
    p.append(cube('DoorPlankSeam', (-2.325, y, 1.54), (.014, .019, 1.87), 'M_WoodDark'))
p.append(cube('DoorDiamondFrame', (-2.33, 0, 2.43), (.055, .34, .34), 'M_WoodDark', (math.pi/4, 0, 0)))
p.append(cube('DoorDiamondGlass', (-2.365, 0, 2.43), (.021, .25, .25), 'M_CottageGlass', (math.pi/4, 0, 0)))
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.064, location=(-2.39, .45, 1.61))
p.append(finish(bpy.context.object, 'M_WoodLight'))

# Roof underlay and broad individual shingles. Eaves run along +/-X.
roof_ridge = 5.12
roof_eave = 3.33
roof_half = 2.44
for sign in (-1, 1):
    p.append(panel('PinkRoofUnderlay', [(0, -2.99, roof_ridge), (sign*roof_half, -2.99, roof_eave),
        (sign*roof_half, 2.99, roof_eave), (0, 2.99, roof_ridge)], .15, 'M_CottagePinkDark'))
    for row in range(5):
        a, b = row/5, (row+1)/5
        x0, x1 = sign*(a*roof_half+.008), sign*(b*roof_half-.008)
        z0, z1 = roof_ridge-a*(roof_ridge-roof_eave)+.065, roof_ridge-b*(roof_ridge-roof_eave)+.065
        for column in range(7):
            y0 = -2.96+column*(5.92/7)+.012
            y1 = -2.96+(column+1)*(5.92/7)-.012
            color = R.choice(['M_CottagePink']*5 + ['M_CottagePinkLight', 'M_CottagePinkDark'])
            p.append(panel('PinkRoofShingle', [(x0, y0, z0), (x1, y0, z1),
                (x1, y1, z1), (x0, y1, z0)], .072, color))
    p.append(cube('RoofEaveFascia', (sign*2.47, 0, 3.31), (.17, 6.1, .22), 'M_WoodDark'))
    for y in (-3.01, 3.01):
        p.append(bar('RoofBargeBoard', (0, y, 5.21), (sign*2.50, y, 3.27), .17, .20, 'M_WoodLight'))
p.append(cube('PinkRidgeCap', (0, 0, 5.19), (.22, 6.04, .18), 'M_CottagePinkLight'))

# Projecting front gable/porch canopy, matching the reference's friendly triangular face.
p.append(triangular_prism('FrontGableFace', [(-2.62, -1.10, 2.87), (-2.62, 1.10, 2.87),
    (-2.62, 0, 4.05)], (.12, 0, 0), 'M_CottageCreamLight'))
for sign in (-1, 1):
    p.append(panel('PorchPinkRoof', [(-3.12, 0, 4.10), (-3.12, sign*1.27, 2.90),
        (-1.03, sign*1.27, 3.55), (-1.03, 0, 4.75)], .14, 'M_CottagePink'))
    p.append(bar('PorchBargeBoard', (-3.13, 0, 4.14), (-3.13, sign*1.31, 2.88), .17, .20, 'M_WoodLight'))
    p.append(bar('FrontGableBrace', (-2.66, sign*.91, 2.97), (-2.66, 0, 3.91), .10, .12, 'M_Wood'))
p.append(bar('PorchRidgeCap', (-3.15, 0, 4.16), (-1.01, 0, 4.81), .13, .16, 'M_CottagePinkLight'))
p.append(cube('FrontGableTie', (-2.67, 0, 2.99), (.14, 2.20, .13), 'M_Wood'))

# Porch and 14 cm risers; center approach is 1.76 m wide and unobstructed.
p.append(cube('PorchBase', (-2.62, 0, .28), (1.18, 2.12, .56), 'M_Stone'))
for index in range(6):
    p.append(cube('PorchFloorboard', (-2.62, -.89+index*.355, .555), (1.18, .335, .07), 'M_Wood'))
for index in range(3):
    top = .14*(index+1)
    p.append(cube('LowEntryStep', (-3.84+index*.30, 0, top/2), (.33, 1.76, top),
                  'M_StoneLight' if index%2 == 0 else 'M_Stone'))
for y in (-1.03, 1.03):
    for x in (-3.14, -2.20):
        p.append(cube('PorchRailPost', (x, y, .98), (.16, .16, .87), 'M_Wood'))
        p.append(cube('PostCap', (x, y, 1.43), (.22, .22, .10), 'M_WoodLight'))
    p.append(cube('PorchSideRail', (-2.67, y, 1.35), (.95, .14, .12), 'M_WoodLight'))

# Low chimney with open dark top, clear in the top-down silhouette.
p.append(cube('ChimneyStack', (.96, 1.59, 4.69), (.56, .62, 1.18), 'M_Stone'))
for x in (.65, 1.27):
    p.append(cube('ChimneyRim', (x, 1.59, 5.36), (.15, .77, .21), 'M_StoneLight'))
for y in (1.275, 1.905):
    p.append(cube('ChimneyRim', (.96, y, 5.36), (.56, .14, .21), 'M_StoneLight'))
p.append(cube('ChimneyOpening', (.96, 1.59, 5.29), (.43, .46, .035), 'M_WoodDark'))
house = asset('SM_PinkRoofHouse', p)

# Separate low-poly open well with staggered stone courses and a hanging wooden bucket.
p = []
for row in range(3):
    for index in range(12):
        start = (index+(row%2)*.5)*math.tau/12+.012
        end = start+math.tau/12-.024
        mat = 'M_Moss' if row < 2 and R.random() < .22 else R.choice(['M_Stone', 'M_StoneLight'])
        p.append(wedge('WellStone', .70, .98 + (.06 if row == 2 else 0), start, end,
            row*.285, (row+1)*.285-.012, mat))
p.append(cylinder('WellDarkWater', (0, 0, .09), (0, 0, .115), .705, 'M_WellWater', 24))
for y in (-1.03, 1.03):
    p.append(cube('WellUpright', (0, y, 1.25), (.22, .24, 2.50), 'M_Wood'))
    p.append(cube('WellPostCap', (0, y, 2.52), (.27, .29, .10), 'M_WoodLight'))
p.append(cylinder('WellWindingAxle', (0, -1.24, 2.22), (0, 1.24, 2.22), .12, 'M_WoodLight', 10))
for y in (-.16, -.08, 0, .08, .16):
    bpy.ops.mesh.primitive_torus_add(major_segments=12, minor_segments=5, major_radius=.136,
        minor_radius=.023, location=(0, y, 2.22), rotation=(math.pi/2, 0, 0))
    obj = bpy.context.object
    obj.name = 'AxleRopeCoil'
    p.append(finish(obj, 'M_CottageRope'))
p.append(cylinder('HangingRope', (-.11, 0, 2.17), (-.11, 0, 1.55), .020, 'M_CottageRope', 6))
p.append(bar('WinchHandle', (0, -1.29, 2.22), (-.26, -1.29, 1.95), .075, .075, 'M_WoodDark'))
p.append(cylinder('WinchGrip', (-.26, -1.25, 1.95), (-.26, -1.47, 1.95), .064, 'M_Wood', 8))
bucket_center = (-.11, 0)
for index in range(10):
    a = index*math.tau/10+.015
    b = (index+1)*math.tau/10-.015
    p.append(wedge('BucketStave', .195, .24, a, b, 1.05, 1.40,
        'M_Wood' if index%3 else 'M_WoodLight', bucket_center))
for z in (1.10, 1.34):
    for index in range(10):
        p.append(wedge('BucketHoop', .239, .259, index*math.tau/10,
            (index+1)*math.tau/10, z, z+.038, 'M_WoodDark', bucket_center))
p.append(cylinder('BucketBottom', (-.11, 0, 1.052), (-.11, 0, 1.08), .20, 'M_WoodDark', 10))
for sign in (-1, 1):
    p.append(cylinder('BucketHandle', (-.11, sign*.225, 1.34), (-.11, 0, 1.57), .024, 'M_CottageRope', 6))
well = asset('SM_FrontWell', p)


def asset_metadata(obj):
    bounds = [Vector(corner) for corner in obj.bound_box]
    assert all(math.isfinite(value) for vertex in obj.data.vertices for value in vertex.co)
    assert min(v.z for v in bounds) >= -.00001, 'Ground-origin asset extends below ground'
    assert all(face.area > 0 for face in obj.data.polygons), 'Degenerate mesh face'
    assert all(slot.material and slot.material.name in PALETTE for slot in obj.material_slots)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    open_edges = sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert open_edges == 0, 'Every individual solid must have closed collision faces'
    return {
        'asset_id': obj.name,
        'file': f'ArtSource/Meshes/{obj.name}.fbx',
        'collision': 'complex',
        'front_axis_blender': '-X',
        'origin': 'ground at (0, 0, 0)',
        'dimensions_m': [round(v, 6) for v in obj.dimensions],
        'bounds_min_m': [round(min(v[i] for v in bounds), 6) for i in range(3)],
        'bounds_max_m': [round(max(v[i] for v in bounds), 6) for i in range(3)],
        'vertices': len(obj.data.vertices),
        'triangles': sum(len(face.vertices)-2 for face in obj.data.polygons),
        'material_slots': [slot.material.name for slot in obj.material_slots],
        'validation': {'finite_vertices': True, 'ground_origin': True,
                       'degenerate_faces': 0, 'non_manifold_edges': open_edges},
    }


metadata = {
    'source': 'ArtSource/Blender/PinkHouseAssets.blend',
    'script': 'Scripts/build_pink_house_assets.py',
    'reference': 'ArtSource/Reference/Ref_PinkRoofLakesideHouse.png',
    'units': 'metres',
    'unreal_conversion': '(Blender X, -Blender Y, Blender Z) * 100; yaw negated',
    'palette_srgb_hex': PALETTE,
    'material_properties': {
        name: {'roughness': .22 if name in ('M_CottageGlass', 'M_WellWater') else .86,
               'metallic': .2 if name in ('M_CottageGlass', 'M_WellWater') else 0.0}
        for name in PALETTE},
    'assets': [asset_metadata(house), asset_metadata(well)],
    'placement_notes': 'House front local -X faces the fixed camera. Well remains separate; place in front yard, offset from the central approach.',
    'door': {'type': 'closed decorative door; no interior gameplay', 'width_m': 1.36,
             'height_m': 2.20, 'threshold_height_m': .59},
    'entry': {'stair_riser_m': .14, 'step_width_m': 1.76, 'porch_top_m': .59,
              'maximum_final_riser_m': .17},
}
(ART/'Layout'/'pink_house_assets.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')

# Presentation objects are instances only; exported assets retain their ground-zero origins.
for original, name, location in ((house, 'Preview_PinkHouse', (0, 0, 0)),
                                  (well, 'Preview_FrontWell', (-4.35, -3.25, 0))):
    obj = bpy.data.objects.new(name, original.data)
    presentation.objects.link(obj)
    obj.location = location
ground_mat = bpy.data.materials.new('PreviewGround')
ground_mat.diffuse_color = (.285, .34, .15, 1)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.025))
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
sun.data.angle = math.radians(50)
scene.world.color = (.40, .44, .50)
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.58, .64, .71, 1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .60
bpy.ops.object.camera_add(location=(-12.4, -8.6, 15.8))
camera = bpy.context.object
camera.name = 'PinkHousePreviewCamera'
target = Vector((-1.15, -.45, 1.65))
camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 15.0
scene.camera = camera
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(ART/'Previews'/'Blender_PinkHouseAssets.png')
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.film_transparent = False
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'PinkHouseAssets.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA PINK HOUSE ASSETS COMPLETE '+json.dumps(metadata['assets']))
