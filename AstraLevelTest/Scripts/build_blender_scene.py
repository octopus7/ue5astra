"""Build the modeled assets and author the 100.8m scene in Blender, then export.
Run with Blender 4.5+: blender -b --factory-startup --python this_file.py
All distances in this source scene are metres. Blender XY -> Unreal X,-Y.
"""
import bpy, math, random, json, struct, sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts'))
from water_geometry import water_geometry,add_edge_mask
ART = ROOT / 'ArtSource'
for folder in ['Meshes','Layout','Blender','Previews']:
    (ART / folder).mkdir(parents=True, exist_ok=True)
R = random.Random(514)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
assets_col = bpy.data.collections.new('01_MeshLibrary')
layout_col = bpy.data.collections.new('02_WoodlandLayout')
scene.collection.children.link(assets_col)
scene.collection.children.link(layout_col)
PALETTE = {
 'M_Bark':'604526','M_BarkLight':'89613A','M_Wood':'A77C45','M_WoodLight':'BF975B','M_WoodDark':'715232',
 'M_LeafOlive':'738344','M_LeafSage':'829A57','M_LeafLight':'95A350','M_Fir':'425F40','M_FirLight':'5C794A',
 'M_Stone':'838780','M_StoneLight':'A0A293','M_Moss':'788747','M_Grass':'697E40','M_GrassLight':'9BA759',
 'M_Reed':'84985B','M_Cattail':'624628','M_Lily':'548455','M_LotusPink':'E6A7AD','M_LotusLight':'F5DAD0',
 'M_Pollen':'D9B65C','M_FlowerCream':'F4E5B6','M_FlowerGold':'D8A74E','M_Mushroom':'BE7844',
 'M_CatCream':'F3E5C9','M_CatOrange':'C98236','M_CatBlack':'343731','M_CatPink':'DB9C92',
 'M_Water':'416F62','M_Ground':'7D8850','M_Path':'B79B66'
}
def lin(v):
    return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
MATS={}
for name,h in PALETTE.items():
    m=bpy.data.materials.new(name);m.use_nodes=True
    c=tuple(lin(int(h[i:i+2],16)/255) for i in (0,2,4))
    m.diffuse_color=(*c,1)
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=.88
    MATS[name]=m

def material(obj,name):
    obj.data.materials.append(MATS[name]);return obj
def cube(name,loc,dims,mat,rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc,rotation=rot)
    o=bpy.context.object;o.name=name;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return material(o,mat)
def ico(name,loc,scale,mat,sub=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub,radius=1,location=loc)
    o=bpy.context.object;o.name=name;o.scale=scale
    for v in o.data.vertices:
        v.co*=R.uniform(.90,1.10)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return material(o,mat)
def beam(name,a,b,r1,r2,mat,verts=7):
    a,b=Vector(a),Vector(b);d=b-a
    bpy.ops.mesh.primitive_cone_add(vertices=verts,radius1=r1,radius2=r2,depth=d.length,location=(a+b)/2)
    o=bpy.context.object;o.name=name;o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    return material(o,mat)
def mesh(name,verts,faces,mat):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(name,me);scene.collection.objects.link(o);return material(o,mat)
def join_asset(name,parts,collision='none'):
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:p.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();o=bpy.context.object;o.name=name
    scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    for c in list(o.users_collection):c.objects.unlink(o)
    assets_col.objects.link(o)
    o['asset_id']=name;o['collision']=collision
    # Apply metre-to-centimetre through FBX unit metadata; Unreal importer converts units.
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{name}.fbx'),use_selection=True,
        object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,
        mesh_smooth_type='FACE',use_mesh_modifiers=True)
    o.hide_render=True;o.hide_set(True)
    return o

