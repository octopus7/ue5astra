"""Independent cozy fishing kit, metres, local +X faces the lake.

Run Blender --background --factory-startup --python this_file.py.
Only the dedicated FishingProps assets, metadata, source and preview are written.
"""
import ast
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
for folder in ('Blender','Meshes','Layout','Previews'):
    (ART/folder).mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
library=bpy.data.collections.new('01_FishingPropsLibrary')
presentation=bpy.data.collections.new('02_FishingPropsPresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)
PALETTE={'M_Fishing_Wood':'A77C45','M_Fishing_WoodLight':'CBA770',
         'M_Fishing_WoodDark':'796047','M_Fishing_Cream':'E7DABB',
         'M_Fishing_Sage':'869C7B','M_Fishing_Teal':'4B858A',
         'M_Fishing_Metal':'78999F','M_Fishing_Coral':'CE806A',
         'M_Fishing_FishSilver':'BAD0CA','M_Fishing_Water':'5AABB5',
         'M_Fishing_Dark':'394F59'}
geometry_source=ROOT/'Scripts'/'build_pink_house_assets.py'
tree=ast.parse(geometry_source.read_text(encoding='utf-8'))
helpers={'linear','finish','cube','mesh','bar','cylinder'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in helpers],type_ignores=[]),str(geometry_source),'exec'))
materials={}
material_properties={}
for name,h in PALETTE.items():
    color=tuple(linear(int(h[i:i+2],16)/255) for i in (0,2,4))
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    mat.diffuse_color=(*color,1)
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    metallic=.25 if name in ('M_Fishing_Teal','M_Fishing_Metal') else 0
    roughness=.38 if metallic else (.18 if name=='M_Fishing_Water' else .84)
    shader.inputs['Roughness'].default_value=roughness
    shader.inputs['Metallic'].default_value=metallic
    shader.inputs['Specular IOR Level'].default_value=.25
    materials[name]=mat
    material_properties[name]={'roughness':roughness,'metallic':metallic,'specular':.25,'emissive_strength':0}


def bevel(obj,width=.015,segments=2):
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('SoftWoodEdges','BEVEL')
    mod.width=width
    mod.segments=segments
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def block(name,p,s,mat,rotation=(0,0,0),edge=.012):
    return bevel(cube(name,p,s,mat,rotation),edge,2)


def tube(name,points,radii,mat,segments=8):
    points=[Vector(p) for p in points]
    first_direction=(points[1]-points[0]).normalized()
    plane_normal=None
    for candidate in points[2:]:
        cross=first_direction.cross(candidate-points[0])
        if cross.length>1e-6:
            plane_normal=cross.normalized()
            break
    verts=[]
    for i,point in enumerate(points):
        direction=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
        across=plane_normal.copy() if plane_normal is not None else direction.cross(Vector((0,1,0)))
        if across.length<.1:
            across=direction.cross(Vector((1,0,0)))
        across.normalize()
        other=direction.cross(across).normalized()
        radius=radii[i] if isinstance(radii,(tuple,list)) else radii
        verts.extend(tuple(point+radius*(math.cos(k*math.tau/segments)*across+math.sin(k*math.tau/segments)*other)) for k in range(segments))
    faces=[tuple(range(segments-1,-1,-1)),tuple(range((len(points)-1)*segments,len(points)*segments))]
    for ring in range(len(points)-1):
        for k in range(segments):
            following=(k+1)%segments
            faces.append((ring*segments+k,ring*segments+following,(ring+1)*segments+following,(ring+1)*segments+k))
    obj=mesh(name,verts,faces,mat)
    for face in obj.data.polygons:
        face.use_smooth=len(face.vertices)==4
    return obj


def ellipsoid(name,p,s,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1,location=p)
    obj=bpy.context.object
    obj.name=name
    obj.scale=s
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for face in obj.data.polygons:
        face.use_smooth=True
    return finish(obj,mat)


