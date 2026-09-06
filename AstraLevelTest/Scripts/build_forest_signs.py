"""Independent forest wayfinding and camp wood asset kit, generated in metres.

Run Blender --background --factory-startup --python this_file.py.
Readable sign front is -X. FBX positions map to Unreal as (X, -Y, Z) * 100.
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
R = random.Random(419)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_ForestSignsMeshLibrary')
presentation = bpy.data.collections.new('02_ForestSignsPresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)
PALETTE = {
    'M_Wood': 'A77C45', 'M_WoodLight': 'BF975B', 'M_WoodDark': '715232',
    'M_ForestWoodShade': '687582', 'M_ForestWoodEnd': 'D1AD75',
    'M_ForestSignSage': 'A5B08A', 'M_ForestSignCream': 'E8D8AC',
    'M_ForestSignPink': 'D8939E', 'M_ForestSignBlue': '639EAE',
    'M_ForestSignGreen': '527E68', 'M_ForestSignRope': 'C9AE77',
}


def linear(value):
    return value / 12.92 if value <= .04045 else ((value+.055)/1.055)**2.4


materials = {}
for name, value in PALETTE.items():
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    color = tuple(linear(int(value[i:i+2], 16)/255) for i in (0, 2, 4))
    material.diffuse_color = (*color, 1)
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .88
    materials[name] = material


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
        mod = obj.modifiers.new('SmallSoftEdge', 'BEVEL')
        mod.width = bevel
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(obj, material)


def cylinder(name, a, b, radius, material, vertices=10):
    direction = Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
        depth=direction.length, location=(Vector(a)+Vector(b))/2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return finish(obj, material)


def slab(name, points_yz, front, depth, material, bevel=0):
    n = len(points_yz)
    vertices = [(x, y, z) for x in (front, front+depth) for y, z in points_yz]
    faces = [tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    obj = mesh(name, vertices, faces, material)
    if bevel:
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new('WornEdge', 'BEVEL')
        mod.width = bevel
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def ring(name, center, radius, width, axis, material, segments=20):
    # Torus is a closed solid, including the coarse wood-end growth rings.
    rotation = {'X': (0, math.pi/2, 0), 'Y': (math.pi/2, 0, 0), 'Z': (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_torus_add(major_segments=segments, minor_segments=4,
        major_radius=radius, minor_radius=width, location=center, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    return finish(obj, material)


def polyline(name, points, width, material, vertices=5):
    return [cylinder(name, a, b, width, material, vertices) for a, b in zip(points, points[1:])]


def bark_trunk(name, bottom, top, rbottom, rtop, facets=10, lean=(0, 0)):
    vertices = []
    for level, t in enumerate((0, .08, .52, .96, 1)):
        radius = rbottom*(1-t)+rtop*t
        if level == 3:
            radius *= 1.025
        for i in range(facets):
            angle = math.tau*i/facets
            jitter = 1+.05*math.sin(i*2.4)
            vertices.append((radius*jitter*math.cos(angle)+lean[0]*t,
                             radius*jitter*math.sin(angle)+lean[1]*t,
                             bottom+(top-bottom)*t))
    faces = [tuple(range(facets-1, -1, -1))]
    for row in range(4):
        for i in range(facets):
            j = (i+1)%facets
            faces.append((row*facets+i, row*facets+j, (row+1)*facets+j, (row+1)*facets+i))
    faces.append(tuple(range(4*facets, 5*facets)))
    obj = mesh(name, vertices, faces, 'M_Wood')
    for mat in ('M_WoodLight', 'M_WoodDark', 'M_ForestWoodShade', 'M_ForestWoodEnd'):
        obj.data.materials.append(materials[mat])
    for face in obj.data.polygons:
        if face.index == len(faces)-1:
            face.material_index = 4
        elif face.normal.x > .55:
            face.material_index = 3
        elif face.index % 7 == 0:
            face.material_index = 2
        elif face.index % 4 == 0:
            face.material_index = 1
    return obj


def asset(name, parts, collision):
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
    # Keep the actual lowest vertex on the ground and the seat/pile at their nominal height.
    zmin = min(v.co.z for v in obj.data.vertices)
    zmax = max(v.co.z for v in obj.data.vertices)
    target_height = {'SM_CampLogStool': .55, 'SM_CampWoodpile': .65}.get(name, zmax-zmin)
    for vertex in obj.data.vertices:
        vertex.co.z = (vertex.co.z-zmin)*target_height/(zmax-zmin)
    obj.data.update()
    bpy.context.view_layer.update()
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    library.objects.link(obj)
    obj['asset_id'] = name
    obj['collision'] = collision
    obj['front_axis'] = '-X'
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{name}.fbx'),
        use_selection=True, object_types={'MESH'}, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
        bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE', use_mesh_modifiers=True)
    obj.hide_render = True
    obj.hide_set(True)
    return obj


# Signpost. The three centres are 0.55 m apart. Front text is replaced by solid pictograms.
p = [bark_trunk('GentlyBentWaypost', 0, 2.40, .14, .105, 10, (.035, -.065))]
for index, (z, direction, paint) in enumerate(((.95, 1, 'M_ForestSignPink'),
                                             (1.50, -1, 'M_ForestSignCream'),
                                             (2.05, 1, 'M_ForestSignSage'))):
    arrow = [(-.64, -.175), (.43, -.175), (.63, 0), (.43, .175), (-.64, .175)]
    yz = [(y*direction, z+zz) for y, zz in arrow]
    p.append(slab('TimberArrowRim', yz, -.218, .17, 'M_WoodLight', .013))
    p.append(slab('PaintedArrowFace', [(y*.965, z+(zz-z)*.86) for y, zz in yz],
                  -.228, .018, paint, .005))
    # Two restrained grain seams each side of the pictogram, ending before the arrow point.
    for zz in (-.077, .079):
        for a, b in ((-.57, -.23), (.24, .42)):
            p += polyline('BroadPaintWear', [(-.24, a*direction, z+zz),
                (-.24, (a+b)*.5*direction, z+zz+.006), (-.24, b*direction, z+zz-.002)],
                .0035, 'M_WoodLight', 4)
    p.append(cylinder('MedallionWoodRim', (-.256, -.065, z), (-.232, -.065, z), .158, 'M_WoodDark', 20))
    p.append(cylinder('CreamPictogramMedallion', (-.270, -.065, z), (-.256, -.065, z), .145,
                       'M_ForestSignCream', 20))
    for y in (-.49, .34):
        p.append(cylinder('WoodenPeg', (-.248, y, z+.115), (-.226, y, z+.115), .016, 'M_WoodDark', 6))
    xx = -.279
    if index == 2:
        # Blue lake waves, 3 bold rows, no typefaces.
        for row in (-.06, 0, .06):
            points = [(xx, -.173+i*.036, z+row+.009*math.sin(i*math.pi/2)) for i in range(7)]
            p += polyline('LakeWavePictogram', points, .010, 'M_ForestSignBlue', 5)
    elif index == 1:
        p.append(slab('TentPictogram', [(-.17, z-.075), (.04, z-.075), (-.065, z+.095)],
                      xx-.004, .017, 'M_ForestSignGreen'))
        p.append(slab('TentOpening', [(-.101, z-.075), (-.031, z-.075), (-.066, z+.045)],
                      xx-.012, .012, 'M_WoodDark'))
        p += polyline('TentRidgePoles', [(xx-.02, -.184, z-.085), (xx-.02, -.065, z+.110),
                                        (xx-.02, .054, z-.085)], .008, 'M_WoodLight', 5)
    else:
        p.append(cube('CottagePictogramWalls', (xx-.005, -.065, z-.025), (.02, .14, .10), 'M_ForestSignPink'))
        p.append(slab('CottagePictogramRoof', [(-.165, z+.016), (.035, z+.016), (-.065, z+.103)],
                      xx-.02, .024, 'M_WoodDark'))
        p.append(cube('CottagePictogramDoor', (xx-.023, -.065, z-.043), (.012, .038, .065), 'M_ForestSignCream'))
        p.append(cube('CottagePictogramChimney', (xx-.005, -.007, z+.079), (.019, .026, .061), 'M_ForestSignPink'))
sign = asset('SM_ForestSignpost', p, 'complex')

# A squat, flat seated stump. Coarse rings are geometry and remain legible from above.
p = [bark_trunk('CampLogSeat', 0, .55, .32, .29, 12)]
for radius in (.10, .20):
    p.append(ring('SeatGrowthRing', (0, 0, .546), radius, .005, 'Z', 'M_WoodLight', 24))
for angle in (.3, 2.8, 4.5):
    a = (.235*math.cos(angle), .235*math.sin(angle), .550)
    b = (.28*math.cos(angle+.055), .28*math.sin(angle+.055), .550)
    p += polyline('SeatEndCrack', [a, b], .005, 'M_WoodDark', 4)
stool = asset('SM_CampLogStool', p, 'complex')

# Stacked short logs in a tidy triangular pile. Axis Y; visible cut faces at +/-Y.
p = []
for row, count in enumerate((4, 3, 2)):
    for column in range(count):
        x = (column-(count-1)/2)*.20
        z = .113+row*.207
        radius = .113-(.008 if row == 2 else 0)
        length = 1.30-(.03 if (row+column)%2 else 0)
        offset = .007*math.sin(column*3+row)
        p.append(cylinder('StackedLogBark', (x, -length/2+offset, z),
                          (x, length/2+offset, z), radius, 'M_Wood' if column%2 else 'M_WoodDark', 9))
        for direction in (-1, 1):
            yy = direction*(length/2+.002)+offset
            p.append(cylinder('SplitLogEnd', (x, yy-direction*.009, z),
                              (x, yy, z), radius*.90, 'M_ForestWoodEnd', 9))
            p.append(ring('StackLogGrowthRing', (x, yy, z), radius*.45, .0045, 'Y', 'M_WoodLight', 12))
        # One generous light bark stripe along the upper side.
        p.append(cylinder('LogBarkHighlight', (x-.025, -length*.46+offset, z+radius*.93),
                          (x-.025, length*.46+offset, z+radius*.93), .017, 'M_WoodLight', 5))
for yy in (-.39, .39):
    points = [(-.406, yy, .030), (-.406, yy, .18), (-.298, yy, .405),
              (-.17, yy, .635), (.17, yy, .635), (.298, yy, .405),
              (.406, yy, .18), (.406, yy, .030), (-.406, yy, .030)]
    p += polyline('SecuringRope', points, .014, 'M_ForestSignRope', 6)
woodpile = asset('SM_CampWoodpile', p, 'complex')


def metadata_for(obj):
    bounds = [Vector(corner) for corner in obj.bound_box]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    open_edges = sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    finite = all(math.isfinite(value) for vertex in obj.data.vertices for value in vertex.co)
    degenerate = sum(face.area <= 1e-12 for face in obj.data.polygons)
    assert finite and open_edges == 0 and degenerate == 0, obj.name
    assert min(v.z for v in bounds) >= -.00001, obj.name
    return {
        'asset_id': obj.name, 'file': f'ArtSource/Meshes/{obj.name}.fbx',
        'collision': obj['collision'], 'front_axis_blender': '-X',
        'origin': 'ground at (0, 0, 0)',
        'dimensions_m': [round(v, 6) for v in obj.dimensions],
        'bounds_min_m': [round(min(v[i] for v in bounds), 6) for i in range(3)],
        'bounds_max_m': [round(max(v[i] for v in bounds), 6) for i in range(3)],
        'vertices': len(obj.data.vertices),
        'triangles': sum(len(face.vertices)-2 for face in obj.data.polygons),
        'material_slots': [slot.material.name for slot in obj.material_slots],
        'validation': {'finite_vertices': finite, 'ground_origin': True,
                       'degenerate_faces': degenerate, 'non_manifold_edges': open_edges},
    }


assets = [sign, stool, woodpile]
metadata = {
    'source': 'ArtSource/Blender/ForestSigns.blend',
    'script': 'Scripts/build_forest_signs.py',
    'reference': 'ArtSource/Reference/Ref_ForestSignpost.png',
    'units': 'metres', 'unreal_conversion': '(Blender X, -Blender Y, Blender Z) * 100; yaw negated',
    'palette_srgb_hex': PALETTE,
    'material_properties': {name: {'roughness': .88, 'metallic': 0.0} for name in PALETTE},
    'assets': [metadata_for(obj) for obj in assets],
    'placement_notes': 'Sign readable front local -X faces the fixed camera at UE yaw 0. Place at path forks, leaving 1.5 m clear walking space. Stool and pile are separate ground-zero assets; rotate freely near tent and campfire. The log pile long axis is Y.',
    'sign': {'height_m': 2.4, 'arrow_centre_spacing_m': .55,
             'pictograms_top_to_bottom': ['lake ripples', 'tent', 'cottage'], 'contains_text': False},
}

# Real FBX roundtrip: assert dimensions, origin, slot order and closed geometry after reimport.
for original, item in zip(assets, metadata['assets']):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ART/'Meshes'/f'{original.name}.fbx'), use_anim=False)
    imported = [o for o in set(bpy.data.objects)-before if o.type == 'MESH']
    assert len(imported) == 1
    copy = imported[0]
    bpy.context.view_layer.update()
    delta = max(abs(copy.dimensions[i]-original.dimensions[i]) for i in range(3))
    assert delta < 1e-5, (original.name, list(copy.dimensions), list(original.dimensions))
    assert copy.location.length < 1e-6
    slots = [s.material.name.split('.')[0] for s in copy.material_slots]
    assert slots == item['material_slots'], (original.name, slots, item['material_slots'])
    bm = bmesh.new()
    bm.from_mesh(copy.data)
    open_edges = sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert open_edges == 0
    item['validation']['fbx_roundtrip'] = {'bounds_max_error_m': round(delta, 8),
        'origin_zero': True, 'material_slots_match': True, 'non_manifold_edges': open_edges}
    for imported_obj in set(bpy.data.objects)-before:
        bpy.data.objects.remove(imported_obj, do_unlink=True)

(ART/'Layout'/'forest_signs.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')

for original, location in ((sign, (0, 1.35, 0)), (stool, (-.05, -.55, 0)),
                            (woodpile, (1.05, -1.10, 0))):
    obj = bpy.data.objects.new('Preview_'+original.name, original.data)
    presentation.objects.link(obj)
    obj.location = location
ground_mat = bpy.data.materials.new('PreviewGround')
ground_mat.diffuse_color = (.34, .39, .27, 1)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.015))
ground = bpy.context.object
ground.name = 'PreviewGround'
ground.data.materials.append(ground_mat)
bpy.ops.object.light_add(type='SUN', location=(-6, -7, 12))
sun = bpy.context.object
sun.rotation_euler = (math.radians(24), math.radians(-20), math.radians(-35))
sun.data.energy = 2.5
sun.data.angle = math.radians(50)
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.48, .63, .86, 1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .70
bpy.ops.object.camera_add(location=(-7.3, -5.7, 5.4))
camera = bpy.context.object
target = Vector((.2, .03, 1.1))
camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 5.3
scene.camera = camera
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1500
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(ART/'Previews'/'Blender_ForestSigns.png')
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.film_transparent = False
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'ForestSigns.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA FOREST SIGNS COMPLETE '+json.dumps(metadata['assets']))