LIB={}
for variant in range(3):
    p=[]
    height=5.8+variant*.45
    p.append(beam('Trunk',(0,0,0),(.18,-.08,height*.66),.48,.22,'M_Bark'))
    for k in range(6):
        a=k*math.tau/6+.2
        p.append(beam('Root',(math.cos(a)*.12,math.sin(a)*.12,.6),(math.cos(a)*1.15,math.sin(a)*1.15,.05),.26,.06,'M_BarkLight'))
    for k in range(5):
        a=k*math.tau/5+variant*.37
        end=(math.cos(a)*1.25,math.sin(a)*1.25,height*.67)
        p.append(beam('Branch',(.1,0,2.1),end,.19,.10,'M_BarkLight'))
        col=['M_LeafOlive','M_LeafSage','M_LeafLight'][(k+variant)%3]
        p.append(ico('Crown',(end[0]*1.13,end[1]*1.13,height*.75), (1.65,1.6,1.6),col,2))
    p.append(ico('TopCrown',(.2,.1,height*.94),(1.8,1.7,1.65),'M_LeafLight',2))
    name=f'SM_Oak_{variant+1:02}';LIB[name]=join_asset(name,p,'trunk')

for variant in range(3):
    p=[beam('FirTrunk',(0,0,0),(.08,0,6.3),.32,.05,'M_Bark')]
    for tier in range(4):
        z=1.25+tier*1.24;rad=2.0-tier*.40+variant*.09;n=18
        verts=[(0,0,z+2.5-tier*.17)]
        for i in range(n):
            a=math.tau*i/n; rr=rad*(1 if i%2==0 else .82)
            verts.append((math.cos(a)*rr,math.sin(a)*rr,z+(.18 if i%2 else 0)))
        faces=[(0,1+i,1+(i+1)%n) for i in range(n)]
        faces.append(tuple(range(n,0,-1)))
        p.append(mesh('FirTier',verts,faces,'M_FirLight' if tier%2 else 'M_Fir'))
    name=f'SM_Fir_{variant+1:02}';LIB[name]=join_asset(name,p,'trunk')

for variant in range(5):
    rock=ico('Stone',(0,0,.55),(1.45+variant*.07,1.15,1.05),'M_Stone',2)
    rock.data.materials.append(MATS['M_StoneLight']);rock.data.materials.append(MATS['M_Moss'])
    for v in rock.data.vertices:
        if v.co.z<-.42:v.co.z=-.42+R.uniform(-.05,.05)
    rock.data.update()
    for face in rock.data.polygons:
        if face.normal.z>.38 and R.random()<.78:face.material_index=2
        elif R.random()<.24:face.material_index=1
    name=f'SM_MossRock_{variant+1:02}';LIB[name]=join_asset(name,[rock],'solid')

def leaf_ribbon(base,angle,length,width,bend,mat):
    d=Vector((math.cos(angle),math.sin(angle),0));side=Vector((-d.y,d.x,0));b=Vector(base)
    centers=[b,b+d*length*.22+Vector((0,0,length*.55)),b+d*length*bend+Vector((0,0,length*.95))]
    verts=[]
    for c,w in zip(centers,[width*.3,width,0]):verts.extend([tuple(c-side*w/2),tuple(c+side*w/2)])
    return mesh('Leaf',verts,[(0,1,3,2),(2,3,5,4)],mat)

p=[]
for i in range(12):
    a=R.random()*math.tau;p.append(leaf_ribbon((R.uniform(-.16,.16),R.uniform(-.16,.16),0),a,R.uniform(.7,1.35),.11,.4,'M_Reed'))
for i in range(4):
    x,y=R.uniform(-.23,.23),R.uniform(-.23,.23);h=R.uniform(1,1.55)
    p.append(beam('Stem',(x,y,0),(x+.1,y,h),.017,.012,'M_Reed',5))
    p.append(beam('Cattail',(x+.1,y,h-.23),(x+.1,y,h),.05,.05,'M_Cattail',7))
LIB['SM_Reeds']=join_asset('SM_Reeds',p)

p=[]
for i in range(3):
    cx,cy=[(-.25,-.20),(.25,.05),(-.05,.30)][i];n=16;r=[.37,.30,.32][i]
    verts=[(cx,cy,.025)]+[(cx+r*math.cos(.25+j*(math.tau-.5)/(n-1)),cy+r*math.sin(.25+j*(math.tau-.5)/(n-1)),.035) for j in range(n)]
    faces=[(0,j+1,j+2) for j in range(n-1)]
    p.append(mesh('LilyPad',verts,faces,'M_Lily'))
