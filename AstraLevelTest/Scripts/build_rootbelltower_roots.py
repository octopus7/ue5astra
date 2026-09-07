"""Build the living tree, gripping roots and botanical details in metres.

No tower geometry is authored here. GrippingRoots shares the tower origin;
the ancient tree belongs five metres behind it along source +Y.
"""
import bpy, bmesh, json, math, random
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]; ART=ROOT/'ArtSource'
for folder in ('Blender','Meshes/RootBelltower','Layout','Previews'):
    (ART/folder).mkdir(parents=True,exist_ok=True)
assert (ART/'Reference/RootBelltower/Ref_RootBelltowerRoots.png').exists()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
library=bpy.data.collections.new('RootBelltowerRoots_Library');scene.collection.children.link(library)
display=bpy.data.collections.new('RootBelltowerRoots_Presentation');scene.collection.children.link(display)
rng=random.Random(90791)
MATERIALS={
 'M_RB_Bark':dict(base_color='82705B',roughness=.9,metallic=0,base_color_texture='ArtSource/Textures/RootBelltower/T_RB_AncientBark.png'),
 'M_RB_BarkRidge':dict(base_color='8F7B60',roughness=.9,metallic=0),
 'M_RB_BarkShadow':dict(base_color='4B5143',roughness=.95,metallic=0),
 'M_RB_RootMoss':dict(base_color='6D8050',roughness=.95,metallic=0),
 'M_RB_LeafJade':dict(base_color='4E745D',roughness=.86,metallic=0),
 'M_RB_LeafOlive':dict(base_color='71884A',roughness=.86,metallic=0),
 'M_RB_LeafLight':dict(base_color='8D9B58',roughness=.86,metallic=0),
 'M_RB_SapGlow':dict(base_color='3FABA4',roughness=.45,metallic=.08,emissive_color='60DBCF',emissive_strength=1.4),
 'M_RB_MushroomStem':dict(base_color='B4B49A',roughness=.85,metallic=0),
 'M_RB_MushroomCap':dict(base_color='B0D9C4',roughness=.6,metallic=0,emissive_color='9AE6C7',emissive_strength=.6),
}
def rgba(s):
    values=[int(s[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values)+(1,)
mats={}
for name,props in MATERIALS.items():
    mat=bpy.data.materials.new(name);mat.use_nodes=True;mat.diffuse_color=rgba(props['base_color'])
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=mat.diffuse_color
    bs.inputs['Roughness'].default_value=props['roughness'];bs.inputs['Metallic'].default_value=props['metallic']
    if props.get('base_color_texture'):
        image=bpy.data.images.load(str(ROOT/props['base_color_texture']));image.pack()
        node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
        mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color'])
    if props.get('emissive_color'):
        bs.inputs['Emission Color'].default_value=rgba(props['emissive_color'])
        bs.inputs['Emission Strength'].default_value=props['emissive_strength']
    mats[name]=mat

class Builder:
    def __init__(self):self.vertices=[];self.faces=[];self.slots=[];self.indices=[]
    def add(self,vertices,faces,material):
        offset=len(self.vertices);self.vertices.extend(vertices)
        self.faces.extend(tuple(offset+i for i in face) for face in faces)
        if material not in self.slots:self.slots.append(material)
        self.indices.extend([self.slots.index(material)]*len(faces))
    def tube(self,points,radii,material='M_RB_Bark',sides=14,steps=4,flutes=.1):
        # Catmull-Rom gives continuous, tapered roots instead of joined cylinders.
        controls=[Vector(p) for p in points];sampled=[];widths=[]
        for i in range(len(controls)-1):
            p0=controls[max(0,i-1)];p1=controls[i];p2=controls[i+1];p3=controls[min(len(controls)-1,i+2)]
            for j in range(steps):
                t=j/steps
                sampled.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
                widths.append(radii[i]*(1-t)+radii[i+1]*t)
        sampled.append(controls[-1]);widths.append(radii[-1]);vertices=[]
        # Choose one transported radial frame to avoid abrupt tube twists.
        last_u=Vector((1,0,0))
        for i,p in enumerate(sampled):
            tangent=(sampled[min(i+1,len(sampled)-1)]-sampled[max(0,i-1)]).normalized()
            u=last_u-tangent*last_u.dot(tangent)
            if u.length<.01:u=tangent.cross(Vector((0,1,0)))
            u.normalize();v=tangent.cross(u).normalized();last_u=u
            for k in range(sides):
                a=math.tau*k/sides;r=widths[i]*(1+flutes*math.sin(5*a+i*.13))
                q=p+r*(u*math.cos(a)+v*math.sin(a));q.z=max(0,q.z)
                vertices.append(tuple(q))
        faces=[tuple(range(sides-1,-1,-1))]
        for i in range(len(sampled)-1):
            for k in range(sides):
                n=(k+1)%sides;faces.append((i*sides+k,i*sides+n,(i+1)*sides+n,(i+1)*sides+k))
        faces.append(tuple((len(sampled)-1)*sides+k for k in range(sides)))
        self.add(vertices,faces,material)
    def ellipsoid(self,center,scale,material,sides=12,rings=6,wobble=.04):
        c=Vector(center);vertices=[tuple(c+Vector((0,0,scale[2])))];faces=[]
        for row in range(1,rings):
            t=math.pi*row/rings
            for j in range(sides):
                a=math.tau*j/sides;f=1+wobble*math.sin(a*5+row*.7)
                vertices.append(tuple(c+Vector((scale[0]*math.sin(t)*math.cos(a)*f,scale[1]*math.sin(t)*math.sin(a)*f,scale[2]*math.cos(t)))))
        end=len(vertices);vertices.append(tuple(c-Vector((0,0,scale[2]))))
        faces.extend((0,1+j,1+(j+1)%sides) for j in range(sides))
        for row in range(rings-2):
            a=1+row*sides;b=a+sides
            faces.extend((a+j,b+j,b+(j+1)%sides,a+(j+1)%sides) for j in range(sides))
        a=1+(rings-2)*sides;faces.extend((a+j,end,a+(j+1)%sides) for j in range(sides))
        self.add(vertices,faces,material)
    def finish(self,name):
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(self.vertices,[],self.faces);mesh.update()
        for name_mat in self.slots:mesh.materials.append(mats[name_mat])
        for poly,index in zip(mesh.polygons,self.indices):poly.material_index=index;poly.use_smooth=True
        bm=bmesh.new();bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6)
        bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(mesh);bm.free();mesh.update()
        obj=bpy.data.objects.new(name,mesh);library.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.018);bpy.ops.object.mode_set(mode='OBJECT')
        # Preserve the smooth authored normals through FBX.
        mesh.normals_split_custom_set([tuple(n.vector) for n in mesh.corner_normals])
        return obj

