"""Rebuild the five Root Belltower architecture meshes from the saved references.

Blender 4.5, source metres, Z up and -Y front. Tower lean is baked into vertices;
the bell is a separate hollow static mesh whose origin is its suspension pivot.
No Unreal assets or shared source libraries are modified by this script.
"""
import bpy
import bmesh
import json
import math
import random
from pathlib import Path
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
for relative in ('Reference/RootBelltower/Ref_RootBelltowerOverview.png',
                 'Reference/RootBelltower/Ref_RootBelltowerArchitecture.png',
                 'Textures/T_AnimeForestRockPaint.png'):
    assert (ART / relative).is_file(), relative
for relative in ('Blender', 'Meshes/RootBelltower', 'Layout', 'Previews'):
    (ART / relative).mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
library = bpy.data.collections.new('RootBelltowerArchitecture_Library')
display = bpy.data.collections.new('RootBelltowerArchitecture_Presentation')
scene.collection.children.link(library)
scene.collection.children.link(display)
rng = random.Random(907851)
MATERIALS = {
    'M_RB_StonePaint': {'base_color': 'D8D4B9', 'roughness': .87, 'metallic': 0,
                      'base_color_texture': 'ArtSource/Textures/T_AnimeForestRockPaint.png'},
    'M_RB_CreamStone': {'base_color': 'D2CCAF', 'roughness': .85, 'metallic': 0},
    'M_RB_LightStone': {'base_color': 'E4DCC3', 'roughness': .83, 'metallic': 0},
    'M_RB_ShadowStone': {'base_color': '989F88', 'roughness': .9, 'metallic': 0},
    'M_RB_Moss': {'base_color': '7A8451', 'roughness': .97, 'metallic': 0},
    'M_RB_MossGold': {'base_color': 'A0A65D', 'roughness': .97, 'metallic': 0},
    'M_RB_TealSlate': {'base_color': '49817B', 'roughness': .72, 'metallic': .02},
    'M_RB_TealSlateLight': {'base_color': '7AA397', 'roughness': .75, 'metallic': .02},
    'M_RB_TealSlateDark': {'base_color': '355956', 'roughness': .81, 'metallic': .02},
    'M_RB_OldWood': {'base_color': '62543C', 'roughness': .91, 'metallic': 0},
    'M_RB_WoodGrain': {'base_color': '92816A', 'roughness': .88, 'metallic': 0},
    'M_RB_Iron': {'base_color': '414A40', 'roughness': .5, 'metallic': .7},
    'M_RB_Bronze': {'base_color': '697660', 'roughness': .46, 'metallic': .73},
    'M_RB_BronzeRim': {'base_color': 'AF9E68', 'roughness': .35, 'metallic': .78},
    'M_RB_BronzeDark': {'base_color': '3F4A3E', 'roughness': .58, 'metallic': .55},
}