for layer,n in [(0,9),(1,7)]:
    for i in range(n):
        a=i*math.tau/n+layer*.25;d=Vector((math.cos(a),math.sin(a),0));side=Vector((-d.y,d.x,0))
        base=Vector((0,0,.09));mid=base+d*(.16-layer*.045)+Vector((0,0,.06));tip=base+d*(.32-layer*.1)+Vector((0,0,.11+layer*.11))
        verts=[tuple(base),tuple(mid-side*.095),tuple(tip),tuple(mid+side*.095),tuple(mid+Vector((0,0,.045)))]
        p.append(mesh('LotusPetal',verts,[(0,1,4),(1,2,4),(2,3,4),(3,0,4)],'M_LotusPink' if layer==0 else 'M_LotusLight'))
p.append(ico('Pollen',(0,0,.20),(.085,.085,.07),'M_Pollen',1))
LIB['SM_Lotus']=join_asset('SM_Lotus',p)

for kind in ['Grass','Fern','Flowers','Mushrooms','Shrub']:
    p=[]
    if kind=='Shrub':
        for i in range(5):p.append(ico('Bush',(R.uniform(-.6,.6),R.uniform(-.5,.5),.43),(.65,.55,.6),'M_LeafSage',1))
    elif kind=='Mushrooms':
        for i in range(3):
            x,y=R.uniform(-.32,.32),R.uniform(-.3,.3);h=R.uniform(.18,.4)
            p.append(beam('Stem',(x,y,0),(x,y,h),.045,.035,'M_FlowerCream',6))
            p.append(ico('Cap',(x,y,h),(.17,.17,.10),'M_Mushroom',1))
    elif kind=='Flowers':
        for i in range(7):
            x,y=R.uniform(-.5,.5),R.uniform(-.4,.4);h=R.uniform(.15,.45)
            p.append(beam('Stem',(x,y,0),(x,y,h),.014,.01,'M_Grass',4))
            p.append(ico('Center',(x,y,h),(.05,.05,.04),'M_Pollen',1))
            for j in range(5):
                a=j*math.tau/5;p.append(ico('Petal',(x+.08*math.cos(a),y+.08*math.sin(a),h),(.07,.07,.025),'M_FlowerCream' if i%2 else 'M_FlowerGold',1))
    elif kind=='Fern':
        for i in range(7):
            a=i*math.tau/7
            for j in range(1,5):
                t=j/5;d=Vector((math.cos(a),math.sin(a),0));s=Vector((-d.y,d.x,0))
                c=d*t*.8+Vector((0,0,.5*math.sin(t*2)))
                for sign in [-1,1]:
                    p.append(mesh('Frond',[tuple(c),tuple(c+s*sign*.18*(1-t/2)-d*.09),tuple(c+d*.2)],[(0,1,2)],'M_GrassLight'))
    else:
        for i in range(9):p.append(leaf_ribbon((R.uniform(-.22,.22),R.uniform(-.22,.22),0),R.random()*math.tau,R.uniform(.2,.48),.07,.4,'M_GrassLight' if i%3 else 'M_Grass'))
    name=f'SM_{kind}';LIB[name]=join_asset(name,p)

