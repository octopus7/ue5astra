"""Five broad-plane forest boulders with softened fracture edges, never subdivided spheres.

Read exact legacy bounds from the preserved 42-vertex cages in ForestSmoothRocks.blend.
Write only the independent ForestFracturedRocks source, FBXs, metadata and preview.
Run Blender --background --factory-startup --python this_file.py.
"""
import bpy
import bmesh
import itertools
import json
import math
from pathlib import Path
from mathutils import Vector,Matrix

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
SOURCE=ART/'Blender'/'ForestSmoothRocks.blend'
TEXTURE_PATH=ART/'Textures'/'T_AnimeForestRockPaint.png'
REFERENCE=ART/'Reference'/'Ref_FracturedForestRocks.png'
assert SOURCE.is_file() and TEXTURE_PATH.is_file()
assert REFERENCE.is_file(),'Wait for the approved fractured-rock detail reference before final generation'
for folder in ('Blender','Meshes','Layout','Previews'):
    (ART/folder).mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
library=bpy.data.collections.new('01_FracturedForestRockLibrary')
presentation=bpy.data.collections.new('02_FracturedRockPresentation')
baseline=bpy.data.collections.new('03_PreservedOriginal42VertexCages')
for collection in (library,presentation,baseline):
    scene.collection.children.link(collection)

material=bpy.data.materials.new('M_ForestRockPaint')
material.use_nodes=True
material.diffuse_color=(.32,.35,.29,1)
shader=material.node_tree.nodes.get('Principled BSDF')
shader.inputs['Roughness'].default_value=.88
shader.inputs['Metallic'].default_value=0
shader.inputs['Specular IOR Level'].default_value=.2
image=bpy.data.images.load(str(TEXTURE_PATH))
image.name='T_AnimeForestRockPaint'
image.colorspace_settings.name='sRGB'
image.pack()
texture=material.node_tree.nodes.new('ShaderNodeTexImage')
texture.image=image
texture.extension='REPEAT'
texture.location=(-400,80)
uv_node=material.node_tree.nodes.new('ShaderNodeUVMap')
uv_node.uv_map='UVMap'
uv_node.location=(-610,80)
material.node_tree.links.new(uv_node.outputs['UV'],texture.inputs['Vector'])
material.node_tree.links.new(texture.outputs['Color'],shader.inputs['Base Color'])

with bpy.data.libraries.load(str(SOURCE),link=False) as (source,loaded):
    loaded.objects=sorted(name for name in source.objects if name.startswith('SOURCE_CAGE_SM_MossRock_'))
assert len(loaded.objects)==5
cages=loaded.objects
for cage in cages:
    assert len(cage.data.vertices)==42
    baseline.objects.link(cage)
    cage.hide_render=True
    cage.hide_set(True)


def bounds(obj):
    return [[min(v.co[i] for v in obj.data.vertices) for i in range(3)],
            [max(v.co[i] for v in obj.data.vertices) for i in range(3)]]


def match_bounds(obj,target):
    current=bounds(obj)
    for vertex in obj.data.vertices:
        for axis in range(3):
            t=(vertex.co[axis]-current[0][axis])/(current[1][axis]-current[0][axis])
            vertex.co[axis]=target[0][axis]+t*(target[1][axis]-target[0][axis])
    obj.data.update()


def make_mesh(name,vertices,faces):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    library.objects.link(obj)
    mesh.materials.append(material)
    for face in mesh.polygons:
        face.use_smooth=True
    return obj


def clipped_polyhedron(name,planes):
    # Intersect designed half-spaces. Each support plane produces one broad polygon,
    # avoiding random triangulation in the shape itself.
    constraints=[(Vector(n),float(d)) for n,d in planes]
    vertices=[]
    for triple in itertools.combinations(constraints,3):
        matrix=Matrix([p[0] for p in triple])
        if abs(matrix.determinant())<1e-6:
            continue
        p=matrix.inverted()@Vector([v[1] for v in triple])
        if all(n.dot(p)<=d+1e-5 for n,d in constraints):
            if not any((p-q).length<1e-5 for q in vertices):
                vertices.append(p)
    faces=[]
    for normal,distance in constraints:
        indices=[i for i,p in enumerate(vertices) if abs(normal.dot(p)-distance)<3e-5]
        if len(indices)<3:
            continue
        center=sum((vertices[i] for i in indices),Vector())/len(indices)
        n=normal.normalized()
        u=n.cross(Vector((0,0,1)))
        if u.length<.1:
            u=n.cross(Vector((0,1,0)))
        u.normalize(); v=n.cross(u)
        indices.sort(key=lambda i:math.atan2((vertices[i]-center).dot(v),(vertices[i]-center).dot(u)))
        faces.append(tuple(indices))
    return make_mesh(name,[tuple(v) for v in vertices],faces)


