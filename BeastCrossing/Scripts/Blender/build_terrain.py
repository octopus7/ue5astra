"""Deterministic authored BeastCrossing island terrain, Blender 4.5.

Run: blender --background --python Scripts/Blender/build_terrain.py
World units are meters. Main grass z=2, plateau grass z=6, ocean z=0.
This asset contains geometry/materials only; its parent scene owns the ocean.
"""
from pathlib import Path
import bpy
import bmesh
import math
import random
from mathutils import Vector

RNG = random.Random(57071)
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "Art" / "Blender" / "terrain.blend"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

def material(name, color, roughness=.86):
    m = bpy.data.materials.new("M_TERR_" + name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = roughness
    return m

M = {
    "wet": material("WetHoneySand", (.53, .37, .20)),
    "sand": material("WarmSand", (.78, .59, .32)),
    "sandlight": material("PaleSand", (.90, .72, .44)),
    "cliff": material("CliffOchre", (.48, .30, .16)),
    "clifflight": material("CliffCream", (.68, .47, .28)),
    "cliffwarm": material("CliffWarm", (.61, .40, .23)),
    "cliffpale": material("CliffPale", (.73, .52, .32)),
    "grassrim": material("GrassRim", (.32, .48, .075)),
    "grass": material("MeadowGreen", (.40, .61, .13)),
    "hillgrass": material("HillMeadowGreen", (.43, .63, .15)),
    "path": material("PathSand", (.67, .46, .23)),
    "tile": material("PathHoneyStone", (.80, .61, .37)),
    "tilelight": material("PathCreamStone", (.86, .69, .44)),
    "tilewarm": material("PathWarmStone", (.75, .53, .29)),
}

def mesh_obj(name, verts, faces, mats, indices=None, smooth=False):
    mesh = bpy.data.meshes.new("TERR_" + name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.clear()
    for m in mats:
        mesh.materials.append(m)
    mesh.update()
    ob = bpy.data.objects.new("TERR_" + name, mesh)
    bpy.context.collection.objects.link(ob)
    for i, poly in enumerate(mesh.polygons):
        poly.use_smooth = smooth
        if indices is not None:
            poly.material_index = indices[i]
    return ob

def bevel(ob, amount=.06, segments=3):
    mod = ob.modifiers.new("Soft handmade edges", "BEVEL")
    mod.width = amount
    mod.segments = segments
    mod.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.select_set(False)
    return ob

def solid_polygon(name, points, bottom, top, mat, edge=0):
    n = len(points)
    v = [(x,y,bottom) for x,y in points] + [(x,y,top) for x,y in points]
    f = [tuple(reversed(range(n))), tuple(range(n,2*n))]
    f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    ob = mesh_obj(name,v,f,[mat])
    if edge:
        bevel(ob,edge,2)
    return ob

def circle(cx,cy,rx,ry,n=96):
    return [(cx+rx*math.cos(i*2*math.pi/n),cy+ry*math.sin(i*2*math.pi/n)) for i in range(n)]

N=160
def island_point(t,rx,ry):
    # Low-frequency organic variation makes a soft, continuous shoreline.
    factor=1 + .018*math.sin(3*t+.3) + .011*math.cos(5*t-1.2)
    return rx*math.cos(t)*factor, ry*math.sin(t)*factor

def ring_solid(name, rings, point_fn, mats, side_indices, top_index):
    v=[]
    for rx,ry,z in rings:
        v += [(*point_fn(i*2*math.pi/N,rx,ry),z) for i in range(N)]
    f=[tuple(reversed(range(N)))]; ids=[0]
    for k in range(len(rings)-1):
        for i in range(N):
            j=(i+1)%N
            f.append((k*N+i,k*N+j,(k+1)*N+j,(k+1)*N+i))
            ids.append(side_indices[k])
    f.append(tuple(range((len(rings)-1)*N,len(rings)*N)));ids.append(top_index)
    ob=mesh_obj(name,v,f,mats,ids,True)
    ob.data.polygons[0].use_smooth=False
    ob.data.polygons[-1].use_smooth=False
    return ob

main=ring_solid("IslandShoreAndMeadow",[
    (43.9,36.0,-1.35), (44.8,36.7,-.55), (44.8,36.7,.10),
    (44.30,36.20,.28), (43.55,35.50,.44),
    (42.5,34.1,.62), (40.75,32.2,1.12),
    (39.72,30.9,1.48), (39.23,30.28,1.75),
    (39.03,30.03,1.94), (38.91,29.91,2.0)
], island_point,
    [M["wet"],M["sand"],M["sandlight"],M["clifflight"],M["grassrim"],M["grass"]],
    [0,0,0,1,2,2,2,3,4,4],5)
main["walkable_height_m"]=2.0
main["design"]="Smooth oval shoreline with an ochre grass lip; no heightfield or image textures"

def plateau_point(t,rx,ry):
    c,s=math.cos(t),math.sin(t)
    x=rx*math.copysign(abs(c)**.62,c)
    y=20.5+ry*math.copysign(abs(s)**.62,s)
    # Small gentle lobe variation without compromising the cottage footprint.
    x += .16*math.sin(3*t)
    y += .10*math.sin(4*t+.2)
    return x,y

hill=ring_solid("NorthPlateau",[
    (16.9,8.70,1.98),(17.10,8.85,2.15),(16.75,8.60,2.42),
    (16.58,8.43,3.85),(16.60,8.45,4.06),
    (16.46,8.30,5.60),(16.62,8.45,5.76),
    (16.65,8.45,5.87),(16.53,8.33,5.98),(16.39,8.19,6.0)
],plateau_point,[M["cliff"],M["clifflight"],M["grassrim"],M["hillgrass"]],
    [0,0,0,1,0,0,2,2,2],3)
hill["walkable_height_m"]=6.0

# Rounded stone courses give the cliff a clearly modeled, warm toy-like face.
for course,(low,high,rx,ry) in enumerate([(2.18,3.97,16.73,8.56),(4.00,5.75,16.54,8.37)]):
    pieces=34
    for i in range(pieces):
        a=(i+.5*course)*2*math.pi/pieces+.004
        b=(i+1+.5*course)*2*math.pi/pieces-.004
        outer=[plateau_point(a+(b-a)*j/4,rx+.07,ry+.07) for j in range(5)]
        inner=[plateau_point(a+(b-a)*j/4,rx-.28,ry-.28) for j in reversed(range(5))]
        col=[M["clifflight"],M["cliffwarm"],M["cliffpale"]][RNG.randrange(3)]
        solid_polygon(f"PlateauStone_{course}_{i:02}",outer+inner,low,high+RNG.uniform(-.035,.035),col,.055)

def bezier(p0,p1,p2,p3,n=48):
    return [Vector(p0)*(1-t)**3 + Vector(p1)*3*t*(1-t)**2 + Vector(p2)*3*t*t*(1-t) + Vector(p3)*t**3 for t in [i/n for i in range(n+1)]]

def ribbon_outline(points,width):
    left=[];right=[]
    for i,p in enumerate(points):
        tang=(points[min(i+1,len(points)-1)]-points[max(i-1,0)]).normalized()
        norm=Vector((-tang.y,tang.x))
        left.append(tuple(p+norm*width/2));right.append(tuple(p-norm*width/2))
    # Clockwise left/forward outline is reversed for upward facing top geometry.
    return list(reversed(left+list(reversed(right))))

plaza=solid_polygon("PlazaBase",circle(0,-8,6.15,6.15),2.008,2.034,M["path"])
curves=[
    ("SouthPath",((0,-28),(1.5,-23),(-.8,-18),(0,-12)),3.0),
    ("WestPath",((-4,-5),(-9,-1),(-17,-.7),(-21,4.6)),2.8),
    ("EastPath",((4,-5),(9,-1),(14,-.5),(16,4.6)),2.8),
    ("PlateauApproach",((0,-3),(.7,.2),(-.4,3.1),(0,6.8)),3.2),
]
path_lines=[]
for name,cps,width in curves:
    points=bezier(*cps)
    path_lines.append((name,points,width))
    ob=solid_polygon(name,ribbon_outline(points,width),2.005,2.030,M["path"])
    # Exact solid unions avoid coplanar seams at the plaza junctions.
    mod=plaza.modifiers.new("Merge path", "BOOLEAN")
    mod.operation="UNION";mod.solver="EXACT";mod.object=ob
    bpy.context.view_layer.objects.active=plaza
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ob,do_unlink=True)
plaza.name="TERR_PathsAndPlaza"

# Concentric shallow pavers, with intentionally small mortar joints.
for ring,(r0,r1,count) in enumerate([(0.05,1.28,8),(1.34,2.64,14),(2.70,3.81,21),(3.87,4.95,27),(5.01,6.09,33)]):
    for i in range(count):
        a=2*math.pi*(i+ring*.33)/count+.008
        b=2*math.pi*(i+1+ring*.33)/count-.008
        poly=[(r1*math.cos(a+(b-a)*j/3),-8+r1*math.sin(a+(b-a)*j/3)) for j in range(4)]
        poly += [(r0*math.cos(a+(b-a)*j/3),-8+r0*math.sin(a+(b-a)*j/3)) for j in reversed(range(4))]
        solid_polygon(f"PlazaPaver_{ring}_{i:02}",poly,2.032,2.055,[M["tile"],M["tilelight"],M["tilewarm"]][RNG.randrange(3)],.012)

# Broad uneven flagstones remain subtle, readable at gameplay distance.
for name,line,width in path_lines:
    walked=0; last=line[0]
    for idx,p in enumerate(line[1:],1):
        walked+=(p-last).length;last=p
        if walked<1.22:continue
        walked=0
        if (p-Vector((0,-8))).length<6.5:continue
        tang=(line[min(idx+1,len(line)-1)]-line[max(0,idx-1)]).normalized()
        normal=Vector((-tang.y,tang.x))
        for k in [-1,1]:
            center=p+normal*(width*.24*k+RNG.uniform(-.08,.08))
            points=[]
            for j in range(7):
                t=j*2*math.pi/7
                r=RNG.uniform(.89,1.07)
                q=center+tang*(math.cos(t)*.60*r)+normal*(math.sin(t)*.61*r)
                points.append(tuple(q))
            solid_polygon(f"{name}_Flagstone_{idx:02}_{k}",points,2.03,2.06,[M["tile"],M["tilelight"]][RNG.randrange(2)],.014)

# Twelve shallow sandstone steps, from y=6.4 to12.4, connect z=2 to z=6.
steps=12; y0=6.4; tread=.50; halfw=2.35; rise=4/steps
profile=[(y0,2.0)]
for i in range(steps):
    profile.extend([(y0+i*tread,2+(i+1)*rise),(y0+(i+1)*tread,2+(i+1)*rise)])
profile += [(y0+steps*tread,2.0)]
v=[(-halfw,y,z) for y,z in profile]+[(halfw,y,z) for y,z in profile]
n=len(profile)
f=[tuple(reversed(range(n))),tuple(range(n,2*n))]
f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
stairs=mesh_obj("PlateauStaircase",v,f,[M["tilelight"]])
bevel(stairs,.045,3)
stairs["start_y_m"]=6.4;stairs["end_y_m"]=12.4
for side in [-1,1]:
    for i in range(steps):
        x=side*2.58;y=y0+(i+.5)*tread
        poly=[(x-.18,y-.25),(x+.18,y-.25),(x+.18,y+.25),(x-.18,y+.25)]
        solid_polygon(f"StairCheek_{side}_{i:02}",poly,2,2+(i+1)*rise+.13,M["clifflight"],.055)
solid_polygon("PlateauLandingPath",[(-1.6,12.3),(1.6,12.3),(1.7,17.8),(-1.7,17.8)],6.006,6.03,M["path"])
for i in range(4):
    for side in [-1,1]:
        x=.77*side;y=12.9+i*1.22
        poly=[(x-.62,y-.46),(x+.51,y-.51),(x+.63,y+.43),(x-.49,y+.52)]
        solid_polygon(f"PlateauLandingPaver_{i}_{side}",poly,6.03,6.055,M["tile"],.02)

# Village source owns the southern dock ramp and its beach approach.

bpy.context.scene.unit_settings.system="METRIC"
bpy.context.scene.unit_settings.scale_length=1.0
bpy.context.scene.world.color=(.18,.22,.26)
for ob in bpy.context.scene.objects:
    ob.select_set(False)
    ob["asset_family"]="BeastCrossing_Terrain"
    if ob.type=="MESH":
        bm=bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(ob.data)
        bm.free()
bpy.context.scene["coordinate_contract"]="Meters; X east; Y north; Z up. Main grass 2; plateau 6; water 0."
bpy.context.scene["terrain_authorship"]="Deterministic authored mesh geometry; generated image used only as visual reference."
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT),compress=True)
objects=[o for o in bpy.context.scene.objects if o.type=="MESH"]
points=[o.matrix_world@Vector(c) for o in objects for c in o.bound_box]
minimum=[min(p[i] for p in points) for i in range(3)]
maximum=[max(p[i] for p in points) for i in range(3)]
print("TERRAIN_VERIFIED", {"file":str(OUTPUT),"mesh_objects":len(objects),"vertices":sum(len(o.data.vertices) for o in objects),"polygons":sum(len(o.data.polygons) for o in objects),"bounds_min":minimum,"bounds_max":maximum,"materials":len(bpy.data.materials)})
