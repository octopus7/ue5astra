"""Assemble cave in Blender and export transforms, lights, terrain and route specification."""
import bpy, json, math, random, struct, sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts'))
import cave_layout as D
ART=ROOT/'ArtSource'; OUT=ART/'Layout/CrystalCave'; OUT.mkdir(parents=True,exist_ok=True)
R=random.Random(D.SEED)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC'
lib=bpy.data.collections.new('01_AssetLibrary');scene.collection.children.link(lib)
placement=bpy.data.collections.new('02_CavePlacement');scene.collection.children.link(placement)
assets={};materials={};sources={};objects=[];lights=[]
for kit,blend in [('rocks','CrystalCaveRocks.blend'),('crystals','CrystalCaveCrystals.blend')]:
    data=json.loads((OUT/f'{kit}_kit.json').read_text(encoding='utf-8'))
    assets.update(data['assets']);materials.update(data['materials'])
    names=list(data['assets'])
    with bpy.data.libraries.load(str(ART/'Blender'/blend),link=False) as (s,t):
        t.objects=list(names)
    for name,obj in zip(names,t.objects):
        assert obj is not None,name
        lib.objects.link(obj);obj.hide_render=True;obj.hide_set(True);sources[name]=obj

def place(asset,x,y,z=None,scale=1,yaw=0,group='Rocks',tags=None,collision=None):
    if z is None:z=D.height(x,y)-.08
    if isinstance(scale,(int,float)):scale=[scale]*3
    name=f'CC_{asset.removeprefix("SM_CC_")}_{len(objects):03d}'
    ob=bpy.data.objects.new(name,sources[asset].data);placement.objects.link(ob)
    ob.location=(x,-y,z);ob.rotation_euler.z=math.radians(-yaw);ob.scale=scale
    ob['asset_id']=asset;ob['group']=group
    objects.append(dict(name=name,asset=asset,group=group,tags=tags or [],collision=collision or assets[asset].get('collision','complex'),
        ue_location_cm=[round(x*100,4),round(y*100,4),round(z*100,4)],ue_rotation_deg=dict(pitch=0,yaw=yaw,roll=0),scale=list(scale)))
    return ob

def crystal(x,y,kind='Cyan',scale=1,z=None,power=1800,radius=650):
    ob=place('SM_CC_Crystal'+kind,x,y,z,scale,R.uniform(-180,180),'Crystals',collision='complex' if scale>.65 else 'none')
    if power:
        z=ob.location.z+(.85 if kind=='Violet' else 1.2)*scale
        rgb=[.13,.77,1] if kind!='Violet' else [.63,.28,1]
        l=dict(name=ob.name+'_Light',ue_location_cm=[x*100,y*100,z*100],color=rgb,intensity=power,radius_cm=radius,source_radius_cm=70*scale)
        lights.append(l)
        data=bpy.data.lights.new(l['name'],'POINT');data.energy=power/5;data.color=rgb;data.shadow_soft_size=.6*scale
        lo=bpy.data.objects.new(l['name'],data);scene.collection.objects.link(lo);lo.location=(x,-y,z)

# Tall rear perimeter, low foreground cutaway. Modules overlap so no walkable cracks remain.
for side in [-1,1]:
    for i in range(15):
        y=-21.5+i*3.08;x=side*(D.half_width(y)+.25)
        name='SM_CC_RockWallLow' if side<0 else 'SM_CC_RockWall_'+['A','B','C'][i%3]
        place(name,x,y,scale=[R.uniform(.90,1.1),R.uniform(.96,1.10),R.uniform(.86,1.15)],yaw=90+R.uniform(-10,10),group='Architecture/Perimeter',tags=['CaveBoundary'])
        # Exterior shoulder: preserve modeled cut top, lower near camera.
        if i%2==0:
            place('SM_CC_RockWall_'+['B','C','A'][i%3],x+side*2.1,y+.4,z=D.height(x,y)-.4,
                scale=[1.2,1.05,.6 if side<0 else 1.35],yaw=90+R.uniform(-12,12),group='Architecture/OuterCrags',tags=['CaveBoundary'])
for y in [-23.7,23.7]:
    for i,x in enumerate([-7.6,-4,0,4,7.6]):
        if y<0 and x==0:continue
        place('SM_CC_RockWall_'+['A','B','C'][i%3],x,y,scale=[1.1,1,.65 if x<0 else 1.1],yaw=R.uniform(-9,9),group='Architecture/EndWalls',tags=['CaveBoundary'])
# Entrance roof fragment is outside the active route; other ceiling is cut away.
place('SM_CC_Portal',0,-23.2,scale=1,yaw=0,group='Architecture/Entrance',tags=['CaveBoundary'])
for i,(x,y) in enumerate(D.ISLANDS):
    place('SM_CC_RockIsland_'+('A' if i==0 else 'B'),x,y,group='Architecture/ForkIslands',tags=['CaveIsland'])
    crystal(.3,y-.3,'Cyan' if i==0 else 'Violet',scale=.85,z=D.height(x,y)+1.52,power=2200,radius=740)

