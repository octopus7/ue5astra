"""Build original toy-like BeastCrossing village geometry, in Blender meters.

Run with Blender 4.5 --background --python build_village.py.
All geometry uses +Z up; front doors face south (-Y). No external textures.
"""
from pathlib import Path
import bpy
import bmesh
import math
import json
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Art' / 'Blender' / 'village.blend'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for block in bpy.data.materials:
    bpy.data.materials.remove(block)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1.0


def material(name, color, roughness=.76):
    mat = bpy.data.materials.new('M_VILL_' + name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    return mat


wood = material('Walnut', (.21, .105, .058))
woodlight = material('HoneyWood', (.49, .278, .115))
woodpale = material('PaleWood', (.69, .44, .22))
doorwood = material('PaintedDoor', (.25, .40, .31))
ivory = material('IvoryTrim', (.96, .87, .67))
stone = material('WarmFoundation', (.50, .46, .36))
panes = material('DeepBlueGlass', (.07, .18, .21), .27)
reflection = material('GlassGlint', (.54, .80, .78), .35)
brass = material('AgedBrass', (.78, .51, .16), .3)
rope = material('HempRope', (.70, .57, .34))
chimney = material('ChimneyBrick', (.55, .255, .15))
chimney_dark = material('ChimneyInterior', (.09, .066, .052))
soil = material('PlanterSoil', (.19, .115, .061))
leaf = material('PlanterLeaf', (.23, .46, .17))
flower = material('PlanterFlower', (.98, .59, .35))
themes = [
    ('Peach', material('PeachPlaster', (.91, .58, .37)),
     material('TealRoof', (.11, .39, .38)), material('TealRoofShade', (.075, .27, .28)),
     material('TealShinglesLight', (.16, .48, .45))),
    ('Cream', material('CreamPlaster', (.92, .81, .58)),
     material('TerracottaRoof', (.72, .245, .12)), material('TerracottaRoofShade', (.45, .13, .065)),
     material('TerracottaShinglesLight', (.82, .33, .15))),
    ('Sage', material('SagePlaster', (.59, .73, .47)),
     material('MustardRoof', (.79, .51, .12)), material('MustardRoofShade', (.48, .30, .071)),
     material('MustardShinglesLight', (.88, .62, .18))),
]


def finish(obj, name, mat, bevel=0):
    obj.name = 'VILL_' + name
    if mat:
        obj.data.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Soft toy edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod = obj.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
        mod.keep_sharp = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.select_set(False)
    return obj


def cube(name, location, scale, mat, bevel=.065, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.dimensions = scale
    if rot:
        obj.rotation_euler = rot
    return finish(obj, name, mat, bevel)


def cylinder(name, start, end, radius, mat, vertices=12, bevel=.025):
    start, end = Vector(start), Vector(end)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                      depth=(end - start).length, location=(start + end) / 2)
    obj = bpy.context.object
    obj.rotation_euler = (end - start).to_track_quat('Z', 'Y').to_euler()
    return finish(obj, name, mat, bevel)


def sphere(name, location, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1, location=location)
    obj = bpy.context.object
    obj.scale = scale
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return finish(obj, name, mat)


def mesh(name, vertices, faces, mat, bevel=.035):
    data = bpy.data.meshes.new('VILL_' + name + '_Mesh')
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new('VILL_' + name, data)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat, bevel)


def extrusion(name, polygon, yfront, yback, mat, bevel=.03):
    """Extrude an X/Z polygon along Y, with consistently outward faces."""
    count = len(polygon)
    vertices = [(x, yfront, z) for x, z in polygon] + [(x, yback, z) for x, z in polygon]
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
    obj = mesh(name, vertices, faces, mat, bevel)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    return obj


def arch(name, x, y, bottom, width, height, depth, mat):
    radius = width / 2
    sideheight = height - radius
    polygon = [(x - radius, bottom), (x + radius, bottom)]
    polygon += [(x + math.cos(a) * radius, bottom + sideheight + math.sin(a) * radius)
                for a in [i * math.pi / 12 for i in range(13)]]
    return extrusion(name, polygon, y - depth / 2, y + depth / 2, mat, .055)