# Bridge local X runs along the stream, local Y spans across it.
for broken in [False,True]:
    p=[]
    for x in [-.85,.85]:
        if not broken:p.append(cube('SupportBeam',(x,0,-.24),(.22,7.4,.32),'M_WoodDark'))
        else:
            for sign in [-1,1]:p.append(cube('SnappedBeam',(x,sign*2.65,-.3),(.23,2.4,.33),'M_WoodDark',(.17*sign,.08,0)))
    for i in range(25):
        y=-3.5+i*.29
        if broken and abs(y)<1.35:continue
        p.append(cube('DeckPlank',(R.uniform(-.025,.025),y,R.uniform(-.025,.025)),(2.05,.265,.14),'M_Wood' if i%3 else 'M_WoodLight',(0,0,R.uniform(-.016,.016))))
    for x in [-1.04,1.04]:
        for y in [-3.35,0,3.35]:
            if broken and y==0:continue
            p.append(cube('RailPost',(x,y,.47),(.15,.16,1.15),'M_WoodDark',((.20 if broken else .015),0,0)))
        if not broken:
            p.append(cube('TopRail',(x,0,.94),(.13,6.9,.13),'M_Wood'))
            p.append(cube('LowerRail',(x,0,.43),(.10,6.9,.10),'M_WoodDark'))
        else:
            for sign in [-1,1]:p.append(cube('BrokenRail',(x,sign*2.8,.8),(.14,1.7,.13),'M_Wood',(.25*sign,0,0)))
    if broken:
        for i in range(7):
            p.append(cube('FallenPlank',(R.uniform(-1.4,1.4),R.uniform(-1.2,1.2),R.uniform(-.65,-.15)),(R.uniform(.7,1.8),.23,.12),'M_WoodDark',(R.uniform(-.2,.2),R.uniform(-.4,.4),R.uniform(-1.2,1.2))))
    else:
        for sign in [-1,1]:p.append(cube('Ramp',(0,sign*4.48,-.30),(2.08,2.05,.14),'M_Wood',(-sign*.30,0,0)))
    name='SM_BridgeBroken' if broken else 'SM_BridgeIntact';LIB[name]=join_asset(name,p,'complex')

p=[]
for x in [-3.4,3.4]:
    for y in [-2.7,2.7]:
        p.append(cube('CornerPost',(x,y,1.55),(.23,.24,3.1),'M_WoodDark'))
for i in range(14):
    x=-3.25+i*.50
    p.append(cube('FloorBoard',(x,0,.11),(.46,5.4,.18),'M_WoodDark' if i%4 else 'M_Wood'))
for i in range(9):
    z=.40+i*.29
    # Back wall, damaged upper courses; side walls have obvious breaches.
    p.append(cube('BackWall',(3.4,0,z),(.16,5.4 if i<5 else 3.5,.255),'M_Wood'))
    p.append(cube('SideWall',(1.0,2.7,z),(4.8 if i<4 else 3.3,.16,.255),'M_WoodLight' if i%3 else 'M_Wood'))
    if i<5:p.append(cube('BrokenSide',(.9,-2.7,z),(3.2,.16,.255),'M_Wood'))
    # The front door gap remains open and wide enough for the cat.
    for y in [-1.95,1.95]:p.append(cube('FrontWall',(-3.4,y,z),(.16,1.45,.255),'M_Wood'))
for y in [-.95,.95]:p.append(cube('DoorJamb',(-3.47,y,1.5),(.24,.19,3),'M_WoodDark'))
p.append(cube('DoorHeader',(-3.47,0,2.95),(.25,2.1,.2),'M_WoodDark'))
for x in [-3.4,-1.2,1.1,3.4]:
    for sign in [-1,1]:
        p.append(beam('RoofRafter',(x,sign*3.0,2.95),(x,0,4.6),.11,.1,'M_WoodDark',4))
p.append(cube('RidgeBeam',(0,0,4.55),(7.2,.20,.2),'M_WoodDark'))
for i in range(13):
    if i in [0,3,4,7,8]:continue
    x=-3.3+i*.54
    for sign in [-1,1]:
        if sign<0 and i<7:continue
        p.append(cube('RemainingRoof',(x,sign*1.45,3.79),(.48,3.48,.12),'M_Wood',(sign*.51,0,0)))
for i in range(14):
    p.append(cube('RubbleBoard',(R.uniform(-4.7,-3.6),R.uniform(-3.8,3.7),.08),(R.uniform(.7,2.2),.24,.13),'M_WoodDark',(R.uniform(-.1,.1),R.uniform(-.1,.1),R.uniform(-2,2))))
for x in [-3.55,3.55]:
    for y in [-2.65,-1.4,0,1.4,2.65]:p.append(ico('Foundation',(x,y,.12),(.43,.61,.27),'M_Stone',1))