def stepped_stone(name,outline,levels,slant):
    # Homothetic, offset polygon rings retain planar side patches and form one solid.
    # levels = z, scale_x, scale_y, offset_x, offset_y.
    count=len(outline)
    vertices=[]
    for z,sx,sy,dx,dy in levels:
        for px,py in outline:
            x=px*sx+dx; y=py*sy+dy
            vertices.append((x,y,z+slant[0]*x+slant[1]*y))
    faces=[tuple(range(count-1,-1,-1)),tuple(range((len(levels)-1)*count,len(levels)*count))]
    for level in range(len(levels)-1):
        for i in range(count):
            j=(i+1)%count
            faces.append((level*count+i,level*count+j,(level+1)*count+j,(level+1)*count+i))
    return make_mesh(name,vertices,faces)


def cut_major_split(obj,center_x,diagonal,depth_z,end_y=2.5):
    # A wide, shallow geological joint: two slanted walls meet below the surface,
    # and the solid remains joined underneath. No separate floating rock pieces.
    vertices=[]
    for y in (-2.5,end_y):
        x=center_x+diagonal*y
        vertices.extend([(x-.018,y,depth_z),(x+.018,y,depth_z),
                         (x+.28,y,2.2),(x-.13,y,2.2)])
    cutter=make_mesh('TemporaryMajorSplit',vertices,
        [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active=obj
    boolean=obj.modifiers.new('SingleMajorGeologicalJoint','BOOLEAN')
    boolean.operation='DIFFERENCE'; boolean.solver='EXACT'; boolean.object=cutter
    bpy.ops.object.modifier_apply(modifier=boolean.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    return obj


def form(index):
    name=f'SM_FracturedForestRock_{index:02}'
    if index==1:
        return clipped_polyhedron(name,[
            ((1,.12,.12),1.02),((-1,.06,-.02),1.00),((.04,1,.08),.95),((-.04,-1,.04),.95),
            ((.12,-.15,1),.80),((.02,.03,-1),.79),
            ((1,1,.03),1.48),((-1,1,.09),1.45),((-1,-1,.12),1.34),((1,-1,.05),1.49),
            ((.62,.3,1),1.12),((-.55,-.05,1),1.12)])
    if index==2:
        wedge=clipped_polyhedron(name,[
            ((1,.10,.16),1.06),((-1,-.12,-.08),1.00),((.05,1,.05),.98),((-.06,-1,.1),.96),
            ((-.58,.08,1),.56),((.04,.06,-1),.78),
            ((1,1,.06),1.48),((-1,1,.15),1.38),((-1,-1,.08),1.35),((1,-1,.20),1.45),
            ((.13,.70,1),1.03)])
        return cut_major_split(wedge,.40,.21,.32,end_y=.26)
    outline=[(-1,-.57),(-.78,-.96),(.37,-1.02),(.95,-.67),(1.04,.20),(.68,.93),(-.40,1.02),(-1.02,.45)]
    if index==3:
        return stepped_stone(name,outline,[
            (-.74,.90,.90,-.04,.01),(-.51,1.00,1.00,0,0),
            (-.06,1.00,1.00,0,0),(.025,.92,.93,.04,.01),
            (.15,1.025,.99,.025,.02),(.61,.95,.91,.10,.01),(.73,.84,.86,.08,.03)],(.11,-.12))
    if index==4:
        leaning=clipped_polyhedron(name,[
            ((1,.10,-.30),1.02),((-1,-.07,.34),.91),((.02,1,.19),.91),((-.06,-1,-.11),.94),
            ((.25,-.42,1),.74),((.03,.06,-1),.80),
            ((1,1,-.05),1.38),((-1,1,.20),1.32),((-1,-1,.11),1.39),((1,-1,-.08),1.37),
            ((.25,.70,1),1.18)])
        return cut_major_split(leaning,.04,.23,.15)
    # Broad lower shoulder, compact offset upper crown and a generous broken ledge.
    return stepped_stone(name,outline,[
        (-.77,.87,.86,-.07,0),(-.50,1.02,1.00,-.07,0),
        (.09,1.02,1.00,-.07,0),(.27,.81,.80,.10,.11),
        (.37,.74,.77,.20,.15),(.74,.70,.73,.25,.20)],(.12,.045))


def finish_shape(obj,target,index):
    match_bounds(obj,target)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    base_faces=len(obj.data.polygons)
    bevel=obj.modifiers.new('SoftFractureEdges','BEVEL')
    bevel.width=(.064,.062,.052,.058,.071)[index-1]
    bevel.segments=3
    bevel.affect='EDGES'
    bevel.limit_method='ANGLE'
    bevel.angle_limit=math.radians(12)
    bevel.use_clamp_overlap=True
    bevel.harden_normals=True
    bevel.face_strength_mode='FSTR_AFFECTED'
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    welded_vertices=0
    if index==4:
        # At the bottom of the narrow joint, opposite bevel strips can end at
        # positions differing by one float ULP. Weld those duplicate endpoints
        # before UVs/normals; otherwise UE drops four microscopic triangles.
        bm=bmesh.new(); bm.from_mesh(obj.data)
        original_count=len(bm.verts)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
        welded_vertices=original_count-len(bm.verts)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(obj.data); bm.free()
    obj['microscopic_bevel_vertices_welded']=welded_vertices
    match_bounds(obj,target)
    for face in obj.data.polygons:
        face.use_smooth=True
        face.material_index=0
    # Keep the top and all broad visible faces together in a continuous UV island.
    cutoff=target[0][2]+.24*(target[1][2]-target[0][2])
    bm=bmesh.new(); bm.from_mesh(obj.data)
    for edge in bm.edges:
        edge.seam=len(edge.link_faces)==2 and ((edge.link_faces[0].calc_center_median().z<cutoff)!=(edge.link_faces[1].calc_center_median().z<cutoff))
    bm.to_mesh(obj.data); bm.free()
    obj.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED',margin=.025)
    bpy.ops.uv.pack_islands(rotate=True,margin=.035)
    bpy.ops.object.mode_set(mode='OBJECT')
    weighted=obj.modifiers.new('BroadPlaneWeightedNormals','WEIGHTED_NORMAL')
    weighted.mode='FACE_AREA_WITH_ANGLE'
    weighted.weight=65
    weighted.keep_sharp=False
    weighted.use_face_influence=True
    bpy.ops.object.modifier_apply(modifier=weighted.name)
    triangulate=obj.modifiers.new('PreserveNormalsForFBX','TRIANGULATE')
    if hasattr(triangulate,'keep_custom_normals'):
        triangulate.keep_custom_normals=True
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    obj.data.update(); bpy.context.view_layer.update()
    obj['asset_id']=obj.name
    obj['original_asset_id']=f'SM_MossRock_{index:02}'
    obj['collision']='complex'
    obj['form']=('blunt block','broad wedge','layered slab','leaning split','shoulder boulder')[index-1]
    return base_faces


def engine_triangle_quality(mesh):
    # Mirror StaticMeshBuilder's PointsEqual test in the final centimetre space.
    # UE 5.7 UE_THRESH_POINTS_ARE_SAME is 0.00002 cm per coordinate.
    threshold_cm=.00002
    degenerate_count=0; edge_lengths=[]
    for face in mesh.polygons:
        assert len(face.vertices)==3
        positions=[mesh.vertices[i].co*100 for i in face.vertices]
        pairs=[(positions[i],positions[(i+1)%3]) for i in range(3)]
        if any(all(abs(a[axis]-b[axis])<=threshold_cm for axis in range(3)) for a,b in pairs):
            degenerate_count+=1
        edge_lengths.extend((a-b).length/100 for a,b in pairs)
    return {'ue_coincident_vertex_triangles':degenerate_count,
            'ue_comparison_threshold_cm':threshold_cm,
            'minimum_triangle_edge_m':min(edge_lengths),
            'minimum_triangle_area_m2':min(face.area for face in mesh.polygons)}


assets=[]; infos=[]
for index,cage in enumerate(cages,1):
    target=bounds(cage)
    obj=form(index)
    base_faces=finish_shape(obj,target,index)
    actual=bounds(obj)
    error=max(abs(actual[j][i]-target[j][i]) for i in range(3) for j in range(2))
    assert error<1e-6
    assert obj.location.length<1e-7 and obj.rotation_euler.to_matrix()==Matrix.Identity(3)
    assert obj.scale==Vector((1,1,1))
    assert obj.data.has_custom_normals
    assert all(face.use_smooth and face.material_index==0 for face in obj.data.polygons)
    assert len(obj.data.materials)==1 and len(obj.data.color_attributes)==0
    bm=bmesh.new(); bm.from_mesh(obj.data)
    non_manifold=sum(not edge.is_manifold for edge in bm.edges)
    volume=bm.calc_volume(signed=True)
    bm.free()
    degenerate=sum(face.area<1e-10 for face in obj.data.polygons)
    finite=all(math.isfinite(v) for vertex in obj.data.vertices for v in vertex.co)
    assert not non_manifold and not degenerate and finite and volume>0,(index,non_manifold,degenerate,finite,volume)
    quality=engine_triangle_quality(obj.data)
    assert quality['ue_coincident_vertex_triangles']==0,(index,quality)
    uv=obj.data.uv_layers['UVMap']
    assert all(math.isfinite(x) for loop in uv.data for x in loop.uv)
    uv_areas=[]
    for face in obj.data.polygons:
        coords=[uv.data[li].uv for li in face.loop_indices]
        uv_areas.append(abs(sum(coords[i].x*coords[(i+1)%len(coords)].y-coords[(i+1)%len(coords)].x*coords[i].y for i in range(len(coords))))/2)
    assert min(uv_areas)>1e-12
    old=f'SM_MossRock_{index:02}'
    info={'original_asset_id':old,'asset_id':obj.name,'new_asset_id':obj.name,
          'file':f'ArtSource/Meshes/{obj.name}.fbx','collision':'complex',
          'original_ue_path':f'/Game/Astra/Meshes/{old}',
          'unreal_asset_path':f'/Game/Astra/Meshes/{old}',
          'unreal_import_target_asset_id':old,'independent_source_asset_id':obj.name,
          'origin':'Original local origin and +0.08 m lower-bound offset preserved exactly',
          'blender_location':[0,0,0],'blender_rotation_radians':[0,0,0],'blender_scale':[1,1,1],
          'bounds_min_m':actual[0],'bounds_max_m':actual[1],
          'original_bounds_min_m':target[0],'original_bounds_max_m':target[1],
          'dimensions_m':[actual[1][i]-actual[0][i] for i in range(3)],
          'vertices':len(obj.data.vertices),'triangles':len(obj.data.polygons),
          'base_shape_polygons':base_faces,'shape_style':obj['form'],
          'material_slots':['M_ForestRockPaint'],'uv_channel':0,
          'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS',
          'validation':{'finite_vertices':finite,'non_manifold_edges':non_manifold,'degenerate_faces':degenerate,
            'microscopic_bevel_vertices_welded':obj['microscopic_bevel_vertices_welded'],**quality,
            'signed_volume_m3':volume,'all_faces_smooth':True,'custom_weighted_normals':True,
            'bounds_error_m':error,'origin_transform_preserved':True,'finite_uv':True,
            'minimum_uv_face_area':min(uv_areas),'vertex_color_attributes':0,
            'random_facet_colors':False,'subdivision_surface_used':False}}
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{obj.name}.fbx'),use_selection=True,
        object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,
        mesh_smooth_type='FACE',use_mesh_modifiers=True,path_mode='STRIP',use_tspace=True)
    obj.hide_render=True; obj.hide_set(True)
    assets.append(obj); infos.append(info)

roundtrip=[]
for original,expected in zip(assets,infos):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ART/'Meshes'/f'{original.name}.fbx'),use_custom_normals=True)
    imported=[o for o in set(bpy.data.objects)-before if o.type=='MESH']
    assert len(imported)==1
    obj=imported[0]; bpy.context.view_layer.update()
    actual=bounds(obj)
    target=[expected['bounds_min_m'],expected['bounds_max_m']]
    error=max(abs(actual[j][i]-target[j][i]) for i in range(3) for j in range(2))
    assert error<1e-5 and obj.data.has_custom_normals
    assert all(face.use_smooth for face in obj.data.polygons) and len(obj.data.materials)==1
    assert obj.data.uv_layers.active is not None
    assert all(math.isfinite(v) for loop in obj.data.uv_layers.active.data for v in loop.uv)
    quality=engine_triangle_quality(obj.data)
    assert quality['ue_coincident_vertex_triangles']==0
    assert len(obj.data.polygons)==expected['triangles']
    bm=bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    non_manifold=sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert not non_manifold
    roundtrip.append({'asset_id':original.name,'bounds_error_m':error,'custom_normals_imported':True,
                      'triangles':len(obj.data.polygons),'triangle_count_preserved':True,**quality,
                      'all_faces_smooth':True,'material_slots':1,'finite_uv':True,
                      'uv_loops':len(obj.data.uv_layers.active.data),'welded_non_manifold_edges':0})
    for item in set(bpy.data.objects)-before:
        bpy.data.objects.remove(item,do_unlink=True)