def roof_strip(name, x1, x2, z1, z2, y1, y2, mat, thickness=.22):
    return extrusion(name, [(x1, z1), (x2, z2), (x2, z2 - thickness), (x1, z1 - thickness)], y1, y2, mat, .055)


def front_window(tag, x, y, z, width=1.35, height=1.4, box=True):
    cube(tag + '_WindowRecess', (x, y, z), (width + .24, .14, height + .25), wood, .09)
    cube(tag + '_BlueGlass', (x, y - .085, z), (width, .10, height), panes, .055)
    for dx in [-width / 2, width / 2]:
        cube(tag + '_FrameSide', (x + dx, y - .17, z), (.15, .18, height + .2), ivory, .04)
    for dz in [-height / 2, height / 2]:
        cube(tag + '_FrameTopBottom', (x, y - .17, z + dz), (width + .2, .18, .15), ivory, .04)
    cube(tag + '_Mullion', (x, y - .19, z), (.09, .12, height), woodpale, .02)
    cube(tag + '_Crossbar', (x, y - .19, z), (width, .12, .085), woodpale, .02)
    cube(tag + '_GlassGlint', (x - .25, y - .145, z + .25), (.055, .021, .30), reflection, .01, (0, -.32, 0))
    cube(tag + '_WindowSill', (x, y - .24, z - height / 2 - .1), (width + .42, .48, .17), woodlight, .05)
    if box:
        cube(tag + '_FlowerBox', (x, y - .43, z - height / 2 - .38), (width + .18, .45, .42), woodlight, .045)
        cube(tag + '_FlowerBoxRim', (x, y - .43, z - height / 2 - .17), (width + .29, .54, .105), woodpale, .04)
        cube(tag + '_FlowerBoxSoil', (x, y - .43, z - height / 2 - .105), (width + .05, .35, .04), soil, .01)
        for i in range(4):
            px = x - width * .38 + i * width * .25
            sphere(tag + '_PlanterLeaf', (px, y - .44, z - height / 2), (.18, .16, .20), leaf)
            sphere(tag + '_PlanterFlower', (px + .04, y - .45, z - height / 2 + .15), (.13, .12, .10), flower)


def fence(name, points, base):
    for i, (x, y) in enumerate(points):
        cube(name + '_Post', (x, y, base + .6), (.23, .23, 1.2), woodpale, .045)
        sphere(name + '_PostCap', (x, y, base + 1.23), (.17, .17, .105), woodlight)
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        for height in [.37, .85]:
            cylinder(name + '_Rail', (x1, y1, base + height), (x2, y2, base + height), .087, woodpale, 8)


def mailbox(tag, x, y, z, roofmat):
    cube(tag + '_MailboxFoot', (x, y, z + .08), (.58, .58, .16), stone)
    cube(tag + '_MailboxPost', (x, y, z + .73), (.22, .22, 1.42), woodlight, .045)
    arch(tag + '_Mailbox', x, y, z + 1.2, .72, .71, .80, roofmat)
    arch(tag + '_MailboxFront', x, y - .419, z + 1.24, .57, .56, .05, ivory)
    cube(tag + '_MailboxSlot', (x, y - .46, z + 1.57), (.38, .035, .07), wood, .018)
    sphere(tag + '_MailboxKnob', (x, y - .5, z + 1.4), (.075, .06, .06), brass)
    cube(tag + '_MailboxFlagStem', (x + .45, y, z + 1.86), (.08, .08, .54), woodlight, .02)
    cube(tag + '_MailboxFlag', (x + .57, y, z + 2.1), (.30, .08, .20), chimney, .035)