LIB['SM_CabinRuin']=join_asset('SM_CabinRuin',p,'complex')

p=[beam('FallenLog',(-1.6,0,.22),(1.6,0,.26),.27,.23,'M_Bark',9),beam('Branch',(.1,0,.24),(.4,.8,.45),.1,.045,'M_BarkLight',6)]
LIB['SM_FallenLog']=join_asset('SM_FallenLog',p,'solid')

# Layout is authored in world metres, with an explicit Blender -> UE handedness conversion.
PATHS=[([(-48,-25),(-30,-23),(-12,-13),(-5,-10),(10,-15),(25,-22),(38,-10)],2.0),
       ([(-5,-10),(-7,-3),(-7,10),(-1,23),(8,35),(28,37),(39,23)],1.6),
       ([(-30,-23),(-29,-13),(-29,1),(-23,12),(-12,15),(-7,10)],1.25)]
PUDDLES=[(-20,-16,2.2,1.25),(-13,-29,1.65,1.0),(4,-28,2.0,1.3),(31,-7,2.3,1.4),(-35,15,1.5,1.15)]
def smooth(a,b,t):
    t=max(0,min(1,(t-a)/(b-a)));return t*t*(3-2*t)
def stream(x):return .6*x+8.5+1.9*math.sin(x/6.8)
def lake_r(x,y):return math.sqrt(((x-19)/15.1)**2+((y-20.7)/12.4)**2)
def base_height(x,y):
    h=.55+.26*math.sin(x/7.6)*math.cos(y/9.2)+.14*math.sin((x+y)/3.6)
    edge=max(0,min(1,(max(abs(x),abs(y))-30)/20));h+=edge*edge*2.1
    h+=1.10*math.exp(-(((x-24)/14)**2+((y+28)/12.5)**2))
    cut=1-smooth(.87,1.19,lake_r(x,y));h=h*(1-cut)-1.35*cut
    if x<13.5:
        width=1.58+.24*math.sin(x/4.3)
        cut=(1-smooth(width*.7,width+1.4,abs(y-stream(x))))*(1-smooth(8.5,13.5,x))
        h=h*(1-cut)-.94*cut
    # A gentle level pad keeps the cabin floor usable.
    pad=1-smooth(4.5,7.5,math.hypot(x-24,y+23))
    h=h*(1-pad)+1.50*pad
    return h
def terrain(x,y):
    h=base_height(x,y)
    for px,py,rx,ry in PUDDLES:
        d=math.sqrt(((x-px)/rx)**2+((y-py)/ry)**2)
        h-=.18*(1-smooth(.50,1.15,d))
    return h
def segdist(x,y,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)
def pathdist(x,y):
    return min(segdist(x,y,a,b)-w for points,w in PATHS for a,b in zip(points,points[1:]))
def clearing(x,y):return math.hypot((x+5)*.9,y+10)
def blocked(x,y,margin=0):
    return lake_r(x,y)<1.15+margin/15 or (x<13.5 and abs(y-stream(x))<3.0+margin)

placed=[]
def place(asset,x,y,z=None,scale=1,yaw=0,tilt=(0,0),group='Forest'):
    src=LIB[asset];o=bpy.data.objects.new(asset.replace('SM_','')+f'_{len(placed):04}',src.data)
    layout_col.objects.link(o);o['asset_id']=asset;o['collision']=src['collision'];o['group']=group
    o.location=(x,-y,terrain(x,y) if z is None else z)
    o.rotation_euler=(math.radians(tilt[0]),math.radians(-tilt[1]),math.radians(-yaw))
    o.scale=(scale,scale,scale) if isinstance(scale,(float,int)) else scale
    placed.append(o);return o

