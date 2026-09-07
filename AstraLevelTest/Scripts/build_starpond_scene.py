"""Assemble authored prop libraries in Blender and export exact UE transforms."""
import bpy
import json
import math
import random
import struct
import sys
from collections import Counter
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
sys.path.insert(0,str(ROOT/'Scripts'))
import starpond_layout as d
from water_geometry import add_edge_mask

bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.unit_settings.system='METRIC'
library=bpy.data.collections.new('01_MeshLibrary');scene.collection.children.link(library)
layout=bpy.data.collections.new('02_StarPondPlacement');scene.collection.children.link(layout)
assets={};materials={};sources={};objects=[];rng=random.Random(d.SEED)

def append(filename,names):
    with bpy.data.libraries.load(str(ART/'Blender'/filename),link=False) as (a,b):
        assert set(names)<=set(a.objects),set(names)-set(a.objects)
        b.objects=list(names)
    for name,obj in zip(names,b.objects):
        library.objects.link(obj);obj.hide_render=True;obj.hide_set(True);sources[name]=obj

old=json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'))
reuse=[f'SM_{tree}_{i:02}' for tree in ('Oak','Fir') for i in range(1,4)]
reuse += [f'SM_MossRock_{i:02}' for i in range(1,6)]
reuse += ['SM_Grass','SM_Fern','SM_Flowers','SM_Reeds','SM_Shrub']
append('AstraWoodland.blend',reuse)
for name in reuse:
    assets[name]=dict(old['assets'][name],file='ArtSource/'+old['assets'][name]['file'],unreal_asset_path='/Game/Astra/Meshes/'+name,reuse_existing=True)
for kit in ('ruins','botany'):
    data=json.loads((ART/f'Layout/starpond_{kit}.json').read_text(encoding='utf-8'))
    names=[a['asset_id'] for a in data['assets']]
    append(Path(data['source']).name,names);materials.update(data['materials'])
    for a in data['assets']:
        assets[a['asset_id']]=dict(a,unreal_asset_path='/Game/Astra/Meshes/StarPond/'+a['asset_id'],reuse_existing=False)

def place(asset,x,y,z=None,scale=1,yaw=0,group='Forest',foliage=False,collision=None,**extra):
    z=d.height(x,y)-.025 if z is None else z
    scale=[scale]*3 if isinstance(scale,(int,float)) else scale
    name=f'SP_{asset.removeprefix("SM_")}_{len(objects):04}'
    obj=bpy.data.objects.new(name,sources[asset].data);layout.objects.link(obj)
    obj.location=(x,-y,z);obj.rotation_euler.z=math.radians(-yaw);obj.scale=scale
    obj['asset_id']=asset;obj['group']=group;obj['native_ue_foliage']=foliage
    objects.append(dict(name=name,asset=asset,group=group,collision=collision or assets[asset].get('collision','none'),
        ue_location_cm=[round(x*100,4),round(y*100,4),round(z*100,4)],
        ue_rotation_deg={'pitch':0,'yaw':yaw,'roll':0},scale=list(scale),foliage=foliage,**extra))
    return obj

# One basin-matched mesh. Vertex red fades the thin irregular perimeter.
n=192;verts=[(0,0,0)];faces=[];weights=[1.]
for radius,weight in ((.55,1),(.82,1),(.93,1),(.97,.5),(1,0)):
    for i in range(n):
        a=i*math.tau/n;r=d.rim(a)*radius
        verts.append((d.RX*math.cos(a)*r,-d.RY*math.sin(a)*r,0));weights.append(weight)
for i in range(n):
    j=(i+1)%n;faces.append((0,1+j,1+i))
    for ring in range(4):
        a=1+ring*n;b=a+n
        faces.extend([(a+i,a+j,b+j),(a+i,b+j,b+i)])
mesh=bpy.data.meshes.new('StarPondSurface');mesh.from_pydata(verts,[],faces);mesh.update();add_edge_mask(mesh,weights)
uv=mesh.uv_layers.new(name='UVMap')
for poly in mesh.polygons:
    for li in poly.loop_indices:
        v=mesh.vertices[mesh.loops[li].vertex_index].co;uv.data[li].uv=(v.x/(d.RX*2)+.5,v.y/(d.RY*2)+.5)
