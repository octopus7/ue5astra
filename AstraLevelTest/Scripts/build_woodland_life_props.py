"""Five independent woodland daily-life props. Blender 4.5, metres, front -X.

All geometry and preview are reproducible; only this kit's files are written.
"""
import ast
import bpy
import bmesh
import json
import math
import random
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
R = random.Random(97531)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_WoodlandLifeLibrary')
presentation = bpy.data.collections.new('02_WoodlandLifePresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)

PALETTE = {
    'M_WoodlandLife_Wood': 'A97B46', 'M_WoodlandLife_WoodLight': 'CDA56A',
    'M_WoodlandLife_WoodDark': '79583B', 'M_WoodlandLife_WoodEnd': 'DFC08A',
    'M_WoodlandLife_Iron': '3F626A', 'M_WoodlandLife_IronEdge': '77908E',
    'M_WoodlandLife_Rope': 'CCB68A', 'M_WoodlandLife_Cream': 'F0E2BD',
    'M_WoodlandLife_Sage': '91A989', 'M_WoodlandLife_SageLight': 'BDCAA5',
    'M_WoodlandLife_Teal': '559DA6', 'M_WoodlandLife_Berry': 'C85E57',
    'M_WoodlandLife_Mushroom': 'DDA04E', 'M_WoodlandLife_Bread': 'BE813C',
    'M_WoodlandLife_Leaf': '5E8B63',
}
helpers = ast.parse((ROOT / 'Scripts/build_pink_house_assets.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in helpers.body if isinstance(n, ast.FunctionDef)
    and n.name in {'linear', 'finish', 'mesh', 'bar', 'cylinder', 'asset_metadata'}],
    type_ignores=[]), 'cottage_geometry_helpers', 'exec'))
materials = {}
material_properties = {}
for name, h in PALETTE.items():
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    color = tuple(linear(int(h[i:i+2], 16)/255) for i in (0, 2, 4))
    m.diffuse_color = (*color, 1)
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    metal = .35 if 'Iron' in name else 0
    rough = .44 if ('Iron' in name or 'Teal' in name) else .88
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    materials[name] = m
    material_properties[name] = {'roughness': rough, 'metallic': metal}


def mat(s):
    return 'M_WoodlandLife_' + s


def cube(name, center, size, material, rotation=(0, 0, 0), bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center, rotation=rotation)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = o.modifiers.new('Soft handworked edges', 'BEVEL')
        mod.width = min(bevel, min(size)*.20)
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(o, material)


def sphere(name, p, size, material, segments=16, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings,
        radius=1, location=p)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for poly in o.data.polygons:
        poly.use_smooth = True
    return finish(o, material)