# Water meshes are unique assets but their transforms still come from this Blender scene.
verts,faces,weights=water_geometry('SM_LakeSurface')
water=mesh('LakeSurface',verts,faces,'M_Water');add_edge_mask(water.data,weights)
LIB['SM_LakeSurface']=join_asset('SM_LakeSurface',[water])
place('SM_LakeSurface',19,20.7,.10,group='Water')
verts,faces,weights=water_geometry('SM_StreamSurface')
river=mesh('StreamSurface',verts,faces,'M_Water');add_edge_mask(river.data,weights)
LIB['SM_StreamSurface']=join_asset('SM_StreamSurface',[river])
place('SM_StreamSurface',0,0,0,group='Water')
verts,faces,weights=water_geometry('SM_Puddle')
puddle=mesh('Puddle',verts,faces,'M_Water');add_edge_mask(puddle.data,weights)
LIB['SM_Puddle']=join_asset('SM_Puddle',[puddle])
for px,py,rx,ry in PUDDLES:place('SM_Puddle',px,py,base_height(px,py)-.045,scale=(rx,ry,1),group='Water/Puddles')

place('SM_BridgeIntact',-7,stream(-7),.87,group='Structures/IntactBridge')
place('SM_BridgeBroken',-29,stream(-29),.94,yaw=-8,group='Structures/CollapsedBridge')
place('SM_CabinRuin',24,-23,1.51,group='Structures/TimberRuin')

# Deliberate framing trees, followed by spaced woodland clusters.
tree_positions=[]
for x,y in [(-17,-21),(-18,-3),(-4,-21),(5,-4),(11,-29),(32,-31),(40,0),(-39,32),(-35,-5),(7,42),(33,42)]:
    if not blocked(x,y,2):
        place(f'SM_Oak_{R.randint(1,3):02}',x,y,scale=R.uniform(.9,1.18),yaw=R.uniform(-180,180));tree_positions.append((x,y))
for i in range(1800):
    if len(tree_positions)>=185:break
    x,y=R.uniform(-48,48),R.uniform(-48,48)
    if blocked(x,y,2.4) or pathdist(x,y)<2.6 or clearing(x,y)<10.5 or math.hypot(x-24,y+23)<8:continue
    if min((math.hypot(x-a,y-b) for a,b in tree_positions),default=999)<4.8:continue
    name=f'SM_{"Oak" if R.random()<.56 else "Fir"}_{R.randint(1,3):02}'
    place(name,x,y,scale=R.uniform(.72,1.25),yaw=R.uniform(-180,180));tree_positions.append((x,y))

# Shore boulders define the lake and stream without sealing off the crossing.
for i in range(42):
    a=i*math.tau/42;x=19+math.cos(a)*16.5;y=20.7+math.sin(a)*13.6
    if x<10 and abs(y-stream(x))<4:continue
    place(f'SM_MossRock_{R.randint(1,5):02}',x,y,z=terrain(x,y)-.18,scale=R.uniform(.45,.95),yaw=R.uniform(-180,180),tilt=(R.uniform(-12,12),R.uniform(-10,10)),group='Rocks/LakeShore')
for i in range(80):
    x=R.uniform(-48,10);y=stream(x)+R.choice([-1,1])*R.uniform(2.9,3.9)
    if abs(x+7)<1.6 or abs(x+29)<1.8:continue
    place(f'SM_MossRock_{R.randint(1,5):02}',x,y,z=terrain(x,y)-.18,scale=R.uniform(.35,.82),yaw=R.uniform(-180,180),tilt=(R.uniform(-15,15),R.uniform(-13,13)),group='Rocks/CreekBanks')
for i in range(65):
    x,y=R.uniform(-47,47),R.uniform(-47,47)
    if blocked(x,y,1) or pathdist(x,y)<.8 or clearing(x,y)<8 or math.hypot(x-24,y+23)<7:continue
    place(f'SM_MossRock_{R.randint(1,5):02}',x,y,z=terrain(x,y)-.20,scale=R.uniform(.45,1.25),yaw=R.uniform(-180,180),tilt=(R.uniform(-12,12),R.uniform(-12,12)),group='Rocks/Woodland')

for i in range(60):
    a=R.random()*math.tau;r=R.uniform(.80,.96);x=19+math.cos(a)*15.1*r;y=20.7+math.sin(a)*12.4*r
    place('SM_Lotus',x,y,.115,scale=R.uniform(.75,1.4),yaw=R.uniform(-180,180),group='Plants/Lotus')