assets=[]
tree=Builder()
tree.tube([(0,0,0),(-.5,.1,3),(0,.4,7),(.9,.4,11),(.5,1.2,15),(1.1,1.4,20)], [2.25,1.95,1.55,1.25,.9,.36],steps=6,sides=24,flutes=.14)
for i in range(9):
    a=i*math.tau/9;dx,dy=math.cos(a),math.sin(a)
    tree.tube([(dx*.8,dy*.8,3),(dx*2.1,dy*2,1.5),(dx*3.7,dy*3.5,.45),(dx*5.8,dy*5.5,0)], [.85,.75,.45,.025])
for side in (-1,1):
    for j in range(4):
        z=9+j*2.3;end=Vector((side*(5+j*.45),1.2+j*.9,z+3))
        tree.tube([(.4,.6,z-2),(side*1.8,1.0,z),(side*3.6,1.3,z+1.2),end], [.8,.62,.4,.16],steps=5)
        for k in range(4):
            c=end+Vector((rng.uniform(-2,2),rng.uniform(-1.6,1.8),rng.uniform(-.2,.8)))
            for layer in range(3):
                tree.ellipsoid(c+Vector((0,0,layer*.36)),(2.6-layer*.46,1.9-layer*.3,.63),['M_RB_LeafJade','M_RB_LeafOlive','M_RB_LeafLight'][(j+k+layer)%3],wobble=.10)
for x,y,z,s in [(1,1.5,21,3.5),(-2,2,20,2.4),(4,3,20.5,2.8)]:
    tree.ellipsoid((x,y,z),(s,s*.65,1.15),'M_RB_LeafOlive',sides=18,rings=8,wobble=.08)
for i in range(7):
    a=i*.8;tree.tube([(math.cos(a)*2,math.sin(a)*2,.3),(math.cos(a)*1.7,math.sin(a)*1.7,3),(math.cos(a)*1.4,math.sin(a)*1.4,6)], [.022,.035,.015],'M_RB_SapGlow',sides=6,steps=5,flutes=0)
assets.append((tree.finish('SM_RB_AncientTree'),'complex'))