mat=bpy.data.materials.new('M_SP_StarWater');mat.use_nodes=True
bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.005,.018,.055,1)
bs.inputs['Roughness'].default_value=.13;bs.inputs['Metallic'].default_value=.1
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ART/'Textures/StarPond/T_SP_SubmergedStars.png'));tex.image.pack()
mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=1.7
mesh.materials.append(mat)
obj=bpy.data.objects.new('SM_SP_StarPondSurface',mesh);library.objects.link(obj)
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
file='ArtSource/Meshes/StarPond/SM_SP_StarPondSurface.fbx'
bpy.ops.export_scene.fbx(filepath=str(ROOT/file),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,
    mesh_smooth_type='FACE',path_mode='STRIP',use_tspace=True)
obj.hide_render=True;obj.hide_set(True);sources[obj.name]=obj
assets[obj.name]=dict(file=file,materials=['M_SP_StarWater'],dimensions_m=[max(v[0] for v in verts)-min(v[0] for v in verts),max(v[1] for v in verts)-min(v[1] for v in verts),0],
    triangles=len(faces),collision='none',unreal_asset_path='/Game/Astra/Meshes/StarPond/'+obj.name,reuse_existing=False)
place(obj.name,0,0,z=d.WATER_Z,group='SunkenStars',material_override='/Game/Astra/Materials/StarPond/M_SP_StarWater')
place('SM_SP_ViewingDais',*d.DAIS,z=1.18,yaw=90,group='Observatory')
place('SM_SP_CrescentGate',d.GATE[0],d.GATE[1]-.65,z=1.18,yaw=90,group='MoonGate')
for i,(x,y,yaw) in enumerate([(-10,-17,140),(8,-17,10),(-10,17,210),(9,17,70),(29,-3.6,110),(32,3.8,30)]):
    place(f'SM_SP_StarMenhir_{i%2+1:02}',x,y,yaw=yaw,scale=rng.uniform(.85,1.13),group='StarMarkers')
for x,y,yaw,s in [(5,-25,-20,1),(22,-12,30,.9),(22,12,140,.85),(-7,29,80,.85)]:
    place('SM_SP_OldWillow',x,y,scale=s,yaw=yaw,group='WillowGrove')

# Star-lilies arranged in bays, keeping the constellation readable.
for i in range(29):
    a=rng.choice([-.95,.78,2.35,3.7])+rng.uniform(-.24,.24)
    r=rng.uniform(.78,.94)*d.rim(a);x=d.RX*math.cos(a)*r;y=d.RY*math.sin(a)*r
    place(f'SM_SP_StarLily_{i%2+1:02}',x,y,z=d.WATER_Z+.025,scale=rng.uniform(.68,1.05),yaw=rng.uniform(0,360),group='SilverLilies',foliage=True)
for i in range(112):
    a=i*math.tau/112+rng.uniform(-.04,.04);r=d.rim(a)*rng.uniform(1.045,1.13)
    x=d.RX*math.cos(a)*r;y=d.RY*math.sin(a)*r
    if abs(y)<2.6 and x<0:continue
    if i%3==0:
        place(f'SM_MossRock_{i%5+1:02}',x,y,scale=rng.uniform(.16,.37),yaw=rng.uniform(0,360),group='PondBank')
    else:
        place('SM_Reeds' if i%4==0 else 'SM_SP_StarFlowers',x,y,scale=rng.uniform(.6,1.05),yaw=rng.uniform(0,360),group='PondBank',foliage=True)

trees=[]
for ix in range(25):
    for iy in range(25):
        x=-48+ix*4+rng.uniform(-1.3,1.3);y=-48+iy*4+rng.uniform(-1.3,1.3)
        if d.reserved(x,y,.9):continue
        # Open the near foreground for fixed top-down visibility.
        if x<-18 and abs(y)<15:continue
        if any(math.hypot(x-a,y-b)<3.15 for a,b in trees):continue
        if max(abs(x),abs(y))<35 and rng.random()<.23:continue
        tree='Oak' if rng.random()<.64 else 'Fir';s=rng.uniform(.8,1.18)
        place(f'SM_{tree}_{rng.randint(1,3):02}',x,y,scale=s,yaw=rng.uniform(0,360),group='ForestCanopy')
        trees.append((x,y))
