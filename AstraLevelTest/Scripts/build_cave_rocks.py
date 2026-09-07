"""Build the independent Crystal Cave rock architecture kit in Blender 4.5.

Run: blender --background --factory-startup --python Scripts/build_cave_rocks.py
All dimensions are metres; the eight exported meshes have bottom-centre pivots.
The presentation is a real Blender render, never an ImageGen reference.
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
MESH_DIR = ART / 'Meshes' / 'CrystalCave'
LAYOUT_DIR = ART / 'Layout' / 'CrystalCave'
PREVIEW_DIR = ART / 'Previews' / 'CrystalCave'
SOURCE = ART / 'Blender' / 'CrystalCaveRocks.blend'
TEXTURE = ART / 'Textures' / 'CrystalCave' / 'T_CC_Rock.png'
for path in (MESH_DIR, LAYOUT_DIR, PREVIEW_DIR, SOURCE.parent):
    path.mkdir(parents=True, exist_ok=True)
for reference in ('Ref_CC_Rocks.png', 'Ref_CC_Overview.png'):
    assert (ART / 'Reference' / 'CrystalCave' / reference).is_file()

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_CrystalCaveRockAssets')
presentation = bpy.data.collections.new('02_PresentationOnly')
scene.collection.children.link(library)
scene.collection.children.link(presentation)


def srgb(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + .055) / 1.055) ** 2.4 for c in channels)


materials = {}
for name, color, multiplier in [('M_CC_Rock', '#646985', 1.0),
                                 ('M_CC_RockDark', '#3F475F', .67)]:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*srgb(color), 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*srgb(color), 1)
    shader.inputs['Roughness'].default_value = .88
    shader.inputs['Specular IOR Level'].default_value = .24
    if TEXTURE.is_file():
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.get('T_CC_Rock') or bpy.data.images.load(str(TEXTURE))
        tex.image.name = 'T_CC_Rock'
        tex.image.pack()
        tex.extension = 'REPEAT'
        tex.location = (-420, 80)
        multiply = mat.node_tree.nodes.new('ShaderNodeMixRGB')
        multiply.blend_type = 'MULTIPLY'
        multiply.inputs[0].default_value = 1
        multiply.inputs[2].default_value = (multiplier, multiplier, multiplier, 1)
        multiply.location = (-180, 80)
        mat.node_tree.links.new(tex.outputs['Color'], multiply.inputs[1])
        mat.node_tree.links.new(multiply.outputs[0], shader.inputs['Base Color'])
    materials[name] = mat


def mesh(name, vertices, faces, dark=False):
    data = bpy.data.meshes.new(name + '_Geometry')
    data.from_pydata(vertices, [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    library.objects.link(obj)
    data.materials.append(materials['M_CC_RockDark' if dark else 'M_CC_Rock'])
    return obj


def slab(name, center, size, seed, dark=False, lean=0.0):
    """Geological slab with clipped corners, a broken crown and one broad ledge.

    No spheres, subdivisions, random triangle colors, or uniform brick primitives.
    Every ring follows a designed eight-sided asymmetric outline.
    """
    rng = random.Random(seed)
    w, d, h = size
    outline = [(-.50, -.28), (-.32, -.50), (.24, -.48), (.50, -.31),
               (.48, .27), (.29, .49), (-.33, .50), (-.51, .19)]
    outline = [(x * rng.uniform(.90, 1.04), y * rng.uniform(.89, 1.04)) for x, y in outline]
    # Keep a long face between each bevel ring. Offsets introduce fracture planes.
    crown_x = rng.uniform(-.09, .09)
    crown_y = rng.uniform(-.09, .09)
    rings = [(0, .90, .91, -.025, .015),
             (.12, 1, 1, 0, 0),
             (.59, 1.00, .98, lean * .5, -.015),
             (.67, .935, .94, lean * .55, -.005),
             (.77, .97, .97, lean + .012, .012),
             (1, .82, .85, lean + crown_x, crown_y)]
    slope_x, slope_y = rng.uniform(-.075, .075), rng.uniform(-.07, .07)
    vertices = []
    for z, sx, sy, dx, dy in rings:
        for x, y in outline:
            px, py = (x * sx + dx) * w, (y * sy + dy) * d
            pz = z * h + (slope_x * px + slope_y * py) * min(z * 3, 1)
            vertices.append((center[0] + px, center[1] + py, center[2] + pz))
    n = len(outline)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range((len(rings) - 1) * n, len(rings) * n))]
    for layer in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            faces.append((layer * n + i, layer * n + j, (layer + 1) * n + j, (layer + 1) * n + i))
    return mesh(name, vertices, faces, dark)


def finish_asset(name, pieces, dimensions):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in pieces:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    # Align exactly with the agreed gameplay footprints and bottom-centre origin.
    lo = [min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    for v in obj.data.vertices:
        for i in range(3):
            v.co[i] = (v.co[i] - lo[i]) / (hi[i] - lo[i]) * dimensions[i]
            if i < 2:
                v.co[i] -= dimensions[i] / 2
    bevel = obj.modifiers.new('SoftenedFractureEdges', 'BEVEL')
    bevel.width = .027 if 'Rubble' in name else .043
    bevel.segments = 3
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = math.radians(18)
    bevel.harden_normals = True
    bevel.use_clamp_overlap = True
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    # Box-project in asset metre space: consistent stone scale on tops and walls.
    uv = obj.data.uv_layers.new(name='UVMap')
    obj.data.update()
    for face in obj.data.polygons:
        face.use_smooth = True
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        axes = ((1, 2), (0, 2), (0, 1))[axis]
        for li in face.loop_indices:
            p = obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv = (p[axes[0]] * .55, p[axes[1]] * .55)
    normals = obj.modifiers.new('BroadPlaneWeightedNormals', 'WEIGHTED_NORMAL')
    normals.mode = 'FACE_AREA_WITH_ANGLE'
    normals.weight = 60
    normals.keep_sharp = False
    bpy.ops.object.modifier_apply(modifier=normals.name)
    tri = obj.modifiers.new('FBXNormalPreservation', 'TRIANGULATE')
    if hasattr(tri, 'keep_custom_normals'):
        tri.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=tri.name)
    obj['asset_id'] = name
    obj['collision'] = 'complex'
    obj['pivot'] = 'bottom centre'
    obj['units'] = 'metres'
    obj['style'] = 'broad fractured slate planes, layered ledges, softened weighted normals'
    bpy.ops.export_scene.fbx(filepath=str(MESH_DIR / (name + '.fbx')), use_selection=True,
        object_types={'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y', axis_up='Z', bake_anim=False, add_leaf_bones=False,
        mesh_smooth_type='FACE', use_mesh_modifiers=True, path_mode='STRIP', use_tspace=True)
    bpy.context.view_layer.update()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    validation = {'non_manifold_edges': sum(not e.is_manifold for e in bm.edges),
                  'degenerate_faces': sum(f.calc_area() < 1e-12 for f in bm.faces),
                  'finite_vertices': all(math.isfinite(c) for v in bm.verts for c in v.co),
                  'finite_uv': all(math.isfinite(c) for loop in obj.data.uv_layers.active.data for c in loop.uv),
                  'custom_normals': obj.data.has_custom_normals,
                  'triangles': len(obj.data.polygons)}
    bm.free()
    assert validation['non_manifold_edges'] == 0, (name, validation)
    assert validation['degenerate_faces'] == 0, (name, validation)
    assert validation['finite_vertices'] and validation['finite_uv']
    actual = [max(v.co[i] for v in obj.data.vertices) - min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    specs[name] = {'file': 'ArtSource/Meshes/CrystalCave/' + name + '.fbx',
                   'materials': [m.name for m in obj.data.materials],
                   'collision': 'complex', 'dimensions_m': [round(v, 6) for v in actual],
                   'nominal_dimensions_m': dimensions, 'origin': 'bottom centre',
                   'validation': validation}
    obj.hide_render = True
    obj.hide_set(True)
    assets.append(obj)
    return obj


assets, specs = [], {}
# Different broken seam positions and crest heights prevent visible wall tiling.
for variant, seed in [('A', 210), ('B', 357), ('C', 816)]:
    rng = random.Random(seed)
    pieces = []
    widths = [1.58, 1.29, 1.53] if variant == 'A' else ([1.13, 1.70, 1.57] if variant == 'B' else [1.96, 2.42])
    x = -2.1
    for col, width in enumerate(widths):
        cx = x + width * .5
        x += width * .91
        heights = [.83, 1.27, .99] if col % 2 == 0 else [1.08, .72, 1.21]
        z = 0
        for layer, height in enumerate(heights):
            pieces.append(slab('WallStratum', (cx + rng.uniform(-.11, .11), rng.uniform(-.07, .07), z),
                (width * rng.uniform(1.00, 1.09), rng.uniform(1.64, 2.01), height),
                seed + col * 47 + layer * 13, dark=(layer == 0), lean=rng.uniform(-.04, .04)))
            z += height * .91
    # Broad basal ledges anchor the wall and vary its floor silhouette.
    pieces.append(slab('BasalShoulder', (-.77, -.64, 0), (2.37, .97, .53), seed + 170, True))
    pieces.append(slab('BrokenFoot', (1.14, -.73, 0), (1.35, .77, .35), seed + 180, True))
    finish_asset('SM_CC_RockWall_' + variant, pieces, [4.0, 2.0, 3.0])

low = [slab('CutawayBase', (0, .08, 0), (4.02, 1.4, .55), 912, True),
       slab('LeftLedge', (-1.20, -.03, .24), (1.73, 1.32, .53), 913),
       slab('MiddleLedge', (.02, .06, .39), (1.39, 1.32, .61), 914),
       slab('RightLedge', (1.17, -.06, .32), (1.78, 1.22, .52), 915),
       slab('LowFoot', (-.65, -.52, .01), (1.16, .55, .22), 916, True)]
finish_asset('SM_CC_RockWallLow', low, [4.0, 1.5, 1.0])

# Broad irregular islands support crystals while preserving 4 x 7 m footprint.
for variant, seed in [('A', 1115), ('B', 1789)]:
    rng = random.Random(seed)
    pieces = [slab('IslandFoundation', (0, 0, 0), (4.1, 7.1, .60), seed, True)]
    for i, (x, y, w, d, z, h) in enumerate([
        (-.81, -1.85, 2.5, 3.02, .28, .74), (.76, -1.70, 2.10, 2.71, .30, .78),
        (-.94, 1.02, 2.31, 3.30, .31, .81), (.81, 1.20, 2.09, 3.14, .32, .68),
        (-.36, -.98, 2.41, 2.60, .88, .65), (.30, 1.10, 2.62, 2.81, .85, .66),
        (-1.48, -.12, .93, 2.12, .07, .52), (1.34, -2.46, .95, 1.72, .05, .42),
        (.08, 2.96, 2.43, .89, .09, .37)]):
        if variant == 'B':
            x, y = -x, -y
        pieces.append(slab('IslandLayer', (x, y, z), (w, d, h * rng.uniform(.91, 1.08)), seed + 17 * i + 1, dark=i >= 6))
    finish_asset('SM_CC_RockIsland_' + variant, pieces, [4.0, 7.0, 1.6])

rubble = []
for i, (x, y, z, w, d, h) in enumerate([(-.20, -.16, 0, .69, .67, .26),
        (.20, .15, 0, .64, .63, .32), (-.18, .22, .05, .45, .43, .46),
        (.32, -.23, .015, .32, .40, .16), (-.40, .31, .00, .27, .29, .18)]):
    rubble.append(slab('BrokenSlate', (x, y, z), (w, d, h), 511 + 91 * i, i % 3 == 0))
finish_asset('SM_CC_RockRubble', rubble, [1.0, 1.0, .5])

# The portal is a natural capstone opening: every jamb vertex lies outside X +/-1.5.
portal = []
for side in (-1, 1):
    for i, (z, h) in enumerate([(0, .95), (.86, 1.08), (1.84, .89)]):
        obj = slab('PortalJamb', (side * 2.27, 0, z), (1.43, 1.19, h), 333 + i * 21 + side, i == 0)
        for v in obj.data.vertices:
            v.co.x = min(v.co.x, -1.54) if side < 0 else max(v.co.x, 1.54)
        portal.append(obj)
portal.append(slab('AncientNaturalCapstone', (0, 0, 2.66), (6.00, 1.16, .84), 877))
portal_obj = finish_asset('SM_CC_Portal', portal, [6.0, 1.2, 3.5])
# Measure each connected rock component after final bevel/export geometry.
# Entire jamb bounds lie outside this rectangle; the capstone lies above it.
adjacency = {v.index: set() for v in portal_obj.data.vertices}
for edge in portal_obj.data.edges:
    a, b = edge.vertices
    adjacency[a].add(b)
    adjacency[b].add(a)
pending = set(adjacency)
components = []
while pending:
    stack = [pending.pop()]
    component = set(stack)
    while stack:
        for index in adjacency[stack.pop()] - component:
            component.add(index)
            pending.discard(index)
            stack.append(index)
    vertices = [portal_obj.data.vertices[i].co for i in component]
    components.append(([min(v[i] for v in vertices) for i in range(3)],
                       [max(v[i] for v in vertices) for i in range(3)]))
left_edge = max(hi[0] for lo, hi in components if hi[0] < 0)
right_edge = min(lo[0] for lo, hi in components if lo[0] > 0)
lintel_bottom = min(lo[2] for lo, hi in components if lo[0] < 0 < hi[0])
assert right_edge - left_edge >= 3.0 and lintel_bottom >= 2.4
specs['SM_CC_Portal']['clear_opening_minimum_m'] = [round(right_edge - left_edge, 5), round(lintel_bottom, 5)]
specs['SM_CC_Portal']['clear_opening_x_bounds_m'] = [round(left_edge, 5), round(right_edge, 5)]
specs['SM_CC_Portal']['clearance_validation'] = 'Conservative bounds of all seven disconnected solid rock components, after bevel and triangulation'

roundtrips = []
for original in assets:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(MESH_DIR / (original.name + '.fbx')), use_custom_normals=True)
    imported = [obj for obj in set(bpy.data.objects) - before if obj.type == 'MESH']
    assert len(imported) == 1
    obj = imported[0]
    lo = [min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    expected = specs[original.name]['dimensions_m']
    error = max(abs(hi[i] - lo[i] - expected[i]) for i in range(3))
    assert error < 1e-4 and obj.data.has_custom_normals and obj.data.uv_layers.active
    roundtrips.append({'asset': original.name, 'bounds_error_m': error,
        'single_mesh': True, 'custom_normals': True, 'uv0': True,
        'material_slots': [m.name.split('.')[0] for m in obj.data.materials]})
    for imported_obj in set(bpy.data.objects) - before:
        bpy.data.objects.remove(imported_obj, do_unlink=True)

metadata = {'source': 'ArtSource/Blender/CrystalCaveRocks.blend',
    'script': 'Scripts/build_cave_rocks.py', 'units': 'metres',
    'axis_conversion': 'FBX axis_forward=-Y axis_up=Z, FBX_SCALE_UNITS',
    'references': ['ArtSource/Reference/CrystalCave/Ref_CC_Rocks.png',
                   'ArtSource/Reference/CrystalCave/Ref_CC_Overview.png'],
    'assets': specs, 'materials': {
        'M_CC_Rock': {'base_color': '#646985', 'texture': 'ArtSource/Textures/CrystalCave/T_CC_Rock.png',
                      'texture_multiplier': 1.0, 'roughness': .88, 'specular': .24},
        'M_CC_RockDark': {'base_color': '#3F475F', 'texture': 'ArtSource/Textures/CrystalCave/T_CC_Rock.png',
                          'texture_multiplier': .67, 'roughness': .88, 'specular': .24}},
    'fbx_roundtrip_validation': roundtrips,
    'placement_notes': 'Wall length is local X. Portal opening along X; use for far-side entrance. Island footprints are exactly 4 x 7 m and never exceed 4.6 x 7.6 m. Low cutaway wall is 1 m high. Complex collision preserves layered silhouettes and portal opening.'}
(LAYOUT_DIR / 'rocks_kit.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')

positions = [(-6.2, 4.4, 0), (0, 4.4, 0), (6.2, 4.4, 0),
             (-6.2, .3, 0), (-2.8, -5.0, 0), (3.0, -5.0, 0),
             (7.8, -5.8, 0), (5.3, -.2, 0)]
for original, position in zip(assets, positions):
    obj = bpy.data.objects.new('Review_' + original.name, original.data)
    presentation.objects.link(obj)
    obj.location = position
ground = bpy.data.materials.new('PresentationGround')
ground.use_nodes = True
ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.032, .038, .060, 1)
ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .95
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.025))
bpy.context.object.data.materials.append(ground)
bpy.context.object.name = 'PresentationFloor'
scene.world = bpy.data.worlds.new('PresentationWorld')
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.14, .18, .31, 1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .6
for name, location, energy, color, size in [
    ('BroadWhiteKey', (-7, -8, 13), 3100, (.73, .83, 1), 10),
    ('CrystalCyanFill', (8, -1, 7), 1250, (.27, .84, 1), 8),
    ('SoftVioletRim', (0, 9, 11), 2600, (.72, .50, 1), 9)]:
    bpy.ops.object.light_add(type='AREA', location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.color = color
    light.data.shape = 'DISK'
    light.data.size = size
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(location=(19, -29, 25))
camera = bpy.context.object
camera.name = 'RockKitReviewCamera'
camera.rotation_euler = (Vector((.3, -.6, .8)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 25
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.resolution_x = 1800
scene.render.resolution_y = 1400
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(PREVIEW_DIR / 'Blender_Rocks.png')
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
bpy.ops.render.render(write_still=True)
print('CRYSTAL_CAVE_ROCKS_COMPLETE ' + json.dumps(specs))
