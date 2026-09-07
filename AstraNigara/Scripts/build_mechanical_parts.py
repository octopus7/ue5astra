"""Build six small mechanical debris meshes with Blender 4.5 in background mode.

blender --background --factory-startup --python Scripts/build_mechanical_parts.py

Geometry uses centimeters (scene scale_length = 0.01). FBX exports include units,
applied transforms and a centered pivot. Import to UE with uniform scale 1.
These are economical VFX LOD0 parts; threads and teeth are simplified.
Lower distance LODs are generated in Unreal by the asset import pipeline.
"""

import json
import math
from pathlib import Path

import bpy
from io_scene_fbx import parse_fbx
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource' / 'MechanicalParts'
FBX = ART / 'FBX'
PREVIEWS = ROOT / 'Docs' / 'Previews'
for directory in (ART, FBX, PREVIEWS):
    directory.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.01
scene.unit_settings.length_unit = 'CENTIMETERS'
assets_collection = bpy.data.collections.new('Mechanical Parts / centered export meshes')
scene.collection.children.link(assets_collection)
preview_collection = bpy.data.collections.new('Presentation / render only')
scene.collection.children.link(preview_collection)


def material(name, color, metallic=0.0, roughness=0.45):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    shader = result.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1.0)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    return result


steel = material('M_MechanicalSteel', (0.29, 0.34, 0.40), 0.88, 0.29)
floor_mat = material('Presentation_Graphite', (0.019, 0.027, 0.044), 0.30, 0.40)
plinth_mat = material('Presentation_Slate', (0.055, 0.073, 0.11), 0.42, 0.33)
text_mat = material('Presentation_Text', (0.75, 0.87, 1.0), 0.10, 0.48)
accent_mat = material('Presentation_Accent', (0.90, 0.39, 0.10), 0.55, 0.35)


def relink(obj, collection):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)


def active_only(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def mesh(name, vertices, faces):
    data = bpy.data.meshes.new(name + '_Geometry')
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    assets_collection.objects.link(obj)
    obj.data.materials.append(steel)
    return obj


def apply_bevel(obj, width, segments=1):
    active_only(obj)
    modifier = obj.modifiers.new('Small machined edge bevels', 'BEVEL')
    modifier.width = width
    modifier.segments = segments
    modifier.limit_method = 'ANGLE'
    modifier.angle_limit = 0.52
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def cylinder(name, radius, depth, z=0.0, sides=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides, radius=radius, depth=depth,
                                     location=(0.0, 0.0, z))
    obj = bpy.context.object
    obj.name = name
    relink(obj, assets_collection)
    obj.data.materials.append(steel)
    return obj


def profile_mesh(name, profile, sides=32, radial_fn=None, gap=0.0):
    """Revolve a closed radial/z profile, including bore and machined chamfers."""
    vertices = []
    count = sides + 1 if gap else sides
    for radius, z in profile:
        for i in range(count):
            angle = (gap / 2 + (2 * math.pi - gap) * i / sides
                     if gap else 2 * math.pi * i / sides)
            r = radial_fn(radius, angle) if radial_fn else radius
            vertices.append((r * math.cos(angle), r * math.sin(angle), z))
    faces = []
    for j in range(len(profile)):
        k = (j + 1) % len(profile)
        for i in range(sides):
            nxt = i + 1 if gap else (i + 1) % sides
            faces.append((j * count + i, j * count + nxt,
                          k * count + nxt, k * count + i))
    if gap:
        faces.append(tuple(j * count for j in reversed(range(len(profile)))))
        faces.append(tuple(j * count + sides for j in range(len(profile))))
    return mesh(name, vertices, faces)


def helix(name, radius, tube_radius, height, turns, steps_per_turn=24, tube_sides=8):
    vertices, faces = [], []
    steps = int(turns * steps_per_turn)
    for i in range(steps + 1):
        angle = 2 * math.pi * turns * i / steps
        z = height * (i / steps - 0.5)
        center = Vector((radius * math.cos(angle), radius * math.sin(angle), z))
        outward = Vector((math.cos(angle), math.sin(angle), 0))
        tangent = Vector((-radius * math.sin(angle), radius * math.cos(angle),
                          height / (2 * math.pi * turns))).normalized()
        binormal = tangent.cross(outward).normalized()
        for j in range(tube_sides):
            ring_angle = 2 * math.pi * j / tube_sides
            point = center + tube_radius * (math.cos(ring_angle) * outward +
                                           math.sin(ring_angle) * binormal)
            vertices.append(tuple(point))
    for i in range(steps):
        for j in range(tube_sides):
            nxt = (j + 1) % tube_sides
            faces.append((i * tube_sides + j, i * tube_sides + nxt,
                          (i + 1) * tube_sides + nxt, (i + 1) * tube_sides + j))
    faces.append(tuple(reversed(range(tube_sides))))
    faces.append(tuple(steps * tube_sides + j for j in range(tube_sides)))
    result = mesh(name, vertices, faces)
    for polygon in result.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return result


def finalize(name, parts):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    obj.location = (0, 0, 0)
    # Every exported mesh has one metal slot; UE can supply its own material.
    obj.data.materials.clear()
    obj.data.materials.append(steel)
    for polygon in obj.data.polygons:
        polygon.material_index = 0
    obj.data.validate(verbose=True)
    obj.data.update()
    # Recalculate normals consistently on each disconnected watertight part.
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.025)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38), keep_sharp_edges=False)
    normals = obj.modifiers.new('Machined face normals', 'WEIGHTED_NORMAL')
    normals.keep_sharp = True
    normals.weight = 50
    bpy.ops.object.modifier_apply(modifier=normals.name)
    # FBX carries the evaluated mesh, including explicit triangulation.
    triangulate = obj.modifiers.new('VFX triangles', 'TRIANGULATE')
    triangulate.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    active_only(obj)
    bpy.ops.export_scene.fbx(
        filepath=str(FBX / (name + '.fbx')), use_selection=True,
        object_types={'MESH'}, global_scale=1.0, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
        bake_space_transform=False, mesh_smooth_type='FACE', use_mesh_modifiers=True,
        add_leaf_bones=False, bake_anim=False, use_triangles=True, path_mode='AUTO')
    return obj


