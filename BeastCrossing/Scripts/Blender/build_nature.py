"""Build the original BeastCrossing island planting module in Blender 4.5.

Run: blender --background --factory-startup --python build_nature.py
All lengths are meters. The module is geometry and solid materials only.
"""
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "Art" / "Blender" / "nature.blend"
random.seed(47281)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene["module"] = "BeastCrossing island nature, original modeled geometry"
scene["coordinate_contract"] = "+X east, +Y north, +Z up, meters; grass=2, plateau=6, beach=.6"


def material(name, color, roughness=.82):
    mat = bpy.data.materials.new("M_NAT_" + name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (*color, 1)
    principled.inputs["Roughness"].default_value = roughness
    return mat


M = {
    "bark": material("WarmBark", (.34, .20, .105)),
    "branch": material("BranchHoney", (.42, .27, .14)),
    "leaf": material("LeafGreen", (.24, .48, .225)),
    "leaflight": material("SpringGreen", (.36, .60, .27)),
    "sage": material("Sage", (.39, .58, .33)),
    "mint": material("Mint", (.32, .58, .41)),
    "pine": material("Pine", (.15, .37, .28)),
    "pineLight": material("PineTips", (.24, .46, .31)),
    "orange": material("OrangeFruit", (.96, .38, .075), .58),
    "peach": material("GoldenPeach", (.97, .59, .27), .63),
    "fruitLeaf": material("FruitLeaf", (.18, .38, .12)),
    "rock": material("ShoreStone", (.49, .55, .54)),
    "rocklight": material("StoneLichen", (.62, .66, .58)),
    "rockdark": material("CoolStone", (.37, .45, .46)),
    "stem": material("Stems", (.20, .43, .20)),
    "cream": material("CreamPetal", (.98, .91, .68)),
    "pink": material("RosePetal", (.98, .55, .57)),
    "white": material("PorcelainPetal", (1., .96, .84)),
    "yellow": material("PollenGold", (.96, .63, .14)),
    "grass": material("GrassFresh", (.42, .61, .27)),
}


def collection(name):
    c = bpy.data.collections.new("NAT_" + name)
    scene.collection.children.link(c)
    return c


TREES = collection("BroadleafTrees")
PINES = collection("Pines")
ROCKS = collection("ShoreRocks")
FLOWERS = collection("FlowerBeds")
BUSHES = collection("Bushes")
GRASS = collection("GrassTufts")


def finish(obj, name, mat, parts=None):
    obj.name = "NAT_" + name
    obj.data.name = obj.name + "_Mesh"
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    if parts is not None:
        parts.append(obj)
    return obj


def ellipsoid(name, loc, scale, mat, parts, phase=0., irregular=0., segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1, location=loc)
    o = bpy.context.object
    for v in o.data.vertices:
        p = v.co
        # Small, continuous broad undulations retain a plush silhouette.
        mod = 1 + irregular * (math.sin(p.x * 4.2 + phase) * math.cos(p.y * 3.5 - phase) + .35 * math.cos(p.z * 5.1 + phase))
        p.x *= scale[0] * mod
        p.y *= scale[1] * mod
        p.z *= scale[2] * mod
    return finish(o, name, mat, parts)


def tapered_path(name, centers, radii, mat, parts, sides=10):
    centers = [Vector(p) for p in centers]
    verts = []
    for i, (center, radius) in enumerate(zip(centers, radii)):
        tangent = centers[min(i + 1, len(centers) - 1)] - centers[max(i - 1, 0)]
        tangent.normalize()
        side = tangent.cross(Vector((0, 1, 0)))
        if side.length < .01:
            side = tangent.cross(Vector((1, 0, 0)))
        side.normalize()
        other = tangent.cross(side).normalized()
        for j in range(sides):
            a = j / sides * math.tau
            p = center + radius * (side * math.cos(a) + other * math.sin(a))
            verts.append(tuple(p))
    faces = [tuple(reversed(range(sides)))]
    for i in range(len(centers) - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple((len(centers) - 1) * sides + j for j in range(sides)))
    mesh = bpy.data.meshes.new("NAT_" + name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("NAT_" + name, mesh)
    scene.collection.objects.link(obj)
    return finish(obj, name, mat, parts)


def leaf(name, start, end, width, mat, parts):
    start, end = Vector(start), Vector(end)
    axis = (end - start).normalized()
    side = axis.cross(Vector((0, 0, 1)))
    if side.length < .05:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(axis).normalized()
    verts = []
    for t, w in [(0., .03), (.22, .70), (.50, 1), (.78, .58), (1., .015)]:
        c = start.lerp(end, t) + up * (math.sin(t * math.pi) * width * .27)
        for k in [-1, 0, 1]:
            p = c + side * (k * width * w / 2) + up * ((1 - abs(k)) * width * .11 * math.sin(t * math.pi))
            verts.append(tuple(p))
    faces = []
    for i in range(4):
        for j in range(2):
            k = i * 3 + j
            faces.append((k, k + 3, k + 4, k + 1))
    # Closed leaf shell: readable from above and below in Unreal.
    verts += [tuple(Vector(v) - up * .024) for v in verts]
    faces += [tuple(v + 15 for v in reversed(f)) for f in faces.copy()]
    outline = [0, 3, 6, 9, 12, 13, 14, 11, 8, 5, 2, 1]
    for a, b in zip(outline, outline[1:] + outline[:1]):
        faces.append((a, b, b + 15, a + 15))
    mesh = bpy.data.meshes.new("NAT_" + name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("NAT_" + name, mesh)
    scene.collection.objects.link(obj)
    return finish(obj, name, mat, parts)


def group(name, parts, target, origin):
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = "NAT_" + name
    obj.data.name = obj.name + "_Mesh"
    scene.cursor.location = origin
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    target.objects.link(obj)
    return obj


def broadleaf(index, pos, scale=1., fruit=False, variant=0):
    x, y, z = pos
    parts = []
    def P(a, b, c):
        return (x + a * scale, y + b * scale, z + c * scale)
    trunk_lean = .14 * (1 if index % 2 else -1)
    tapered_path("Trunk", [P(0, 0, -.04), P(.02, .02, .4), P(trunk_lean, 0, 2.5), P(.04, .1, 4.7)], [.53 * scale, .40 * scale, .27 * scale, .17 * scale], M["bark"], parts, 12)
    for a in range(5):
        angle = a / 5 * math.tau + index
        dx, dy = math.cos(angle), math.sin(angle)
        tapered_path("FlaredRoot", [P(dx * .1, dy * .1, .5), P(dx * .54, dy * .54, .14), P(dx * 1.05, dy * 1.05, .025)], [.21 * scale, .17 * scale, .018 * scale], M["bark"], parts, 8)
    lobes = [(-1.24, -.42, 4.92, 1.88, 1.78, 1.68), (1.12, -.24, 5.11, 1.96, 1.82, 1.74), (-.12, 1.06, 5.25, 2.06, 1.90, 1.84), (.05, .14, 6.27, 1.88, 1.77, 1.61)]
    shades = [["leaf", "leaflight", "leaf", "leaflight"], ["sage", "leaflight", "sage", "sage"], ["mint", "sage", "mint", "sage"]][variant % 3]
    for i, (dx, dy, h, sx, sy, sz) in enumerate(lobes):
        if i < 3:
            tapered_path("Branch", [P(.08, 0, 2.4 + i * .25), P(dx * .52, dy * .52, 3.4), P(dx, dy, h - .3)], [.22 * scale, .17 * scale, .07 * scale], M["branch"], parts, 10)
        ellipsoid("CrownLobe", P(dx, dy, h), (sx * scale, sy * scale, sz * scale), M[shades[i]], parts, phase=index * .5 + i, irregular=.033, segments=24, rings=16)
    # Modeled individual leaf plates overlap each plush canopy mass. Hidden
    # plates in overlapping lobes are omitted; no texture planes or alpha masks.
    for i, (dx, dy, h, sx, sy, sz) in enumerate(lobes):
        for row, (theta, count) in enumerate([(.44, 7), (.83, 11), (1.19, 13), (1.54, 14)]):
            for k in range(count):
                a = k / count * math.tau + row * .34 + index * .41
                mid_angle = theta + .13
                mx = dx + sx * math.sin(mid_angle) * math.cos(a) * 1.04
                my = dy + sy * math.sin(mid_angle) * math.sin(a) * 1.04
                mz = h + sz * math.cos(mid_angle) * 1.04
                hidden = any(((mx - ox) / rx) ** 2 + ((my - oy) / ry) ** 2 + ((mz - oz) / rz) ** 2 < .96 for j, (ox, oy, oz, rx, ry, rz) in enumerate(lobes) if j != i)
                if hidden:
                    continue
                start = P(dx + sx * math.sin(theta) * math.cos(a) * 1.04, dy + sy * math.sin(theta) * math.sin(a) * 1.04, h + sz * math.cos(theta) * 1.04)
                end = P(dx + sx * math.sin(theta + .34) * math.cos(a) * 1.075, dy + sy * math.sin(theta + .34) * math.sin(a) * 1.075, h + sz * math.cos(theta + .34) * 1.075)
                shade = shades[i] if k % 3 else ("leaflight" if variant == 0 else "sage")
                leaf("CanopyLeaf", start, end, (.49 + .10 * (k % 3)) * scale, M[shade], parts)
    if fruit:
        # Hanging fruit deliberately faces the southern overview camera.
        for i, (dx, dy, h) in enumerate([(-1.64, -1.55, 4.82), (.65, -1.93, 5.11), (1.98, -1.20, 4.55), (-.10, -1.70, 6.56), (2.02, .60, 5.34)]):
            center = P(dx, dy, h)
            fr = .37 * scale
            ellipsoid("Fruit", center, (fr, fr * .94, fr * 1.02), M["orange" if index % 3 else "peach"], parts, segments=16, rings=12)
            tapered_path("FruitStem", [P(dx, dy, h + .28), P(dx + .04, dy, h + .52)], [.039 * scale, .024 * scale], M["branch"], parts, 6)
            leaf("FruitLeaf", P(dx + .02, dy, h + .44), P(dx + .39, dy + .04, h + .62), .20 * scale, M["fruitLeaf"], parts)
    obj = group(f"Tree_{index:02d}_{'Fruit' if fruit else 'Broadleaf'}", parts, TREES, pos)
    obj["planting_surface"] = "Plateau" if z == 6 else "Meadow"
    return obj


# Planting is deliberately grouped at island edges. Open foreground frames the plaza.
tree_layout = [
    (-31, -13, 2, 1.00, True, 0), (-33, -3, 2, 1.10, False, 1),
    (-31, 8, 2, .93, False, 2), (-29, 18, 2, 1.06, True, 0),
    (-20, 23, 2, .91, False, 1), (-10.7, 24, 6, .84, True, 0),
    (10.7, 24, 6, .88, False, 2), (20, 22, 2, 1.06, False, 1),
    (28, 17, 2, 1.08, True, 0), (32, 7, 2, .98, False, 2),
    (33, -4, 2, 1.03, False, 1), (30, -15, 2, .90, True, 0),
    (-25, -21, 2, .83, False, 1), (24, -22, 2, .86, False, 2),
    (-11.0, 7.8, 2, .85, True, 0), (25.3, 4.8, 2, .85, False, 1),
    (-26, -8, 2, .84, True, 0), (25, -7.5, 2, .88, False, 2),
    (-8.4, -20.2, 2, .79, False, 1), (11.6, -19, 2, .81, True, 0),
]
for i, (x, y, z, s, f, v) in enumerate(tree_layout, 1):
    broadleaf(i, (x, y, z), s, f, v)


def pine(index, pos, scale):
    x, y, z = pos
    parts = []
    tapered_path("PineTrunk", [(x, y, z), (x + .1, y, z + 4 * scale), (x, y, z + 8 * scale)], [.48 * scale, .26 * scale, .10 * scale], M["bark"], parts, 12)
    for n in range(4):
        a = n * math.tau / 4 + .6
        tapered_path("PineRoot", [(x, y, z + .3), (x + math.cos(a) * .83, y + math.sin(a) * .83, z + .02)], [.23, .015], M["bark"], parts, 8)
    # Custom rounded conical tiers, with gently scalloped skirts, not faceted cones.
    for tier, (h, radius, height) in enumerate([(2.6, 2.55, 3.7), (4.55, 2.10, 3.4), (6.25, 1.5, 3.15)]):
        profile = [(0, .36), (.055, .84), (.13, 1), (.26, .87), (.51, .60), (.76, .34), (.93, .11), (1, .008)]
        verts, faces = [], []
        sides = 32
        for t, r in profile:
            for k in range(sides):
                a = k / sides * math.tau
                sway = 1 + .035 * math.cos(5 * a + tier)
                verts.append((x + math.cos(a) * radius * r * scale * sway, y + math.sin(a) * radius * r * scale * sway, z + (h + t * height + .045 * math.cos(5 * a) * (1 - t)) * scale))
        for j in range(len(profile) - 1):
            for k in range(sides):
                a, b = j * sides + k, j * sides + (k + 1) % sides
                faces.append((a, b, b + sides, a + sides))
        faces.append(tuple(reversed(range(sides))))
        faces.append(tuple((len(profile) - 1) * sides + k for k in range(sides)))
        mesh = bpy.data.meshes.new("NAT_PineTier_Mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new("NAT_PineTier", mesh)
        scene.collection.objects.link(obj)
        finish(obj, "PineTier", M["pine" if tier % 2 == 0 else "pineLight"], parts)
        for row, (upper, lower, r0, r1, count) in enumerate([(.52, .24, .60, .91, 14), (.29, .07, .87, 1.04, 17)]):
            for k in range(count):
                a = math.tau * k / count + row * .23 + tier * .37
                start = (x + math.cos(a) * radius * r0 * scale * 1.035, y + math.sin(a) * radius * r0 * scale * 1.035, z + (h + upper * height) * scale)
                end = (x + math.cos(a) * radius * r1 * scale * 1.035, y + math.sin(a) * radius * r1 * scale * 1.035, z + (h + lower * height) * scale)
                leaf("PineFoliageSpray", start, end, (.60 if tier < 2 else .44) * scale, M["pineLight" if (k + row) % 3 == 0 else "pine"], parts)
    return group(f"Pine_{index:02d}", parts, PINES, pos)


pine(1, (-14.2, 26.3, 6), 1.0)
pine(2, (14.2, 26.3, 6), .91)


rock_positions = [(-38, -16, .54), (-41.3, -3, .54), (-35, 23, .58), (-22, 32, .57), (26, 30, .55), (40.5, 9, .54), (38, -20, .54), (21, -32, .52)]
for i, (x, y, z) in enumerate(rock_positions, 1):
    parts = []
    for j, (dx, dy, sx, sy, sz) in enumerate([(0, 0, 1.72, 1.38, 1.44), (1.78, -.52, .87, .98, .78), (-1.03, -1.24, .76, .66, .49)]):
        obj = ellipsoid("BeachRock", (x + dx, y + dy, z + sz * .52), (sx, sy, sz), M[["rock", "rocklight", "rockdark"][(i + j) % 3]], parts, phase=i + j, irregular=.11, segments=16, rings=10)
        obj.rotation_euler = (.04 * j, -.08 * i, i * .72 + j)
    group(f"RockGroup_{i:02d}", parts, ROCKS, (x, y, z))


def flower(parts, x, y, z, height, petal_key, seed):
    rng = random.Random(seed)
    leanx, leany = rng.uniform(-.12, .12), rng.uniform(-.1, .1)
    tip = Vector((x + leanx, y + leany, z + height))
    tapered_path("FlowerStem", [(x, y, z), (x + leanx * .3, y + leany * .3, z + height * .45), tuple(tip)], [.043, .035, .024], M["stem"], parts, 6)
    for side in [-1, 1]:
        leaf("FlowerLeaf", (x + leanx * .25, y, z + height * (.31 if side == -1 else .49)), (x + side * .39, y + .15 * side, z + height * .64), .23, M["leaflight"], parts)
    petal_number = 6 if seed % 2 else 7
    for j in range(petal_number):
        a = j / petal_number * math.tau + seed * .31
        cx, cy = tip.x + math.cos(a) * .205, tip.y + math.sin(a) * .205
        obj = ellipsoid("RoundedPetal", (cx, cy, tip.z), (.235, .12, .065), M[petal_key], parts, segments=12, rings=8)
        obj.rotation_euler = (0, -.10, a)
    ellipsoid("FlowerHeart", (tip.x, tip.y, tip.z + .058), (.136, .136, .085), M["yellow"], parts, segments=12, rings=8)


flower_positions = [
    (-7.8, -12.7, 2), (7.8, -12.7, 2), (-11.8, -6.8, 2), (11.8, -5, 2),
    (-24.8, .5, 2), (-16.0, -2.6, 2), (8.5, 2.0, 2), (20.9, 1.8, 2),
    (-7.1, 18.0, 6), (7.1, 18.0, 6), (-24.9, -13.2, 2), (25.8, -10.2, 2),
]
for i, (x, y, z) in enumerate(flower_positions, 1):
    parts = []
    petal = ["cream", "pink", "white"][i % 3]
    for j, (dx, dy) in enumerate([(-.46, -.12), (.1, -.33), (.53, .14), (-.16, .40), (.16, .21)]):
        flower(parts, x + dx, y + dy, z, .66 + .22 * random.random(), petal, i * 17 + j)
    group(f"Flowers_{i:02d}_{petal.title()}", parts, FLOWERS, (x, y, z))


bush_positions = [
    (-31, -20, 2), (-35, -9, 2), (-33.5, 14, 2), (-24, 24.2, 2),
    (-9.5, 27.4, 6), (9.5, 27.4, 6), (27, 21.8, 2), (35.5, .8, 2),
    (31.5, -19.3, 2), (-19, -18.4, 2), (19.2, -18.8, 2),
    (-29.0, 7.5, 2), (24.0, 12, 2), (-8.0, 24.5, 6), (8.0, 24.5, 6),
]
for i, (x, y, z) in enumerate(bush_positions, 1):
    parts = []
    for j, (dx, dy, size) in enumerate([(-.52, 0, .95), (.48, -.10, .91), (.01, .37, 1.10)]):
        ellipsoid("BushLobe", (x + dx, y + dy, z + size * .54), (size, size * .87, size * .85), M["mint" if i % 2 else "sage"], parts, phase=i + j, irregular=.04, segments=16, rings=12)
    if i % 3 == 0:
        for j in range(5):
            bx, by = x + random.uniform(-.8, .8), y + random.uniform(-.5, .1)
            ellipsoid("BushBlossom", (bx, by, z + .95 + random.random() * .3), (.12, .12, .09), M["cream"], parts, segments=10, rings=8)
    group(f"Bush_{i:02d}", parts, BUSHES, (x, y, z))


tuft_positions = [
    (-34,-18,2),(-33,-11,2),(-35,3,2),(-29,13,2),(-26,21,2),(-18,25,2),
    (20,25,2),(31,14,2),(35,3,2),(32,-9,2),(29,-21,2),
    (-18,-23,2),(-14,-22,2),(-6,-24,2),(6,-24,2),(17,-23,2),
    (-26,-6,2),(-25,-4,2),(-15,-11,2),(-13,-10,2),(15,-12,2),(20,-11,2),
    (-27,1,2),(-14,4,2),(24,2,2),(23,-2,2),(-8,26.5,6),(8,26.5,6),
    (-13,19,6),(13,19,6),(-7,14.5,6),(7,14.5,6),
]
for i, (x, y, z) in enumerate(tuft_positions, 1):
    parts = []
    for j in range(6):
        a = j * math.tau / 6 + i
        h = random.uniform(.38, .72)
        start = (x + .1 * math.cos(a), y + .1 * math.sin(a), z + .015)
        end = (x + .44 * math.cos(a), y + .44 * math.sin(a), z + h)
        leaf("GrassBlade", start, end, .20, M["grass" if j % 2 else "leaflight"], parts)
    group(f"GrassTuft_{i:02d}", parts, GRASS, (x, y, z))


# Remove the now empty factory collection and all construction selections.
for col in list(bpy.data.collections):
    if not col.objects and not col.children:
        bpy.data.collections.remove(col)
bpy.ops.object.select_all(action="DESELECT")
scene.cursor.location = (0, 0, 0)
scene.world.color = (.28, .32, .38)
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type == "VIEW_3D":
        area.spaces.active.clip_end = 1000
        area.spaces.active.region_3d.view_distance = 95
        area.spaces.active.region_3d.view_location = (0, 0, 4)

assert len(TREES.objects) == 20
assert len(PINES.objects) == 2
assert len(FLOWERS.objects) == 12
assert all(o.type == "MESH" and o.name.startswith("NAT_") for o in scene.objects)
assert all(m.name.startswith("M_NAT_") for m in bpy.data.materials)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
print("NATURE_VERIFIED", {"objects": len(scene.objects), "materials": len(bpy.data.materials), "vertices": sum(len(o.data.vertices) for o in scene.objects), "triangles": sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in scene.objects), "blend": str(OUTPUT)})