def cottage(index, center, width=7.5, depth=6.0):
    x, y, z = center
    title, plaster, roof, roofdark, rooflight = themes[index]
    tag = title + 'Cottage'
    front, back = y - depth / 2, y + depth / 2
    walltop, ridge = z + 3.85, z + 6.20
    cube(tag + '_StoneFooting', (x, y, z + .15), (width + .25, depth + .2, .30), stone, .12)
    cube(tag + '_PlasterBody', (x, y, z + 2.025), (width, depth, 3.75), plaster, .16)
    extrusion(tag + '_Gable', [(x - width / 2, walltop - .04), (x, ridge - .24),
              (x + width / 2, walltop - .04)], front + .01, back - .01, plaster, .045)
    for dx in [-width / 2 + .04, width / 2 - .04]:
        for dy in [-depth / 2 + .04, depth / 2 - .04]:
            cube(tag + '_CornerTimber', (x + dx, y + dy, z + 2.03), (.24, .24, 3.83), ivory, .045)
    cube(tag + '_FrontBaseTrim', (x, front - .055, z + .42), (width, .19, .22), woodpale, .04)
    cube(tag + '_FrontWallHeader', (x, front - .06, walltop - .12), (width, .20, .18), ivory, .04)
    for side in [-1, 1]:
        cube(tag + '_SideBaseTrim', (x + side * width / 2, y, z + .42), (.18, depth, .22), woodpale, .04)

    # Gently flared roof profile; each exposed band has individual raised shingles.
    half = width / 2 + .67
    profile = [(0, ridge), (half * .36, ridge - .86), (half * .7, walltop + .41), (half, walltop - .03)]
    for side in [-1, 1]:
        for row in range(len(profile) - 1):
            a, b = profile[row], profile[row + 1]
            roof_strip(tag + '_RoofBase', x + side * a[0], x + side * b[0], a[1], b[1], front - .64, back + .64, roofdark, .28)
            pieces = 8
            span = (depth + 1.34) / pieces
            for col in range(pieces):
                y1 = front - .67 + col * span + .022
                y2 = y1 + span - .044
                shinglemat = rooflight if (row * 2 + col + index) % 4 == 0 else roof
                roof_strip(tag + '_RaisedShingle', x + side * a[0], x + side * b[0], a[1] + .055, b[1] + .055, y1, y2, shinglemat, .135)
        for edgey in [front - .70, back + .70]:
            for a, b in zip(profile, profile[1:]):
                cylinder(tag + '_RoundedFascia', (x + side * a[0], edgey, a[1] - .09),
                         (x + side * b[0], edgey, b[1] - .09), .13, roofdark, 10)
        cylinder(tag + '_RoundEave', (x + side * half, front - .7, walltop - .11),
                 (x + side * half, back + .7, walltop - .11), .15, roofdark, 12)
    cylinder(tag + '_RidgeCap', (x, front - .75, ridge + .055), (x, back + .75, ridge + .055), .19, rooflight, 12)

    # Tall arched timber front door with five separately modeled slats.
    arch(tag + '_DoorSurround', x, front - .14, z + .26, 1.90, 2.75, .28, ivory)
    arch(tag + '_DoorInset', x, front - .315, z + .29, 1.57, 2.48, .16, wood)
    arch(tag + '_DoorLeaf', x, front - .419, z + .34, 1.40, 2.36, .13, doorwood if index != 0 else woodlight)
    for dx in [-.49, -.245, 0, .245, .49]:
        cube(tag + '_DoorSlat', (x + dx, front - .494, z + 1.18), (.025, .035, 1.63), wood, .008)
    cylinder(tag + '_KnobPlate', (x + .43, front - .50, z + 1.49), (x + .43, front - .535, z + 1.49), .12, brass, 12)
    sphere(tag + '_DoorKnob', (x + .43, front - .61, z + 1.49), (.09, .10, .09), brass)
    for step in range(3):
        cube(tag + '_FrontStep', (x, front - .76 - step * .30, z + .255 - step * .075),
             (2.08 + step * .22, .48, .21 - step * .045), stone, .065)

    for offset in [-width * .29, width * .29]:
        front_window(tag, x + offset, front - .10, z + 2.24, width=1.3 if index < 2 else 1.6)

    # Small circular attic window and square lattice; look south.
    cylinder(tag + '_AtticFrame', (x, front - .08, z + 4.5), (x, front - .30, z + 4.5), .44, ivory, 20, .04)
    cylinder(tag + '_AtticGlass', (x, front - .305, z + 4.5), (x, front - .337, z + 4.5), .32, panes, 20, .02)
    cube(tag + '_AtticMullion', (x, front - .36, z + 4.5), (.065, .055, .61), woodpale, .015)
    cube(tag + '_AtticCrossbar', (x, front - .36, z + 4.5), (.61, .055, .065), woodpale, .015)

    # Side windows face east and west, rotated as a complete local group.
    for sign in [-1, 1]:
        before = set(bpy.data.objects)
        front_window(tag + '_Side', 0, 0, z + 2.1, 1.4, 1.25, False)
        for obj in set(bpy.data.objects) - before:
            local = obj.location.copy()
            angle = sign * math.pi / 2
            obj.location.x = x + sign * (width / 2 + .04) + local.x * math.cos(angle) - local.y * math.sin(angle)
            obj.location.y = y + .8 + local.x * math.sin(angle) + local.y * math.cos(angle)
            obj.rotation_euler.z += angle

    # Compact curved porch canopy, one on each cottage.
    awningz = z + 3.38
    roof_strip(tag + '_PorchCanopy', x - 1.37, x + 1.37, awningz, awningz, front - 1.30, front - .21, roof, .17)
    for i in range(7):
        sphere(tag + '_CanopyScallop', (x - 1.17 + i * .39, front - 1.31, awningz - .09), (.22, .115, .19), ivory)
    for dx in [-1.16, 1.16]:
        cylinder(tag + '_CanopyBrace', (x + dx, front - .13, z + 2.76), (x + dx, front - 1.12, awningz - .17), .055, woodpale, 8)

    # Four brick courses and overhanging cap, inset dark opening above roof.
    cx, cy = x + width * .29, y + 1.45
    cbase = walltop + 1.0
    for course in range(4):
        cube(tag + '_ChimneyCourse', (cx, cy, cbase + course * .35), (.74, .77, .33), chimney, .038)
        cube(tag + '_ChimneyMortar', (cx, cy, cbase + course * .35 + .17), (.75, .78, .028), ivory, .007)
    top = cbase + 1.29
    cube(tag + '_ChimneyCap', (cx, cy, top), (.93, .96, .17), stone, .045)
    cube(tag + '_ChimneyOpening', (cx, cy, top + .09), (.55, .57, .035), chimney_dark, .045)
    mailbox(tag, x - width / 2 - .60, front - 2.00, z, roof)

    # Low garden edges leave a generous open route through the south doorway.
    gardenleft = x - width / 2 - 1.10
    gardenright = x + width / 2 + 1.10
    fence(tag + '_GardenWest', [(gardenleft, y + 2.5), (gardenleft, y), (gardenleft, front - 1.0)], z)
    fence(tag + '_GardenEast', [(gardenright, y + 2.5), (gardenright, y), (gardenright, front - 1.0)], z)
    fence(tag + '_GardenFrontWest', [(gardenleft, front - 1.0), (x - 2.9, front - 1.0)], z)
    fence(tag + '_GardenFrontEast', [(x + 2.9, front - 1.0), (gardenright, front - 1.0)], z)