def verify_export(name, expected_dimensions):
    """Read back actual FBX metadata/vertices so a unit mistake fails generation."""
    data, version = parse_fbx.parse(str(FBX / (name + '.fbx')))
    settings = next(child for child in data.elems if child.id == b'GlobalSettings')
    properties = next(child for child in settings.elems if child.id == b'Properties70')
    unit_cm = next(child.props[-1] for child in properties.elems
                   if child.props[0] == b'UnitScaleFactor')
    assert abs(unit_cm - 1.0) < .00001, (name, 'FBX must use centimeters', unit_cm)
    objects = next(child for child in data.elems if child.id == b'Objects')
    geometries = [child for child in objects.elems if child.id == b'Geometry']
    assert len(geometries) == 1, (name, 'FBX must contain exactly one geometry')
    coordinates = next(child.props[0] for child in geometries[0].elems if child.id == b'Vertices')
    exported_dimensions = [max(coordinates[axis::3]) - min(coordinates[axis::3]) for axis in range(3)]
    for actual, expected in zip(sorted(exported_dimensions), sorted(expected_dimensions)):
        assert abs(actual - expected) < .0001, (name, exported_dimensions, expected_dimensions)
    return {'version': version, 'unit_scale_cm': unit_cm,
            'geometry_count': len(geometries),
            'geometry_dimensions_cm': [round(value, 5) for value in exported_dimensions]}


# Hex-head bolt: a chamfered hex head and a continuous helical ridge on its shaft.
head = cylinder('Bolt head', 0.98, 0.56, z=1.47, sides=6)
apply_bevel(head, 0.065, 1)
shank = cylinder('Bolt shank', 0.34, 2.94, z=-0.28, sides=12)
apply_bevel(shank, 0.045)
thread = helix('Bolt simplified helical thread', 0.365, 0.052, 2.45, 6.0,
               steps_per_turn=10, tube_sides=3)
thread.location.z = -0.39
bolt = finalize('SM_HexBolt', [head, shank, thread])


def hex_radius(radius, angle):
    # Only the outer contours are hexagonal; the small bore remains circular.
    if radius < 0.65:
        return radius
    sector = (angle + math.pi / 6) % (math.pi / 3) - math.pi / 6
    return radius * math.cos(math.pi / 6) / math.cos(sector)


nut_profile = [(.80, -.43), (.90, -.33), (.90, .33), (.80, .43),
               (.43, .43), (.365, .35), (.365, .10), (.405, 0),
               (.365, -.10), (.43, -.43)]
nut = finalize('SM_HexNut', [profile_mesh('Nut with through bore', nut_profile,
                                       sides=24, radial_fn=hex_radius)])