for i in range(90):
    if i<65:
        a=R.random()*math.tau;x=19+math.cos(a)*15.1*R.uniform(1.00,1.08);y=20.7+math.sin(a)*12.4*R.uniform(1.00,1.08)
    else:
        x=R.uniform(-48,8);y=stream(x)+R.choice([-1,1])*R.uniform(1.7,2.5)
    place('SM_Reeds',x,y,min(.05,terrain(x,y)),scale=R.uniform(.7,1.15),yaw=R.uniform(-180,180),group='Plants/Reeds')

for i in range(1650):
    x,y=R.uniform(-49,49),R.uniform(-49,49)
    if blocked(x,y,-.1) or pathdist(x,y)<.1 or clearing(x,y)<5.8 or math.hypot(x-24,y+23)<5.5:continue
    if any(math.hypot((x-px)/rx,(y-py)/ry)<1.2 for px,py,rx,ry in PUDDLES):continue
    kind=R.choices(['Grass','Fern','Flowers','Shrub','Mushrooms'],weights=[45,20,18,12,5])[0]
    place('SM_'+kind,x,y,scale=R.uniform(.75,1.45),yaw=R.uniform(-180,180),group='Plants/'+kind)
for x,y in [(-26,-37),(15,-34),(38,5),(-12,30)]:place('SM_FallenLog',x,y,yaw=R.uniform(-180,180),group='Rocks/FallenLogs')

# Preview Landscape mesh and exact Unreal unsigned 16-bit heightmap.
verts=[];faces=[];height_u16=[]
for j in range(127):
    for i in range(127):
        x=-50.4+i*.8;y=-50.4+j*.8
        h=terrain(x,y);raw=max(0,min(65535,round(32768+h*128)))
        height_u16.append(raw);verts.append((x,-y,(raw-32768)/128))
for j in range(126):
    for i in range(126):
        k=j*127+i;faces.append((k,k+127,k+128,k+1))
ground=mesh('Landscape_Source_100m',verts,faces,'M_Ground')
for f in ground.data.polygons:f.use_smooth=True
attr=ground.data.color_attributes.new(name='TerrainTint',type='FLOAT_COLOR',domain='POINT')
green=MATS['M_Ground'].diffuse_color;path=MATS['M_Path'].diffuse_color
for i,v in enumerate(verts):
    x,y=v[0],-v[1];d=min(pathdist(x,y),clearing(x,y)-7.2)
    alpha=1-smooth(-.5,1.2,d);shore=1-smooth(.0,.50,abs(v[2]-.1))
    alpha=max(alpha,shore*.6)
    attr.data[i].color=tuple(green[c]*(1-alpha)+path[c]*alpha for c in range(3))+(1,)