def ring(name, p, radius, thickness, material, axis='Z', scale=(1, 1, 1), n=32):
    rot = {'X': (0, math.pi/2, 0), 'Y': (math.pi/2, 0, 0), 'Z': (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_torus_add(major_segments=n, minor_segments=6,
        location=p, rotation=rot, major_radius=radius, minor_radius=thickness)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for poly in o.data.polygons:
        poly.use_smooth = True
    return finish(o, material)


def tube(name, points, radius, material, n=6):
    """One closed tube along a 3D path, with smooth normals and no duplicated balls."""
    vs = []
    for i, p in enumerate(points):
        tangent = Vector(points[min(i+1, len(points)-1)])-Vector(points[max(i-1, 0)])
        q = tangent.to_track_quat('Z', 'Y')
        vs.extend(tuple(Vector(p)+q@Vector((radius*math.cos(k*math.tau/n),
            radius*math.sin(k*math.tau/n), 0))) for k in range(n))
    fs = [tuple(range(n-1, -1, -1)), tuple(range((len(points)-1)*n, len(points)*n))]
    fs += [(j*n+k, j*n+(k+1)%n, (j+1)*n+(k+1)%n, (j+1)*n+k)
        for j in range(len(points)-1) for k in range(n)]
    o = mesh(name, vs, fs, material)
    for poly in o.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    return o


def basket(p=(0, 0, 0), scale=1, handle=True):
    parts = []
    x, y, z = p
    def at(a, b, c): return (x+a*scale, y+b*scale, z+c*scale)
    base = cylinder('Oval basket base', at(0, 0, .012), at(0, 0, .063),
        .30*scale, mat('WoodDark'), 32)
    base.scale.y = .70
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    parts.append(base)
    for i in range(20):
        a = math.tau*i/20
        parts.append(tube('Basket upright weave', [at(.29*math.cos(a), .20*math.sin(a), .06),
            at(.36*math.cos(a), .25*math.sin(a), .40)], .016*scale, mat('WoodLight')))
    for i in range(6):
        zz = .085+i*.058
        r = .30+i*.012
        parts.append(ring('Broad horizontal basket weave', at(0, 0, zz), r*scale,
            .017*scale, mat('Wood' if i%2 else 'WoodLight'), scale=(1, .7, 1), n=32))
    parts.append(ring('Bound basket rim', at(0, 0, .405), .369*scale, .026*scale,
        mat('WoodLight'), scale=(1, .70, 1)))
    if handle:
        points = [at(.36*math.cos(a), 0, .41+.36*math.sin(a)) for a in [i*math.pi/20 for i in range(21)]]
        parts.append(tube('Arched basket handle', points, .026*scale, mat('Wood')))
        for i in (0, 20):
            px, py, pz = points[i]
            parts.append(cylinder('Handle binding', (px, py, pz-.05*scale),
                (px, py, pz+.07*scale), .040*scale, mat('Rope'), 10))
    return parts


def mug(p, scale=1):
    x, y, z = p
    n = 20
    profile = [(.085, 0), (.105, .17), (.083, .17), (.066, .023)]
    vs = [(x+r*scale*math.cos(i*math.tau/n), y+r*scale*math.sin(i*math.tau/n), z+zz*scale)
        for r, zz in profile for i in range(n)]
    fs = [tuple(range(n-1, -1, -1)), tuple(range(3*n, 4*n))]
    fs += [(j*n+i, j*n+(i+1)%n, (j+1)*n+(i+1)%n, (j+1)*n+i) for j in range(3) for i in range(n)]
    body = mesh('Open enamel mug', vs, fs, mat('Teal'))
    for f in body.data.polygons:
        f.use_smooth = len(f.vertices) == 4
    return [body, ring('Mug handle', (x+.125*scale, y, z+.095*scale), .063*scale,
        .015*scale, mat('Teal'), axis='Y', n=16)]


def crate(p, size):
    x, y, z = p
    sx, sy, sz = size
    parts = []
    for xx in (-.5, .5):
        for yy in (-.5, .5):
            parts.append(cube('Crate corner post', (x+sx*xx, y+sy*yy, z+sz/2),
                (.065, .065, sz), mat('WoodLight')))
    for k in range(3):
        for yy in (-.5, .5):
            parts.append(cube('Crate horizontal slat', (x, y+sy*yy, z+(k+.5)*sz/3),
                (sx, .04, sz/3-.013), mat('Wood' if k == 1 else 'WoodLight')))
        for xx in (-.5, .5):
            parts.append(cube('Crate end slat', (x+sx*xx, y, z+(k+.5)*sz/3),
                (.04, sy, sz/3-.013), mat('Wood')))
    for k in range(4):
        parts.append(cube('Crate lid and floor plank', (x, y+(k-1.5)*sy/4, z+sz+.01),
            (sx+.025, sy/4-.008, .035), mat('WoodLight' if k%2 else 'Wood')))
    parts.append(cube('Crate base', (x, y, z+.022), (sx, sy, .045), mat('WoodDark')))
    return parts


def asset(name, parts, collision):
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    zmin = min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        v.co.z -= zmin
    o.data.update()
    bpy.context.view_layer.update()
    # Explicit UV0 for lightmaps and optional future painted materials.
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    for c in list(o.users_collection):
        c.objects.unlink(o)
    library.objects.link(o)
    o['asset_id'] = name
    o['collision'] = collision
    o['front_axis'] = '-X'
    bpy.ops.export_scene.fbx(filepath=str(ART / 'Meshes' / f'{name}.fbx'), use_selection=True,
        object_types={'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y', axis_up='Z', bake_anim=False, add_leaf_bones=False,
        mesh_smooth_type='FACE', use_mesh_modifiers=True)
    o.hide_render = True
    o.hide_set(True)
    return o


# Chopping area: a sturdy ringed stump, embedded axe and a few split logs.
p = []
n = 24
vs = []
for zz, rr in ((0, .47), (.09, .44), (.56, .395), (.63, .40)):
    vs.extend((rr*(1+.035*math.sin(i*2.8))*math.cos(i*math.tau/n),
        rr*(1+.035*math.sin(i*2.8))*math.sin(i*math.tau/n), zz) for i in range(n))
fs = [tuple(range(n-1, -1, -1)), tuple(range(3*n, 4*n))]
fs += [(j*n+i, j*n+(i+1)%n, (j+1)*n+(i+1)%n, (j+1)*n+i) for j in range(3) for i in range(n)]
stump = mesh('Hand hewn chopping stump', vs, fs, mat('WoodDark'))
for f in stump.data.polygons:
    f.use_smooth = len(f.vertices) == 4
p.append(stump)
p.append(cylinder('Light cut wood surface', (0, 0, .619), (0, 0, .638), .383, mat('WoodEnd'), 32))
for r in (.10, .20, .30, .357):
    p.append(ring('Coarse growth ring', (0, 0, .641), r, .0045, mat('WoodLight'), n=40))
for i in range(16):
    a = math.tau*i/16
    p.append(tube('Broad bark ridge', [(.436*math.cos(a), .436*math.sin(a), .07),
        (.390*math.cos(a+.02), .390*math.sin(a+.02), .57)], .016, mat('Wood')))
# Axe blade thickness runs Y. Handle extends diagonally up and toward +X.
ax = [(-.16, -.045, .60), (.025, -.04, .65), (.035, -.038, .85),
      (-.02, -.04, .95), (-.22, -.025, .96), (-.28, -.013, .80)]
ax += [(x, -y, z) for x, y, z in ax]
af = [tuple(range(5, -1, -1)), tuple(range(6, 12))]
af += [(i, (i+1)%6, (i+1)%6+6, i+6) for i in range(6)]
p.append(mesh('Embedded axe head', ax, af, mat('Iron')))
p.append(cylinder('Long diagonal axe handle', (-.10, 0, .83), (.58, .03, 1.32), .039, mat('WoodLight'), 12))
p.append(cylinder('Axe dark grip', (.45, .024, 1.225), (.60, .031, 1.334), .049, mat('WoodDark'), 12))
for i, (x, y, a) in enumerate(((-.54, -.29, .45), (-.67, -.03, -.15), (.25, .64, .25))):
    p.append(cube('Split firewood', (x, y, .075), (.50, .14, .15), mat('WoodLight'), rotation=(0, 0, a), bevel=.023))
for i in range(9):
    a = R.uniform(0, math.tau)
    rr = R.uniform(.54, .78)
    p.append(cube('Wood chip', (rr*math.cos(a), rr*math.sin(a), .018),
        (R.uniform(.055, .105), .04, .036), mat('WoodEnd'), rotation=(0, .1, a), bevel=.003))
chopping = asset('SM_ChoppingStump', p, 'complex')

# Open foraging basket with mushrooms, red berries and a folded cloth.
p = basket()
for x, y, h, r in ((-.17, -.03, .40, .12), (.13, .08, .47, .14), (.04, -.11, .37, .105)):
    p.append(cylinder('Mushroom stem', (x, y, .18), (x+.012, y, h), .04, mat('Cream'), 10))
    p.append(sphere('Golden mushroom cap', (x, y, h), (r, r*.85, .055), mat('Mushroom')))
for i in range(11):
    a = i*2.399
    p.append(sphere('Gathered red berry', (.23*math.cos(a), .14*math.sin(a), .30+R.random()*.10),
        (.048, .046, .046), mat('Berry'), 12, 6))
p.append(cube('Folded foraging kerchief', (-.25, -.50, .05), (.42, .29, .10), mat('Sage'),
    rotation=(0, 0, -.20), bevel=.03))
p.append(cube('Cream kerchief hem', (-.25, -.60, .087), (.35, .018, .025), mat('Cream'),
    rotation=(0, 0, -.20), bevel=.005))
for x in (-.39, -.10):
    p.append(sphere('Kerchief knot', (x, -.48, .08), (.07, .05, .04), mat('SageLight'), 12, 6))
foraging = asset('SM_ForagingBasket', p, 'none')

# Picnic blanket: gentle corner curl, readable broad checks and a modest meal.
p = []
vs = []
for layer in range(2):
    for i in range(9):
        for j in range(9):
            x, y = -1+i*.25, -1+j*.25
            z = .033 + .016*math.sin(x*3)*math.sin(y*3)-layer*.026
            vs.append((x, y, z))
fs = []
colors = []
for layer in range(2):
    for i in range(8):
        for j in range(8):
            a = layer*81+i*9+j
            f = (a, a+9, a+10, a+1)
            fs.append(f if layer == 0 else tuple(reversed(f)))
            colors.append(2 if i%2 and j%2 else 1 if (i+j)%2 else 0)
border = list(range(9))+[i*9+8 for i in range(1, 9)]+list(range(79, 71, -1))+[i*9 for i in range(7, 0, -1)]
for a, b in zip(border, border[1:]+border[:1]):
    fs.append((a, b, b+81, a+81))
    colors.append(0)
cloth = mesh('Continuous gently folded check blanket', vs, fs, mat('Cream'))
cloth.data.materials.append(materials[mat('SageLight')])
cloth.data.materials.append(materials[mat('Sage')])
for face, color in zip(cloth.data.polygons, colors):
    face.material_index = color
    face.use_smooth = True
p.append(cloth)
for side in (-1, 1):
    for k in range(16):
        p.append(cylinder('Blanket fringe', (side*.985, -.93+k*.125, .035),
            (side*1.055, -.93+k*.125, .017), .008, mat('Cream'), 6))
p.extend(basket((.53, .50, .045), .75, True))
p.append(cube('Bread cloth', (-.38, .32, .064), (.72, .50, .028), mat('Cream'), rotation=(0, 0, .18), bevel=.015))
p.append(sphere('Rustic bread loaf', (-.38, .32, .195), (.29, .20, .15), mat('Bread'), 20, 10))
for xx in (-.53, -.39, -.25):
    p.append(tube('Bread scored crust', [(xx-.025, .22, .301), (xx, .30, .342), (xx+.025, .39, .308)],
        .012, mat('WoodEnd')))
p.extend(mug((-.38, -.40, .06), 1.1))
p.extend(mug((-.01, -.29, .06), 1.1))
for x, y in ((.44, -.35), (.70, -.25), (.66, -.54)):
    p.append(sphere('Picnic apple', (x, y, .15), (.104, .103, .10), mat('Berry'), 16, 8))
    p.append(cylinder('Apple stem', (x, y, .228), (x+.02, y, .281), .012, mat('WoodDark'), 6))
    leaf = sphere('Apple leaf', (x+.034, y, .255), (.045, .019, .007), mat('Leaf'), 12, 6)
    leaf.rotation_euler.z = .4
    p.append(leaf)
picnic = asset('SM_PicnicSet', p, 'none')

# Repair materials grouped so the toolbox remains visibly open from above.
p = []
for layer in range(3):
    for j in range(3):
        p.append(cube('Fresh bridge replacement plank', (.02*(layer%2), .23+j*.14, .035+layer*.08),
            (1.75-.06*((layer+j)%2), .129, .075), mat('WoodLight' if j%2 else 'WoodEnd'), bevel=.009))
for xx in (-.52, .52):
    p.append(tube('Binding around repair planks', [(xx, .152, .02), (xx, .152, .238),
        (xx, .595, .238), (xx, .595, .02), (xx, .152, .02)], .016, mat('Rope')))
# Toolbox - the handle is high and thin; the open tray and tools are readable.
p.append(cube('Open toolbox floor', (-.13, -.42, .035), (.78, .36, .07), mat('WoodDark')))
for yy in (-.61, -.23):
    p.append(cube('Toolbox low side', (-.13, yy, .165), (.80, .04, .27), mat('Wood')))
for xx in (-.55, .29):
    p.append(cube('Toolbox handle upright', (xx, -.42, .27), (.055, .39, .52), mat('WoodLight')))
p.append(cylinder('Toolbox carry handle', (-.55, -.42, .49), (.29, -.42, .49), .03, mat('WoodLight'), 10))
p.append(cylinder('Hammer wood handle', (-.41, -.52, .12), (.02, -.47, .16), .025, mat('WoodLight'), 8))
p.append(cube('Hammer head', (.02, -.47, .16), (.09, .17, .08), mat('Iron'), bevel=.011))
p.append(cylinder('Chisel handle', (-.29, -.33, .10), (-.10, -.32, .13), .031, mat('WoodEnd'), 8))
p.append(bar('Chisel blade', (-.10, -.32, .13), (.13, -.305, .17), .047, .015, mat('IronEdge')))
for yy in (-.638, -.202):
    for xx in (-.43, .17):
        p.append(cube('Toolbox metal corner', (xx, yy, .17), (.055, .013, .17), mat('Iron'), bevel=.003))
points = []
for i in range(121):
    a = i*math.tau*3/120
    r = .09+.14*i/120
    points.append((.69+r*math.cos(a), -.37+r*math.sin(a), .036))
points += [(1.01, -.38, .035), (1.09, -.44, .024)]
p.append(tube('Loose coil of thick rope', points, .022, mat('Rope')))
repair = asset('SM_BridgeRepairSupplies', p, 'none')

# Handcart fronts -X: two pull handles, two spoked wheels, crate cargo.
p = []
for j in range(5):
    p.append(cube('Cart bed plank', (.12, (j-2)*.18, .61), (1.20, .169, .075),
        mat('WoodLight' if j%2 else 'Wood'), bevel=.012))
for y in (-.50, .50):
    for k in range(3):
        p.append(cube('Cart side slat', (.12, y, .75+k*.16), (1.28, .07, .125), mat('Wood'), bevel=.014))
    for xx in (-.49, .73):
        p.append(cube('Cart corner upright', (xx, y, .83), (.09, .09, .79), mat('WoodLight'), bevel=.014))
    for x in (-.49, .73):
        p.append(cube('Cart blue iron bracket', (x, y*1.08, .64), (.17, .028, .17), mat('Iron'), bevel=.007))
    # Resting handles connect naturally to the raised bed.
    p.append(bar('Long cart handle', (-.45, y*.75, .58), (-1.43, y*.80, .24), .07, .065, mat('Wood')))
    p.append(cylinder('Handcart comfortable grip', (-1.44, y*.80, .237), (-1.23, y*.79, .31), .048, mat('WoodLight'), 12))
    p.append(bar('Resting handle foot', (-.75, y*.73, .44), (-.79, y*.73, .018), .055, .07, mat('WoodDark')))
for k in range(3):
    p.append(cube('Cart back slat', (.77, 0, .75+k*.16), (.07, .97, .125), mat('WoodLight'), bevel=.012))
p.append(cylinder('Cart axle', (.15, -.74, .43), (.15, .74, .43), .067, mat('Iron'), 12))
for y in (-.645, .645):
    p.append(ring('Wood wheel rim', (.15, y, .43), .363, .068, mat('WoodDark'), axis='Y', n=32))
    p.append(ring('Blue iron wheel tire', (.15, y, .43), .425, .026, mat('Iron'), axis='Y', n=40))
    for i in range(8):
        a = math.tau*i/8
        p.append(bar('Wheel wood spoke', (.15, y, .43),
            (.15+.353*math.cos(a), y, .43+.353*math.sin(a)), .047, .055, mat('WoodLight')))
    p.append(cylinder('Wheel wooden hub', (.15, y-.09, .43), (.15, y+.09, .43), .10, mat('WoodLight'), 16))
    p.append(cylinder('Iron axle cap', (.15, y+math.copysign(.095, y), .43),
        (.15, y+math.copysign(.108, y), .43), .055, mat('Iron'), 12))
p.extend(crate((.35, .14, .66), (.50, .42, .38)))
p.extend(crate((-.18, -.17, .66), (.39, .37, .30)))
cart = asset('SM_WoodHandcart', p, 'complex')

assets = [chopping, foraging, picnic, repair, cart]
records = []
for o in assets:
    record = asset_metadata(o)
    record['collision'] = o['collision']
    record['normal_import_method'] = 'FBXNIM_IMPORT_NORMALS_AND_TANGENTS'
    record['validation']['uv0_finite'] = bool(o.data.uv_layers) and all(
        math.isfinite(c) for uv in o.data.uv_layers.active.data for c in uv.uv)
    records.append(record)
metadata = {
    'source': 'ArtSource/Blender/WoodlandLifeProps.blend',
    'script': 'Scripts/build_woodland_life_props.py',
    'reference': 'ArtSource/Reference/Ref_WoodlandLifeProps.png',
    'units': 'metres', 'unreal_conversion': '(X,-Y,Z)*100',
    'palette_srgb_hex': PALETTE, 'material_properties': material_properties,
    'assets': records,
}
(ART / 'Layout/woodland_life_props.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')

# Fresh FBX import proves transforms, material slots, UVs and nondegenerate geometry survived.
roundtrip = []
for o, record in zip(assets, records):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ART / 'Meshes' / (o.name+'.fbx')), use_custom_normals=True)
    imported = [a for a in set(bpy.data.objects)-before if a.type == 'MESH']
    assert len(imported) == 1
    test = imported[0]
    bpy.context.view_layer.update()
    dim_error = max(abs(a-b) for a, b in zip(o.dimensions, test.dimensions))
    triangles = sum(len(f.vertices)-2 for f in test.data.polygons)
    check = {
        'asset_id': o.name, 'dimensions_error_m': dim_error,
        'triangles': triangles, 'same_triangles': triangles == record['triangles'],
        'uv0_finite': bool(test.data.uv_layers) and all(math.isfinite(c)
            for uv in test.data.uv_layers.active.data for c in uv.uv),
        'valid_material_indices': all(f.material_index < len(test.material_slots) for f in test.data.polygons),
        'custom_normals': test.data.has_custom_normals,
        'nonzero_faces': all(f.area > 0 for f in test.data.polygons),
    }
    check['passed'] = dim_error < .00001 and all(check[k] for k in
        ('same_triangles', 'uv0_finite', 'valid_material_indices', 'custom_normals', 'nonzero_faces'))
    assert check['passed'], check
    roundtrip.append(check)
    for a in set(bpy.data.objects)-before:
        bpy.data.objects.remove(a, do_unlink=True)
(ART / 'Previews/WoodlandLifeProps_FBXValidation.json').write_text(json.dumps({
    'passed': all(r['passed'] for r in roundtrip), 'assets': roundtrip}, indent=2), encoding='utf-8')

# Two presentation rows. Library assets remain in-place at origin, hidden from render.
for a, pos in zip(assets, [(-2.4, .3, 0), (-.25, .7, 0), (2.3, .5, 0), (-1.5, -2.1, 0), (1.55, -2.3, 0)]):
    o = bpy.data.objects.new('Preview_'+a.name, a.data)
    presentation.objects.link(o)
    o.location = pos
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.05))
ground = bpy.context.object
ground.name = 'WoodlandLifePreviewGround'
gm = bpy.data.materials.new('WoodlandLifePreviewGround')
gm.diffuse_color = (.44, .45, .36, 1)
ground.data.materials.append(gm)
bpy.ops.object.light_add(type='SUN', location=(-5, -8, 12))
sun = bpy.context.object
sun.rotation_euler = (.5, -.4, -.6)
sun.data.energy = 2.5
sun.data.angle = math.radians(50)
scene.world = bpy.data.worlds.new('WoodlandLifeBlueSky')
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get('Background')
bg.inputs['Color'].default_value = (.48, .62, .78, 1)
bg.inputs['Strength'].default_value = .65
bpy.ops.object.camera_add(location=(-8, -11, 14))
cam = bpy.context.object
cam.rotation_euler = (Vector((0, -.7, .25))-cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 8.1
scene.camera = cam
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1800
scene.render.resolution_y = 1400
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(ART / 'Previews/Blender_WoodlandLifeProps.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART / 'Blender/WoodlandLifeProps.blend'))
bpy.ops.render.render(write_still=True)
print('WOODLAND LIFE PROPS COMPLETE '+json.dumps(records))