spring_coil = helix('Compression spring', .57, .10, 3.20, 6.0,
                    steps_per_turn=12, tube_sides=6)
bpy.context.view_layer.update()
# Keep the original overall height as cross-section tessellation changes.
spring_coil.scale.z = 3.39782 / spring_coil.dimensions.z
spring = finalize('SM_CoilSpring', [spring_coil])


def gear_radius(radius, angle):
    if radius < 1.0:
        return radius
    # Four corners per tooth: root, two tip corners, root (12 broad teeth).
    tooth_corner = int(round(angle / (2 * math.pi) * 48)) % 4
    return radius if tooth_corner in (1, 2) else radius * .80


gear_body = profile_mesh('Twelve tooth gear',
                        [(1.50, -.27), (1.50, .22), (1.44, .28),
                         (.38, .28), (.38, -.27)], sides=48, radial_fn=gear_radius)
gear_hub = profile_mesh('Gear raised hub',
                       [(.67, -.43), (.67, .43), (.38, .43), (.38, -.43)], sides=12)
bpy.context.view_layer.update()
# Tooth sampling moves the extreme tip off the axes; preserve the 3 cm size.
gear_xy_scale = 3.0 / max(gear_body.dimensions.x, gear_body.dimensions.y)
gear_body.scale.x = gear_body.scale.y = gear_xy_scale
gear = finalize('SM_SpurGear', [gear_body, gear_hub])

washer = finalize('SM_Washer', [profile_mesh('Chamfered washer with through bore',
                  [(.80, -.09), (.85, -.055), (.85, .055), (.80, .09),
                   (.355, .09), (.355, -.09)], sides=16)])

coupler_profile = [(.84, -1.35), (.93, -1.26), (.93, -.82), (.875, -.76),
                   (.875, -.68), (.93, -.62), (.93, .62), (.875, .68),
                   (.875, .76), (.93, .82), (.93, 1.26), (.84, 1.35),
                   (.48, 1.35), (.42, 1.27), (.42, -1.27), (.48, -1.35)]
coupler_body = profile_mesh('Split shaft coupling', coupler_profile, sides=16, gap=.065)
coupler = finalize('SM_ShaftCoupler', [coupler_body])

assets = [bolt, nut, spring, gear, washer, coupler]
budgets = {'SM_HexBolt': (400, 700), 'SM_HexNut': (250, 500),
           'SM_CoilSpring': (600, 1000), 'SM_SpurGear': (300, 600),
           'SM_Washer': (120, 250), 'SM_ShaftCoupler': (300, 600)}
previous_triangles = {'SM_HexBolt': 1348, 'SM_HexNut': 1152,
                      'SM_CoilSpring': 2316, 'SM_SpurGear': 1344,
                      'SM_Washer': 512, 'SM_ShaftCoupler': 1052}
target_max_cm = {'SM_HexBolt': 3.5, 'SM_HexNut': 1.8, 'SM_CoilSpring': 3.39782,
                 'SM_SpurGear': 3.0, 'SM_Washer': 1.7, 'SM_ShaftCoupler': 2.7}
report = {
    'generator': 'Scripts/build_mechanical_parts.py',
    'blender_version': bpy.app.version_string,
    'scene_unit_scale_meters': .01,
    'fbx_unit': 'centimeter',
    'unreal_import_uniform_scale': 1.0,
    'geometry_tier': 'VFX LOD0; lower distance LODs are generated in Unreal',
    'pivot': 'center of geometry bounds; transforms applied',
    'purpose': 'Small visual debris; no engineering tolerances or collision meshes',
    'assets': []}
for obj in assets:
    obj.data.calc_loop_triangles()
    triangle_count = len(obj.data.loop_triangles)
    assert budgets[obj.name][0] <= triangle_count <= budgets[obj.name][1], (obj.name, triangle_count)
    assert abs(max(obj.dimensions) - target_max_cm[obj.name]) < .0001, (obj.name, obj.dimensions)
    report['assets'].append({
        'name': obj.name, 'fbx': 'FBX/' + obj.name + '.fbx',
        'dimensions_cm': [round(v, 5) for v in obj.dimensions],
        'vertices': len(obj.data.vertices), 'triangles': triangle_count,
        'triangle_budget': list(budgets[obj.name]),
        'previous_triangles': previous_triangles[obj.name],
        'reduction_percent': round(100 * (1 - triangle_count / previous_triangles[obj.name]), 2),
        'material_slots': len(obj.data.materials),
        'uv_channels': len(obj.data.uv_layers),
        'location': list(obj.location), 'scale': list(obj.scale),
        'fbx_verification': verify_export(obj.name, obj.dimensions)})