# Large chamber landmark rests beyond the thoroughfare and leaves endpoint clear.
crystal(4.3,20,'Heart',scale=1,power=5000,radius=1050)
for x,y,k,s,p in [
    (3.8,-20,'Cyan',1,2200),(-4.7,-22,'Cyan',.62,900),
    (7.9,-13,'Cyan',.75,1500),(-7.8,-11.5,'Cyan',.85,1600),
    (7.9,-6,'Cyan',.65,1300),(-7.8,-4.3,'Cyan',.60,1300),
    (4.8,-.9,'Cyan',.9,1900),(-5.7,.1,'Violet',.8,1900),
    (7.8,5,'Violet',.85,1800),(-7.9,5.5,'Violet',.80,1800),
    (7.6,11,'Violet',.7,1500),(-7.8,12.2,'Violet',.9,1800),
    (-5.5,18,'Cyan',1,2500),(1,23,'Cyan',.8,1900),(-7,22,'Cyan',.55,900)]:
    crystal(x,y,k,s,power=p,radius=650 if k=='Cyan' else 620)

# Small edge shards and rubble are excluded from every validated walking ribbon.
for i in range(105):
    y=R.uniform(-22,23);side=R.choice([-1,1]);x=side*R.uniform(6.8,D.half_width(y)-.2)
    if D.route_distance(x,y)<1.45:continue
    if any(math.hypot(x-l['ue_location_cm'][0]/100,y-l['ue_location_cm'][1]/100)<1 for l in lights):continue
    if i%3==0:place('SM_CC_CrystalShards',x,y,scale=R.uniform(.6,1.3),yaw=R.uniform(0,360),group='Details/Shards',collision='none')
    else:place('SM_CC_RockRubble',x,y,scale=R.uniform(.35,.9),yaw=R.uniform(0,360),group='Details/Rubble',collision='none')

# Real source terrain: UE rectangular component grid, Blender Y flipped.
verts=[];faces=[];heights=[]
for iy in range(64):
    y=-25+iy*50/63
    for ix in range(127):
        x=-15+ix*30/126;z=D.height(x,y);verts.append((x,-y,z));heights.append(round(32768+z*128))
for iy in range(63):
    for ix in range(126):
        a=iy*127+ix;faces.append((a,a+127,a+128,a+1))
mesh=bpy.data.meshes.new('CaveLandscapeGrid');mesh.from_pydata(verts,[],faces);mesh.update()
land=bpy.data.objects.new('Landscape_Source_50x30m',mesh);scene.collection.objects.link(land)
m=bpy.data.materials.new('Preview_CC_Floor');m.use_nodes=True
bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.055,.064,.1,1);bs.inputs['Roughness'].default_value=.86
mesh.materials.append(m)
(OUT/'cave_height.r16').write_bytes(struct.pack('<'+'H'*len(heights),*heights))
(OUT/'cave_routes.json').write_text(json.dumps(D.routes_json(),indent=2),encoding='utf-8')
data=dict(schema_version=1,seed=D.SEED,map='/Game/Astra/Maps/L_AstraCrystalCave',dimensions_m=[30,50],
    axis_mapping='Blender (x,y,z) m -> Unreal (x,-y,z)*100 cm; yaw=-Blender Z degrees',
    landscape=dict(samples=[127,64],origin_cm=[-1500,-2500,0],scale=[3000/126,5000/63,100],file='ArtSource/Layout/CrystalCave/cave_height.r16'),
    assets=assets,materials=materials,objects=objects,lights=lights,spawn_cm=[0,-2100,D.height(0,-21)*100+100],
    cutaway='Low foreground perimeter; no roof over traversable interior; only entrance lintel outside entry spawn.',
    review_cameras=[dict(name='CaveOverview',look=[0,0,70],width=6000),dict(name='CaveFork1',look=[0,-900,100],width=2600),
      dict(name='CaveFork2',look=[0,800,100],width=2600),dict(name='CaveHeart',look=[260,1970,130],width=2000)])
(OUT/'cave_layout.json').write_text(json.dumps(data,indent=2),encoding='utf-8')

world=bpy.data.worlds.new('CavePreviewWorld') if not scene.world else scene.world;scene.world=world;world.use_nodes=True
world.node_tree.nodes.get('Background').inputs[0].default_value=(.025,.03,.055,1);world.node_tree.nodes.get('Background').inputs[1].default_value=.25
ld=bpy.data.lights.new('PreviewSoftFill','AREA');ld.energy=1300;ld.shape='DISK';ld.size=35
lo=bpy.data.objects.new('PreviewSoftFill',ld);scene.collection.objects.link(lo);lo.location=(-6,0,20)
camd=bpy.data.cameras.new('CaveOverview');cam=bpy.data.objects.new('CaveOverview',camd);scene.collection.objects.link(cam)
cam.location=(-36,0,57);target=Vector((0,0,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
camd.type='ORTHO';camd.ortho_scale=58;scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraCrystalCave.blend'))
scene.render.filepath=str(ART/'Previews/CrystalCave/Blender_CaveOverview.png');bpy.ops.render.render(write_still=True)
print('CRYSTAL CAVE LAYOUT COMPLETE',len(objects),'objects',len(lights),'lights')
