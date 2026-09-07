"""Assemble the complete belltower level in Blender and export exact placement."""
import bpy,json,math,random,struct,sys
from collections import Counter
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource';sys.path.insert(0,str(ROOT/'Scripts'))
import rootbelltower_layout as d
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.unit_settings.system='METRIC'
library=bpy.data.collections.new('01_MeshLibrary');scene.collection.children.link(library)
layout=bpy.data.collections.new('02_RootBelltowerPlacement');scene.collection.children.link(layout)
assets={};materials={};sources={};objects=[];rng=random.Random(d.SEED)
def append(file,names):
    with bpy.data.libraries.load(str(ART/'Blender'/file),link=False) as (a,b):
        assert set(names)<=set(a.objects);b.objects=list(names)
    for name,obj in zip(names,b.objects):
        library.objects.link(obj);obj.hide_render=True;obj.hide_set(True);sources[name]=obj
old=json.loads((ART/'Layout/woodland_layout.json').read_text())
reuse=[f'SM_{tree}_{i:02}' for tree in ('Oak','Fir') for i in range(1,4)]+[f'SM_MossRock_{i:02}' for i in range(1,6)]+['SM_Grass','SM_Fern','SM_Flowers','SM_Shrub']
append('AstraWoodland.blend',reuse)
for name in reuse:assets[name]=dict(old['assets'][name],file='ArtSource/'+old['assets'][name]['file'],unreal_asset_path='/Game/Astra/Meshes/'+name,reuse_existing=True)
kits={}
for kit in ('architecture','roots'):
    data=json.loads((ART/f'Layout/rootbelltower_{kit}.json').read_text());kits[kit]=data
    names=[a['asset_id'] for a in data['assets']];append(Path(data['source']).name,names);materials.update(data['materials'])
    for info in data['assets']:assets[info['asset_id']]=dict(info,unreal_asset_path='/Game/Astra/Meshes/RootBelltower/'+info['asset_id'],reuse_existing=False)
def place(asset,x,y,z=None,scale=1,yaw=0,pitch=0,group='Forest',foliage=False,collision=None,movable=False,label=None):
    z=d.height(x,y)-.025 if z is None else z;scale=[scale]*3 if isinstance(scale,(int,float)) else scale
    name=label or f'RB_{asset.removeprefix("SM_")}_{len(objects):04}'
    obj=bpy.data.objects.new(name,sources[asset].data);layout.objects.link(obj)
    obj.matrix_world=Matrix.Translation((x,-y,z)) @ Matrix.Rotation(math.radians(-yaw),4,'Z') @ Matrix.Rotation(math.radians(pitch),4,'Y') @ Matrix.Diagonal((*scale,1))
    obj['asset_id']=asset;obj['native_ue_foliage']=foliage
    objects.append(dict(name=name,asset=asset,group=group,collision=collision or assets[asset].get('collision','none'),
        ue_location_cm=[round(x*100,4),round(y*100,4),round(z*100,4)],ue_rotation_deg=dict(pitch=pitch,yaw=yaw,roll=0),scale=scale,foliage=foliage,movable=movable))
    return obj
tower_z=d.height(*d.TOWER)
place('SM_RB_Tower',*d.TOWER,z=tower_z,yaw=90,group='Landmark',label='RB_Tower')
place('SM_RB_AncientTree',*d.TREE,z=tower_z,yaw=90,group='Landmark',label='RB_AncientTree')
place('SM_RB_GrippingRoots',*d.TOWER,z=tower_z,yaw=90,group='Landmark',label='RB_GrippingRoots')
# Bell suspension follows the tower's baked lean; source (x,y,z) rotates into UE (y,x,z) at yaw90.
pivot=kits['architecture']['bell_pivot_m']
bell=[d.TOWER[0]+pivot[1],d.TOWER[1]+pivot[0],tower_z+pivot[2]]
place('SM_RB_Bell',bell[0],bell[1],z=bell[2],yaw=90,pitch=7,group='Landmark',collision='none',movable=True,label='RB_Bell')
place('SM_RB_Courtyard',*d.COURTYARD,z=d.height(*d.COURTYARD),yaw=15,group='Courtyard',label='RB_Courtyard')
place('SM_RB_RootArch',*d.ARCH,z=d.height(*d.ARCH),yaw=90,group='RootPassage',label='RB_RootArch')
place('SM_RB_CloisterArch',*d.CLOISTER,z=d.height(*d.CLOISTER),group='Cloister',label='RB_CloisterArch')
for x,y,yaw,s in [(-8,14,10,.8),(-18,12,-8,.62),(3,21,70,.7)]:
    place('SM_RB_FallenCapital',x,y,yaw=yaw,scale=s,group='Cloister')