def cup(name,p,r,h,mat,n=20):
    profile=[(.80,0),(.84,.07),(1,1),(.90,1),(.72,.13)]
    vertices=[(p[0]+r*rad*math.cos(k*math.tau/n),p[1]+r*rad*math.sin(k*math.tau/n),p[2]+h*z) for rad,z in profile for k in range(n)]
    faces=[tuple(range(n-1,-1,-1)),tuple(range(4*n,5*n))]
    for j in range(4):
        for k in range(n):
            faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
    obj=mesh(name,vertices,faces,mat)
    for face in obj.data.polygons:
        face.use_smooth=len(face.vertices)==4 and face.index not in range(2+2*n,2+3*n)
    return obj


def cloth(name,nx,ny,point,thickness,mat):
    top=[point(i/(nx-1),j/(ny-1)) for i in range(nx) for j in range(ny)]
    # Thick enough to remain a closed solid, including its soft curved edges.
    vertices=top+[(x,y,z-thickness) for x,y,z in top]
    count=len(top)
    faces=[]
    for i in range(nx-1):
        for j in range(ny-1):
            a=i*ny+j; q=(a,a+1,a+ny+1,a+ny)
            faces.append(q)
            faces.append(tuple(v+count for v in reversed(q)))
    boundary=list(range(ny))+[i*ny+ny-1 for i in range(1,nx)]+list(range((nx-1)*ny+ny-2,(nx-1)*ny-1,-1))+[i*ny for i in range(nx-2,0,-1)]
    for i,a in enumerate(boundary):
        b=boundary[(i+1)%len(boundary)]
        faces.append((a,b,b+count,a+count))
    obj=mesh(name,vertices,faces,mat)
    for face in obj.data.polygons:
        face.use_smooth=True
    return obj


def asset(name,parts):
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=name
    scene.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    bottom=min(v.co.z for v in obj.data.vertices)
    for vertex in obj.data.vertices:
        vertex.co.z-=bottom
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    library.objects.link(obj)
    # A conventional packed UV is retained for later art revisions, even for palette materials.
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.012)
    bpy.ops.object.mode_set(mode='OBJECT')
    triangulate=obj.modifiers.new('ExportStableTriangles','TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    obj['asset_id']=name
    obj['front_axis']='+X'
    obj['collision']='none'
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{name}.fbx'),
        use_selection=True,object_types={'MESH'},apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True,
        path_mode='STRIP',use_tspace=True)
    obj.hide_render=True
    obj.hide_set(True)
    return obj


# Rod stand: broad stable base, two separate reels, curved rods pointing local +X.
p=[]
for y in (-.48,.48):
    p.append(block('StandFoot',(0,y,.06),(.72,.14,.12),'M_Fishing_Wood'))
    p.append(block('StandUpright',(.15,y,.34),(.12,.13,.63),'M_Fishing_Wood'))
    p.append(bevel(bar('StandRearBrace',(-.28,y,.11),(.15,y,.60),.09,.095,'M_Fishing_WoodDark'),.01))