cottage(0, (-21, 8, 2), 7.5)
cottage(1, (16, 9, 2), 7.8)
cottage(2, (0, 22, 6), 8.8)


def curve_rope(name, points, radius=.045):
    data = bpy.data.curves.new('VILL_' + name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 16
    data.bevel_depth = radius
    data.bevel_resolution = 2
    spline = data.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1)
    obj = bpy.data.objects.new('VILL_' + name, data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    obj.data.materials.append(rope)
    obj.select_set(False)
    return obj


# Raised wooden dock deck: z=1.0 at top. The approach meets it at y=-36.
for side in [-1, 1]:
    cube('Dock_LongBeam', (side * 1.48, -41.5, .63), (.24, 11.4, .34), wood, .06)
for i in range(16):
    py = -36.35 - i * .70
    cube('Dock_DeckPlank', (0, py, .855), (4.0, .66, .29), woodpale if i % 4 in (0, 3) else woodlight, .055)
    for side in [-1, 1]:
        for edge in [-.19, .19]:
            cylinder('Dock_Peg', (side * 1.48, py + edge, .994), (side * 1.48, py + edge, 1.011), .035, wood, 8, .003)

postys = [-36.1, -39.6, -43.1, -46.60]
for side in [-1, 1]:
    for py in postys:
        cylinder('Dock_Piling', (side * 2.03, py, -1.30), (side * 2.03, py, 1.94), .18, woodlight, 12, .055)
        cylinder('Dock_PostCap', (side * 2.03, py, 1.91), (side * 2.03, py, 2.01), .22, woodpale, 12, .02)
        cylinder('Dock_RopeWrap', (side * 2.03, py, 1.50), (side * 2.03, py, 1.65), .20, rope, 12, .012)
    for a, b in zip(postys, postys[1:]):
        points = [(side * 2.03, a + (b - a) * t / 16, 1.58 - .26 * math.sin(math.pi * t / 16)) for t in range(17)]
        curve_rope('Dock_SaggingRope', points)

# A flat grass boardwalk continues the path, followed by a beach-spanning ramp.
# Actual terrain grass ends near y=-30.1; descending any earlier buries planks.
def approach_height(y):
    return 2.10 if y >= -30 else 2.10 + (y + 30) * 1.05 / 6


for i in range(18):
    y1 = -27.0 - i * .5
    y2 = y1 - .485
    z1, z2 = approach_height(y1), approach_height(y2)
    vertices = [(-1.87, y1, z1), (1.87, y1, z1), (1.87, y2, z2), (-1.87, y2, z2),
                (-1.87, y1, z1 - .18), (1.87, y1, z1 - .18), (1.87, y2, z2 - .18), (-1.87, y2, z2 - .18)]
    mesh('Dock_RampPlank', vertices, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], woodpale if i % 3 == 0 else woodlight, .04)