for x,y,yaw,s in [(9,-9,15,1),(-17,-17,130,.72),(18,15,70,.8),(1,24,20,.8)]:
    place('SM_RB_CrawlingRoot',x,y,yaw=yaw,scale=s,group='RootGarden')
for i in range(52):
    x,y=rng.choice([(d.ARCH[0],d.ARCH[1]-4),(d.TREE[0],7),(-9,15),(15,-7),(5,22)])
    x+=rng.uniform(-2.5,2.5);y+=rng.uniform(-1.5,1.5)
    if d.demo_distance(x,y)<.85:continue
    place('SM_RB_GlowMushrooms',x,y,scale=rng.uniform(.65,1.2),yaw=rng.uniform(0,360),foliage=True,group='SapGarden')
for x,y,z,yaw,s in [(7,-3.9,8.5,90,1),(6,4,7,90,.8),(12,-3,11,40,1.2),(-3,-16.8,3.4,0,.65)]:
    place('SM_RB_MossPendant',x,y,z=z,scale=s,yaw=yaw,group='HangingMoss')
trees=[]
for ix in range(25):
    for iy in range(25):
        x=-48+ix*4+rng.uniform(-1.2,1.2);y=-48+iy*4+rng.uniform(-1.2,1.2)
        if d.reserved(x,y,1):continue
        if x<-9 and abs(y)<20 and rng.random()<.82:continue
        if any(math.hypot(x-a,y-b)<3.1 for a,b in trees):continue
        if max(abs(x),abs(y))<36 and rng.random()<.28:continue
        kind='Oak' if rng.random()<.75 else 'Fir'
        place(f'SM_{kind}_{rng.randint(1,3):02}',x,y,scale=rng.uniform(.82,1.16),yaw=rng.uniform(0,360),group='ForestCanopy')
        trees.append((x,y))
for i in range(4100):
    if i<2800:
        a,b=rng.choice(trees);x=a+rng.uniform(-2.4,2.4);y=b+rng.uniform(-2.4,2.4)
    else:x=rng.uniform(-49,49);y=rng.uniform(-49,49)
    if max(abs(x),abs(y))>49 or d.path_distance(x,y)<1.55 or d.demo_distance(x,y)<.95:continue
    if -14<x<19 and abs(y)<9:continue
    if math.hypot(x-d.ARCH[0],y-d.ARCH[1])<3.6 or math.hypot(x-d.CLOISTER[0],y-d.CLOISTER[1])<3.2:continue
    name=rng.choices(['SM_Grass','SM_Fern','SM_Flowers'],[.47,.45,.08])[0]
    place(name,x,y,scale=rng.uniform(.55,1),yaw=rng.uniform(0,360),foliage=True,group='ForestFloor')
for i in range(45):
    x=rng.uniform(-46,46);y=rng.uniform(-46,46)
    if d.reserved(x,y,.45):continue
    place(f'SM_MossRock_{rng.randint(1,5):02}',x,y,scale=rng.uniform(.25,.65),yaw=rng.uniform(0,360),group='ForestRocks')
vertices=[];heights=[];faces=[];colors=[]
for iy in range(127):
    y=-50.4+iy*.8
    for ix in range(127):
        x=-50.4+ix*.8;h=d.height(x,y);vertices.append((x,-y,h));heights.append(round(32768+h*128))
        trail=1-d.smooth(1.2,2.1,d.path_distance(x,y));plaza=1-d.smooth(5.8,8,math.hypot(x+6,y));f=max(trail,plaza)
        colors.append(tuple(a*(1-f)+b*f for a,b in zip((.15,.25,.11),(.43,.36,.24))))
for y in range(126):
    for x in range(126):
        a=y*127+x;faces.append((a,a+127,a+128,a+1))
