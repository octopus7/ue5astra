"""Build a walkable timber fishing pier from the saved detailed reference.

Metres; +X points into the lake. Pile-foot origin Z=0, deck top Z=2.35.
The placement buries the piles at -1.50m: deck +0.85m, ramp foot +0.64m.
"""
import bpy,bmesh,ast,json,math,random
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource';rng=random.Random(1709)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
library=bpy.data.collections.new('01_FishingDockLibrary');scene.collection.children.link(library)
PALETTE={'M_DockWood':'B9905E','M_DockWoodLight':'CAA775','M_DockWoodDark':'80603E','M_DockEnd':'BE996A','M_DockRope':'D2C199','M_DockNail':'59626A'}
tree=ast.parse((ROOT/'Scripts/build_pink_house_assets.py').read_text(encoding='utf-8'))
names={'linear','finish','cube','mesh','bar','cylinder','asset','asset_metadata'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),__file__,'exec'))
materials={}
wood_path=ART/'Textures/T_FishingDockWood.png'
wood_image=bpy.data.images.load(str(wood_path)) if wood_path.exists() else None
for name,h in PALETTE.items():
    m=bpy.data.materials.new(name);m.use_nodes=True;c=tuple(linear(int(h[i:i+2],16)/255) for i in (0,2,4))
    m.diffuse_color=(*c,1);bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*c,1);bs.inputs['Roughness'].default_value=.86
    if name.startswith('M_DockWood') and wood_image:
        t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=wood_image
        mix=m.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
        tint={'M_DockWood':(1,1,1,1),'M_DockWoodLight':(1.12,1.10,1.04,1),'M_DockWoodDark':(.63,.64,.64,1)}[name]
        mix.inputs[2].default_value=tint;m.node_tree.links.new(t.outputs['Color'],mix.inputs[1]);m.node_tree.links.new(mix.outputs[0],bs.inputs['Base Color'])
    materials[name]=m

parts=[]
def prepare(o,axis=1,bevel=0):
    bpy.context.view_layer.objects.active=o
    if bevel:
        mod=o.modifiers.new('Soft timber edges','BEVEL');mod.width=bevel;mod.segments=1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    uv=o.data.uv_layers.new(name='UVMap') if not o.data.uv_layers else o.data.uv_layers.active
    for face in o.data.polygons:
        normal=face.normal;across=min((i for i in range(3) if i!=axis),key=lambda i:abs(normal[i]))
        for li in face.loop_indices:
            v=o.data.vertices[o.data.loops[li].vertex_index].co
            uv.data[li].uv=(v[across]/.34+.17,v[axis]/2+.23)
    parts.append(o);return o
def timber(name,center,size,mat='M_DockWood',axis=1,bevel=.012):
    return prepare(cube(name,center,size,mat),axis,bevel)
def pole(name,a,b,r,mat='M_DockWoodDark',n=16):
    o=cylinder(name,a,b,r,mat,n)
    for f in o.data.polygons:f.use_smooth=len(f.vertices)==4
    return prepare(o,2)
def brace(name,a,b,w=.13):return prepare(bar(name,a,b,w,w,'M_DockWoodDark'),2,.01)
def ring(name,center,radius,thickness,mat):
    bpy.ops.mesh.primitive_torus_add(major_segments=20,minor_segments=5,location=center,major_radius=radius,minor_radius=thickness)
    o=bpy.context.object;o.name=name;finish(o,mat)
    for f in o.data.polygons:f.use_smooth=True
    parts.append(o);return o

# Broad plank seams remain readable from the fixed overhead camera.
for start,end,width in [(0,3.0,1.8),(3.0,6.2,4.0)]:
    count=round((end-start)/.24);step=(end-start)/count
    for i in range(count):
        x=start+(i+.5)*step
        timber('DeckPlank',(x,0,2.305),(step-.012,width,.09),'M_DockWoodLight' if i%5==0 else 'M_DockWood')
        if i%3==0:
            for y in (-width/2+.14,width/2-.14):pole('IronPeg',(x,y,2.351),(x,y,2.355),.013,'M_DockNail',8)
    timber('UnderDeck',(0.5*(start+end),0,2.18),(end-start,width-.08,.15),'M_DockWoodDark',1)
    for y in (-width/2+.09,width/2-.09):timber('LongRim',(0.5*(start+end),y,2.20),(end-start,.18,.24),'M_DockWoodDark',0)
    for x in (start+.13,end-.13):timber('CrossBeam',(x,0,2.13),(.20,width+.18,.23),'M_DockWoodDark')