p.append(block('StandCrossBrace',(-.20,0,.16),(.12,1.06,.12),'M_Fishing_WoodLight'))
p.append(block('RodCradle',(.15,0,.60),(.16,1.06,.12),'M_Fishing_WoodLight'))
for y in (-.25,.25):
    p.append(tube('CradleU',[(.10,y-.07,.66),(.10,y-.07,.72),(.10,y+.07,.72),(.10,y+.07,.66)],.016,'M_Fishing_Teal',6))
    handle_start=Vector((-.45,y,.22)); handle_end=Vector((.02,y,.64))
    p.append(cylinder('CreamRodGrip',handle_start,handle_end,.047,'M_Fishing_Cream',12))
    direction=(handle_end-handle_start).normalized()
    for t in (.10,.28,.47,.66,.84):
        center=handle_start.lerp(handle_end,t)
        p.append(cylinder('GripBinding',center-direction*.009,center+direction*.009,.049,'M_Fishing_WoodLight',12))
    rod_points=[]
    for i in range(14):
        t=i/13
        rod_points.append((.01+1.54*t,y,.63+1.58*t-.53*t*t))
    p.append(tube('CurvedSageRod',rod_points,[.024-.013*i/13 for i in range(14)],'M_Fishing_Sage',8))
    # The reel sits beside the grip, readable from the elevated camera.
    p.append(cylinder('ReelFoot',(-.17,y,.45),(-.17,y-.07,.37),.025,'M_Fishing_Dark',8))
    p.append(ellipsoid('ReelBody',(-.17,y-.08,.36),(.087,.047,.082),'M_Fishing_Teal'))
    p.append(cylinder('ReelSpool',(-.10,y-.08,.37),(-.01,y-.08,.44),.065,'M_Fishing_Metal',12))
    p.append(tube('ReelCrank',[(-.19,y-.12,.34),(-.22,y-.19,.31),(-.12,y-.19,.27)],.014,'M_Fishing_Teal',6))
    p.append(cylinder('ReelCrankGrip',(-.12,y-.19,.26),(-.12,y-.25,.26),.023,'M_Fishing_Cream',8))
    for t in (.28,.59,.88):
        x=.01+1.54*t; z=.63+1.58*t-.53*t*t
        p.append(cylinder('RodGuideBand',(x-.015,y,z-.015),(x+.015,y,z+.015),.030*(1-t*.45),'M_Fishing_Metal',8))
    tip=rod_points[-1]
    p.append(tube('ShortDisplayLine',[tip,(tip[0],y,tip[2]-.21)],.0035,'M_Fishing_Cream',5))
    float_z=tip[2]-.25
    p.append(ellipsoid('FloatCream',(tip[0],y,float_z-.013),(.032,.032,.040),'M_Fishing_Cream'))
    p.append(ellipsoid('FloatCoral',(tip[0],y,float_z+.022),(.033,.033,.025),'M_Fishing_Coral'))
rods=asset('SM_FishingRodStand',p)

# Low folding chair, canvas seat sags softly; back is -X so sitting direction is +X.
p=[]
for y in (-.32,.32):
    p.append(bevel(bar('ChairCrossLegA',(-.32,y,.035),(.27,y,.45),.072,.070,'M_Fishing_Wood'),.012))
    p.append(bevel(bar('ChairCrossLegB',(.32,y,.035),(-.28,y,.72),.072,.070,'M_Fishing_Wood'),.012))
    p.append(bevel(bar('ChairBackSupport',(-.17,y,.37),(-.35,y,.83),.072,.075,'M_Fishing_WoodLight'),.013))
    p.append(cylinder('ChairPivot',(-.015,y-.045,.30),(-.015,y+.045,.30),.052,'M_Fishing_Metal',12))
for x,z in ((-.30,.12),(.30,.12),(.23,.43),(-.18,.48)):
    p.append(cylinder('ChairCrossbar',(x,-.34,z),(x,.34,z),.033,'M_Fishing_WoodLight',10))
p.append(cloth('CreamCanvasSeat',6,7,lambda u,v:(-.18+.41*u,-.30+.60*v,.445-.058*math.sin(math.pi*v)*math.sin(math.pi*u)),.013,'M_Fishing_Cream'))
p.append(cloth('SageCanvasBack',4,7,lambda u,v:(-.22-.105*u+.021*math.sin(math.pi*v),-.30+.60*v,.56+.235*u),.014,'M_Fishing_Sage'))
for y in (-.295,.295):
    p.append(tube('SeatCanvasHem',[(-.18+.41*i/6,y,.448) for i in range(7)],.009,'M_Fishing_WoodLight',6))
    p.append(tube('BackCanvasHem',[(-.22-.105*i/4,y,.56+.235*i/4) for i in range(5)],.008,'M_Fishing_Cream',6))