metadata={'source':'ArtSource/Blender/ForestFracturedRocks.blend',
          'original_source':'ArtSource/Blender/ForestSmoothRocks.blend',
          'rebuild_baseline':'SOURCE_CAGE_SM_MossRock_01..05 preserved original 42-vertex cages',
          'script':'Scripts/build_fractured_forest_rocks.py',
          'reference':'ArtSource/Reference/Ref_FracturedForestRocks.png','units':'metres',
          'unreal_conversion':'(Blender X, -Blender Y, Blender Z) * 100; existing actor transforms unchanged',
          'replacement_map':{i['original_asset_id']:i['asset_id'] for i in infos},
          'material_properties':{'M_ForestRockPaint':{'base_color_texture':'ArtSource/Textures/T_AnimeForestRockPaint.png',
              'base_color_formula':'sRGB-decoded TextureSample(UV0).rgb','texture_srgb':True,
              'roughness':.88,'metallic':0,'specular':.2,'uv_channel':0,'normal_texture':None,
              'emissive':0,'random_facet_colors':False}},
          'assets':infos,'fbx_roundtrip_validation':roundtrip,
          'placement_notes':'Reimport the independent new FBX into its original SM_MossRock UE asset. Keep all existing actor and Blender object transforms, labels, asset IDs and collision references. Only mesh geometry, UV and authored normals change; exact original bounding boxes and pivots are preserved.'}
