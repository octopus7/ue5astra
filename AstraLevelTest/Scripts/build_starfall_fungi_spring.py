"""Independent Starfall fungi and spring stone kit. Blender 4.5, metres, Z up.

The scene layout, water and sky are deliberately owned by the integrating task.
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
REFERENCE = ART / 'Reference/Starfall/Ref_StarfallFungiSpring.png'
for folder in ('Blender', 'Meshes/Starfall', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
library = bpy.data.collections.new('StarfallFungiSpring_Library')
scene.collection.children.link(library)
presentation = bpy.data.collections.new('StarfallFungiSpring_Presentation')
scene.collection.children.link(presentation)

MATERIALS = {
    'M_SF_Fungi_RedCap': {'base_color': 'C95445', 'roughness': .72, 'metallic': 0},
    'M_SF_Fungi_OchreCap': {'base_color': 'D29643', 'roughness': .76, 'metallic': 0},
    'M_SF_Fungi_CreamCap': {'base_color': 'E3BD81', 'roughness': .76, 'metallic': 0},
    'M_SF_Fungi_StemIvory': {'base_color': 'E9DDAD', 'roughness': .83, 'metallic': 0},
    'M_SF_Fungi_CreamSpots': {'base_color': 'FFF0C2', 'roughness': .85, 'metallic': 0},
    'M_SF_Fungi_OchreSpeckles': {'base_color': 'E2B778', 'roughness': .82, 'metallic': 0},
    'M_SF_Fungi_CreamFreckles': {'base_color': 'AA7D4A', 'roughness': .83, 'metallic': 0},
    'M_SF_Fungi_WarmGills': {'base_color': 'BA9972', 'roughness': .85, 'metallic': 0},
    'M_SF_Fungi_TealCap': {'base_color': '297C87', 'roughness': .52, 'metallic': 0},
    'M_SF_Fungi_LilacCap': {'base_color': '7973AA', 'roughness': .55, 'metallic': 0},
    'M_SF_Fungi_GlowStem': {'base_color': '91BFB9', 'roughness': .75, 'metallic': 0},
    'M_SF_Fungi_TurquoiseGlow': {'base_color': '95EEE0', 'roughness': .55, 'metallic': 0,
                                'emissive_color': '62EED6', 'emissive_strength': 1.7},
    'M_SF_Fungi_LavenderGlow': {'base_color': 'D5BDFA', 'roughness': .55, 'metallic': 0,
                               'emissive_color': 'BFA1F3', 'emissive_strength': 1.55},
    'M_SF_Spring_PaintedStone': {'base_color': 'BBC9D6', 'roughness': .88, 'metallic': 0,
                                'base_color_texture': 'ArtSource/Textures/T_AnimeForestRockPaint.png'},
    'M_SF_Spring_Moss': {'base_color': '829A59', 'roughness': .94, 'metallic': 0},
    'M_SF_Spring_Fern': {'base_color': '699356', 'roughness': .87, 'metallic': 0},
    'M_SF_Spring_FernLight': {'base_color': 'A4B779', 'roughness': .87, 'metallic': 0},
}


def rgba(s):
    channels = [int(s[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple((v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4) for v in channels) + (1,)


materials = {}
for name, props in MATERIALS.items():
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba(props['base_color'])
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = rgba(props['base_color'])
    shader.inputs['Roughness'].default_value = props['roughness']
    if 'emissive_color' in props:
        shader.inputs['Emission Color'].default_value = rgba(props['emissive_color'])
        shader.inputs['Emission Strength'].default_value = props['emissive_strength']
    if 'base_color_texture' in props:
        image = bpy.data.images.load(str(ROOT / props['base_color_texture']))
        image.pack()
        texture = mat.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image = image
        mat.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    materials[name] = mat


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def mesh_object(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh)
    library.objects.link(obj)
    mesh.materials.append(materials[mat])
    for p in mesh.polygons:
        p.use_smooth = True
    return obj


def ellipsoid(name, center, radii, mat, segments=16, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=center)
    obj = bpy.context.object
    obj.name = name
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    library.objects.link(obj)
    obj.scale = radii
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(materials[mat])
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def lathe(name, profile, center, mat, segments=40, stretch=(1, 1), phase=0):
    # A single vertex at each pole avoids degenerate triangles in UE's FBX builder.
    vertices = []; rings = []
    for radius, z in profile:
        if radius < 1e-7:
            rings.append([len(vertices)])
            vertices.append((center[0], center[1], center[2]+z))
        else:
            ring = []
            for i in range(segments):
                angle = 2*math.pi*i/segments
                undulation = 1 + .018*math.cos(3*angle+phase) + .012*math.sin(5*angle-phase)
                ring.append(len(vertices))
                vertices.append((center[0]+radius*math.cos(angle)*stretch[0]*undulation,
                                 center[1]+radius*math.sin(angle)*stretch[1]*undulation,
                                 center[2]+z))
            rings.append(ring)
    faces = []
    for a, b in zip(rings, rings[1:]):
        for i in range(segments):
            j = (i+1) % segments
            if len(a) == 1:
                faces.append((a[0], b[j], b[i]))
            elif len(b) == 1:
                faces.append((a[i], a[j], b[0]))
            else:
                faces.append((a[i], a[j], b[j], b[i]))
    return mesh_object(name, vertices, faces, mat)


def tube(name, points, radius, mat, sides=6):
    vertices = []
    for index, p in enumerate(points):
        tangent = Vector(points[min(index+1, len(points)-1)]) - Vector(points[max(index-1, 0)])
        tangent.normalize()
        side = tangent.cross(Vector((0, 0, 1)))
        if side.length < .001:
            side = tangent.cross(Vector((0, 1, 0)))
        side.normalize(); up = tangent.cross(side).normalized()
        taper = .72 + .28*math.sin(math.pi*index/(len(points)-1))
        for i in range(sides):
            a = 2*math.pi*i/sides
            vertices.append(tuple(Vector(p) + radius*taper*(side*math.cos(a)+up*math.sin(a))))
    faces = [tuple(range(sides-1, -1, -1))]
    for row in range(len(points)-1):
        for i in range(sides):
            j = (i+1) % sides
            faces.append((row*sides+i, row*sides+j, (row+1)*sides+j, (row+1)*sides+i))
    faces.append(tuple((len(points)-1)*sides+i for i in range(sides)))
    return mesh_object(name, vertices, faces, mat)


def mushroom(parts, xy, height, radius, style, seed):
    rng = random.Random(seed)
    cap_material = ('M_SF_Fungi_RedCap', 'M_SF_Fungi_OchreCap', 'M_SF_Fungi_CreamCap',
                    'M_SF_Fungi_TealCap', 'M_SF_Fungi_LilacCap')[style]
    glow = style >= 3
    gill_material = ('M_SF_Fungi_TurquoiseGlow' if style == 3 else 'M_SF_Fungi_LavenderGlow') if glow else 'M_SF_Fungi_WarmGills'
    stem_material = 'M_SF_Fungi_GlowStem' if glow else 'M_SF_Fungi_StemIvory'
    top_height = radius * (.60 if glow else .70)
    rim_z = height - top_height
    stem_r = radius * (.16 if glow else .22)
    bend = rng.uniform(-.1, .1)*radius
    stem_profile = [(0, 0), (.82*stem_r, 0), (1.12*stem_r, .05*height),
                    (.97*stem_r, .20*height), (.77*stem_r, .46*height),
                    (.8*stem_r, rim_z-.04*radius), (0, rim_z-.04*radius)]
    stem = lathe('MushroomCurvedStem', stem_profile, (xy[0], xy[1], 0), stem_material, 24)
    for vertex in stem.data.vertices:
        vertex.co.x += bend*(vertex.co.z/height)**2
    parts.append(stem)
    if style != 1:
        collar = [(stem_r, .03*height), (stem_r*1.12, -.015*height),
                  (stem_r*1.60, -.10*height), (stem_r*1.44, -.09*height),
                  (stem_r*.98, -.013*height), (stem_r, .03*height)]
        parts.append(lathe('SoftFlaredStemCollar', collar,
                           (xy[0]+bend*.33, xy[1], rim_z-.14*height), stem_material, 28))
    center = (xy[0]+bend*(rim_z/height)**2, xy[1], rim_z)
    stretch = (rng.uniform(.96, 1.06), rng.uniform(.91, 1))
    profile = [(0, top_height)]
    for i in range(1, 13):
        theta = (math.pi*.5)*i/12
        profile.append((radius*math.sin(theta), top_height*math.cos(theta)))
    profile += [(radius*.986, -.05*radius), (radius*.92, -.08*radius),
                (radius*.68, -.074*radius), (radius*.20, -.045*radius), (0, -.042*radius)]
    cap = lathe('MushroomRoundedCap', profile, center, cap_material, 40, stretch, seed)
    cap.data.materials.append(materials[gill_material])
    # The underside is intentionally warmer/darker on ordinary fungi.
    for face in cap.data.polygons:
        average_z = sum(cap.data.vertices[i].co.z for i in face.vertices)/len(face.vertices)
        if average_z < center[2]-.035*radius:
            face.material_index = 1
    parts.append(cap)
    for i in range(16 if glow else 12):
        a = 2*math.pi*i/(16 if glow else 12)
        pts = [(center[0]+radius*t*math.cos(a)*stretch[0], center[1]+radius*t*math.sin(a)*stretch[1],
                center[2]-radius*(.082+.023*math.sin(t*math.pi))) for t in (.22, .46, .72, .93)]
        parts.append(tube('RadialGillRib', pts, radius*(.017 if glow else .011), gill_material, 5))
    if glow:
        # Restrained rim line and gills carry emission; the dome is a colored surface.
        ring = [(radius*.976, -.035*radius), (radius*1.004, -.012*radius),
                (radius*1.012, .012*radius), (radius*.994, .035*radius),
                (radius*.976, -.035*radius)]
        parts.append(lathe('ThinGlowingCapRim', ring, center, gill_material, 48, stretch, seed))
    for index in range(5 if glow else 8):
        rr = (.24 if index == 0 else rng.uniform(.35, .84))*radius
        angle = rng.uniform(0, math.tau)
        if index == 0:
            rr = .05*radius
        x = rr*math.cos(angle)*stretch[0]; y = rr*math.sin(angle)*stretch[1]
        z = top_height*math.sqrt(max(.01, 1-(rr/radius)**2))
        s = radius*rng.uniform(.052, .085) if glow or style in (1, 2) else radius*rng.uniform(.09, .145)
        spot_material = (gill_material if glow else
                         ('M_SF_Fungi_CreamSpots', 'M_SF_Fungi_OchreSpeckles', 'M_SF_Fungi_CreamFreckles')[style])
        spot = ellipsoid('SoftRaisedCapSpot', (center[0]+x, center[1]+y, center[2]+z),
                         (s, s*rng.uniform(.8, 1.08), radius*.020),
                         spot_material, 12, 6)
        normal = Vector((x/(radius*radius*stretch[0]**2), y/(radius*radius*stretch[1]**2), z/(top_height*top_height))).normalized()
        spot.rotation_euler = normal.to_track_quat('Z', 'Y').to_euler()
        parts.append(spot)


def spring_stone(index, center, dimensions, angle):
    rng = random.Random(991+index)
    corners = 7 + index % 3
    outline = [(math.cos(math.tau*i/corners)*rng.uniform(.9, 1.06),
                math.sin(math.tau*i/corners)*rng.uniform(.88, 1.05)) for i in range(corners)]
    height = dimensions[2]
    rings = [(0, .79, 0, 0), (.14, 1, -.045, .035), (.72, .96, .045, -.04), (1, .79, -.03, .04)]
    vertices = []
    for z, scale, dx, dy in rings:
        for x, y in outline:
            vertices.append(((x*scale+dx)*dimensions[0]/2,
                             (y*scale+dy)*dimensions[1]/2,
                             z*height + (.026*x-.018*y)*height if z else 0))
    faces = [tuple(range(corners-1, -1, -1))]
    for row in range(len(rings)-1):
        for i in range(corners):
            j = (i+1)%corners
            faces.append((row*corners+i, row*corners+j, (row+1)*corners+j, (row+1)*corners+i))
    faces.append(tuple((len(rings)-1)*corners+i for i in range(corners)))
    obj = mesh_object('SpringBroadFracturedStone', vertices, faces, 'M_SF_Spring_PaintedStone')
    activate(obj)
    bevel = obj.modifiers.new('SoftFractureEdges', 'BEVEL'); bevel.width = .045; bevel.segments = 3
    bevel.limit_method = 'ANGLE'; bevel.angle_limit = .3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    weighted = obj.modifiers.new('BroadStoneNormals', 'WEIGHTED_NORMAL'); weighted.weight = 60
    bpy.ops.object.modifier_apply(modifier=weighted.name)
    obj.location = center; obj.rotation_euler.z = angle
    return obj


def fern(parts, base, scale, orientation):
    for index in range(5):
        a = orientation + (index-2)*.58
        length = scale*(.7+.13*(2-abs(index-2)))
        pts = [(base[0]+math.cos(a)*length*t, base[1]+math.sin(a)*length*t,
                base[2]+scale*(.10+.55*math.sin(math.pi*.7*t))) for t in (0, .3, .6, .85, 1)]
        parts.append(tube('FernStem', pts, scale*.012, 'M_SF_Spring_Fern', 5))
        for t in (.22, .39, .55, .70, .84):
            p = Vector((base[0]+math.cos(a)*length*t, base[1]+math.sin(a)*length*t,
                        base[2]+scale*(.10+.55*math.sin(math.pi*.7*t))))
            for side in (-1, 1):
                direction = Vector((math.cos(a+side*1.1), math.sin(a+side*1.1), .2))
                extent = scale*.23*(1-.6*t)
                across = Vector((-math.sin(a), math.cos(a), 0))*scale*.034
                tip = p+direction*extent
                mid = p+direction*extent*.46
                leaf = mesh_object('FernLeaf', [tuple(p), tuple(mid+across), tuple(tip),
                                                tuple(mid-across), tuple(mid+Vector((0, 0, scale*.018)))],
                                   [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)],
                                   'M_SF_Spring_FernLight' if index%2 else 'M_SF_Spring_Fern')
                parts.append(leaf)


def finish_asset(name, parts, collision):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.hide_set(False); obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object; obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # All source pieces are smooth shaded. Preserve their split normals during FBX triangulation.
    triangulate = obj.modifiers.new('FBXTriangles', 'TRIANGULATE')
    if hasattr(triangulate, 'keep_custom_normals'):
        triangulate.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.data.update()
    if not obj.data.has_custom_normals:
        normals = [tuple(n.vector) for n in obj.data.corner_normals]
        obj.data.normals_split_custom_set(normals)
    obj['asset_id'] = name; obj['collision'] = collision
    return obj


def bounds(obj):
    return [[min(v.co[axis] for v in obj.data.vertices) for axis in range(3)],
            [max(v.co[axis] for v in obj.data.vertices) for axis in range(3)]]


assert REFERENCE.is_file(), 'Generate and inspect the new fungi/spring detail reference before final modeling.'
assets = []
patterns = [
    [(-.38, .20, 1.12, .49), (.37, .33, .77, .37), (.36, -.39, .49, .27), (-.27, -.37, .36, .22)],
    [(-.31, .20, .98, .52), (.43, .18, .67, .38), (.25, -.43, .44, .26)],
    [(-.27, .24, 1.20, .47), (.40, .26, .83, .35), (.39, -.37, .61, .31),
     (-.27, -.39, .49, .28), (-.61, -.06, .33, .19)],
]
for index, pattern in enumerate(patterns):
    parts = []
    for mushroom_index, (x, y, h, r) in enumerate(pattern):
        mushroom(parts, (x, y), h, r, index, 110+index*31+mushroom_index)
    assets.append(finish_asset(f'SM_SF_MushroomCluster_{index+1:02}', parts, 'none'))
for index, pattern in enumerate([
    [(-.33, .17, 1.26, .46), (.36, .13, .90, .35), (.20, -.40, .55, .26), (-.37, -.39, .39, .20)],
    [(-.26, .19, 1.07, .47), (.37, .18, .73, .36), (.15, -.41, .45, .25)],
]):
    parts = []
    for mushroom_index, (x, y, h, r) in enumerate(pattern):
        mushroom(parts, (x, y), h, r, index+3, 720+index*31+mushroom_index)
    assets.append(finish_asset(f'SM_SF_GlowMushroomCluster_{index+1:02}', parts, 'none'))
parts = []
for index in range(18):
    rng = random.Random(7000+index)
    angle = math.tau*index/18 + rng.uniform(-.032, .032)
    radial = 2.42 + .085*math.sin(3*angle+.4) + rng.uniform(-.025, .025)
    center = (radial*math.cos(angle), radial*math.sin(angle), 0)
    dims = (rng.uniform(.94, 1.10), rng.uniform(.86, 1.04), rng.uniform(.36, .67))
    parts.append(spring_stone(index, center, dims, angle))
    if index%3 != 0:
        moss_center = (center[0]-.065*math.cos(angle), center[1]-.065*math.sin(angle), dims[2]*.985)
        moss = ellipsoid('SmallSpringMossCushion', moss_center, (.28, .22, .023), 'M_SF_Spring_Moss', 24, 8)
        for vertex in moss.data.vertices:
            a = math.atan2(vertex.co.y, vertex.co.x)
            factor = 1 + .20*math.sin(3*a+index) + .12*math.cos(5*a-index)
            vertex.co.x *= factor; vertex.co.y *= factor
        moss.rotation_euler.z = angle
        parts.append(moss)
    if index in (1, 5, 9, 13, 16):
        fern(parts, ((radial+.40)*math.cos(angle), (radial+.40)*math.sin(angle), .10), .50, angle)
assets.append(finish_asset('SM_SF_SpringRockRing', parts, 'complex'))

infos = []
for obj in assets:
    activate(obj)
    bb = bounds(obj)
    tri_count = len(obj.data.polygons)
    assert all(len(p.vertices) == 3 and p.area > 1e-12 for p in obj.data.polygons)
    assert all(p.use_smooth for p in obj.data.polygons)
    assert obj.data.has_custom_normals and obj.data.uv_layers.active
    assert abs(bb[0][2]) < 1e-5
    names = [m.name for m in obj.data.materials]
    info = {'asset_id': obj.name, 'file': f'ArtSource/Meshes/Starfall/{obj.name}.fbx',
            'materials': names, 'collision': obj['collision'],
            'dimensions_m': [bb[1][i]-bb[0][i] for i in range(3)],
            'bounds_min_m': bb[0], 'bounds_max_m': bb[1],
            'triangles': tri_count, 'vertices': len(obj.data.vertices),
            'normal_import_method': 'IMPORT_NORMALS_AND_TANGENTS',
            'pivot': 'ground-centered at Z=0', 'uv_channel': 0}
    bpy.ops.export_scene.fbx(filepath=str(ROOT/info['file']), use_selection=True, object_types={'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
        bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE', use_mesh_modifiers=True,
        path_mode='STRIP', use_tspace=True)
    obj.hide_render = True; obj.hide_set(True)
    infos.append(info)

roundtrip = []
for original, expected in zip(assets, infos):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ROOT/expected['file']), use_custom_normals=True)
    added = set(bpy.data.objects)-before
    meshes = [o for o in added if o.type == 'MESH']
    assert len(meshes) == 1
    imported = meshes[0]
    actual = bounds(imported)
    error = max(abs(actual[j][i]-[expected['bounds_min_m'], expected['bounds_max_m']][j][i]) for j in range(2) for i in range(3))
    assert error < 2e-5, (original.name, error)
    assert len(imported.data.polygons) == expected['triangles']
    assert imported.data.has_custom_normals and all(p.use_smooth for p in imported.data.polygons)
    assert len(imported.data.materials) == len(expected['materials'])
    assert imported.data.uv_layers.active
    finite_uv = all(math.isfinite(value) for loop in imported.data.uv_layers.active.data for value in loop.uv)
    assert finite_uv
    roundtrip.append({'asset_id': original.name, 'passed': True, 'bounds_error_m': error,
                      'triangles': len(imported.data.polygons), 'triangle_count_preserved': True,
                      'material_count': len(imported.data.materials), 'authored_normals_preserved': True,
                      'all_faces_smooth': True, 'finite_uv': True, 'ground_pivot_preserved': True})
    for obj in added:
        bpy.data.objects.remove(obj, do_unlink=True)

metadata = {'source': 'ArtSource/Blender/StarfallFungiSpring.blend',
            'script': 'Scripts/build_starfall_fungi_spring.py',
            'reference': 'ArtSource/Reference/Starfall/Ref_StarfallFungiSpring.png',
            'units': 'metres', 'materials': MATERIALS, 'assets': infos,
            'placement_notes': 'Use clusters as foliage in 15x15 m ordinary and 5x5 m luminous habitats. '
                               'Spring rocks have a clear approximately 3.8 m interior and no water surface; reuse existing water material.',
            'fbx_roundtrip_validation': roundtrip}
(ART/'Layout/starfall_fungi_spring.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
(ART/'Previews/StarfallFungiSpring_Validation.json').write_text(json.dumps(
    {'passed': True, 'asset_count': len(assets), 'assets': infos, 'fbx_roundtrip_validation': roundtrip}, indent=2)+'\n', encoding='utf-8')

positions = [(-3.6, -1.9, 0), (-3.6, .2, 0), (-3.6, 2.4, 0),
             (-1.35, -1.5, 0), (-1.35, 1.35, 0), (3.05, .25, 0)]
for original, position in zip(assets, positions):
    duplicate = bpy.data.objects.new('Preview_'+original.name, original.data)
    presentation.objects.link(duplicate)
    duplicate.location = position
ground = bpy.data.materials.new('PreviewOnly_SageGround'); ground.use_nodes = True
ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.19, .25, .135, 1)
ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .95
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.025))
bpy.context.object.name = 'PreviewOnlyGround'; bpy.context.object.data.materials.append(ground)
scene.world = bpy.data.worlds.new('PreviewOnlySoftSky'); scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.63, .74, .9, 1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .62
bpy.ops.object.light_add(type='SUN', location=(-5, -8, 12))
sun = bpy.context.object; sun.name = 'PreviewOnlySun50deg'
sun.rotation_euler = (.4, -.5, -.55); sun.data.energy = 2.3; sun.data.angle = math.radians(50)
bpy.ops.object.camera_add(location=(-10, -14, 15))
camera = bpy.context.object; camera.name = 'PreviewOnlyCamera'
camera.rotation_euler = (Vector((.6, .3, .2))-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'; camera.data.ortho_scale = 14.5; scene.camera = camera
scene.render.engine = 'CYCLES'; scene.cycles.samples = 40; scene.cycles.use_denoising = True
scene.render.resolution_x = 1800; scene.render.resolution_y = 1300; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(ART/'Previews/Blender_StarfallFungiSpring.png')
scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/StarfallFungiSpring.blend'))
bpy.ops.render.render(write_still=True)
print('STARFALL_FUNGI_SPRING_COMPLETE '+json.dumps(infos))