chair=asset('SM_FishingChair',p)

# Water bucket with two little silver fish. All water/fish remain below the rim.
p=[cup('TealFishBucket',(0,0,0),.31,.45,'M_Fishing_Teal',20),
   cylinder('BucketWater',(0,0,.316),(0,0,.333),.265,'M_Fishing_Water',24)]
for z,r in ((.045,.259),(.424,.304)):
    points=[(r*math.cos(i*math.tau/24),r*math.sin(i*math.tau/24),z) for i in range(25)]
    p.append(tube('BucketHoop',points,.013,'M_Fishing_Metal',6))
handle=[(.307*math.cos(i*math.pi/16),0,.42+.265*math.sin(i*math.pi/16)) for i in range(17)]
p.append(tube('BucketBail',handle,.012,'M_Fishing_Metal',8))
p.append(cylinder('BucketWoodGrip',(-.085,0,.677),(.085,0,.677),.027,'M_Fishing_WoodLight',10))
for index,(cx,cy,angle) in enumerate(((-.045,-.105,.32),(.04,.105,-.25))):
    fishparts=[]
    fishparts.append(ellipsoid('FishBody',(0,0,.367),(.127,.043,.029),'M_Fishing_FishSilver'))
    fishparts.append(ellipsoid('FishBack',(0,0,.384),(.102,.027,.014),'M_Fishing_Metal'))
    fishparts.append(mesh('FishTail',[(-.09,-.012,.36),(-.18,-.064,.362),(-.16,0,.382),(-.18,.064,.362),(-.09,.012,.36),
                                        (-.09,-.012,.372),(-.18,-.064,.374),(-.16,0,.394),(-.18,.064,.374),(-.09,.012,.372)],
                               [(4,3,2,1,0),(5,6,7,8,9),(0,1,6,5),(1,2,7,6),(2,3,8,7),(3,4,9,8),(4,0,5,9)],'M_Fishing_Metal'))
    for sign in (-1,1):
        fishparts.append(ellipsoid('FishEye',(.086,sign*.030,.381),(.009,.006,.005),'M_Fishing_Dark'))
    for part in fishparts:
        # Geometry helpers produce world-space origins; apply the whole fish group transform.
        bpy.ops.object.select_all(action='DESELECT')
        part.select_set(True); bpy.context.view_layer.objects.active=part
        scene.cursor.location=(0,0,0)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        part.rotation_euler.z=angle
        part.location.x=cx; part.location.y=cy
    p.extend(fishparts)
bucket=asset('SM_FishBucket',p)

# Tackle box opened towards +X, only a few chunky useful items inside.
p=[block('TackleBase',(0,0,.035),(.47,.66,.07),'M_Fishing_WoodDark')]
for y in (-.31,.31):
    p.append(block('TackleSide',(0,y,.17),(.47,.055,.28),'M_Fishing_Teal'))
for x in (-.21,.21):
    p.append(block('TackleEnd',(x,0,.17),(.055,.61,.28),'M_Fishing_Wood'))
for y in (-.31,.31):
    p.append(block('TackleRim',(0,y,.31),(.49,.04,.04),'M_Fishing_WoodLight',edge=.006))
for x in (-.22,.22):
    p.append(block('TackleRim',(x,0,.31),(.04,.64,.04),'M_Fishing_WoodLight',edge=.006))
p.append(block('TackleDivider',(0,.07,.17),(.39,.025,.20),'M_Fishing_WoodLight',edge=.004))
# Upright lid tilts back slightly, leaving the compartment readable from above.
lid_x=-.31; lid_z=.53; lid_tilt=math.radians(-12)
p.append(block('OpenLid',(lid_x,0,lid_z),(.055,.66,.45),'M_Fishing_Teal',(0,lid_tilt,0),edge=.012))
for y in (-.31,.31):
    p.append(block('LidWoodSide',(lid_x+.037,y,lid_z),(.035,.04,.45),'M_Fishing_WoodLight',(0,lid_tilt,0),edge=.006))