(ART/'Layout/rootbelltower_height.r16').write_bytes(struct.pack('<16129H',*heights))
mesh=bpy.data.meshes.new('RootBelltowerLandscape');mesh.from_pydata(vertices,[],faces);mesh.update()
color=mesh.color_attributes.new(name='TerrainPreview',type='FLOAT_COLOR',domain='POINT')
for c,v in zip(color.data,colors):c.color=(*v,1)
obj=bpy.data.objects.new('LandscapePreview_100m_RootBelltower',mesh);layout.objects.link(obj)
mat=bpy.data.materials.new('PreviewOnlyRootBelltowerGround');mat.use_nodes=True
attr=mat.node_tree.nodes.new('ShaderNodeVertexColor');attr.layer_name='TerrainPreview';bs=mat.node_tree.nodes['Principled BSDF'];mat.node_tree.links.new(attr.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.9;mesh.materials.append(mat)
code=['float2 p=Pos.xy*.01;float d=10000.;float2 a,b,q;']
for path in d.PATHS:
    for a,b in zip(path,path[1:]):code.append(f'a=float2({a[0]},{a[1]});b=float2({b[0]},{b[1]});q=b-a;d=min(d,length(p-a-q*saturate(dot(p-a,q)/dot(q,q))));')
code+=['float n=sin(p.x*2.4+sin(p.y*1.7))*.4+sin(p.y*3.1-p.x)*.2;',
 'float trail=1-smoothstep(1.2,2.1,d+n*.12);float plaza=1-smoothstep(5.8,8.,length(p-float2(-6,0)));',
 'float grain=dot(Tex.rgb,float3(.25,.55,.2));float3 grass=Tex.rgb*float3(.64,.88,.70);',
 'float3 path=float3(.31,.25,.16)*(.9+grain*.85+n*.018);return lerp(grass,path,max(trail,plaza));']
(ART/'Layout/rootbelltower_ground.hlsl').write_text('\n'.join(code)+'\n')
cameras=[dict(name='RBOverview',look_cm=[0,0,500],width=11200,pitch=-60,yaw=0),
 dict(name='RBTower',look_cm=[550,0,1000],width=4200,pitch=-38,yaw=15,arm=3000,near_clip_cm=10),
 dict(name='RBBell',look_cm=[bell[0]*100,bell[1]*100,bell[2]*100-80],width=1350,pitch=-24,yaw=6,arm=1050,near_clip_cm=10),
 dict(name='RBRoots',look_cm=[300,0,530],width=2900,pitch=-39,yaw=-22,arm=2500,near_clip_cm=10),
 dict(name='RBArch',look_cm=[-300,-1400,310],width=1800,pitch=-34,yaw=12,arm=3000,near_clip_cm=10),
 dict(name='RBCloister',look_cm=[-1300,1200,330],width=1800,pitch=-43,yaw=-90,arm=3000,near_clip_cm=10),
 dict(name='RBTowerLater',look_cm=[550,0,1000],width=4200,pitch=-38,yaw=15,arm=3000,near_clip_cm=10)]
data=dict(version=1,seed=d.SEED,map=d.MAP,source='ArtSource/Blender/AstraRootBelltower.blend',units='metres, exported transforms centimetres',
    assets=assets,materials=materials,objects=objects,terrain_file='ArtSource/Layout/rootbelltower_height.r16',terrain=dict(samples=127,spacing_cm=80,extent_cm=10080),
    spawn_cm=[-2500,-200,d.height(-25,-2)*100+100],paths=d.PATHS,demo_shots=d.DEMO,review_cameras=cameras,
    resonance_center_cm=[-600,0,170],bell_label='RB_Bell',lights=[dict(name='RB_SapLight_1',ue_location_cm=[200,-310,470],intensity=180,radius=550,color=[.12,.8,.64]),dict(name='RB_BellLight',ue_location_cm=[bell[0]*100-170,bell[1]*100,bell[2]*100-120],intensity=1800,radius=650,color=[1,.71,.35])])
(ART/'Layout/rootbelltower_layout.json').write_text(json.dumps(data,indent=2)+'\n')
report=dict(passed=True,placements=len(objects),native_foliage=sum(o['foliage'] for o in objects),new_assets=sum(not a['reuse_existing'] for a in assets.values()),by_group=dict(Counter(o['group'] for o in objects)),landscape_samples=len(heights),bell_world_pivot_cm=[c*100 for c in bell])
(ART/'Previews/RootBelltowerLayout_Validation.json').write_text(json.dumps(report,indent=2)+'\n')
scene.world=bpy.data.worlds.new('PreviewOnlyBelltowerSky');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.55,.7,.86,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55
bpy.ops.object.light_add(type='SUN',location=(-30,-20,50));sun=bpy.context.object;sun.rotation_euler=(.4,-.5,-.5);sun.data.energy=2;sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-55,18,50));camera=bpy.context.object;camera.rotation_euler=(Vector((4,0,7))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=57;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.render.filepath=str(ART/'Previews/Blender_RootBelltowerOverview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraRootBelltower.blend'));bpy.ops.render.render(write_still=True)
print('ROOT_BELLTOWER_LAYOUT_COMPLETE '+json.dumps(report),flush=True)