mat=MATS['M_Ground'];nodes=mat.node_tree.nodes;attrnode=nodes.new('ShaderNodeVertexColor');attrnode.layer_name='TerrainTint'
mat.node_tree.links.new(attrnode.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color'])
with open(ART/'Layout'/'landscape_height.r16','wb') as f:f.write(struct.pack('<'+str(len(height_u16))+'H',*height_u16))

# Add a non-exported block cat to the Blender preview. Runtime parts animate in Unreal.
cat_parts=[]
for n,loc,dims,mat in [
 ('Body',(0,0,.78),(.34,.42,.52),'M_CatCream'),('Head',(.03,0,1.30),(.54,.62,.48),'M_CatCream'),
 ('OrangeHead',(.05,.17,1.43),(.53,.29,.24),'M_CatOrange'),('BlackHead',(-.11,-.19,1.45),(.30,.25,.20),'M_CatBlack'),
 ('Muzzle',(.33,0,1.19),(.12,.35,.20),'M_CatCream'),('Nose',(.40,0,1.24),(.03,.08,.05),'M_CatPink'),
 ('EyeL',(.31,-.16,1.32),(.03,.08,.10),'M_CatBlack'),('EyeR',(.33,.16,1.32),(.03,.08,.10),'M_CatBlack'),
 ('EarL',(.01,-.23,1.64),(.25,.18,.26),'M_CatBlack'),('EarR',(.01,.23,1.64),(.25,.18,.26),'M_CatOrange'),
 ('ArmL',(0,-.30,.79),(.17,.16,.34),'M_CatCream'),('ArmR',(0,.30,.79),(.17,.16,.34),'M_CatOrange'),
 ('LegL',(0,-.13,.30),(.18,.18,.42),'M_CatOrange'),('LegR',(0,.13,.30),(.18,.18,.42),'M_CatBlack'),
 ('PawL',(.05,-.13,.09),(.28,.20,.14),'M_CatCream'),('PawR',(.05,.13,.09),(.28,.20,.14),'M_CatCream'),
 ('Tail',(-.36,0,.65),(.35,.15,.15),'M_CatOrange')]:cat_parts.append(cube(n,loc,dims,mat))
LIB['SM_CalicoPreview']=join_asset('SM_CalicoPreview',cat_parts)
cat=place('SM_CalicoPreview',-6,-10,yaw=155,group='PreviewOnly')

# Export the actual Blender object transforms; Unreal never re-scatters these objects.
records=[]
for o in placed:
    e=o.rotation_euler
    records.append({'name':o.name,'asset':o['asset_id'],'group':o['group'],'collision':o['collision'],
        'blender_location_m':list(o.location),'blender_rotation_euler_rad':list(e),'scale':list(o.scale),
        'ue_location_cm':[o.location.x*100,-o.location.y*100,o.location.z*100],
        'ue_rotation_deg':{'pitch':-math.degrees(e.y),'yaw':-math.degrees(e.z),'roll':math.degrees(e.x)}})
data={'version':1,'seed':514,'units':'metres','ue_units':'centimetres','axis_mapping':'UE=(Blender.X,-Blender.Y,Blender.Z)',
      'terrain':{'samples':127,'spacing_cm':80,'extent_cm':10080,'origin_cm':[-5040,-5040,0],'height_scale':100,'file':'landscape_height.r16'},
      'paths':PATHS,'puddles':PUDDLES,'spawn_cm':[-600,-1000,terrain(-6,-10)*100+100],
      'palette_srgb_hex':PALETTE,'assets':{n:{'file':f'Meshes/{n}.fbx','collision':o['collision'],'materials':[s.name for s in o.data.materials],'dimensions_m':list(o.dimensions)} for n,o in LIB.items()},
      'objects':records,'lighting':{'directional_source_angle_degrees':50}}
(ART/'Layout'/'woodland_layout.json').write_text(json.dumps(data,indent=2),encoding='utf-8')

# Blender overview for layout QA, using the same broad 50-degree source angle.
bpy.ops.object.light_add(type='SUN',location=(-10,-30,40));sun=bpy.context.object;sun.name='Sun_SourceAngle50'
sun.rotation_euler=(math.radians(26),math.radians(-22),math.radians(-35));sun.data.energy=2.5;sun.data.angle=math.radians(50)
scene.world.color=(.22,.26,.32)
bpy.ops.object.camera_add(location=(-80,-3,105));cam=bpy.context.object;cam.name='OverviewCamera'
cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=118
scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(ART/'Previews'/'Blender_LayoutOverview.png')
scene.view_settings.view_transform='AgX'
assets_col.hide_render=True
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'AstraWoodland.blend'))
bpy.ops.render.render(write_still=True)
print(json.dumps({'assets':len(LIB),'layout_objects':len(records),'trees':len(tree_positions),'height_samples':len(height_u16),'blend':str(ART/'Blender'/'AstraWoodland.blend')}))

# Reproduce the later cottage/well addition whenever its independent assets exist.
if (ART/'Layout'/'pink_house_assets.json').exists() and (ART/'Blender'/'PinkHouseAssets.blend').exists():
    import runpy
    runpy.run_path(str(ROOT/'Scripts'/'place_pink_house_blender.py'),run_name='__main__')