for z in (.325,.73):
    p.append(block('LidWoodEdge',(lid_x+.036,0,z),(.045,.64,.04),'M_Fishing_WoodLight',edge=.006))
for y in (-.22,.22):
    p.append(cylinder('LidHinge',(-.225,y-.035,.31),(-.225,y+.035,.31),.028,'M_Fishing_Metal',10))
    p.append(block('HandlePlate',(.247,y,.19),(.026,.06,.07),'M_Fishing_Metal',edge=.005))
p.append(tube('BoxRopeHandle',[(.27,-.22,.19),(.33,-.15,.12),(.345,0,.095),(.33,.15,.12),(.27,.22,.19)],.014,'M_Fishing_Cream',8))
p.append(block('TackleLatch',(.246,0,.30),(.025,.08,.07),'M_Fishing_Metal',edge=.005))
for index,y in enumerate((-.21,-.09,.03)):
    x=-.256
    p.append(ellipsoid('StoredFloatCream',(x,y,.57),(.024,.035,.065),'M_Fishing_Cream'))
    p.append(ellipsoid('StoredFloatCap',(x+.01,y,.61),(.025,.035,.025),'M_Fishing_Coral' if index<2 else 'M_Fishing_Sage'))
    p.append(cylinder('FloatStem',(x,y,.63),(x,y,.69),.007,'M_Fishing_WoodLight',6))
for y in (-.18,-.005):
    p.append(cup('BaitTin',(.025,y,.075),.068,.093,'M_Fishing_Metal',14))
    p.append(cylinder('BaitTinContents',(.025,y,.14),(.025,y,.151),.057,'M_Fishing_WoodLight' if y<-.1 else 'M_Fishing_Coral',14))
    for k in range(4):
        p.append(ellipsoid('BaitPellet',(.025+.028*math.cos(k*math.pi/2),y+.027*math.sin(k*math.pi/2),.160),(.016,.011,.013),'M_Fishing_Cream' if y<-.1 else 'M_Fishing_Coral'))
for y in (.15,.235):
    p.append(ellipsoid('SmallFishingWeight',(.04,y,.11),(.035,.025,.032),'M_Fishing_Metal'))
    p.append(tube('BluntStoredHook',[(-.255,y,.64),(-.235,y,.57),(-.222,y,.53),(-.208,y,.548)],.006,'M_Fishing_Metal',6))
tackle=asset('SM_FishingTackleBox',p)
assets=[rods,chair,bucket,tackle]


def asset_metadata(obj):
    bpy.context.view_layer.update()
    bounds=[Vector(corner) for corner in obj.bound_box]
    bm=bmesh.new(); bm.from_mesh(obj.data)
    non_manifold=sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    degenerate=sum(face.area<=1e-12 for face in obj.data.polygons)
    assert not non_manifold and not degenerate, f'{obj.name}: open={non_manifold}, degenerate={degenerate}'
    assert all(math.isfinite(value) for vertex in obj.data.vertices for value in vertex.co)
    assert abs(min(v.z for v in bounds))<1e-6
    return {'asset_id':obj.name,'file':f'ArtSource/Meshes/{obj.name}.fbx','collision':'none',
            'front_axis_blender':'+X','origin':'ground at (0, 0, 0)',
            'dimensions_m':[round(x,6) for x in obj.dimensions],
            'bounds_min_m':[round(min(v[i] for v in bounds),6) for i in range(3)],
            'bounds_max_m':[round(max(v[i] for v in bounds),6) for i in range(3)],
            'vertices':len(obj.data.vertices),'triangles':sum(len(face.vertices)-2 for face in obj.data.polygons),
            'material_slots':[slot.material.name for slot in obj.material_slots],
            'validation':{'finite_vertices':True,'ground_origin':True,'non_manifold_edges':non_manifold,'degenerate_faces':degenerate,'uv_channel':0}}