for i in range(4800):
    if i<3100:
        tx,ty=rng.choice(trees);a=rng.uniform(0,math.tau);r=rng.uniform(.6,3)
        x=tx+math.cos(a)*r;y=ty+math.sin(a)*r
    else:x=rng.uniform(-49,49);y=rng.uniform(-49,49)
    if max(abs(x),abs(y))>49 or d.path_distance(x,y)<1.55 or d.demo_distance(x,y)<.95:continue
    if d.pond_distance(x,y)<1.14:continue
    if any(math.hypot(x-c[0],y-c[1])<r for c,r in [(d.DAIS,3.4),(d.GATE,3.8),(d.ELEPHANT,2.8)]):continue
    if d.pond_distance(x,y)<1.55 and rng.random()<.60:continue
    asset=rng.choices(['SM_Grass','SM_Fern','SM_Flowers','SM_SP_StarFlowers'],[.54,.27,.10,.09])[0]
    place(asset,x,y,scale=rng.uniform(.55,1),yaw=rng.uniform(0,360),foliage=True,group='ForestUnderstory')
for i in range(56):
    x=rng.uniform(-46,46);y=rng.uniform(-46,46)
    if d.reserved(x,y,.5):continue
    place(f'SM_MossRock_{rng.randint(1,5):02}',x,y,scale=rng.uniform(.3,.65),yaw=rng.uniform(0,360),group='ForestRocks')

# Native Landscape heightmap and a Blender preview of exactly those samples.
verts=[];heights=[];faces=[];colors=[]
for iy in range(127):
    y=-50.4+iy*.8
    for ix in range(127):
        x=-50.4+ix*.8;h=d.height(x,y);heights.append(round(32768+h*128));verts.append((x,-y,h))
        dry=1-d.smooth(1.15,2.05,d.path_distance(x,y));bank=1-d.smooth(1.04,1.23,d.pond_distance(x,y))
        f=max(dry,bank);colors.append(tuple(a*(1-f)+b*f for a,b in zip((.20,.32,.085),(.50,.39,.20))))
for y in range(126):
    for x in range(126):
        a=y*127+x;faces.append((a,a+127,a+128,a+1))