for side in [-1, 1]:
    for ya, yb in [(-27, -30), (-30, -36)]:
        cylinder('Dock_RampSupport', (side * 1.55, ya, approach_height(ya) - .28),
                 (side * 1.55, yb, approach_height(yb) - .28), .12, wood, 8)
    approachposts = [-27.25, -30.0, -33.0]
    for py in approachposts:
        pz = approach_height(py)
        cylinder('Dock_ApproachPost', (side * 2.03, py, pz - .9), (side * 2.03, py, pz + .83), .13, woodlight, 12, .04)
        cylinder('Dock_ApproachCap', (side * 2.03, py, pz + .79), (side * 2.03, py, pz + .89), .17, woodpale, 12, .018)
    for ya, yb in zip(approachposts, approachposts[1:] + [-36.1]):
        points = []
        for step in range(17):
            t = step / 16
            py = ya + (yb - ya) * t
            endheight = 1.58 if yb == -36.1 else approach_height(yb) + .65
            pz = (approach_height(ya) + .65) * (1 - t) + endheight * t - .12 * math.sin(math.pi * t)
            points.append((side * 2.03, py, pz))
        curve_rope('Dock_ApproachRope', points)

# Small swimming ladder off the east edge of the dock.
for py in [-43.85, -44.8]:
    cylinder('Dock_LadderRail', (2.23, py, -.80), (2.23, py, 1.47), .065, woodpale, 10)
    cylinder('Dock_LadderHandle', (1.78, py, 1.40), (2.23, py, 1.47), .065, woodpale, 10)
for pz in [-.5, -.03, .44, .91]:
    cylinder('Dock_LadderRung', (2.23, -43.85, pz), (2.23, -44.8, pz), .067, woodlight, 10)

# Plaza bench, centered clear of the plaza's six-meter circular space.
bx, by, bz = 8, -8, 2
for dx in [-1.04, 1.04]:
    for dy in [-.33, .33]:
        cube('Bench_Leg', (bx + dx, by + dy, bz + .46), (.17, .18, .92), wood, .04)
    cube('Bench_SeatSupport', (bx + dx, by, bz + .78), (.19, 1.15, .15), wood, .04)
    cube('Bench_BackUpright', (bx + dx, by + .43, bz + 1.18), (.16, .17, 1.45), wood, .04, (.12, 0, 0))
    cube('Bench_ArmRest', (bx + dx, by, bz + 1.32), (.25, 1.12, .17), woodpale, .055)
for row in range(4):
    cube('Bench_SeatSlat', (bx, by - .41 + row * .27, bz + .91), (2.72, .24, .18), woodpale, .06)