(ART / 'mechanical_parts_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def preview_copy(obj, location, rotation=(0, 0, 0)):
    duplicate = obj.copy()
    duplicate.data = obj.data
    duplicate.name = 'Preview_' + obj.name
    preview_collection.objects.link(duplicate)
    duplicate.location = location
    duplicate.rotation_euler = rotation
    return duplicate


def display_text(text, location, size, mat=text_mat, align='CENTER'):
    data = bpy.data.curves.new('Label ' + text, 'FONT')
    data.body, data.size, data.align_x = text, size, align
    data.extrude = .001
    obj = bpy.data.objects.new('Label ' + text, data)
    preview_collection.objects.link(obj)
    obj.location = location
    data.materials.append(mat)
    return obj


# Six assets shown at the same scale. Camera-facing type avoids rotated labels.
layouts = [(-5.2, 2.8), (0, 2.8), (5.2, 2.8), (-5.2, -3.0), (0, -3.0), (5.2, -3.0)]
labels = ['HEX BOLT', 'HEX NUT', 'COIL SPRING', 'SPUR GEAR', 'WASHER', 'SHAFT COUPLER']
rotations = [(0.30, -0.20, -.25), (0, 0, .2), (0, .16, .0),
             (.12, .0, -.15), (.0, .0, .0), (0, -.20, .2)]
for obj, (x, y), label, rotation in zip(assets, layouts, labels, rotations):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=2.23, depth=.22, location=(x, y, 0))
    plinth = bpy.context.object
    plinth.name = 'Presentation_Platform_' + obj.name
    relink(plinth, preview_collection)
    plinth.data.materials.append(plinth_mat)
    apply_bevel(plinth, .07, 2)
    copy = preview_copy(obj, (x, y, 0), rotation)
    bpy.context.view_layer.update()
    min_z = min((copy.matrix_world @ Vector(corner)).z for corner in copy.bound_box)
    copy.location.z = .13 - min_z
    display_text(label, (x, y - 2.60, .08), .33)
    dims = next(item['dimensions_cm'] for item in report['assets'] if item['name'] == obj.name)
    triangles = next(item['triangles'] for item in report['assets'] if item['name'] == obj.name)
    display_text(f'{max(dims):.1f} CM  /  {triangles} TRIS', (x, y - 3.07, .08), .24, accent_mat)

assets_collection.hide_render = True
assets_collection.hide_viewport = True
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.19))
ground = bpy.context.object
ground.name = 'Presentation_Floor'
relink(ground, preview_collection)
ground.data.materials.append(floor_mat)
display_text('MECHANICAL DEBRIS', (0, 6.1, .03), .67)
display_text('ASTRA NIGARA   /   SMALL DESTRUCTION   /   OPTIMIZED VFX LOD0',
             (0, 5.43, .03), .23, accent_mat)

world = scene.world or bpy.data.worlds.new('Studio World')
scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.15, .19, .29, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = .40


def area(name, position, power, size, color):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size, data.color = power, 'DISK', size, color
    obj = bpy.data.objects.new(name, data)
    preview_collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector((0, 0, 0)) - obj.location).to_track_quat('-Z', 'Y').to_euler()


area('Large cool key', (-6, -3, 14), 1400, 8, (.74, .84, 1))
area('Long warm rim', (5, 7, 10), 1800, 7, (1, .70, .40))
area('Front softbox', (1, -10, 5), 950, 6, (.63, .78, 1))
camera_data = bpy.data.cameras.new('Mechanical parts overview')
camera = bpy.data.objects.new('Mechanical parts overview', camera_data)
preview_collection.objects.link(camera)
camera.location = (0, -15.5, 24)
camera.rotation_euler = (Vector((0, 0, .25)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 20.8
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1800
scene.render.resolution_y = 1450
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(PREVIEWS / 'MechanicalParts_Lineup.png')
scene.view_settings.view_transform = 'AgX'
scene.render.film_transparent = False
scene.render.use_file_extension = True
scene.render.image_settings.color_mode = 'RGB'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ART / 'MechanicalParts.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA_MECHANICAL_PARTS_OK ' + json.dumps(report, separators=(',', ':')))
