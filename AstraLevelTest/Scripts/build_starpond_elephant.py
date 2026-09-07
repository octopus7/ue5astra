"""Star Pond mochi unicorn elephant: real skinning and seamless 8 s idle.

Run with Blender 4.5 --factory-startup -b --python this_file.py.
Metres, Z up, face toward -Y; export in the same convention as scenery.
"""
import bpy
import bmesh
import json
import math
import os
import time
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
for folder in ('Blender', 'Meshes/StarPond', 'Layout', 'Previews'):
    (ART/folder).mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = 241

MATERIALS = {
    'M_SP_ElephantSkin': {'base_color':'BDA5D1', 'roughness':.48},
    'M_SP_ElephantInnerEar': {'base_color':'E5BEDC', 'roughness':.53},
    'M_SP_ElephantCheek': {'base_color':'EDAEC8', 'roughness':.57},
    'M_SP_ElephantIvory': {'base_color':'FFF0C8', 'roughness':.39},
    'M_SP_ElephantGold': {'base_color':'EACB85', 'roughness':.36, 'metallic':.12},
    'M_SP_ElephantEye': {'base_color':'302C40', 'roughness':.12},
    'M_SP_ElephantEyeLight': {'base_color':'FFFFFF', 'roughness':.2},
}

def rgba(value):
    c = [int(value[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c)+(1,)

mats = {}
for name, props in MATERIALS.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba(props['base_color'])
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = mat.diffuse_color
    node.inputs['Roughness'].default_value = props['roughness']
    node.inputs['Metallic'].default_value = props.get('metallic',0)
    mats[name] = mat

parts = []

def active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def mesh(name, verts, faces, material, group=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    bm = bmesh.new(); bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data); bm.free()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    data.materials.append(mats[material])
    for p in data.polygons: p.use_smooth=True
    parts.append(obj)
    if group: weight_all(obj, group)
    return obj

def weight_all(obj, group):
    vg = obj.vertex_groups.get(group) or obj.vertex_groups.new(name=group)
    vg.add(list(range(len(obj.data.vertices))),1,'REPLACE')

def ellipsoid(name, center, radii, material, group=None, seg=40, rings=24, flatten_bottom=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=center)
    obj=bpy.context.object;obj.name=name;obj.scale=radii
    bpy.ops.object.transform_apply(location=True,rotation=False,scale=True)
    if flatten_bottom is not None:
        for v in obj.data.vertices: v.co.z=max(flatten_bottom,v.co.z)
    obj.data.materials.append(mats[material])
    for p in obj.data.polygons: p.use_smooth=True
    parts.append(obj)
    if group: weight_all(obj, group)
    return obj

def tube(name, points, radii, material, group=None, sides=20):
    vs=[]; fs=[]
    for j,p in enumerate(points):
        tangent=Vector(points[min(len(points)-1,j+1)])-Vector(points[max(0,j-1)])
        tangent.normalize()
        u=tangent.cross(Vector((1,0,0)))
        if u.length<.01:u=tangent.cross(Vector((0,1,0)))
        u.normalize();v=tangent.cross(u).normalized()
        for i in range(sides):
            a=math.tau*i/sides
            vs.append(Vector(p)+radii[j]*(math.cos(a)*u+math.sin(a)*v))
        if j:
            for i in range(sides):
                n=(i+1)%sides; fs.append(((j-1)*sides+i,(j-1)*sides+n,j*sides+n,j*sides+i))
    fs.append(tuple(range(sides-1,-1,-1)))
    fs.append(tuple((len(points)-1)*sides+i for i in range(sides)))
    return mesh(name,vs,fs,material,group)

# One continuous pear-shaped head and body; no separate head ball.
body=ellipsoid('Continuous_Mochi_Pear', (0,0,1.23),(.87,.77,.98),'M_SP_ElephantSkin',seg=64,rings=40)
for v in body.data.vertices:
    h=(v.co.z-1.23)/.98
    v.co.x*=1-.10*h
    v.co.y*=1-.06*h
    if -.99999<h<0:
        # A broad mochi belly, so the small feet emerge from the body rather
        # than reading as four separate spheres attached to a round ball.
        factor=(1-h**4)**.25/(1-h*h)**.5
        v.co.x*=factor;v.co.y*=factor
    if h<0:v.co.z-=.10*abs(h)
    # A mild forward forehead bulge preserves a face without a neck seam.
    v.co.y-=.055*math.exp(-((v.co.z-1.76)/.38)**2)
    # Latest reference: extend torso rearward 30%, keeping the face at the front.
    v.co.y=-.80+(v.co.y+.80)*1.30
legs=[]
leg_centers={}
for side,s in [('L',-1),('R',1)]:
    for end,y in [('Front',-.39),('Back',.77)]:
        key=f'Foot_{end}_{side}';center=(s*.50,y,.31)
        center=(s*.50,y,.23)
        leg_centers[key]=center
        legs.append(ellipsoid(key,center,(.29,.30,.285),'M_SP_ElephantSkin',flatten_bottom=.025))
# Fuse only the body and legs, producing broad smooth transitions.
active(body)
for o in legs:o.select_set(True)
bpy.ops.object.join()
for o in legs:parts.remove(o)
remesh=body.modifiers.new('Continuous soft silhouette','REMESH')
remesh.mode='VOXEL';remesh.voxel_size=.027;remesh.use_smooth_shade=True
bpy.ops.object.modifier_apply(modifier=remesh.name)
smooth=body.modifiers.new('Mochi surface smoothing','SMOOTH');smooth.factor=1.1;smooth.iterations=7
bpy.ops.object.modifier_apply(modifier=smooth.name)
dec=body.modifiers.new('Efficient round silhouette','DECIMATE');dec.ratio=.105
bpy.ops.object.modifier_apply(modifier=dec.name)
sub=body.modifiers.new('Soft game surface','SUBSURF');sub.levels=1
bpy.ops.object.modifier_apply(modifier=sub.name)
for p in body.data.polygons:p.use_smooth=True
for n in ['Body']+list(leg_centers):body.vertex_groups.new(name=n)
for v in body.data.vertices:
    if v.co.z>=.8:
        body.vertex_groups['Body'].add([v.index],1,'REPLACE')
    else:
        nearest=min(leg_centers,key=lambda k:(Vector(leg_centers[k])-v.co).length)
        t=max(0,min(1,(v.co.z-.39)/.41));t=t*t*(3-2*t)
        body.vertex_groups[nearest].add([v.index],1-t,'REPLACE')
        body.vertex_groups['Body'].add([v.index],t,'REPLACE')

# Thick short curl, smoothly narrowing and visibly turned upwards at the end.
trunk_path=[(0,-.60,1.54),(0,-.77,1.43),(-.02,-.91,1.30),(-.025,-.97,1.18),
            (.025,-1.00,1.085),(.14,-1.015,1.075),(.225,-1.015,1.14),(.22,-1.015,1.24),(.15,-1.015,1.265)]
trunk_radii=[.207,.185,.146,.118,.096,.078,.063,.047,.022]
# Smooth Catmull-Rom interpolation of centreline and radii.
def catmull(values,steps=5):
    out=[]
    for i in range(len(values)-1):
        p0=values[max(0,i-1)];p1=values[i];p2=values[i+1];p3=values[min(len(values)-1,i+2)]
        for j in range(steps):
            t=j/steps
            out.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
    out.append(values[-1]);return out
tp=catmull([Vector(p) for p in trunk_path]);tr=catmull(trunk_radii)
trunk=tube('Short_Curled_Trunk',tp,tr,'M_SP_ElephantSkin',sides=28)
cap=ellipsoid('Rounded_Trunk_Tip',tp[-1],(.025,.025,.025),'M_SP_ElephantSkin',seg=20,rings=12)
active(trunk);cap.select_set(True);bpy.ops.object.join();parts.remove(cap)
remesh=trunk.modifiers.new('Round continuous curl','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.009
bpy.ops.object.modifier_apply(modifier=remesh.name)
sm=trunk.modifiers.new('Polished curl','SMOOTH');sm.factor=.7;sm.iterations=4
bpy.ops.object.modifier_apply(modifier=sm.name)
dec=trunk.modifiers.new('Curl topology budget','DECIMATE');dec.ratio=.25
bpy.ops.object.modifier_apply(modifier=dec.name)
for p in trunk.data.polygons:p.use_smooth=True
trunk_bone_points=[trunk_path[i] for i in [0,2,4,6,8]]
for n in range(4):trunk.vertex_groups.new(name=f'Trunk_{n+1}')
for vertex in trunk.data.vertices:
    best_distance=1e9;best_param=0
    for j,(pa,pb) in enumerate(zip(tp,tp[1:])):
        delta=pb-pa;f=max(0,min(1,(vertex.co-pa).dot(delta)/delta.length_squared))
        distance=(vertex.co-(pa+delta*f)).length_squared
        if distance<best_distance:best_distance=distance;best_param=j+f
    pos=best_param/(len(tp)-1)*4
    a=min(3,int(pos)); b=min(3,a+1);f=pos-a
    trunk.vertex_groups[f'Trunk_{a+1}'].add([vertex.index],1-f if b!=a else 1,'REPLACE')
    if b!=a:trunk.vertex_groups[f'Trunk_{b+1}'].add([vertex.index],f,'REPLACE')

# Round droplet ears with a quiet inset pink cushion.
eye_centers={}
def face_surface(x,z):
    hit,point,normal,index=body.ray_cast(Vector((x,-4,z)),Vector((0,1,0)))
    assert hit
    return point,normal
def face_shape(name,x,z,radii,material,group,offset=0):
    point,normal=face_surface(x,z)
    obj=ellipsoid(name,point+normal*offset,radii,material,group,32,20)
    # Ellipsoid vertices are world-space; rotate around its centre, not origin.
    center=point+normal*offset
    rotation=Vector((0,-1,0)).rotation_difference(normal)
    for v in obj.data.vertices:v.co=center+rotation@(v.co-center)
    return obj,center,normal
for side,s in [('L',-1),('R',1)]:
    ear=ellipsoid('Floppy_Ear_'+side,(s*.82,-.11,1.56),(.45,.17,.48),'M_SP_ElephantSkin','Ear_'+side)
    ear.rotation_euler.y=s*-.17
    inset=ellipsoid('Pink_Ear_'+side,(s*.875,-.258,1.56),(.325,.045,.35),'M_SP_ElephantInnerEar','Ear_'+side)
    inset.rotation_euler.y=s*-.17
    # Glossy small eyes, pastel cheek dots. Shapes sit on the body surface.
    eye,center,normal=face_shape('Eye_'+side,s*.315,1.59,(.073,.039,.085),'M_SP_ElephantEye','Blink_'+side,.012)
    eye_centers[side]=center
    shine_center=center+normal*.036+Vector((-.018,0,.025))
    ellipsoid('Eye_Shine_'+side,shine_center,(.009,.007,.010),'M_SP_ElephantEyeLight','Blink_'+side,20,12)
    face_shape('Blush_'+side,s*.465,1.39,(.097,.018,.065),'M_SP_ElephantCheek','Body',.008)

# Simple ivory cone and one rounded gold spiral ridge.
horn_center=Vector((0,-.30,2.045))
horn_points=[];horn_r=[]
for j in range(30):
    t=j/29
    horn_points.append(horn_center+Vector((0,-.10*t*t,.47*t)))
    horn_r.append(.147*(1-t)**.85+.002)
horn=tube('Ivory_Unicorn_Horn',horn_points,horn_r,'M_SP_ElephantIvory','Horn',sides=40)
spiral=[];spiral_r=[]
for j in range(130):
    t=j/129*.94;a=math.tau*3.1*t
    rad=.147*(1-t)**.85+.004
    spiral.append(horn_center+Vector((rad*math.cos(a),-.10*t*t+rad*math.sin(a),.47*t)))
    spiral_r.append(.018*(1-t)+.005)
tube('Soft_Horn_Spiral',spiral,spiral_r,'M_SP_ElephantGold','Horn',sides=10)
# Small toenail ovals, far smaller than the feet.
for name,c in leg_centers.items():
    for j in range(3):
        x=c[0]+(j-1)*.126
        ellipsoid('Tiny_Toe_'+name+'_'+str(j),(x,c[1]-.249,.105),(.058,.036,.07),
                  'M_SP_ElephantIvory',name,20,12)
tail_path=[(0,1.13,.95),(.05,1.37,.80),(.09,1.41,.64),(.12,1.40,.49)]
tail=tube('Little_Tail',tail_path,[.06,.049,.038,.029],'M_SP_ElephantSkin','Tail',sides=14)
ellipsoid('Tail_Pom',(.12,1.40,.48),(.082,.069,.113),'M_SP_ElephantInnerEar','Tail',24,16)

# All visible parts form a single real skinned mesh with per-vertex weights.
active(body)
for obj in parts:obj.select_set(True)
bpy.ops.object.join()
character=body;character.name='SK_SP_UnicornElephant'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
scene.cursor.location=(0,0,0)
bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
ground_offset=min(v.co.z for v in character.data.vertices)
for v in character.data.vertices:v.co.z-=ground_offset

arm_data=bpy.data.armatures.new('SKEL_SP_UnicornElephant')
rig=bpy.data.objects.new('Armature',arm_data)
scene.collection.objects.link(rig)
active(rig);bpy.ops.object.mode_set(mode='EDIT')
bone_spec={}
def bone(name,head,tail,parent=None):
    if name!='Root':
        head=Vector(head)-Vector((0,0,ground_offset))
        tail=Vector(tail)-Vector((0,0,ground_offset))
    b=arm_data.edit_bones.new(name);b.head=head;b.tail=tail
    if parent:b.parent=arm_data.edit_bones[parent]
    b.use_deform=True
    bone_spec[name]={'head_m':list(head),'tail_m':list(tail),'parent':parent}
bone('Root',(0,0,0),(0,0,.3))
bone('Body',(0,0,.62),(0,0,1.55),'Root')
for name,c in leg_centers.items():bone(name,(c[0],c[1],.06),(c[0],c[1],.52),'Root')
for side,s in [('L',-1),('R',1)]:
    bone('Ear_'+side,(s*.57,-.1,1.67),(s*1.02,-.1,1.4),'Body')
    bone('Blink_'+side,eye_centers[side],eye_centers[side]+Vector((0,0,.15)),'Body')
bone('Horn',horn_center,horn_center+Vector((0,-.1,.47)),'Body')
for n in range(4):bone(f'Trunk_{n+1}',trunk_bone_points[n],trunk_bone_points[n+1],'Body' if n==0 else f'Trunk_{n}')
bone('Tail',(0,1.13,.95),(.12,1.40,.49),'Body')
bpy.ops.object.mode_set(mode='OBJECT')
modifier=character.modifiers.new('Actual weighted elephant skeleton','ARMATURE');modifier.object=rig
modifier.use_deform_preserve_volume=False
character.parent=rig
for pb in rig.pose.bones:pb.rotation_mode='XYZ'

# Bake the 8-second idle: feet and root stay planted throughout the full clip.
rig.animation_data_create()
action=bpy.data.actions.new('A_SP_UnicornElephant_Idle')
rig.animation_data.action=action
for frame in range(1,242):
    p=(frame-1)/240;w=math.tau*p
    for pb in rig.pose.bones:
        pb.location=(0,0,0);pb.rotation_euler=(0,0,0);pb.scale=(1,1,1)
    breath=math.sin(w*2)
    rig.pose.bones['Body'].scale=(1+.012*breath,1+.008*breath,1+.01*breath)
    for side,s in [('L',-1),('R',1)]:
        pb=rig.pose.bones['Ear_'+side]
        pb.rotation_euler=(.035*math.sin(w*2+s*.3),.02*math.sin(w),s*.06*math.sin(w*2))
        blink=1
        for center in (.30,.77):
            d=abs(p-center)
            if d<.026:blink=min(blink,1-.93*math.cos(d/.026*math.pi/2)**2)
        rig.pose.bones['Blink_'+side].scale=(1,blink,1)
    for n in range(4):
        pb=rig.pose.bones[f'Trunk_{n+1}']
        pb.rotation_euler=(.027*math.sin(w+n*.4),.035*math.sin(w+n*.45),.035*math.sin(w*2+n*.3))
    rig.pose.bones['Tail'].rotation_euler=(.055*math.sin(w),.11*math.sin(w),.09*math.sin(w*2))
    # Endpoints are sampled from the same periodic formulas; tiny float noise rounded.
    for pb in rig.pose.bones:
        for prop in ('location','rotation_euler','scale'):
            values=getattr(pb,prop)
            for i in range(3):values[i]=round(values[i],9)
            pb.keyframe_insert(data_path=prop,frame=frame,group=pb.name)
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                for kp in fc.keyframe_points:kp.interpolation='LINEAR'
scene.frame_set(1)

# Meaningful deformation/loop/grounding validation on evaluated geometry.
def evaluated_vertices(frame,obj=character):
    scene.frame_set(frame);bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data=evaluated.to_mesh()
    coords=[obj.matrix_world@v.co for v in data.vertices]
    evaluated.to_mesh_clear();return coords
v0=evaluated_vertices(1);vquarter=evaluated_vertices(31);vend=evaluated_vertices(241)
weights=[]
for v in character.data.vertices:
    ws=[g.weight for g in v.groups if g.weight>1e-7]
    weights.append((sum(ws),len(ws)))
planted=[i for i,v in enumerate(v0) if v.z<.23]
root_samples={};foot_samples={};max_ground_drift=0
for frame in [1,31,61,91,121,151,181,211,241]:
    vs=evaluated_vertices(frame)
    max_ground_drift=max(max_ground_drift,max((vs[i]-v0[i]).length for i in planted))
    root_samples[str(frame)]=list(rig.pose.bones['Root'].matrix.translation)
    foot_samples[str(frame)]={name:list(rig.pose.bones[name].matrix.translation) for name in leg_centers}
validation={
    'style':'Smooth pastel toy; continuous mochi body/head; no realistic skin details',
    'vertices':len(character.data.vertices),
    'triangles':sum(len(p.vertices)-2 for p in character.data.polygons),
    'bones':len(arm_data.bones),'weighted_vertices':sum(1 for s,n in weights if n),
    'max_influences':max(n for s,n in weights),
    'max_weight_sum_error':max(abs(s-1) for s,n in weights),
    'max_sampled_deformation_m':max((a-b).length for a,b in zip(v0,vquarter)),
    'max_loop_endpoint_error_m':max((a-b).length for a,b in zip(v0,vend)),
    'max_ground_vertex_drift_m':max_ground_drift,
    'planted_vertex_count':len(planted),
    'mesh_ground_z_m':min(v.z for v in v0),
    'root_samples_m':root_samples,'foot_samples_m':foot_samples,
    'duration_seconds':8,'fps':30,'frame_range':[1,241],
}
assert validation['weighted_vertices']==validation['vertices']
assert validation['max_weight_sum_error']<1e-5
assert validation['max_loop_endpoint_error_m']<1e-6
assert validation['max_ground_vertex_drift_m']<1e-6
assert validation['max_sampled_deformation_m']>.008

scene.frame_set(1)
active(rig);character.select_set(True)
fbx=ART/'Meshes/StarPond/SK_SP_UnicornElephant.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH','ARMATURE'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    mesh_smooth_type='FACE',use_mesh_modifiers=True,add_leaf_bones=False,
    use_armature_deform_only=True,bake_anim=True,bake_anim_use_all_bones=True,
    bake_anim_use_nla_strips=False,bake_anim_use_all_actions=False,bake_anim_step=1,
    bake_anim_simplify_factor=0,path_mode='STRIP')

# FBX roundtrip: verify a real armature, skin and keyed animation survived export.
before=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(fbx),use_anim=True)
added=set(bpy.data.objects)-before
rt_rig=next(o for o in added if o.type=='ARMATURE')
rt_mesh=next(o for o in added if o.type=='MESH')
rt_action=rt_rig.animation_data.action
rt_start=int(rt_action.frame_range[0]);rt_end=int(rt_action.frame_range[1])
rt_a=evaluated_vertices(rt_start,rt_mesh);rt_b=evaluated_vertices(rt_start+30,rt_mesh);rt_endverts=evaluated_vertices(rt_end,rt_mesh)
validation['fbx_roundtrip']={
    'bones':len(rt_rig.data.bones),'vertex_groups':len(rt_mesh.vertex_groups),
    'armature_modifier':any(m.type=='ARMATURE' for m in rt_mesh.modifiers),
    'animation_action':rt_action.name,'frame_range':list(rt_action.frame_range),
    'max_sampled_deformation_m':max((a-b).length for a,b in zip(rt_a,rt_b)),
    'max_loop_endpoint_error_m':max((a-b).length for a,b in zip(rt_a,rt_endverts))}
assert validation['fbx_roundtrip']['bones']==len(arm_data.bones)
assert validation['fbx_roundtrip']['armature_modifier']
assert validation['fbx_roundtrip']['max_sampled_deformation_m']>.008
assert validation['fbx_roundtrip']['max_loop_endpoint_error_m']<1e-5
for o in added:bpy.data.objects.remove(o,do_unlink=True)

# A restrained studio preview shows the true geometry, rig and idle phases.
floor_mat=bpy.data.materials.new('Preview_Matte');floor_mat.diffuse_color=rgba('E4E1F0')
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,.0));floor=bpy.context.object
floor.name='PREVIEW_ONLY_Floor';floor.data.materials.append(floor_mat)
world=bpy.data.worlds.new('Pastel preview world');scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.43,.44,.55,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45
def area(name,loc,power,size,color):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj);obj.location=loc
    obj.rotation_euler=(Vector((0,0,1.1))-obj.location).to_track_quat('-Z','Y').to_euler()
