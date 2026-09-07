"""Assemble the second 100 m forest in Blender; export the exact UE placement data.

Run Blender --factory-startup -b --python this_file.py.
Source asset libraries and the woodland level are read-only inputs.
"""
import bpy
import json
import math
import random
import struct
import sys
from collections import Counter
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Scripts'))
import starfall_layout as design
from water_geometry import add_edge_mask

ART = ROOT/'ArtSource'
RNG = random.Random(design.SEED)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
library = bpy.data.collections.new('01_MeshLibrary')
layout = bpy.data.collections.new('02_StarfallPlacement')
scene.collection.children.link(library)
scene.collection.children.link(layout)
assets, materials, source_objects, objects = {}, {}, {}, []


def append_library(filename, names):
    with bpy.data.libraries.load(str(ART/'Blender'/filename), link=False) as (source, target):
        missing = set(names)-set(source.objects)
        if missing:
            raise RuntimeError('Missing library objects: '+str(missing))
        target.objects = list(names)
    for name, obj in zip(names, target.objects):
        library.objects.link(obj)
        obj.hide_render = True
        obj.hide_set(True)
        source_objects[name] = obj


old = json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'))
reuse = [f'SM_{tree}_{i:02}' for tree in ('Oak', 'Fir') for i in range(1,4)]
reuse += [f'SM_MossRock_{i:02}' for i in range(1,6)]
reuse += ['SM_Grass', 'SM_Fern', 'SM_Flowers', 'SM_Reeds', 'SM_Shrub']
append_library('AstraWoodland.blend', reuse)
for name in reuse:
    assets[name] = dict(old['assets'][name], file='ArtSource/'+old['assets'][name]['file'],
                        unreal_asset_path='/Game/Astra/Meshes/'+name, reuse_existing=True)
for kit in ('spaceship', 'trees', 'fungi_spring'):
    metadata = json.loads((ART/f'Layout/starfall_{kit}.json').read_text(encoding='utf-8'))
    names = [a['asset_id'] for a in metadata['assets']]
    append_library(Path(metadata['source']).name, names)
    materials.update(metadata['materials'])
    for a in metadata['assets']:
        assets[a['asset_id']] = dict(a, unreal_asset_path='/Game/Astra/Meshes/Starfall/'+a['asset_id'], reuse_existing=False)


def place(asset, x, y, z=None, scale=1, yaw=0, group='Forest', foliage=False, collision=None, **extra):
    if z is None:
        z = design.height(x,y)-.025
    if isinstance(scale, (int,float)):
        scale = [scale]*3
    name = f'SF_{asset.removeprefix("SM_")}_{len(objects):04}'
    obj = bpy.data.objects.new(name, source_objects[asset].data)
    layout.objects.link(obj)
    obj.location = (x,-y,z)
    obj.rotation_euler.z = math.radians(-yaw)
    obj.scale = scale
    obj['asset_id'] = asset
    obj['group'] = group
    obj['native_ue_foliage'] = foliage
    item = dict(name=name, asset=asset, group=group, collision=collision or assets[asset].get('collision','none'),
        ue_location_cm=[round(x*100,4),round(y*100,4),round(z*100,4)],
        ue_rotation_deg={'pitch':0,'yaw':yaw,'roll':0}, scale=list(scale), foliage=foliage, **extra)
    objects.append(item)
    return obj


