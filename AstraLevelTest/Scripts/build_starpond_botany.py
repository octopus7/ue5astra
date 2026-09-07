"""Build the Star Pond botanical kit in metres from the approved detail reference.

Blender 4.5 --factory-startup -b --python Scripts/build_starpond_botany.py
Library meshes have local floor origins; larger presentation duplicates are separate.
All leaves, petals and pads are closed geometry. No alpha cards are required.
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
OUT = ART / 'Meshes' / 'StarPond'
OUT.mkdir(parents=True, exist_ok=True)
for folder in ('Blender', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
assert (ART / 'Reference/StarPond/Ref_StarPondBotany.png').exists()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
SCENE = bpy.context.scene
SCENE.unit_settings.system = 'METRIC'
SCENE.unit_settings.scale_length = 1.0
LIBRARY = bpy.data.collections.new('01_StarPondBotany_Library')
PREVIEW = bpy.data.collections.new('02_StarPondBotany_Presentation')
SCENE.collection.children.link(LIBRARY)
SCENE.collection.children.link(PREVIEW)

MATERIALS = {
    'M_SP_Lily_JadePad': {'base_color': '326455', 'roughness': .55, 'metallic': 0},
    'M_SP_Lily_PadVein': {'base_color': '61916B', 'roughness': .62, 'metallic': 0},
    'M_SP_Lily_SilverPetal': {'base_color': 'DEE9EE', 'roughness': .36, 'metallic': .10},
    'M_SP_Lily_IvoryPetal': {'base_color': 'FBF3D9', 'roughness': .42, 'metallic': .03},
    'M_SP_Lily_BluePetal': {'base_color': 'ADBCCA', 'roughness': .48, 'metallic': .04},
    'M_SP_Lily_WarmGold': {'base_color': 'F8CD67', 'roughness': .38, 'metallic': .15,
                           'emissive_color': 'FFD281', 'emissive_strength': .22},
    'M_SP_Grass_BlueSilver': {'base_color': '719FAB', 'roughness': .64, 'metallic': .03},
    'M_SP_Grass_DeepTeal': {'base_color': '356970', 'roughness': .75, 'metallic': 0},
    'M_SP_Grass_SilverEdge': {'base_color': 'ACD5CE', 'roughness': .59, 'metallic': .03},
    'M_SP_Flower_StarBlue': {'base_color': '8ECEDE', 'roughness': .46, 'metallic': .04},
    'M_SP_Willow_Bark': {'base_color': '746852', 'roughness': .89, 'metallic': 0},
    'M_SP_Willow_BarkRidge': {'base_color': '918169', 'roughness': .86, 'metallic': 0},
    'M_SP_Willow_BarkShadow': {'base_color': '4D504A', 'roughness': .92, 'metallic': 0},
    'M_SP_Willow_Moss': {'base_color': '697846', 'roughness': .94, 'metallic': 0},
    'M_SP_Willow_LeafGreen': {'base_color': '658952', 'roughness': .81, 'metallic': 0},
    'M_SP_Willow_LeafLight': {'base_color': '8BA65A', 'roughness': .80, 'metallic': 0},
    'M_SP_Willow_LeafJade': {'base_color': '46796B', 'roughness': .83, 'metallic': 0},
    'M_SP_Willow_LeafShadow': {'base_color': '4B724F', 'roughness': .88, 'metallic': 0},
}


def linear(x):
    return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4


def rgba(value):
    return tuple(linear(int(value[i:i+2], 16) / 255) for i in (0, 2, 4)) + (1,)


MATS = {}
for name, info in MATERIALS.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba(info['base_color'])
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = info['roughness']
    shader.inputs['Metallic'].default_value = info['metallic']
    if info.get('emissive_strength'):
        shader.inputs['Emission Color'].default_value = rgba(info['emissive_color'])
        shader.inputs['Emission Strength'].default_value = info['emissive_strength']
    MATS[name] = mat


class Builder:
    def __init__(self):
        self.verts, self.faces, self.indices, self.slots = [], [], [], []
        self.leaf_count = 0

    def add(self, vertices, faces, material):
        offset = len(self.verts)
        self.verts.extend(tuple(v) for v in vertices)
        self.faces.extend(tuple(offset + i for i in face) for face in faces)
        if material not in self.slots:
            self.slots.append(material)
        self.indices.extend([self.slots.index(material)] * len(faces))

    def ellipsoid(self, center, scale, material, sides=16, rings=8):
        center = Vector(center)
        vertices = [center + Vector((0, 0, scale[2]))]
        for row in range(1, rings):
            theta = math.pi * row / rings
            for col in range(sides):
                a = math.tau * col / sides
                vertices.append(center + Vector((scale[0]*math.sin(theta)*math.cos(a),
                                                scale[1]*math.sin(theta)*math.sin(a),
                                                scale[2]*math.cos(theta))))
        vertices.append(center-Vector((0, 0, scale[2])))
        faces = [(0, 1+j, 1+(j+1)%sides) for j in range(sides)]
        for row in range(rings-2):
            a, b = 1+row*sides, 1+(row+1)*sides
            for j in range(sides):
                k = (j+1)%sides
                faces.append((a+j, b+j, b+k, a+k))
        a = 1+(rings-2)*sides
        faces.extend((a+j, len(vertices)-1, a+(j+1)%sides) for j in range(sides))
        self.add(vertices, faces, material)

    def tube(self, points, radii, material, sides=10, flutes=0):
        points = [Vector(p) for p in points]
        vertices = []
        for row, point in enumerate(points):
            tangent = (points[min(len(points)-1,row+1)] - points[max(0,row-1)]).normalized()
            helper = Vector((0, 1, 0)) if abs(tangent.z) > .9 else Vector((0, 0, 1))
            u = tangent.cross(helper).normalized()
            v = tangent.cross(u).normalized()
            for j in range(sides):
                a = math.tau*j/sides
                r = radii[row]*(1 + flutes*math.sin(5*a+.42*row))
                vertices.append(point + r*(math.cos(a)*u+math.sin(a)*v))
        faces = [tuple(range(sides-1,-1,-1))]
        for row in range(len(points)-1):
            for j in range(sides):
                k = (j+1)%sides
                faces.append((row*sides+j,row*sides+k,(row+1)*sides+k,(row+1)*sides+j))
        faces.append(tuple((len(points)-1)*sides+j for j in range(sides)))
        self.add(vertices, faces, material)

    def blade(self, points, widths, thickness, material, across=None):
        """Closed, lenticular leaf with pointed ends and smoothly changing cross-section."""
        points = [Vector(p) for p in points]
        tangent = (points[-1]-points[0]).normalized()
        if across is None:
            across = tangent.cross(Vector((0,0,1)))
            if across.length < .01:
                across = Vector((1,0,0))
        across = Vector(across).normalized()
        up = across.cross(tangent).normalized()
        if up.z < 0:
            up = -up
        vertices = [points[0]]
        # Six vertices around each full closed section, with a pronounced upper ridge.
        for row in range(1,len(points)-1):
            width = widths[row]
            for x, z in ((-1,0),(-.55,.75),(0,1),(.55,.75),(1,0),(0,-.22)):
                vertices.append(points[row]+across*x*width+up*z*thickness)
        vertices.append(points[-1])
        faces = [(0,1+(j+1)%6,1+j) for j in range(6)]
        for row in range(len(points)-3):
            a, b = 1+row*6, 1+(row+1)*6
            for j in range(6):
                k = (j+1)%6
                faces.append((a+j,a+k,b+k,b+j))
        a = 1+(len(points)-3)*6
        faces.extend((a+j,a+(j+1)%6,len(vertices)-1) for j in range(6))
        self.add(vertices, faces, material)
        self.leaf_count += 1


def smooth_path(knots, radii, subdivisions=4):
    points, rr = [], []
    knots = [Vector(p) for p in knots]
    for i in range(len(knots)-1):
        p0, p1 = knots[max(i-1,0)], knots[i]
        p2, p3 = knots[i+1], knots[min(i+2,len(knots)-1)]
        for j in range(subdivisions):
            t = j/subdivisions
            points.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
            rr.append(radii[i]*(1-t)+radii[i+1]*t)
    points.append(knots[-1]); rr.append(radii[-1])
    return points, rr


def pad(b, center, radius, angle):
    """Concave radial notch makes each pad read as an actual water-lily leaf."""
    center = Vector(center)
    n = 40
    vertices = [center + Vector((0,0,.012)), center-Vector((0,0,.006))]
    # Closed contour goes from the heart of the notch around to its other side.
    ring = []
    for i in range(n):
        a = angle+.14+(math.tau-.28)*i/(n-1)
        r = radius*(1+.028*math.sin(3*a)+.018*math.cos(7*a))
        ring.append(center+Vector((r*math.cos(a),r*.90*math.sin(a),.009+radius*.015*math.cos(3*a))))
    ring.append(center+Vector((.015*math.cos(angle),.015*math.sin(angle),.012)))
    for p in ring:
        vertices.append(p)
    for p in ring:
        vertices.append(p-Vector((0,0,.014)))
    count = len(ring)
    faces = []
    for i in range(count):
        j = (i+1)%count
        faces.extend(((0,2+i,2+j),(1,2+count+j,2+count+i),(2+i,2+count+i,2+count+j,2+j)))
    b.add(vertices,faces,'M_SP_Lily_JadePad')
    for i in range(10):
        a = angle+.3+i*(math.tau-.6)/9
        pts = [center+Vector((radius*t*math.cos(a),radius*t*.90*math.sin(a),.022)) for t in (.08,.4,.7,.92)]
        b.tube(pts,[.0025,.002,.0015,.0008],'M_SP_Lily_PadVein',5)


def flower(b, center, radius, star=False, rotation=0):
    c = Vector(center)
    tiers = [(5,radius*.07,1,.10,.34)] if star else [(10,.03,1,.20,.35),(9,.026,.80,.62,.30),(7,.021,.58,1.13,.25)]
    for tier, (count,base_r,length_factor,lift,width) in enumerate(tiers):
        for i in range(count):
            a = rotation+math.tau*i/count+tier*.25
            length = radius*length_factor
            pts=[]
            for t in (0,.22,.5,.77,1):
                radial=base_r+length*t
                z=radius*(.07*t+lift*t*t)+tier*radius*.11
                pts.append(c+Vector((radial*math.cos(a),radial*math.sin(a),z)))
            widths=[0,length*width*.71,length*width,length*width*.55,0]
            mat='M_SP_Flower_StarBlue' if star else ('M_SP_Lily_BluePetal' if tier==0 and i%4==0 else ('M_SP_Lily_IvoryPetal' if tier==2 else 'M_SP_Lily_SilverPetal'))
            b.blade(pts,widths,radius*.055,mat,(-math.sin(a),math.cos(a),0))
    if star:
        b.ellipsoid(c+Vector((0,0,radius*.14)),(radius*.18,radius*.18,radius*.20),'M_SP_Lily_WarmGold',12,6)
    else:
        b.ellipsoid(c+Vector((0,0,radius*.39)),(radius*.21,radius*.21,radius*.19),'M_SP_Lily_WarmGold',16,8)
        for i in range(13):
            a=math.tau*i/13
            r=radius*.15
            stem=[c+Vector((math.cos(a)*r,math.sin(a)*r,radius*.30)),c+Vector((math.cos(a)*r*1.6,math.sin(a)*r*1.6,radius*(.61+.10*math.sin(a*3))))]
            b.tube(stem,[radius*.014,radius*.010],'M_SP_Lily_WarmGold',6)
            b.ellipsoid(stem[-1],(radius*.035,radius*.035,radius*.063),'M_SP_Lily_WarmGold',8,6)


def lily(variant):
    b=Builder()
    if variant==1:
        arrangements=[((-.21,.035,.011),.25,2.6),((.20,.075,.012),.23,-.2),((.005,-.21,.008),.265,-1.3)]
        center=(0,0,.05); radius=.255
    else:
        arrangements=[((-.21,-.01,.011),.26,3.4),((.185,-.145,.012),.25,-.7),((.10,.22,.017),.205,1.5)]
        center=(-.032,.007,.052); radius=.239
    for loc,r,a in arrangements:
        pad(b,loc,r,a)
    flower(b,center,radius,rotation=.22*variant)
    if variant==2:
        # A small side bud gives the second lily a separate, more asymmetric silhouette.
        b.tube([(.19,.13,.035),(.18,.17,.12),(.19,.18,.16)],[.01,.007,.006],'M_SP_Lily_PadVein',8)
        b.ellipsoid((.19,.18,.18),(.028,.027,.055),'M_SP_Lily_IvoryPetal',12,8)
    return b


def grasses():
    b=Builder(); rng=random.Random(8817)
    for i in range(25):
        a=math.tau*i/25+rng.uniform(-.13,.13)
        r=rng.uniform(.19,.34)
        h=rng.uniform(.15,.29)
        base=Vector((rng.uniform(-.035,.035),rng.uniform(-.035,.035),0))
        pts=[]
        for t in (0,.23,.5,.76,1):
            radial=r*t*t
            z=h*math.sin(t*math.pi*.78)+.02*t
            pts.append(base+Vector((math.cos(a)*radial,math.sin(a)*radial,z)))
        w=rng.uniform(.013,.022)
        b.blade(pts,[0,w*.7,w,w*.55,0],.006,
                ('M_SP_Grass_DeepTeal','M_SP_Grass_BlueSilver','M_SP_Grass_SilverEdge')[i%3],
                (-math.sin(a),math.cos(a),0))
    for i,(x,y,h) in enumerate([(-.11,.025,.37),(.075,.06,.46),(.12,-.085,.31),(-.045,-.06,.27)]):
        pts=[(x*.12,y*.12,0),(x*.4,y*.5,h*.42),(x*.86,y*.85,h*.82),(x,y,h)]
        path,rr=smooth_path(pts,[.007,.005,.004,.003],3)
        b.tube(path,rr,'M_SP_Grass_DeepTeal',7)
        flower(b,(x,y,h),.065,star=True,rotation=i*.8)
    return b


def merged_wood(wood):
    """Union branch joints before adding bark ridges or leaves, to avoid visible tube seams."""
    data=bpy.data.meshes.new('WillowUnionSource')
    data.from_pydata(wood.verts,[],wood.faces);data.update()
    for slot in wood.slots:data.materials.append(MATS[slot])
    for face,idx in zip(data.polygons,wood.indices):face.material_index=idx
    obj=bpy.data.objects.new('WillowUnionSource',data);SCENE.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    remesh=obj.modifiers.new('ContinuousOldWood','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.047
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    smooth=obj.modifiers.new('SoftenBranchJoints','SMOOTH');smooth.factor=.8;smooth.iterations=5
    bpy.ops.object.modifier_apply(modifier=smooth.name)
    decimate=obj.modifiers.new('BroadTopdownWoodForms','DECIMATE');decimate.ratio=.42
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    result=Builder()
    result.add([v.co.copy() for v in obj.data.vertices],[tuple(p.vertices) for p in obj.data.polygons],'M_SP_Willow_Bark')
    bpy.data.objects.remove(obj,do_unlink=True)
    return result


def willow():
    wood=Builder();detail=Builder();b=Builder();rng=random.Random(2481)
    trunk_knots=[(0,0,.08),(-.29,.05,.85),(-.50,.07,1.65),(-.36,0,2.40),(.26,.06,3.14),(.77,.06,3.95),(.62,.10,4.95),(.71,.20,5.8),(1.18,.23,6.78),(1.19,.27,7.5)]
    radii=[.66,.57,.49,.44,.39,.32,.26,.23,.17,.09]
    main,rr=smooth_path(trunk_knots,radii,5)
    wood.tube(main,rr,'M_SP_Willow_Bark',20,.13)
    # Broad buttress roots and several interwoven trunk ridges provide old-tree flow.
    for i in range(9):
        a=math.tau*i/9
        r=rng.uniform(1.0,1.55)
        roots=[(.32*math.cos(a),.32*math.sin(a),.64),(.64*math.cos(a),.64*math.sin(a),.29),
               (r*.78*math.cos(a+.10),r*.78*math.sin(a+.10),.12),(r*math.cos(a+.18),r*math.sin(a+.18),.035)]
        pts,rads=smooth_path(roots,[.27,.24,.14,.028],3)
        wood.tube(pts,rads,'M_SP_Willow_Bark',10,.06)
        if i%3==0:
            moss=[p+Vector((0,0,r*.72)) for p,r in zip(pts[2:-1],rads[2:-1])]
            detail.tube(moss,[r*.45 for r in rads[2:-1]],'M_SP_Willow_Moss',8)
    for i in range(10):
        a=math.tau*i/10
        pts=[]; rads=[]
        for j,(p,r) in enumerate(zip(main,rr)):
            phase=a+.7*j/len(main)+.28*math.sin(j*.12)
            pts.append(p+Vector((math.cos(phase)*r*.91,math.sin(phase)*r*.91,0)))
            rads.append(max(.018,r*.12))
        detail.tube(pts,rads,'M_SP_Willow_BarkRidge' if i%3 else 'M_SP_Willow_BarkShadow',7)
    # Each crown follows a distinct branch rather than a symmetrical radial tree.
    crowns=[
        ((1.20,.25,7.47),(1.00,.93,.78),[(.67,.15,5.5),(1.0,.2,6.4),(1.2,.25,7.3)], [.23,.15,.055]),
        ((-.76,.08,6.25),(1.16,1.02,.75),[(.65,.1,4.8),(-.10,.10,5.24),(-.77,.08,6.10)],[.24,.20,.055]),
        ((2.28,.22,5.98),(1.16,.97,.78),[(.5,.05,3.8),(1.63,.16,4.7),(2.28,.22,5.83)],[.28,.20,.055]),
        ((-1.90,-.01,4.26),(1.15,.98,.82),[(-.32,0,2.26),(-1.39,-.03,2.81),(-1.90,-.01,4.12)],[.35,.23,.055]),
        ((2.31,-.18,3.77),(1.31,1.05,.80),[(.11,.02,2.86),(1.39,-.08,3.04),(2.31,-.18,3.65)],[.31,.20,.055]),
        ((-.65,1.16,4.86),(1.17,.98,.79),[(-.25,.12,2.37),(-.48,.80,3.20),(-.65,1.16,4.70)],[.29,.17,.05]),
    ]
    for ci,(center,scale,branch,rads) in enumerate(crowns):
        path,radii=smooth_path(branch,rads,5)
        wood.tube(path,radii,'M_SP_Willow_Bark',12,.08)
        # Light ridges run along the separate forks as well.
        sidepath=[p+Vector((0,-r*.85,0)) for p,r in zip(path,radii)]
        detail.tube(sidepath,[max(.012,r*.12) for r in radii],'M_SP_Willow_BarkRidge',6)
        c=Vector(center); rx,ry,rz=scale
        b.ellipsoid(c,(rx*.92,ry*.92,rz*.93),'M_SP_Willow_LeafShadow',20,10)
        for row in range(6):
            theta=.25+row*.41
            around=max(8,round(22*math.sin(theta)))
            for col in range(around):
                phi=math.tau*(col+(row%2)*.5)/around+ci*.51
                normal=Vector((math.sin(theta)*math.cos(phi),math.sin(theta)*math.sin(phi),math.cos(theta)))
                down=Vector((math.cos(theta)*math.cos(phi),math.cos(theta)*math.sin(phi),-math.sin(theta)))
                across=Vector((-math.sin(phi),math.cos(phi),0))
                start=c+Vector((normal.x*rx,normal.y*ry,normal.z*rz))
                length=rng.uniform(.53,.68)
                pts=[]
                for t in (0,.24,.53,.79,1):
                    pts.append(start+down*length*t+normal*(.02+.075*math.sin(math.pi*t))-Vector((0,0,.16*t*t)))
                w=rng.uniform(.155,.19)
                mat='M_SP_Willow_LeafLight' if row<2 and col%3 else ('M_SP_Willow_LeafJade' if row>3 else 'M_SP_Willow_LeafGreen')
                b.blade(pts,[0,w*.72,w,w*.5,0],.019,mat,across)
        # Open hanging trails silhouette against gaps between crowns and below them.
        for strand in range(18):
            a=math.tau*strand/18+ci*.17
            length=rng.uniform(.78,1.58)
            start=c+Vector((rx*.77*math.cos(a),ry*.77*math.sin(a),-.15))
            pts=[start+Vector((math.cos(a)*.09*t,math.sin(a)*.09*t,-length*t)) for t in (0,.33,.67,1)]
            b.tube(pts,[.012,.010,.007,.0025],'M_SP_Willow_LeafShadow',5)
            for j in range(6):
                t=.09+j*.14
                side=1 if j%2 else -1
                p=start+Vector((math.cos(a)*.09*t,math.sin(a)*.09*t,-length*t))
                direction=Vector((-math.sin(a)*side*.24,math.cos(a)*side*.24,-.39))
                lp=[p+direction*u+Vector((math.cos(a)*.04*math.sin(math.pi*u),math.sin(a)*.04*math.sin(math.pi*u),0)) for u in (0,.25,.55,.8,1)]
                b.blade(lp,[0,.043,.055,.028,0],.010,'M_SP_Willow_LeafJade' if j>2 else 'M_SP_Willow_LeafGreen')
    merged=merged_wood(wood)
    for component in (detail,b):
        for material_index,material in enumerate(component.slots):
            faces=[face for face,idx in zip(component.faces,component.indices) if idx==material_index]
            used=sorted({i for face in faces for i in face})
            lookup={old:new for new,old in enumerate(used)}
            merged.add([component.verts[i] for i in used],[tuple(lookup[i] for i in face) for face in faces],material)
        merged.leaf_count+=component.leaf_count
    return merged


ASSETS=[]; INFOS=[]


def bounds(obj):
    return [[min(v.co[a] for v in obj.data.vertices) for a in range(3)],
            [max(v.co[a] for v in obj.data.vertices) for a in range(3)]]


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False); obj.select_set(True)
    bpy.context.view_layer.objects.active=obj


def finish(name,b,collision,target_width=None,target_height=None,description=''):
    data=bpy.data.meshes.new(name)
    data.from_pydata(b.verts,[],b.faces); data.update()
    for key in b.slots:
        data.materials.append(MATS[key])
    for p,idx in zip(data.polygons,b.indices):
        p.material_index=idx; p.use_smooth=True
    obj=bpy.data.objects.new(name,data); LIBRARY.objects.link(obj)
    bb=bounds(obj)
    factor=target_height/(bb[1][2]-bb[0][2]) if target_height else target_width/max(bb[1][0]-bb[0][0],bb[1][1]-bb[0][1])
    for v in data.vertices:
        v.co.z-=bb[0][2]
        v.co*=factor
    bm=bmesh.new(); bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bm.to_mesh(data); bm.free()
    activate(obj)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(64),island_margin=.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in data.polygons:p.use_smooth=True
    data.update()
    data.normals_split_custom_set([tuple(n.vector) for n in data.corner_normals])
    bb=bounds(obj)
    bm=bmesh.new(); bm.from_mesh(data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    degenerate=sum(f.calc_area()<1e-12 for f in bm.faces)
    bm.free()
    assert nonmanifold==0,(name,'nonmanifold',nonmanifold)
    assert degenerate==0,(name,'degenerate',degenerate)
    assert abs(bb[0][2])<1e-6
    assert data.uv_layers.active and data.has_custom_normals
    info={'asset_id':name,'file':f'ArtSource/Meshes/StarPond/{name}.fbx','materials':b.slots,
          'collision':collision,'dimensions_m':[bb[1][i]-bb[0][i] for i in range(3)],
          'bounds_min_m':bb[0],'bounds_max_m':bb[1],'triangles':len(data.polygons),'vertices':len(data.vertices),
          'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS','pivot':'ground origin at local Z=0',
          'uv_channel':0,'actual_leaf_and_petal_count':b.leaf_count,'description':description,
          'validation':{'non_manifold_edges':nonmanifold,'degenerate_triangles':degenerate,'smooth_normals':True}}
    if collision=='trunk':
        info['trunk_collision']={'radius_m':.90*factor,'height_m':2.9*factor,'centre_xy_m':[-.16*factor,0],
                                 'roots_no_collision':True,'canopy_no_collision':True}
    bpy.ops.export_scene.fbx(filepath=str(ROOT/info['file']),use_selection=True,object_types={'MESH'},
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True,path_mode='STRIP',use_tspace=True)
    obj.hide_render=True;obj.hide_set(True)
    ASSETS.append(obj);INFOS.append(info)


finish('SM_SP_StarLily_01',lily(1),'none',target_width=.94,
       description='Three notched jade pads surrounding a silver-white, three-tier pointed star lily with warm gold stamens.')
finish('SM_SP_StarLily_02',lily(2),'none',target_width=.90,
       description='Asymmetric silver-white lily with three different pads and a closed side bud.')
finish('SM_SP_StarFlowers',grasses(),'none',target_width=.64,
       description='Blue-silver curved grass blades supporting four five-point pale blue star flowers with gold centres.')
finish('SM_SP_OldWillow',willow(),'trunk',target_height=8.1,
       description='Asymmetric old willow with sinuous fluted trunk, six branching green leaf crowns and open, jade drooping leaf trails.')

ROUNDTRIP=[]
for original,expected in zip(ASSETS,INFOS):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ROOT/expected['file']),use_custom_normals=True)
    added=set(bpy.data.objects)-before
    meshes=[o for o in added if o.type=='MESH']
    assert len(meshes)==1
    obj=meshes[0];bb=bounds(obj)
    error=max(abs(bb[j][i]-[expected['bounds_min_m'],expected['bounds_max_m']][j][i]) for j in range(2) for i in range(3))
    slots=[s.material.name.split('.')[0] for s in obj.material_slots]
    finite_uv=bool(obj.data.uv_layers.active) and all(math.isfinite(value) for loop in obj.data.uv_layers.active.data for value in loop.uv)
    assert error<1e-5 and len(obj.data.polygons)==expected['triangles']
    assert slots==expected['materials'] and finite_uv
    assert obj.data.has_custom_normals and all(p.use_smooth for p in obj.data.polygons)
    assert obj.location.length<1e-6
    result={'asset_id':original.name,'passed':True,'bounds_error_m':error,'triangles':len(obj.data.polygons),
            'triangle_count_preserved':True,'ordered_material_slots_preserved':True,'finite_uv':True,
            'authored_smooth_normals_preserved':True,'ground_pivot_preserved':True}
    ROUNDTRIP.append(result)
    for added_obj in added:bpy.data.objects.remove(added_obj,do_unlink=True)

metadata={'source':'ArtSource/Blender/StarPondBotany.blend','script':'Scripts/build_starpond_botany.py',
          'reference':'ArtSource/Reference/StarPond/Ref_StarPondBotany.png','units':'metres',
          'materials':MATERIALS,'assets':INFOS,'fbx_roundtrip_validation':ROUNDTRIP,
          'placement_notes':'Lily pads sit on local Z=0, so align them just above the pond water. '
          'Flowers are small collision-free shoreline foliage. Willow uses trunk-only collision; '
          'keep its long canopy over water and preserve clear walking space beneath the outer leaf drapes. '
          'Presentation lilies and grass are enlarged 4.5 times for visual inspection; library geometry has actual dimensions.'}
(ART/'Layout/starpond_botany.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
(ART/'Previews/StarPondBotany_Validation.json').write_text(json.dumps({'passed':True,'asset_count':len(INFOS),
    'assets':INFOS,'fbx_roundtrip_validation':ROUNDTRIP},indent=2)+'\n',encoding='utf-8')

# Independent presentation duplicates are intentionally enlarged to inspect the small plants.
for original,location,scale in zip(ASSETS,[(-4.0,-2.2,0),(-4.0,1.1,0),(-3.8,4.3,0),(2.2,1.4,0)],[4.5,4.5,4.5,1]):
    display=bpy.data.objects.new('Preview_'+original.name,original.data)
    PREVIEW.objects.link(display);display.location=location;display.scale=(scale,scale,scale)
ground=bpy.data.materials.new('PreviewOnly_StarPondGround');ground.use_nodes=True
ground.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.10,.15,.145,1)
ground.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.93
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025))
bpy.context.object.name='PreviewOnly_Ground';bpy.context.object.data.materials.append(ground)
SCENE.world=bpy.data.worlds.new('PreviewOnly_StarPondSky');SCENE.world.use_nodes=True
SCENE.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.63,.75,.91,1)
SCENE.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55
bpy.ops.object.light_add(type='SUN',location=(-8,-10,15));sun=bpy.context.object
sun.name='PreviewOnly_SoftSun_50deg';sun.rotation_euler=(.35,-.50,-.4);sun.data.energy=2.4;sun.data.angle=math.radians(50)
bpy.ops.object.light_add(type='AREA',location=(-5,-8,10));key=bpy.context.object
key.name='PreviewOnly_SoftFill';key.data.energy=800;key.data.shape='DISK';key.data.size=7
key.rotation_euler=(Vector((0,0,3))-key.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(-10,-19,15));camera=bpy.context.object
camera.name='PreviewOnly_BotanyCamera';camera.rotation_euler=(Vector((-.1,1.0,3.3))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=15.5;SCENE.camera=camera
SCENE.render.engine='CYCLES';SCENE.cycles.samples=32;SCENE.cycles.use_denoising=True
SCENE.render.resolution_x=1800;SCENE.render.resolution_y=1500;SCENE.render.resolution_percentage=100
SCENE.render.image_settings.file_format='PNG';SCENE.render.filepath=str(ART/'Previews/Blender_StarPondBotany.png')
SCENE.view_settings.view_transform='AgX';SCENE.view_settings.look='AgX - Medium High Contrast'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/StarPondBotany.blend'))
bpy.ops.render.render(write_still=True)
print('STARPOND_BOTANY_COMPLETE '+json.dumps(INFOS))