area('Softbox',(-3,-4,6),750,5,(1,.89,.84))
area('LavenderFill',(4,-1,4),500,4,(.82,.85,1))
area('Rim',(0,3,5),900,3,(1,.95,.82))
data=bpy.data.cameras.new('Preview_Camera');camera=bpy.data.objects.new('Preview_Camera',data)
scene.collection.objects.link(camera);scene.camera=camera
camera.location=(4,-7,3.7);target=Vector((0,-.08,1.30))
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
data.type='ORTHO';data.ortho_scale=3.75
scene.render.engine='CYCLES';scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.render.resolution_x=1100;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
def render_preview(path):
    destination=Path(path)
    temporary=destination.with_name(destination.stem+'_render_tmp.png')
    scene.render.filepath=str(temporary)
    bpy.ops.render.render(write_still=True)
    for attempt in range(12):
        try:
            os.replace(temporary,destination)
            break
        except PermissionError:
            if attempt==11:raise
            time.sleep(.25)
for frame,name in [(1,'ThreeQuarter'),(31,'Breath'),(73,'Blink')]:
    scene.frame_set(frame)
    render_preview(ART/f'Previews/Blender_StarPondElephant_{name}.png')
camera.location=(0,-8,2.45)
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
scene.frame_set(1);render_preview(ART/'Previews/Blender_StarPondElephant_Front.png')
camera.location=(7,0,2.50)
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
render_preview(ART/'Previews/Blender_StarPondElephant_Side.png')
camera.location=(3.2,-4.8,6.7)
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
render_preview(ART/'Previews/Blender_StarPondElephant_Top.png')
camera.location=(4,-7,3.7);camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
active(rig)
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/StarPondElephant.blend'))
metadata={
    'name':'Star Pond Unicorn Elephant','source':'ArtSource/Blender/StarPondElephant.blend',
    'fbx':'ArtSource/Meshes/StarPond/SK_SP_UnicornElephant.fbx',
    'skeleton':'SKEL_SP_UnicornElephant','animation':'A_SP_UnicornElephant_Idle',
    'forward_blender':'-Y','units':'metres','ue_import_scale':1,
    'body_height_m':2.2,'overall_height_m':2.52,
    'reference':'ArtSource/Reference/StarPond/Ref_StarPondElephantOval.png',
    'torso_rear_depth_factor':1.30,
    'material_slots':[s.name for s in character.data.materials],
    'materials':MATERIALS,'bones':bone_spec,
    'animation_duration_seconds':8,'animation_looping':True,'animation_root_motion':False,
    'integration':'Call import_starpond_elephant.import_and_place(location_cm, yaw) in the target map. Returns (actor, report); does not save map.',
}
(ART/'Layout/starpond_elephant.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
(ART/'Previews/Blender_StarPondElephant_Validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
print('STARPOND_ELEPHANT_COMPLETE '+json.dumps(validation))