# Shallow continuous wedge under the sloped planks: no stair at the bank.
verts=[(x,y,z) for x,z in [(-2.4,2.14),(0,2.35)] for y in [-.90,.90]]
verts += [(x,y,z-.14) for x,y,z in verts]
prepare(mesh('RampUnderlay',verts,[(0,1,3,2),(6,7,5,4),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)],'M_DockWoodDark'))
slope=.21/2.4
for i in range(10):
    x=-2.4+(i+.5)*.24;z=2.14+(x+2.4)*slope
    o=timber('RampPlank',(x,0,z-.034),(.23,1.8,.072),'M_DockWoodLight' if i%4==0 else 'M_DockWood')
    o.rotation_euler.y=-math.atan(slope)
for y in (-.94,.94):
    brace('RampEdge',(-2.4,y,2.18),(0,y,2.39),.12)

# Piles, low side rails and rope collars. Fishing edge and centre access stay open.
for x,width in [(0,.99),(1.50,.99),(3.04,2.06),(6.12,2.06)]:
    for y in (-width,width):
        pole('TimberPile',(x,y,0),(x,y,3.20),.15)
        pole('CutPostCap',(x,y,3.20),(x,y,3.245),.163,'M_DockEnd')
        for rad in (.067,.12):ring('EndGrain',(x,y,3.249),rad,.004,'M_DockWoodDark')
        if x in (3.04,6.12):
            for dz in (0,.058,.116):ring('RopeBinding',(x,y,2.98+dz),.16,.025,'M_DockRope')
for y in (-.99,.99):
    for z in (2.78,3.06):brace('ApproachRail',(0,y,z),(2.91,y,z),.10)
    # Short landing post does not block entry from the dirt path.
    pole('RampPost',(-2.32,y,1.98),(-2.32,y,2.88),.12)
    brace('SlopeRail',(-2.32,y,2.82),(0,y,3.08),.095)
for y in (-2.06,2.06):
    for z in (2.78,3.06):brace('PlatformRail',(3.08,y,z),(6.07,y,z),.11)
    brace('UnderDiagonal',(3.08,y,1.45),(4.2,y,2.12),.14)
    brace('UnderDiagonal',(6.07,y,1.45),(5.0,y,2.12),.14)

dock=asset('SM_FishingDock',parts);dock['front_axis']='+X'
spec=asset_metadata(dock);spec['front_axis_blender']='+X';spec['origin']='pile bottom, deck surface at local Z 2.35m';spec['normal_import_method']='IMPORT_NORMALS_AND_TANGENTS'
props={n:{'roughness':.86,'metallic':0,'specular':.15} for n in PALETTE}
for n,tint in [('M_DockWood',[1,1,1]),('M_DockWoodLight',[1.12,1.10,1.04]),('M_DockWoodDark',[.63,.64,.64])]:
    props[n].update({'base_color_texture':'Textures/T_FishingDockWood.png','tint_linear':tint})
meta={'source':'ArtSource/Blender/FishingDock.blend','script':'Scripts/build_fishing_dock.py','reference':'ArtSource/Reference/Ref_FishingDock.png','palette_srgb_hex':PALETTE,'material_properties':props,'assets':[spec],
      'deck_surface_local_z_m':2.35,'bank_approach_local':[-2.4,0,2.14],'walkway_bounds_xy_m':[0,3,-.90,.90],'platform_bounds_xy_m':[3,6.2,-2,2],'placement_ue_m':[4,28,-1.50],'forward_axis':'+X'}
(ART/'Layout/fishing_dock.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
preview=bpy.data.objects.new('Preview_FishingDock',dock.data);scene.collection.objects.link(preview)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.02));floor=bpy.context.object
mat=bpy.data.materials.new('DockPreviewGround');mat.diffuse_color=(.28,.30,.31,1);floor.data.materials.append(mat)
scene.world=bpy.data.worlds.new('DockPreviewSky');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.52,.66,.85,1);bg.inputs['Strength'].default_value=.65
bpy.ops.object.light_add(type='SUN',location=(-5,-7,10));sun=bpy.context.object;sun.rotation_euler=(.5,-.4,-.6);sun.data.energy=2.5;sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-9,-9,11));cam=bpy.context.object;cam.rotation_euler=(Vector((1.8,0,1.6))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=11;scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(ART/'Previews/Blender_FishingDock.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/FishingDock.blend'));bpy.ops.render.render(write_still=True)
print('FISHING DOCK COMPLETE '+json.dumps(spec))