grip=Builder()
for side in (-1,1):
    routes=[([(0,5,3),(side*2.5,3.5,3.8),(side*3.55,.2,4.5),(side*4,-3,2),(side*5.5,-6.5,0)], [1.2,1.1,.8,.65,.025]),
            ([(side*.8,4.7,7),(side*2.4,2.6,8.1),(side*3.4,.1,6.7),(side*3.8,-3,1.5),(side*7.8,-4.9,0)], [.95,.85,.7,.5,.025]),
            ([(0,5.3,1),(side*3.5,3.1,.9),(side*5.7,.8,.45),(side*8.8,-1.2,0)], [1,.65,.36,.02])]
    for points,radii in routes:
        grip.tube(points,radii,steps=6,sides=18)
        glow=[(x+side*r*.4,y-r*.85,z+r*.25) for (x,y,z),r in zip(points,radii)]
        grip.tube(glow,[max(.015,r*.032) for r in radii],'M_RB_SapGlow',sides=6,steps=6,flutes=0)
        for x,y,z in points[1:-1]:
            grip.ellipsoid((x,y,z+.6),(.5,.68,.15),'M_RB_RootMoss')
assets.append((grip.finish('SM_RB_GrippingRoots'),'complex'))

arch=Builder()
arch_points=[(-3.8,0,0),(-3.1,0,1.5),(-2.1,0,3.4),(0,.1,4.15),(2.1,0,3.4),(3.1,0,1.5),(3.8,0,0)]
arch.tube(arch_points,[.72,.68,.56,.49,.6,.75,.82],sides=18,steps=7)
arch.tube([(x,y-r*.98,z+.03) for (x,y,z),r in zip(arch_points,[.72,.68,.56,.49,.6,.75,.82])],[.02,.022,.028,.02,.03,.022,.016],'M_RB_SapGlow',sides=6,steps=7,flutes=0)
for side in (-1,1):
    for i in range(4):
        arch.tube([(side*3.1,0,1.3),(side*(3.5+i*.18),(-1 if i%2 else 1)*.8,.4),(side*(4.2+i*.27),(-1 if i%2 else 1)*(1.5+i*.23),0)],[.35,.21,.018],steps=5)
for x in (-2,-1,0,1,2):arch.ellipsoid((x,.08,4.18-abs(x)*.22),(.6,.54,.16),'M_RB_RootMoss')
arch_obj=arch.finish('SM_RB_RootArch');assets.append((arch_obj,'complex'))
arch_bvh=BVHTree.FromPolygons([v.co for v in arch_obj.data.vertices],[p.vertices[:] for p in arch_obj.data.polygons],all_triangles=True)
clearance=0
for x in (-1.2,-.6,0,.6,1.2):
    for z in (.15,.8,1.6,2.4,2.75):
        assert arch_bvh.ray_cast(Vector((x,-2,z)),Vector((0,1,0)),4)[0] is None,(x,z)
        clearance+=1

root=Builder()
root.tube([(-3.5,0,0),(-2,.2,.5),(0,0,.95),(1.6,-.35,.5),(3.5,0,0)],[.03,.44,.54,.32,.02],steps=6,sides=16)
for side in (-1,1):
    root.tube([(side*.8,0,.7),(side*1.6,.8,.3),(side*2.7,1.6,0)],[.22,.17,.015],steps=5)
root.tube([(-2,.05,.82),(0,-.15,1.4),(1.8,-.35,.75)],[.02,.024,.018],'M_RB_SapGlow',sides=6,steps=6,flutes=0)
assets.append((root.finish('SM_RB_CrawlingRoot'),'complex'))

fungi=Builder()
for x,y,z,r in [(-.28,.1,.58,.34),(.22,0,.82,.41),(.35,.24,.36,.24),(-.15,-.28,.28,.20)]:
    fungi.tube([(x,y,0),(x+.03,y,z*.55),(x,y,z)],[.045,.038,.025],'M_RB_MushroomStem',sides=9,steps=3)
    fungi.ellipsoid((x,y,z),(r,r*.77,.11),'M_RB_MushroomCap',sides=18,rings=6)