for row in range(3):
    cube('Bench_BackSlat', (bx, by + .50 + row * .028, bz + 1.24 + row * .25), (2.74, .14, .21), woodlight, .065)

# Dock direction marker: raised arrow icon, deliberately no text.
sx, sy, sz = 3.3, -27.6, 2
cube('DockSign_Post', (sx, sy, sz + .91), (.20, .23, 1.82), woodlight, .05)
cube('DockSign_Board', (sx, sy, sz + 1.63), (1.85, .19, .74), woodpale, .14, (0, -.04, 0))
extrusion('DockSign_RaisedArrow', [(sx - .57, sz + 1.67), (sx + .05, sz + 1.67),
          (sx + .05, sz + 1.84), (sx + .52, sz + 1.60), (sx + .05, sz + 1.36),
          (sx + .05, sz + 1.53), (sx - .57, sz + 1.53)], sy - .14, sy - .1, ivory, .015)
for dx in [-.70, .70]:
    cylinder('DockSign_Peg', (sx + dx, sy - .10, sz + 1.63), (sx + dx, sy - .13, sz + 1.63), .048, wood, 10, .005)

def clean_degenerate_normals(obj):
    """Remove sub-micron bevel slivers before FBX triangulation can export them."""
    data = obj.data
    data.calc_loop_triangles()
    bad_count = sum(triangle.area < 1e-10 for triangle in data.loop_triangles)
    if not bad_count:
        return 0
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-5)
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='BEAUTY', ngon_method='BEAUTY')
    bad_faces = [face for face in bm.faces if face.calc_area() < 1e-10]
    if bad_faces:
        bmesh.ops.delete(bm, geom=bad_faces, context='FACES_ONLY')
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    data.update()
    # Explicit valid face normals avoid retaining stale custom normals after cleanup.
    loop_normals = [(0, 0, 1)] * len(data.loops)
    for polygon in data.polygons:
        for loop_index in polygon.loop_indices:
            loop_normals[loop_index] = tuple(polygon.normal)
    data.normals_split_custom_set(loop_normals)
    data.calc_loop_triangles()
    assert not any(triangle.area < 1e-10 for triangle in data.loop_triangles), obj.name
    assert not any(normal.vector.length < 1e-6 for normal in data.corner_normals), obj.name
    obj['removed_degenerate_triangles'] = bad_count
    return bad_count


# Export-ready static geometry: no modifiers, curves, cameras, or image dependencies.
removed_degenerate_triangles = 0
for obj in list(bpy.data.objects):
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        obj.select_set(False)
        removed_degenerate_triangles += clean_degenerate_normals(obj)
        obj['beastcrossing_module'] = 'village'
        obj['units'] = 'meters'

scene = bpy.context.scene
scene['module'] = 'BeastCrossing Village'
scene['design'] = 'Original cozy island cottages and timber dock; procedural modeled geometry only.'
scene['placement_contract'] = 'grass=2m; north plateau=6m; ocean=0m; doors face south (-Y)'
meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
corners = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
report = {
    'objects': len(meshes),
    'vertices': sum(len(obj.data.vertices) for obj in meshes),
    'polygons': sum(len(obj.data.polygons) for obj in meshes),
    'materials': len(bpy.data.materials),
    'bounds_min': [round(min(p[axis] for p in corners), 3) for axis in range(3)],
    'bounds_max': [round(max(p[axis] for p in corners), 3) for axis in range(3)],
    'non_mesh_objects': [obj.name for obj in bpy.data.objects if obj.type != 'MESH'],
    'unapplied_modifiers': [obj.name for obj in meshes if obj.modifiers],
    'removed_degenerate_triangles': removed_degenerate_triangles,
}
scene['verification'] = json.dumps(report)
assert not report['non_mesh_objects']
assert not report['unapplied_modifiers']
assert all(obj.name.startswith('VILL_') for obj in meshes)
assert all(mat.name.startswith('M_VILL_') for mat in bpy.data.materials)
assert all(not obj.data.materials or obj.data.materials[0].use_nodes for obj in meshes)
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print('VILLAGE_VERIFIED ' + json.dumps(report))