(ART/'Layout'/'forest_fractured_rocks.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
(ART/'Previews'/'FracturedForestRocks_Validation.json').write_text(json.dumps({'assets':infos,'fbx_roundtrip_validation':roundtrip},indent=2)+'\n',encoding='utf-8')

positions=[(-1.7,-3.5,0),(-1.7,0,0),(-1.7,3.5,0),(2.2,-2.0,0),(2.2,2.0,0)]
for index,(original,position) in enumerate(zip(assets,positions)):
    obj=bpy.data.objects.new('Preview_'+original.name,original.data)
    presentation.objects.link(obj)
    obj.location=position
    obj.location.z=-infos[index]['bounds_min_m'][2]
    obj.rotation_euler.z=math.radians((-18,22,-12,10,-18)[index])
ground=bpy.data.materials.new('FracturedRockPreviewGround'); ground.use_nodes=True
ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.39,.41,.29,1)
ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.95
bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-.02))
bpy.context.object.name='PreviewGround'; bpy.context.object.data.materials.append(ground)
scene.world=bpy.data.worlds.new('FracturedRockSky'); scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.65,.73,.90,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.60
bpy.ops.object.light_add(type='SUN',location=(-8,-9,14)); sun=bpy.context.object
sun.name='SoftSun_50deg'; sun.rotation_euler=(.4,-.48,-.55); sun.data.energy=2.6; sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-13,-10,12)); camera=bpy.context.object
camera.rotation_euler=(Vector((0,0,.55))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'; camera.data.ortho_scale=14.5; scene.camera=camera
scene.render.engine='CYCLES'; scene.cycles.samples=48; scene.cycles.use_denoising=True
scene.render.resolution_x=1800; scene.render.resolution_y=1300; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(ART/'Previews'/'Blender_FracturedForestRocks.png')
scene.view_settings.view_transform='AgX'; scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'ForestFracturedRocks.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA FRACTURED ROCKS COMPLETE '+json.dumps(infos))