assets.append((fungi.finish('SM_RB_GlowMushrooms'),'none'))
moss=Builder()
for i in range(13):
    x=rng.uniform(-.7,.7);y=rng.uniform(-.17,.17);h=rng.uniform(.55,1.55)
    moss.tube([(x,y,1.6),(x+.12,y,1.2),(x+.08,y+.03,1.6-h)],[.095,.08,.006],'M_RB_RootMoss',sides=7,steps=4)
    for j in range(3):moss.ellipsoid((x+.09,y,1.6-h*j/3),(.13,.07,.17),'M_RB_LeafOlive',sides=8,rings=4)
assets.append((moss.finish('SM_RB_MossPendant'),'none'))

infos=[]
for obj,collision in assets:
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    vertices=[v.co for v in obj.data.vertices];low=[min(v[i] for v in vertices) for i in range(3)];high=[max(v[i] for v in vertices) for i in range(3)]
    assert all(math.isfinite(c) for v in vertices for c in v)
    assert all(p.area>1e-10 for p in obj.data.polygons),obj.name
    info=dict(asset_id=obj.name,file=f'ArtSource/Meshes/RootBelltower/{obj.name}.fbx',materials=[m.name for m in obj.data.materials],
              collision=collision,dimensions_m=[high[i]-low[i] for i in range(3)],bounds_min_m=low,bounds_max_m=high,
              triangles=len(obj.data.polygons),vertices=len(vertices),front_axis='-Y',uv_channel=0,normal_import_method='IMPORT_NORMALS_AND_TANGENTS')
    bpy.ops.export_scene.fbx(filepath=str(ROOT/info['file']),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,
        mesh_smooth_type='FACE',path_mode='STRIP',use_tspace=True)
    infos.append(info);obj.hide_render=True;obj.hide_set(True)
roundtrip=[]
for expected in infos:
    before=set(bpy.data.objects);bpy.ops.import_scene.fbx(filepath=str(ROOT/expected['file']),use_custom_normals=True)
    added=set(bpy.data.objects)-before;found=[o for o in added if o.type=='MESH'];assert len(found)==1
    obj=found[0];dims=[max(v.co[i] for v in obj.data.vertices)-min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    error=max(abs(a-b) for a,b in zip(dims,expected['dimensions_m']))
    assert error<.0001 and len(obj.data.polygons)==expected['triangles']
    assert obj.data.has_custom_normals and obj.data.uv_layers.active
    roundtrip.append(dict(asset_id=expected['asset_id'],passed=True,bounds_error_m=error,triangles_preserved=True,normals_preserved=True,uv0_present=True))
    for obj in added:bpy.data.objects.remove(obj,do_unlink=True)
meta=dict(source='ArtSource/Blender/RootBelltowerRoots.blend',script='Scripts/build_rootbelltower_roots.py',units='metres',
          reference='ArtSource/Reference/RootBelltower/Ref_RootBelltowerRoots.png',materials=MATERIALS,assets=infos,
          placement_notes='GrippingRoots shares tower origin. Place AncientTree at tower-local (0,+5,0). RootArch passage runs along source Y.',
          arch_clearance=dict(width_m=2.4,height_m=2.75,ray_count=clearance),fbx_roundtrip_validation=roundtrip)
(ART/'Layout/rootbelltower_roots.json').write_text(json.dumps(meta,indent=2)+'\n')
(ART/'Previews/RootBelltowerRoots_Validation.json').write_text(json.dumps(dict(passed=True,**meta),indent=2)+'\n')
for (obj,_),position in zip(assets,[(-8,5,0),(-8,0,0),(9,1,0),(9,-6,0),(5,-8,0),(7,-8,1)]):
    copy=bpy.data.objects.new('Preview_'+obj.name,obj.data);display.objects.link(copy);copy.location=position
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.03));ground=bpy.context.object
mat=bpy.data.materials.new('PreviewOnlyGround');mat.diffuse_color=(.20,.25,.20,1);ground.data.materials.append(mat)
scene.world=bpy.data.worlds.new('PreviewOnlySky');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.63,.76,.88,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.6
bpy.ops.object.light_add(type='SUN',location=(-20,-30,45));sun=bpy.context.object;sun.rotation_euler=(.5,-.4,-.6);sun.data.energy=2.5;sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(32,-50,36));camera=bpy.context.object
camera.rotation_euler=(Vector((0,0,11))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=52;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
scene.render.filepath=str(ART/'Previews/Blender_RootBelltowerRoots.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/RootBelltowerRoots.blend'))
bpy.ops.render.render(write_still=True)
print('ROOT_BELLTOWER_ROOTS_COMPLETE '+json.dumps([dict(name=i['asset_id'],triangles=i['triangles']) for i in infos]),flush=True)