(ART/'Layout/starpond_height.r16').write_bytes(struct.pack('<16129H',*heights))
mesh=bpy.data.meshes.new('StarPondLandscape');mesh.from_pydata(verts,[],faces);mesh.update()
color=mesh.color_attributes.new(name='TerrainPreview',type='FLOAT_COLOR',domain='POINT')
for c,v in zip(color.data,colors):c.color=(*v,1)
obj=bpy.data.objects.new('LandscapePreview_100m_StarPond',mesh);layout.objects.link(obj)
mat=bpy.data.materials.new('PreviewOnly_StarPondGround');mat.use_nodes=True
attr=mat.node_tree.nodes.new('ShaderNodeVertexColor');attr.layer_name='TerrainPreview'
bs=mat.node_tree.nodes.get('Principled BSDF');mat.node_tree.links.new(attr.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.9;mesh.materials.append(mat)

code=['float2 p=Pos.xy*.01;float d=10000.;float2 a,b,q;']
for path in d.PATHS:
    for a,b in zip(path,path[1:]):
        code.append(f'a=float2({a[0]:.5f},{a[1]:.5f});b=float2({b[0]:.5f},{b[1]:.5f});q=b-a;d=min(d,length(p-a-q*saturate(dot(p-a,q)/dot(q,q))));')
code += ['float n=sin(p.x*2.4+sin(p.y*1.7))*.4+sin(p.y*3.1-p.x)*.2;',
 'float dry=1-smoothstep(1.12,2.05,d+n*.12);float2 v=p/float2(12.,14.5);float t=atan2(v.y,v.x);',
 'float r=length(v)/(1+.042*sin(3*t+.4)+.024*sin(7*t));float bank=1-smoothstep(1.04,1.24,r);',
 'float grain=dot(Tex.rgb,float3(.25,.55,.2));float3 grass=Tex.rgb*float3(.84,1.04,.95);',
 'float3 trail=float3(.46,.34,.17)*(.88+grain*.85+n*.018);return lerp(grass,trail,max(dry,bank));']
(ART/'Layout/starpond_ground.hlsl').write_text('\n'.join(code)+'\n',encoding='utf-8')
cameras=[
 dict(name='SPOverview',look_cm=[0,0,210],width=11600,pitch=-60,yaw=0),
 dict(name='SPPond',look_cm=[0,0,180],width=5100,pitch=-57,yaw=0),
 dict(name='SPConstellation',look_cm=[0,0,100],width=3400,pitch=-67,yaw=0),
 dict(name='SPGate',look_cm=[1780,0,430],width=2000,pitch=-42,yaw=0),
 dict(name='SPLilies',look_cm=[-750,-950,100],width=1700,pitch=-53,yaw=0),
 dict(name='SPElephant',look_cm=[-100,2300,240],width=700,pitch=-32,yaw=-22,arm=500,near_clip_cm=10),
 dict(name='SPElephantLater',look_cm=[-100,2300,240],width=700,pitch=-32,yaw=-22,arm=500,near_clip_cm=10),
]
data=dict(version=1,seed=d.SEED,map=d.MAP,source='ArtSource/Blender/AstraStarPond.blend',
    units='metres, exported transforms centimetres',assets=assets,materials=materials,objects=objects,
    terrain_file='ArtSource/Layout/starpond_height.r16',terrain=dict(samples=127,spacing_cm=80,extent_cm=10080),
    spawn_cm=[-1600,0,1.18*100+30+98],paths=d.PATHS,demo_shots=d.DEMO,review_cameras=cameras,
    elephant=dict(ue_location_cm=[d.ELEPHANT[0]*100,d.ELEPHANT[1]*100,118],yaw=135),
    zones=dict(pond=dict(center_m=[0,0],radii_m=[d.RX,d.RY],water_z_m=d.WATER_Z),dais_m=d.DAIS,gate_m=d.GATE,stars_m=d.STARS),lights=[])
(ART/'Layout/starpond_layout.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
# Keep the real skinned guardian and its action in the complete Blender placement.
with bpy.data.libraries.load(str(ART/'Blender/StarPondElephant.blend'),link=False) as (a,b):
    b.objects=['Armature','SK_SP_UnicornElephant']
rig,skin=b.objects
for element in (rig,skin):layout.objects.link(element)
rig.location=(d.ELEPHANT[0],-d.ELEPHANT[1],1.18)
rig.rotation_euler.z=math.radians(90-data['elephant']['yaw'])
rig['ue_location_cm']=data['elephant']['ue_location_cm'];rig['ue_yaw']=data['elephant']['yaw']
scene.frame_set(1)
report=dict(passed=True,placements=len(objects),native_foliage=sum(o['foliage'] for o in objects),
    by_group=dict(Counter(o['group'] for o in objects)),landscape_samples=len(heights),new_assets=sum(not a['reuse_existing'] for a in assets.values()),
    exact_water_perimeter_mask_zero=all(w==0 for w in weights[-n:]))
(ART/'Previews/StarPondLayout_Validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
scene.world=bpy.data.worlds.new('PreviewOnly_StarPondSky');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.58,.75,.95,1);bg.inputs['Strength'].default_value=.6
bpy.ops.object.light_add(type='SUN',location=(-30,-20,50));sun=bpy.context.object;sun.rotation_euler=(.4,-.5,-.5);sun.data.energy=2;sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-58,0,87));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=108;scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1800;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(ART/'Previews/Blender_StarPondOverview.png')
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraStarPond.blend'))
print('STAR_POND_LAYOUT_READY '+json.dumps(report),flush=True)
bpy.ops.render.render(write_still=True)
print('STAR_POND_BLENDER_COMPLETE',flush=True)