asset_info=[asset_metadata(obj) for obj in assets]
roundtrip=[]
for original,expected in zip(assets,asset_info):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ART/'Meshes'/f'{original.name}.fbx'),use_custom_normals=True)
    imported=[obj for obj in set(bpy.data.objects)-before if obj.type=='MESH']
    assert len(imported)==1
    obj=imported[0]
    bpy.context.view_layer.update()
    dimension_error=max(abs(obj.dimensions[i]-expected['dimensions_m'][i]) for i in range(3))
    assert dimension_error<1e-5
    assert len(obj.data.materials)==len(original.data.materials)
    uv=obj.data.uv_layers.active
    assert uv is not None and len(uv.data)>0
    assert all(math.isfinite(value) for loop in uv.data for value in loop.uv)
    assert obj.data.has_custom_normals
    bm=bmesh.new(); bm.from_mesh(obj.data)
    non_manifold=sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert not non_manifold
    roundtrip.append({'asset_id':original.name,'dimension_error_m':dimension_error,'uv_loops':len(uv.data),
                      'finite_uv':True,'custom_normals_imported':True,'non_manifold_edges':0,
                      'material_slots':len(obj.data.materials)})
    for item in set(bpy.data.objects)-before:
        bpy.data.objects.remove(item,do_unlink=True)
metadata={'source':'ArtSource/Blender/FishingProps.blend','script':'Scripts/build_fishing_props.py',
          'reference':'ArtSource/Reference/Ref_FishingProps.png','units':'metres',
          'unreal_conversion':'(Blender X, -Blender Y, Blender Z) * 100; forward +X',
          'palette_srgb_hex':PALETTE,'material_properties':material_properties,
          'assets':asset_info,'fbx_roundtrip_validation':roundtrip,
          'placement_notes':'Local +X is towards the lake. Put rod stand near the outer +X deck edge; its short 0.21 m display lines remain on the asset. Chair sits 0.65–0.9 m behind the stand (-X), with bucket at its side and tackle box towards the dry shore side. All props are non-blocking decoration; keep a 1.0 m wide walking lane on the deck.'}
(ART/'Layout'/'fishing_props.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
(ART/'Previews'/'FishingProps_Validation.json').write_text(json.dumps({'assets':asset_info,'fbx_roundtrip_validation':roundtrip},indent=2)+'\n',encoding='utf-8')

for original,location,angle in ((rods,(.15,1.0,0),0),(chair,(-.7,-.68,0),0),
                                (bucket,(-.15,2.2,0),0),(tackle,(-1.2,.55,0),0)):
    obj=bpy.data.objects.new('Preview_'+original.name,original.data)
    presentation.objects.link(obj)
    obj.location=location
    obj.rotation_euler.z=math.radians(angle)
ground_material=bpy.data.materials.new('FishingPreviewGround')
ground_material.use_nodes=True
ground_material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.59,.57,.44,1)
ground_material.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.93
bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-.015))
bpy.context.object.data.materials.append(ground_material)
bpy.context.object.name='PreviewGround'
scene.world=bpy.data.worlds.new('FishingPreviewSky')
scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.65,.73,.9,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.65
bpy.ops.object.light_add(type='SUN',location=(-7,-8,12))
sun=bpy.context.object
sun.name='SoftSun_50deg'
sun.rotation_euler=(.45,-.5,-.6)
sun.data.energy=2.6
sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(7,-9,10))
camera=bpy.context.object
camera.rotation_euler=(Vector((0,.72,.58))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=5.0
scene.camera=camera
scene.render.engine='CYCLES'
scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.render.resolution_x=1700
scene.render.resolution_y=1400
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ART/'Previews'/'Blender_FishingProps.png')
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'FishingProps.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA FISHING PROPS COMPLETE '+json.dumps(asset_info))