def rgba(value):
    values = [int(value[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values)+(1,)


materials = {}
for name, properties in MATERIALS.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba(properties['base_color'])
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = properties['roughness']
    shader.inputs['Metallic'].default_value = properties['metallic']
    if properties.get('base_color_texture'):
        image = bpy.data.images.load(str(ROOT / properties['base_color_texture']))
        image.pack()
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = image
        mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
    materials[name] = mat


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def mesh_object(name, vertices, faces, material):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    library.objects.link(obj)
    mesh.materials.append(materials[material])
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def soften(obj, width=.025, segments=2):
    activate(obj)
    mod = obj.modifiers.new('BroadSoftEdges', 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    mod.angle_limit = .30
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = obj.modifiers.new('FaceWeightedNormals', 'WEIGHTED_NORMAL')
    mod.keep_sharp = True
    mod.weight = 70
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def prism_xz(name, points, front, back, material):
    n = len(points)
    vertices = [(x, y, z) for y in (front, back) for x, z in points]
    faces = [tuple(range(n-1, -1, -1)), tuple(n+i for i in range(n))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    return mesh_object(name, vertices, faces, material)


def cube(name, center, dimensions, material, bevel=.025):
    x, y, z = center
    dx, dy, dz = [v/2 for v in dimensions]
    obj = prism_xz(name, [(x-dx, z-dz), (x+dx, z-dz),
                          (x+dx, z+dz), (x-dx, z+dz)], y-dy, y+dy, material)
    return soften(obj, bevel) if bevel else obj


def transform(obj, matrix):
    obj.data.transform(matrix)
    obj.data.update()
    return obj


def side(obj, index):
    return transform(obj, Matrix.Rotation(index*math.pi/2, 4, 'Z'))


def stone():
    return rng.choices(['M_RB_CreamStone', 'M_RB_LightStone', 'M_RB_StonePaint',
                        'M_RB_ShadowStone'], [55, 18, 24, 3])[0]


def lathe(name, profile, material, segments=48):
    # A closed cross-section revolves into a hollow, watertight shell.
    vertices = [(r*math.cos(math.tau*i/segments), r*math.sin(math.tau*i/segments), z)
                for r, z in profile for i in range(segments)]
    faces = []
    for j in range(len(profile)):
        for i in range(segments):
            faces.append((j*segments+i, j*segments+(i+1) % segments,
                          ((j+1) % len(profile))*segments+(i+1) % segments,
                          ((j+1) % len(profile))*segments+i))
    return mesh_object(name, vertices, faces, material)


def cylinder(name, radius, low, high, material, segments=32):
    vertices = [(radius*math.cos(math.tau*i/segments), radius*math.sin(math.tau*i/segments), z)
                for z in (low, high) for i in range(segments)]
    faces = [tuple(range(segments-1, -1, -1)), tuple(segments+i for i in range(segments))]
    faces += [(i, (i+1) % segments, segments+(i+1) % segments, segments+i) for i in range(segments)]
    return mesh_object(name, vertices, faces, material)


def tube(name, points, radius, material, sides=8):
    vertices = []
    for i, point in enumerate(points):
        tangent = Vector(points[min(i+1, len(points)-1)])-Vector(points[max(i-1, 0)])
        tangent.normalize()
        ref = Vector((0, 0, 1)) if abs(tangent.z) < .9 else Vector((0, 1, 0))
        u = tangent.cross(ref).normalized()
        v = tangent.cross(u).normalized()
        vertices += [tuple(Vector(point)+radius*(math.cos(math.tau*j/sides)*u+
                     math.sin(math.tau*j/sides)*v)) for j in range(sides)]
    faces = [tuple(range(sides-1, -1, -1)), tuple((len(points)-1)*sides+j for j in range(sides))]
    for i in range(len(points)-1):
        for j in range(sides):
            faces.append((i*sides+j, i*sides+(j+1) % sides,
                          (i+1)*sides+(j+1) % sides, (i+1)*sides+j))
    return mesh_object(name, vertices, faces, material)


def oval(name, center, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=center)
    obj = bpy.context.object
    obj.name = name
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    library.objects.link(obj)
    obj.scale = scale
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    obj.data.materials.append(materials[material])
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def arch_blocks(name, radius, thickness, spring, front, back, count=13):
    objects = []
    for i in range(count):
        lo = math.pi*i/count+.006
        hi = math.pi*(i+1)/count-.006
        angles = [lo+(hi-lo)*j/3 for j in range(4)]
        outline = [(radius*math.cos(a), spring+radius*math.sin(a)) for a in angles]
        outline += [((radius+thickness)*math.cos(a), spring+(radius+thickness)*math.sin(a))
                    for a in reversed(angles)]
        objects.append(soften(prism_xz(name, outline, front, back, stone()), .018))
    return objects


def finish(name, parts, collision='complex'):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    tri = obj.modifiers.new('ExportTriangles', 'TRIANGULATE')
    if hasattr(tri, 'keep_custom_normals'):
        tri.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=tri.name)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tiny = [face for face in bm.faces if face.calc_area() < 1e-8]
    if tiny:
        bmesh.ops.delete(bm, geom=tiny, context='FACES_ONLY')
    bm.to_mesh(obj.data)
    bm.free()
    activate(obj)
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.008)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.data.update()
    if not obj.data.has_custom_normals:
        obj.data.normals_split_custom_set([tuple(n.vector) for n in obj.data.corner_normals])
    obj['asset_id'] = name
    obj['collision'] = collision
    obj['front_axis'] = '-Y'
    return obj


LEAN_RADIANS = math.radians(7)
LEAN = Matrix.Translation((0, 0, .8)) @ Matrix.Rotation(LEAN_RADIANS, 4, 'Y') @ Matrix.Translation((0, 0, -.8))
BELL_PIVOT = LEAN @ Vector((0, -.15, 13.05))


def tower():
    foundation = []
    for x in range(6):
        for y in range(6):
            foundation.append(cube('FoundationBroadSlab', (x-2.5, y-2.5, .19), (.997, .997, .38), stone(), .024))
    for index in range(4):
        for i in range(6):
            foundation.append(side(cube('FoundationDressedEdge', (i*.90-2.25, -2.45, .55),
                                        (.898, .55, .34), stone(), .024), index))
    body = []
    # Four genuine lower walls. Window and door openings are built into the masonry.
    for index in range(4):
        for row in range(20):
            z = .78+row*.445
            center_z = z+.2125
            half_open = 0
            if index == 0 and center_z < 3.6:
                half_open = 1.08
            if 5.45 < center_z < 7.75:
                half_open = .47
            spans = [(-2.68, -half_open), (half_open, 2.68)] if half_open else [(-2.68, 2.68)]
            for lo, hi in spans:
                count = max(1, round((hi-lo)/.87))
                for j in range(count):
                    a, b = lo+(hi-lo)*j/count, lo+(hi-lo)*(j+1)/count
                    body.append(side(cube('CoursedCreamWall', ((a+b)/2, -2.39, center_z),
                                           (b-a-.018, .56, .425), stone(), .025), index))
        # Engaged corner quoins and projecting horizontal cornices.
        for x in (-2.43, 2.43):
            for row in range(19):
                body.append(side(cube('CornerQuoin', (x, -2.49, 1.04+row*.454),
                                       (.62, .71, .435), 'M_RB_LightStone' if row % 4 else stone(), .027), index))
        for z, width, height in ((.82, 5.70, .22), (4.82, 5.78, .23), (9.61, 5.95, .31),
                                 (9.88, 5.65, .18), (14.32, 5.92, .27), (14.57, 6.08, .23)):
            for i in range(6):
                body.append(side(cube('ProjectingCorniceStone', ((i-2.5)*width/6, -2.53, z),
                                       (width/6-.012, .71, height), stone(), .022), index))
        # The rectangular wall aperture receives a rounded stone surround and a recessed wood grille.
        for x in (-.55, .55):
            body.append(side(cube('WindowSideStone', (x, -2.71, 6.40), (.19, .24, 1.57), stone(), .017), index))
        for obj in arch_blocks('WindowArchVoussoir', .46, .20, 7.10, -2.84, -2.55, 9):
            body.append(side(obj, index))
        body.append(side(cube('WindowSill', (0, -2.73, 5.54), (1.32, .52, .19), stone(), .021), index))
        for x in (-.23, .23):
            body.append(side(cube('WindowIronGrille', (x, -2.23, 6.40), (.045, .055, 1.68), 'M_RB_Iron', .008), index))
        body.append(side(cube('WindowIronCrossbar', (0, -2.23, 6.4), (.83, .055, .045), 'M_RB_Iron', .008), index))
    # Closed oak door, visible hinges, recessed into a real stone doorway.
    for i in range(8):
        x = (i-3.5)*.252
        top = 2.48+math.sqrt(max(0, .98*.98-x*x))
        body.append(cube('IndividualDoorPlank', (x, -2.13, (.75+top)/2), (.243, .18, top-.75), 'M_RB_OldWood', .018))
    for x in (-1.12, 1.12):
        for i in range(4):
            body.append(cube('DoorJamb', (x, -2.70, 1.00+i*.43), (.28, .39, .413), stone(), .023))
    body += arch_blocks('DoorArchVoussoir', 1.00, .33, 2.45, -2.92, -2.50, 11)
    for z in (1.20, 2.15):
        body.append(cube('IronDoorStrap', (0, -2.24, z), (1.86, .065, .10), 'M_RB_Iron', .013))
        for x in (-.78, -.28, .28, .78):
            body.append(oval('DoorStrapRivet', (x, -2.28, z), (.042, .018, .042), 'M_RB_BronzeRim'))
    body.append(oval('DoorLatch', (.24, -2.29, 1.76), (.075, .038, .095), 'M_RB_BronzeRim'))
    # A real open upper belfry, with one arch on each face and no false black panels.
    for x in (-2.26, 2.26):
        for y in (-2.26, 2.26):
            for row in range(9):
                body.append(cube('BelfryCornerColumn', (x, y, 10.16+row*.43), (.80, .80, .412), stone(), .026))
            body.append(cube('BelfryColumnCapital', (x, y, 12.10), (1.04, 1.04, .25), 'M_RB_LightStone', .023))
    for index in range(4):
        for obj in arch_blocks('BelfryArchVoussoir', 1.72, .50, 12.12, -2.68, -1.99, 13):
            body.append(side(obj, index))
        # Shallow spandrel pieces sit above the arch apex; the opening remains unobstructed.
        for x in (-2.08, 2.08):
            body.append(side(cube('BelfryUpperCorner', (x, -2.30, 13.83), (.96, .66, .67), stone(), .024), index))
        for i in range(6):
            body.append(side(cube('RoofFrieze', ((i-2.5)*.90, -2.36, 14.12), (.886, .62, .28), stone(), .022), index))
    body.append(cube('BelfryFloor', (0, 0, 9.71), (4.61, 4.61, .19), 'M_RB_ShadowStone', .035))
    body.append(cube('BellOakSuspensionBeam', (0, -.15, 13.26), (4.52, .48, .43), 'M_RB_OldWood', .045))
    for x in (-1.94, -.37, .37, 1.94):
        body.append(cube('BellBeamIronHoop', (x, -.15, 13.26), (.12, .52, .49), 'M_RB_Iron', .014))
    for x in (-.34, .34):
        body.append(cube('BellPivotBearing', (x, -.15, 13.06), (.15, .29, .25), 'M_RB_BronzeDark', .015))
    body.append(cube('BellFixedAxle', (0, -.15, 13.05), (.95, .14, .14), 'M_RB_Iron', .025))
    # Exposed rafters are deliberately visible through the missing front shingles.
    roof_base, roof_top = 14.64, 17.77
    for index in range(4):
        for u in (-.8, 0, .8):
            points = [(3.06*u, -3.06, roof_base), (.12*u, -.12, roof_top)]
            body.append(side(tube('ExposedRoofRafter', points, .105, 'M_RB_OldWood', 6), index))
        for row in range(9):
            t0, t1 = row/9, min(1, (row+1.13)/9)
            z0, z1 = roof_base+(roof_top-roof_base)*t0, roof_base+(roof_top-roof_base)*t1
            r0, r1 = 3.10*(1-t0)+.1*t0, 3.10*(1-t1)+.1*t1
            body.append(side(tube('ExposedRoofPurlin', [(-r0, -r0+.08, z0), (r0, -r0+.08, z0)],
                                       .075, 'M_RB_OldWood', 6), index))
            count = max(1, round(2*r0/.53))
            for col in range(count):
                u0, u1 = -1+2*col/count, -1+2*(col+1)/count
                center = (u0+u1)/2
                if index == 0 and row < 6 and abs(center-.13) < (.30 if row < 4 else .20):
                    continue
                if index == 1 and row in (1, 2, 3) and .15 < center < .60:
                    continue
                gap = .012
                vertices = [(r0*u0+gap, -r0-.018, z0), (r0*u1-gap, -r0-.018, z0),
                            (r1*u1-gap, -r1-.035, z1), (r1*u0+gap, -r1-.035, z1)]
                vertices += [(x, y+.065, z-.02) for x, y, z in vertices]
                faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                         (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
                slate = rng.choice(['M_RB_TealSlate', 'M_RB_TealSlate', 'M_RB_TealSlateLight', 'M_RB_TealSlateDark'])
                body.append(side(soften(mesh_object('IndividualTealRoofShingle', vertices, faces, slate), .009), index))
    body.append(cube('RoofFinialBase', (0, 0, 17.75), (.35, .35, .14), 'M_RB_Bronze', .018))
    body.append(cylinder('RoofFinialStem', .055, 17.77, 17.97, 'M_RB_BronzeRim', 16))
    body.append(oval('RoofFinialTip', (0, 0, 17.99), (.088, .088, .10), 'M_RB_Bronze'))
    # Discrete moss follows cornices; large wood roots are supplied by the separate tree kit.
    for index in range(4):
        for i in range(15):
            x = rng.uniform(-2.6, 2.6)
            z = rng.choice([.96, 4.96, 9.79, 14.46])
            body.append(side(oval('CorniceMossCushion', (x, -2.84, z),
                                  (rng.uniform(.15, .32), .085, .065), 'M_RB_Moss'), index))
    for obj in body:
        transform(obj, LEAN)
    return finish('SM_RB_Tower', foundation+body)


def bell():
    parts = []
    profile = [(.16, -.30), (.24, -.40), (.34, -.55), (.41, -.87), (.46, -1.28),
               (.56, -1.63), (.74, -1.91), (.88, -2.05), (.91, -2.17), (.85, -2.23),
               (.77, -2.20), (.75, -2.10), (.64, -1.97), (.47, -1.70), (.35, -1.29),
               (.29, -.89), (.23, -.63), (.12, -.52)]
    shell = lathe('ActualHollowBronzeBell', profile, 'M_RB_Bronze', 64)
    shell.data.materials.append(materials['M_RB_BronzeDark'])
    shell.data.materials.append(materials['M_RB_BronzeRim'])
    for index, poly in enumerate(shell.data.polygons):
        ring = index//64
        poly.material_index = 2 if ring in (7, 8, 9) else 1 if ring >= 10 else 0
    parts.append(shell)
    for z, r in ((-.60, .352), (-1.61, .565), (-2.04, .884)):
        ring = [(r-.012, z-.025), (r+.018, z-.025), (r+.018, z+.025), (r-.012, z+.025)]
        parts.append(lathe('CastBellDecorativeRing', ring, 'M_RB_BronzeRim', 64))
    # A vertical suspension eye touches the local origin; all animated geometry hangs below it.
    eye = [(0, .16*math.cos(math.tau*i/32), -.20+.16*math.sin(math.tau*i/32)) for i in range(33)]
    parts.append(tube('BellSuspensionEye', eye, .04, 'M_RB_BronzeRim', 8))
    parts.append(cylinder('ClapperStem', .055, -2.12, -.58, 'M_RB_BronzeDark', 16))
    parts.append(oval('VisibleBellClapper', (0, 0, -2.16), (.175, .175, .175), 'M_RB_BronzeRim'))
    # Broad leaf-shaped casting motifs read without tiny text or fragile intersecting geometry.
    for i in range(8):
        a = math.tau*i/8
        leaf = prism_xz('BellCastLeafEmblem', [(-.055, -1.15), (0, -.97), (.055, -1.15), (0, -1.31)],
                        -.467, -.447, 'M_RB_BronzeRim')
        parts.append(transform(leaf, Matrix.Rotation(a, 4, 'Z')))
    return finish('SM_RB_Bell', parts, 'none')


def cloister():
    parts = []
    for x in (-2.04, 2.04):
        parts.append(cube('CloisterFoot', (x, 0, .075), (.91, 1.12, .15), stone(), .018))
        for row in range(5):
            parts.append(cube('CloisterPierBlock', (x, 0, .41+row*.47), (.74, .85, .454), stone(), .03))
        parts.append(cube('CloisterCapital', (x, 0, 2.57), (.95, 1.01, .24), 'M_RB_LightStone', .021))
        for sign in (-1, 1):
            spiral = [(x+.20*math.exp(-t*.17)*math.cos(t), sign*.515,
                       2.60+.14*math.exp(-t*.17)*math.sin(t)) for t in [j*math.pi/12 for j in range(37)]]
            parts.append(tube('CloisterCapitalVolute', spiral, .032, 'M_RB_CreamStone', 7))
    parts += arch_blocks('CloisterArchVoussoir', 1.64, .61, 2.58, -.50, .50, 13)
    for x, z, width, height in ((-2.12, 3.64, .68, 1.22), (2.12, 3.39, .68, .80),
                                (-1.92, 4.33, .88, .29), (-1.13, 4.53, .65, .33),
                                (-.38, 4.65, .78, .26), (.44, 4.68, .80, .30),
                                (1.19, 4.50, .68, .23), (1.86, 4.35, .62, .23)):
        parts.append(cube('BrokenCloisterCoping', (x, 0, z), (width, .83, height), stone(), .032))
    for x, z in ((-2.20, .17), (1.86, .16), (-1.9, 2.73), (.42, 4.82)):
        parts.append(oval('CloisterStoneMoss', (x, -.19, z), (.24, .31, .06), 'M_RB_Moss'))
    return finish('SM_RB_CloisterArch', parts)


def courtyard():
    # A single continuous 10 cm slab under every ring prevents character-sized gaps.
    parts = [cylinder('ContinuousWalkableCourtyardBase', 6.0, 0, .10, 'M_RB_ShadowStone', 128)]
    parts.append(cylinder('CourtyardCenterStone', .70, .09, .12, 'M_RB_CreamStone', 48))
    for row in range(8):
        inner, outer = .70+row*.65, min(6.0, .70+(row+1)*.65)
        count = max(12, round(math.tau*(inner+outer)/2/.73))
        for col in range(count):
            a = math.tau*(col+(row % 2)*.5)/count+.002
            b = math.tau*(col+1+(row % 2)*.5)/count-.002
            angles = [a+(b-a)*i/3 for i in range(4)]
            points = [(inner*math.cos(t), inner*math.sin(t)) for t in reversed(angles)]
            points += [(outer*math.cos(t), outer*math.sin(t)) for t in angles]
            n = len(points)
            vertices = [(x, y, z) for z in (.095, .12) for x, y in points]
            faces = [tuple(range(n-1, -1, -1)), tuple(n+i for i in range(n))]
            faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
            parts.append(mesh_object('BroadRadialPavingStone', vertices, faces, stone()))
    # Shallow flush bronze roots form a circular datum, safely below a normal footstep.
    for r in (1.12, 3.29):
        parts.append(lathe('CourtyardFlushBronzeCircle', [(r, .115), (r+.025, .115),
                           (r+.025, .122), (r, .122)], 'M_RB_BronzeRim', 128))
    return finish('SM_RB_Courtyard', parts)


def capital():
    parts = [lathe('FallenColumnFlutedCore', [(.40, 0), (.49, .07), (.47, .20), (.36, .30),
                    (.34, 1.01), (.50, 1.15), (.56, 1.22), (.54, 1.34), (.40, 1.35)],
                   'M_RB_StonePaint', 32)]
    parts += [cube('CapitalSquareAbacus', (0, 0, 1.40), (1.22, 1.22, .17), 'M_RB_CreamStone', .045),
              cube('CapitalBaseSlab', (0, 0, .10), (1.10, 1.10, .20), 'M_RB_LightStone', .035)]
    for i in range(12):
        a = math.tau*i/12
        leaf = prism_xz('BroadAcanthusLeaf', [(-.13, .31), (-.18, .62), (-.11, .90), (0, 1.12),
                                          (.11, .90), (.18, .62), (.13, .31)], -.48, -.34, 'M_RB_CreamStone')
        parts.append(transform(soften(leaf, .019), Matrix.Rotation(a, 4, 'Z')))
    for index in range(4):
        for x in (-.31, .31):
            pts = [(x+.19*math.exp(-t*.15)*math.cos(t), -.56,
                    1.14+.16*math.exp(-t*.15)*math.sin(t)) for t in [j*math.pi/12 for j in range(37)]]
            parts.append(side(tube('CarvedCapitalVolute', pts, .045, 'M_RB_LightStone', 8), index))
    turn = Matrix.Rotation(math.pi/2, 4, 'Y')
    for obj in parts:
        transform(obj, turn)
    low = min(v.co.z for obj in parts for v in obj.data.vertices)
    for obj in parts:
        transform(obj, Matrix.Translation((-.74, 0, -low)))
    return finish('SM_RB_FallenCapital', parts, 'none')


def bounds(obj):
    return [[min(v.co[a] for v in obj.data.vertices) for a in range(3)],
            [max(v.co[a] for v in obj.data.vertices) for a in range(3)]]


assets = [tower(), bell(), cloister(), courtyard(), capital()]
# Measure traversability against the actual triangles, not a nominal doorway rectangle.
arch = assets[2]
bvh = BVHTree.FromPolygons([v.co for v in arch.data.vertices],
                          [tuple(p.vertices) for p in arch.data.polygons], all_triangles=True)
clearance_rays = 0
for x in (-1.4, -.7, 0, .7, 1.4):
    for z in (.18, .7, 1.3, 2.0, 2.6, 3.2):
        hit = bvh.ray_cast(Vector((x, -1.2, z)), Vector((0, 1, 0)), 2.4)
        assert hit[0] is None, ('Cloister opening blocked', x, z, hit[0])
        clearance_rays += 1
court = assets[3]
bvh = BVHTree.FromPolygons([v.co for v in court.data.vertices],
                          [tuple(p.vertices) for p in court.data.polygons], all_triangles=True)
floor_samples = []
for y in range(-11, 12):
    for x in range(-11, 12):
        if math.hypot(x*.5, y*.5) > 5.75:
            continue
        hit = bvh.ray_cast(Vector((x*.5, y*.5, 1)), Vector((0, 0, -1)), 2)
        assert hit[0] is not None and .099 < hit[0].z < .123, (x, y, hit[0])
        floor_samples.append(float(hit[0].z))
infos = []
for obj in assets:
    activate(obj)
    bb = bounds(obj)
    assert all(len(p.vertices) == 3 and p.area > 1e-10 for p in obj.data.polygons), obj.name
    assert all(p.use_smooth for p in obj.data.polygons)
    assert obj.data.has_custom_normals and obj.data.uv_layers.active
    info = {'asset_id': obj.name, 'file': f'ArtSource/Meshes/RootBelltower/{obj.name}.fbx',
            'materials': [m.name for m in obj.data.materials], 'collision': obj['collision'],
            'dimensions_m': [bb[1][i]-bb[0][i] for i in range(3)],
            'bounds_min_m': bb[0], 'bounds_max_m': bb[1],
            'triangles': len(obj.data.polygons), 'vertices': len(obj.data.vertices),
            'normal_import_method': 'IMPORT_NORMALS_AND_TANGENTS',
            'pivot': 'suspension pivot; geometry hangs below Z=0' if obj.name == 'SM_RB_Bell' else 'floor origin at Z=0',
            'uv_channel': 0, 'front_axis': '-Y'}
    bpy.ops.export_scene.fbx(filepath=str(ROOT / info['file']), use_selection=True, object_types={'MESH'},
                            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y',
                            axis_up='Z', bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE',
                            use_mesh_modifiers=True, path_mode='STRIP', use_tspace=True)
    obj.hide_render = True
    obj.hide_set(True)
    infos.append(info)

roundtrip = []
for expected in infos:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ROOT / expected['file']), use_custom_normals=True)
    added = set(bpy.data.objects)-before
    imported = [o for o in added if o.type == 'MESH']
    assert len(imported) == 1
    obj = imported[0]
    actual = bounds(obj)
    error = max(abs(actual[j][i]-[expected['bounds_min_m'], expected['bounds_max_m']][j][i])
                for j in range(2) for i in range(3))
    assert error < 3e-5, (expected['asset_id'], error)
    assert len(obj.data.polygons) == expected['triangles']
    assert obj.data.has_custom_normals and all(p.use_smooth for p in obj.data.polygons)
    imported_mats = [m.name.rsplit('.', 1)[0] if m.name.rsplit('.', 1)[-1].isdigit() else m.name
                     for m in obj.data.materials]
    assert imported_mats == expected['materials'], imported_mats
    assert obj.data.uv_layers.active
    assert all(math.isfinite(v) for loop in obj.data.uv_layers.active.data for v in loop.uv)
    roundtrip.append({'asset_id': expected['asset_id'], 'passed': True, 'bounds_error_m': error,
                      'triangle_count_preserved': True, 'ordered_material_slots_preserved': True,
                      'authored_normals_preserved': True, 'all_faces_smooth': True, 'finite_uv': True})
    for obj in added:
        bpy.data.objects.remove(obj, do_unlink=True)

metadata = {'source': 'ArtSource/Blender/RootBelltowerArchitecture.blend',
            'script': 'Scripts/build_rootbelltower_architecture.py',
            'reference': 'ArtSource/Reference/RootBelltower/Ref_RootBelltowerArchitecture.png',
            'units': 'metres', 'materials': MATERIALS, 'assets': infos,
            'tower_lean_degrees_towards_blender_positive_x': 7,
            'bell_pivot_m': list(BELL_PIVOT), 'bell_rotation_degrees_xyz': [0, 7, 0],
            'tower_nominal_foundation_width_m': 6,
            'placement_notes': 'Tower lean is already baked into vertices. Do not add a second 7 degree tilt. '
            'Bell origin is its suspension pivot: put it at bell_pivot_m then rotate local Y +7 degrees. '
            'Cloister faces -Y with a tested 2.8 m wide by 3.2 m tall clear passage. '
            'Courtyard is a 12 m diameter continuous low slab (10 to 12.2 cm) with radial paving. '
            'Giant tree and roots are deliberately separate assets.',
            'fbx_roundtrip_validation': roundtrip}
(ART / 'Layout/rootbelltower_architecture.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
validation = {'passed': True, 'asset_count': 5, 'assets': infos, 'fbx_roundtrip_validation': roundtrip,
              'bell_pivot_m': list(BELL_PIVOT), 'bell_hollow_shell': True,
              'accessibility': {'arch_clearance_width_m': 2.8, 'arch_clearance_height_m': 3.2,
                                'arch_clearance_rays_passed': clearance_rays,
                                'courtyard_floor_sample_count': len(floor_samples),
                                'courtyard_min_height_m': min(floor_samples),
                                'courtyard_max_height_m': max(floor_samples),
                                'courtyard_continuous_foundation': True}}
(ART / 'Previews/RootBelltowerArchitecture_Validation.json').write_text(json.dumps(validation, indent=2)+'\n', encoding='utf-8')

placements = [(0, 2, 0), tuple(BELL_PIVOT+Vector((0, 2, 0))), (-6.8, -.5, 0), (-.6, -9.5, 0), (6.3, -5.6, 0)]
duplicates = []
for original, position in zip(assets, placements):
    duplicate = bpy.data.objects.new('Preview_'+original.name, original.data)
    display.objects.link(duplicate)
    duplicate.location = position
    if original.name == 'SM_RB_Bell':
        duplicate.rotation_euler.y = LEAN_RADIANS
    duplicates.append(duplicate)
ground = bpy.data.materials.new('PreviewOnlyWarmGreyGround')
ground.use_nodes = True
ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.20, .22, .19, 1)
ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .95
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.03))
bpy.context.object.name = 'PreviewOnlyGround'
bpy.context.object.data.materials.append(ground)
scene.world = bpy.data.worlds.new('PreviewOnlySoftSky')
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.60, .72, .83, 1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .72
bpy.ops.object.light_add(type='SUN', location=(-5, -8, 22))
sun = bpy.context.object
sun.rotation_euler = (.45, -.5, -.55)
sun.data.energy = 2.5
sun.data.angle = math.radians(50)
bpy.ops.object.light_add(type='AREA', location=(1, -12, 15))
area = bpy.context.object
area.data.energy = 1700
area.data.shape = 'DISK'
area.data.size = 8
area.rotation_euler = (Vector((0, 0, 7))-area.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(location=(24, -39, 27))
camera = bpy.context.object
camera.rotation_euler = (Vector((-.5, -2.1, 7.4))-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 29.0
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1600
scene.render.resolution_y = 1600
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.filepath = str(ART / 'Previews/Blender_RootBelltowerArchitecture.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART / 'Blender/RootBelltowerArchitecture.blend'))
bpy.ops.render.render(write_still=True)
camera.location = (8, -18, 16)
camera.rotation_euler = (Vector(tuple(BELL_PIVOT+Vector((0, 2, -.9))))-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = 9
scene.render.resolution_x = 1400
scene.render.resolution_y = 1400
scene.render.filepath = str(ART / 'Previews/Blender_RootBelltowerArchitecture_Belfry.png')
bpy.ops.render.render(write_still=True)
print('ROOT_BELLTOWER_ARCHITECTURE_COMPLETE '+json.dumps(infos))