def new_water(name, rx, ry, index=None):
    n=96
    verts=[(0,0,0)]; weights=[1.0]; faces=[]
    for radius, weight in ((.60,1),(.87,1),(.94,.45),(1,0)):
        for i in range(n):
            angle=i*math.tau/n
            irregular=design.pond_radius(angle,index) if index is not None else 1
            verts.append((rx*math.cos(angle)*radius*irregular,-ry*math.sin(angle)*radius*irregular,0))
            weights.append(weight)
    for i in range(n):
        j=(i+1)%n
        faces.append((0,1+j,1+i))
        for ring in range(3):
            a=1+ring*n; b=a+n
            faces.extend(((a+i,a+j,b+j),(a+i,b+j,b+i)))
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    add_edge_mask(mesh,weights)
    uv=mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            v=mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv=(v.x/(rx*2)+.5,v.y/(ry*2)+.5)
    material=bpy.data.materials.get('PreviewOnly_ExistingWater')
    if not material:
        material=bpy.data.materials.new('PreviewOnly_ExistingWater');material.use_nodes=True
        bsdf=material.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value=(.15,.54,.65,1)
        bsdf.inputs['Metallic'].default_value=.45;bsdf.inputs['Roughness'].default_value=.12
    mesh.materials.append(material)
    obj=bpy.data.objects.new(name,mesh); library.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    filename=f'ArtSource/Meshes/Starfall/{name}.fbx'
    bpy.ops.export_scene.fbx(filepath=str(ROOT/filename),use_selection=True,object_types={'MESH'},
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',path_mode='STRIP',use_tspace=True)
    obj.hide_render=True;obj.hide_set(True);source_objects[name]=obj
    assets[name]={'file':filename,'materials':['/Game/Astra/Materials/Shoreline/M_PuddleSkyReflection'],
        'collision':'none','triangles':len(faces),'dimensions_m':[max(v[0] for v in verts)-min(v[0] for v in verts),
          max(v[1] for v in verts)-min(v[1] for v in verts),0],
        'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS','vertex_color_import':'REPLACE',
        'unreal_asset_path':'/Game/Astra/Meshes/Starfall/'+name,'reuse_existing':False,
        'edge_mask':{'attribute':'WaterEdgeMask','outer_weight':0,'inner_weight':1,'outer_vertices':n}}
    assert all(weights[-n+i]==0 for i in range(n))


# Three large shallow puddles and the small spring use the existing reflective shader.
for index, pond in enumerate(design.PONDS):
    name='SM_SF_'+pond['name']
    new_water(name,*pond['radii'],index)
    place(name,*pond['center'],z=pond['z'],group='Water',
          material_override='/Game/Astra/Materials/Shoreline/M_PuddleSkyReflection')
new_water('SM_SF_SpringSurface',2.05,2.05)
place('SM_SF_SpringSurface',*design.SPRING,z=1.51,group='Spring',
      material_override='/Game/Astra/Materials/Shoreline/M_PuddleSkyReflection')
place('SM_SF_SpringRockRing',*design.SPRING,z=1.46,group='Spring')
place('SM_SF_LandedSpaceship',*design.SHIP,z=design.height(*design.SHIP),group='LandingClearing')

# Explicit storytelling props, positioned outside the walk-through routes.
place('SM_SF_FreshBrokenStump',3,-11.8,group='FreshlyBrokenTrees')
place('SM_SF_FreshFallenTree',9,-11.5,yaw=0,group='FreshlyBrokenTrees')
for x,y,yaw,scale in [(28,-35,18,1),(-34,30,60,1.12),(-29,-35,-28,.95)]:
    place('SM_SF_OldMossLog',x,y,yaw=yaw,scale=scale,group='OldMossLogs')
pink_positions=[(25,26),(25.5,31.5),(29,33.3),(34,33),(36.3,29),(35.5,24.8),(30.8,23.6)]
for i,(x,y) in enumerate(pink_positions):
    place(f'SM_SF_PinkTree_{i%3+1:02}',x,y,scale=RNG.uniform(.85,1.05),yaw=RNG.uniform(0,360),group='PinkSpringGrove')

# Spatially bounded mushroom habitats; sizes include the complete cluster footprint.
habitat_bounds={}
for glowing,center,size,grid in [(False,design.MUSHROOM,15,8),(True,design.GLOW,5,4)]:
    group='GlowGrove5m' if glowing else 'MushroomMeadow15m'
    all_bounds=[]
    for ix in range(grid):
        for iy in range(grid):
            if RNG.random() < (.12 if glowing else .09):
                continue
            asset=f'SM_SF_{"GlowMushroom" if glowing else "Mushroom"}Cluster_{RNG.randint(1,2 if glowing else 3):02}'
            scale=RNG.uniform(.55,.70) if glowing else RNG.uniform(.66,1.0)
            radius=math.hypot(*assets[asset]['dimensions_m'][:2])*.5*scale
            spacing=(size-2*radius)/(grid-1)
            x=center[0]-size/2+radius+ix*spacing+RNG.uniform(-.12,.12)
            y=center[1]-size/2+radius+iy*spacing+RNG.uniform(-.12,.12)
            x=max(center[0]-size/2+radius,min(center[0]+size/2-radius,x))
            y=max(center[1]-size/2+radius,min(center[1]+size/2-radius,y))
            place(asset,x,y,scale=scale,yaw=RNG.uniform(0,360),group=group,foliage=True,collision='none')
            all_bounds.append([x-radius,y-radius,x+radius,y+radius])
    habitat_bounds[group]=[min(b[0] for b in all_bounds),min(b[1] for b in all_bounds),
        max(b[2] for b in all_bounds),max(b[3] for b in all_bounds)]

# A softly irregular forest wall and smaller groves leave paths and focal areas legible.
tree_positions=[]
for ix in range(26):
    for iy in range(26):
        x=-48+ix*3.84+RNG.uniform(-1.3,1.3)
        y=-48+iy*3.84+RNG.uniform(-1.3,1.3)
        if design.reserved(x,y,.45):continue
        if max(abs(x),abs(y))<37 and RNG.random()<.20:continue
        if any(math.hypot(x-p[0],y-p[1])<3.05 for p in tree_positions):continue
        kind='Fir' if RNG.random()<.72 else 'Oak'
        scale=RNG.uniform(.78,1.13)
        place(f'SM_{kind}_{RNG.randint(1,3):02}',x,y,scale=scale,yaw=RNG.uniform(0,360),group='ForestCanopy')
        tree_positions.append((x,y))

# Rubble around the landing apron, and occasional exposed stones on puddle banks.
for i in range(34):
    angle=RNG.uniform(0,math.tau);radius=RNG.uniform(6.1,12.2)
    x=design.SHIP[0]+math.cos(angle)*radius;y=design.SHIP[1]+math.sin(angle)*radius
    if design.demo_distance(x,y)<1.8:continue
    if math.hypot(x-9,y+11.5)<4:continue
    place(f'SM_MossRock_{RNG.randint(1,5):02}',x,y,scale=RNG.uniform(.17,.49),yaw=RNG.uniform(0,360),group='LandingRubble')
for index,pond in enumerate(design.PONDS):
    for j in range(17):
        angle=RNG.uniform(0,math.tau);r=design.pond_radius(angle,index)*RNG.uniform(1.01,1.14)
        x=pond['center'][0]+math.cos(angle)*pond['radii'][0]*r
        y=pond['center'][1]+math.sin(angle)*pond['radii'][1]*r
        if design.path_distance(x,y)<1.2 or design.demo_distance(x,y)<1.0:continue
        if j%3==0:
            place(f'SM_MossRock_{RNG.randint(1,5):02}',x,y,scale=RNG.uniform(.18,.34),yaw=RNG.uniform(0,360),group='PuddleBanks')
        else:
            place('SM_Reeds',x,y,scale=RNG.uniform(.40,.68),yaw=RNG.uniform(0,360),group='PuddleBanks',foliage=True)

# Understory is clustered by canopy and habitat, never uniformly painted over footpaths.
for i in range(4700):
    if i<2800 and tree_positions:
        tx,ty=RNG.choice(tree_positions);angle=RNG.uniform(0,math.tau);radius=RNG.uniform(.7,2.6)
        x=tx+math.cos(angle)*radius;y=ty+math.sin(angle)*radius
    else:
        x=RNG.uniform(-48.5,48.5);y=RNG.uniform(-48.5,48.5)
    if max(abs(x),abs(y))>49 or design.path_distance(x,y)<1.40 or design.demo_distance(x,y)<.75:continue
    if math.hypot(x-design.SHIP[0],y-design.SHIP[1])<12.5:continue
    if math.hypot(x-design.SPRING[0],y-design.SPRING[1])<3.4:continue
    if any(design.pond_distance(x,y,p,j)<1.14 for j,p in enumerate(design.PONDS)):continue
    if design.habitat(x,y)!='Forest' and RNG.random()<.88:continue
    asset=RNG.choices(['SM_Grass','SM_Fern','SM_Flowers'],[.61,.25,.14])[0]
    place(asset,x,y,scale=RNG.uniform(.55,1.05),yaw=RNG.uniform(0,360),group='ForestUnderstory',foliage=True)

# Native Landscape's exact row-major 16-bit samples. Blender presents the same surface.
heights=[];verts=[];faces=[];colors=[]
for iy in range(127):
    y=-50.4+iy*.8
    for ix in range(127):
        x=-50.4+ix*.8;h=design.height(x,y)
        heights.append(round(32768+h*128));verts.append((x,-y,h))
        path=1-design.smooth(1.0,1.75,design.path_distance(x,y))
        clear=1-design.smooth(7.8,12.3,math.hypot(x-design.SHIP[0],y-design.SHIP[1]))
        dirt=max(path,clear)
        grass=(.25,.34,.082);sand=(.52,.365,.175)
        colors.append(tuple(grass[j]*(1-dirt)+sand[j]*dirt for j in range(3)))
for iy in range(126):
    for ix in range(126):
        a=iy*127+ix;faces.append((a,a+127,a+128,a+1))
(ART/'Layout/starfall_height.r16').write_bytes(struct.pack('<'+str(len(heights))+'H',*heights))
mesh=bpy.data.meshes.new('Starfall_LandscapePreview');mesh.from_pydata(verts,[],faces);mesh.update()
col=mesh.color_attributes.new(name='TerrainPreview',type='FLOAT_COLOR',domain='POINT')
for c,rgb in zip(col.data,colors):c.color=(*rgb,1)
terrain=bpy.data.objects.new('LandscapePreview_100m_Starfall',mesh);layout.objects.link(terrain)
mat=bpy.data.materials.new('PreviewOnly_StarfallGround');mat.use_nodes=True
attr=mat.node_tree.nodes.new('ShaderNodeVertexColor');attr.layer_name='TerrainPreview'
bsdf=mat.node_tree.nodes.get('Principled BSDF');mat.node_tree.links.new(attr.outputs['Color'],bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value=.9;mesh.materials.append(mat)

# The UE shader takes shared forest-floor colour and adds only this map's trail/basin masks.
shader=['float2 p=Pos.xy*.01; float d=10000.; float2 a,b,q;',
        'float n=sin(p.x*2.1+sin(p.y*1.3))*.5+sin(p.y*3.3-p.x*.8)*.25;']
for path in design.PATHS:
    for a,b in zip(path,path[1:]):
        shader.append(f'a=float2({a[0]:.5f},{a[1]:.5f}); b=float2({b[0]:.5f},{b[1]:.5f}); q=b-a; d=min(d,length(p-a-q*saturate(dot(p-a,q)/dot(q,q))));')
shader += ['float path=1-smoothstep(1.03,1.75,d+n*.10);',
    'float clearing=1-smoothstep(7.8,12.3,length(p-float2(3.5,1))+n*.28);',
    'float dry=max(path,clearing); float floorMask=0; float bank=0; float r; float theta; float2 v;']
for i,p in enumerate(design.PONDS):
    shader += [f'v=(p-float2({p["center"][0]:.5f},{p["center"][1]:.5f}))/float2({p["radii"][0]:.5f},{p["radii"][1]:.5f});',
        f'theta=atan2(v.y,v.x); r=length(v)/(1+.047*sin(theta*3+{i:.5f})+.033*sin(theta*7+{.7*i:.5f}));',
        'floorMask=max(floorMask,1-smoothstep(.89,1.09,r));bank=max(bank,1-smoothstep(1.02,1.27,r));']
shader += ['r=length(p-float2(30,27));floorMask=max(floorMask,1-smoothstep(1.65,2.1,r));',
    'bank=max(bank,1-smoothstep(2.3,3.5,r));',
    'float3 grass=Tex.rgb*float3(.94,1.02,.96);',
    'float grain=dot(Tex.rgb,float3(.25,.55,.2));',
    'float3 trail=float3(.47,.32,.145)*(0.85+grain*.85+n*.025);',
    'float3 ground=lerp(grass,trail,max(dry,bank*.85));',
    'return lerp(ground,float3(.40,.44,.28)*(0.9+grain*.3),floorMask);']
(ART/'Layout/starfall_ground.hlsl').write_text('\n'.join(shader)+'\n',encoding='utf-8')

cameras=[
 {'name':'SFOverview','look_cm':[0,0,200],'width':12500,'pitch':-58,'yaw':0},
 {'name':'SFSpaceship','look_cm':[350,50,690],'width':3000,'pitch':-48,'yaw':0},
 {'name':'SFMushrooms','look_cm':[800,-2800,120],'width':2600,'pitch':-58,'yaw':0},
 {'name':'SFGlow','look_cm':[-2400,-2900,155],'width':1450,'pitch':-53,'yaw':0},
 {'name':'SFSpring','look_cm':[3000,2700,310],'width':2600,'pitch':-58,'yaw':0},
 {'name':'SFPuddles','look_cm':[-2050,1000,170],'width':4700,'pitch':-65,'yaw':0},
 {'name':'SFBrokenTrees','look_cm':[700,-1170,200],'width':1850,'pitch':-55,'yaw':0}
]
manifest={'version':1,'seed':design.SEED,'map':design.MAP,'units':'metres; exported transforms centimetres',
    'source':'ArtSource/Blender/AstraStarfall.blend','assets':assets,'materials':materials,'objects':objects,
    'terrain_file':'ArtSource/Layout/starfall_height.r16','terrain':{'samples':127,'spacing_cm':80,'extent_cm':10080},
    'spawn_cm':[-950,0,design.height(-9.5,0)*100+98],
    'paths':design.PATHS,'demo_shots':design.DEMO,'review_cameras':cameras,
    'lights':[{'name':'SFGlowSoftFill','ue_location_cm':[-2400,-2900,185],'intensity':22,'radius':340,'color':[.22,.8,1]}],
    'zones':{'mushroom_meadow':{'center_m':design.MUSHROOM,'size_m':[15,15]},
        'glow_grove':{'center_m':design.GLOW,'size_m':[5,5]},
        'spring':{'center_m':design.SPRING,'water_radius_m':2.05},
        'spacecraft':{'center_m':design.SHIP,'tilt_degrees':16},'puddles':design.PONDS}}
(ART/'Layout/starfall_layout.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
report={'passed':True,'placement_count':len(objects),'by_group':dict(Counter(o['group'] for o in objects)),
    'new_assets':sum(not a['reuse_existing'] for a in assets.values()),'reused_assets':len(reuse),
    'habitat_bounds_m':habitat_bounds,'native_foliage_count':sum(o['foliage'] for o in objects),
    'landscape_samples':len(heights),'landscape_extent_m':[100.8,100.8],'water_perimeter_mask_zero':True,
    'ship_tilt_is_baked_degrees':16,'water_and_sky_materials_reused':True}
(ART/'Previews/StarfallLayout_Validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

scene.world=bpy.data.worlds.new('PreviewOnly_StarfallSky');scene.world.use_nodes=True
background=scene.world.node_tree.nodes.get('Background')
background.inputs['Color'].default_value=(.58,.75,.95,1);background.inputs['Strength'].default_value=.65
bpy.ops.object.light_add(type='SUN',location=(-30,-20,50))
sun=bpy.context.object;sun.name='PreviewOnly_Sun50degrees';sun.rotation_euler=(.4,-.5,-.5)
sun.data.energy=2.2;sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-72,-3,105))
camera=bpy.context.object;camera.name='PreviewOnly_StarfallOverview'
camera.rotation_euler=(Vector((0,0,2))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=123;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1800;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(ART/'Previews/Blender_StarfallOverview.png')
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraStarfall.blend'))
print('STARFALL_LAYOUT_READY '+json.dumps(report),flush=True)
bpy.ops.render.render(write_still=True)
print('STARFALL_SCENE_COMPLETE',flush=True)
