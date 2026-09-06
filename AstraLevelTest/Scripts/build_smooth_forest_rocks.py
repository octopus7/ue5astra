"""Derive smooth forest rocks from the five original woodland moss rocks.

Original names, meshes, main Blender scene, layout and UE assets remain untouched.
Each replacement preserves the exact local bounding box and the original origin.
Run Blender --background --factory-startup --python this_file.py.
"""
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
SOURCE=ART/'Blender'/'AstraWoodland.blend'
OUTPUT_SOURCE=ART/'Blender'/'ForestSmoothRocks.blend'
TEXTURE_PATH=ART/'Textures'/'T_AnimeForestRockPaint.png'
TEXTURE_RELATIVE='ArtSource/Textures/T_AnimeForestRockPaint.png'
for folder in ('Blender','Meshes','Layout','Previews'):
    (ART/folder).mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
library=bpy.data.collections.new('01_SmoothForestRockLibrary')
presentation=bpy.data.collections.new('02_SmoothRockPresentation')
baseline=bpy.data.collections.new('03_PreservedOriginal42VertexCages')
scene.collection.children.link(library)
scene.collection.children.link(presentation)
scene.collection.children.link(baseline)
material=bpy.data.materials.new('M_ForestRockPaint')
material.use_nodes=True
shader=material.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value=(.32,.35,.29,1)
shader.inputs['Roughness'].default_value=.88
shader.inputs['Metallic'].default_value=0
shader.inputs['Specular IOR Level'].default_value=.20
material.diffuse_color=(.32,.35,.29,1)
texture_ready=TEXTURE_PATH.is_file()
assert texture_ready,'Generate and save T_AnimeForestRockPaint.png before building final rock assets'
if texture_ready:
    texture=bpy.data.images.load(str(TEXTURE_PATH))
    texture.name='T_AnimeForestRockPaint'
    texture.colorspace_settings.name='sRGB'
    texture.pack()
    sample=material.node_tree.nodes.new('ShaderNodeTexImage')
    sample.image=texture
    sample.extension='REPEAT'
    sample.interpolation='Linear'
    sample.location=(-380,100)
    uv_node=material.node_tree.nodes.new('ShaderNodeUVMap')
    uv_node.uv_map='UVMap'
    uv_node.location=(-600,100)
    material.node_tree.links.new(uv_node.outputs['UV'],sample.inputs['Vector'])
    material.node_tree.links.new(sample.outputs['Color'],shader.inputs['Base Color'])

baseline_source=SOURCE
baseline_prefix='SM_MossRock_'
if OUTPUT_SOURCE.is_file():
    with bpy.data.libraries.load(str(OUTPUT_SOURCE),link=False) as (existing,_):
        preserved=sorted(name for name in existing.objects if name.startswith('SOURCE_CAGE_SM_MossRock_'))
    if len(preserved)==5:
        baseline_source=OUTPUT_SOURCE
        baseline_prefix='SOURCE_CAGE_SM_MossRock_'
with bpy.data.libraries.load(str(baseline_source),link=False) as (source,loaded):
    loaded.objects=sorted(name for name in source.objects if name.startswith(baseline_prefix))
assert len(loaded.objects)==5,'Expected the original five moss rock variants'


def bounds(obj):
    return ([min(v.co[i] for v in obj.data.vertices) for i in range(3)],
            [max(v.co[i] for v in obj.data.vertices) for i in range(3)])


def mesh_validation(obj):
    bm=bmesh.new(); bm.from_mesh(obj.data)
    non_manifold=sum(not edge.is_manifold for edge in bm.edges)
    volume=bm.calc_volume(signed=True)
    bm.free()
    finite=all(math.isfinite(x) for vertex in obj.data.vertices for x in vertex.co)
    degenerate=sum(face.area<1e-10 for face in obj.data.polygons)
    assert finite and not non_manifold and not degenerate and volume>0
    assert all(p.use_smooth and p.material_index==0 for p in obj.data.polygons)
    return {'finite_vertices':True,'non_manifold_edges':non_manifold,
            'degenerate_faces':degenerate,'signed_volume_m3':volume,
            'all_faces_smooth':True,'random_face_materials_removed':True,
            'vertex_color_attributes':len(obj.data.color_attributes)}


assets=[]
asset_info=[]
for index,obj in enumerate(loaded.objects,1):
    original_name=obj.name.removeprefix('SOURCE_CAGE_')
    assert len(obj.data.vertices)==42,'Use the preserved coarse original cages, never subdivide an already refined replacement'
    cage=obj.copy()
    cage.data=obj.data.copy()
    cage.name='SOURCE_CAGE_'+original_name
    # Rename the loaded cage first to free its exact stable name on repeat builds.
    obj.name='Working_'+original_name
    cage.name='SOURCE_CAGE_'+original_name
    baseline.objects.link(cage)
    cage.hide_render=True
    cage.hide_set(True)
    original_bounds=bounds(obj)
    original_location=list(obj.location)
    original_rotation=list(obj.rotation_euler)
    original_scale=list(obj.scale)
    obj.name=f'SM_SmoothForestRock_{index:02}'
    library.objects.link(obj)
    obj.hide_render=False
    obj.hide_viewport=False
    obj.hide_set(False)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    # Catmull-Clark converts the coarse triangular cage into a continuous curved hull.
    subdivision=obj.modifiers.new('RoundedStoneSurface','SUBSURF')
    subdivision.subdivision_type='CATMULL_CLARK'
    subdivision.levels=2
    subdivision.render_levels=2
    bpy.ops.object.modifier_apply(modifier=subdivision.name)
    # A small relaxation removes pinched joints while retaining the original asymmetry.
    relaxation=obj.modifiers.new('GentleSurfaceRelaxation','SMOOTH')
    relaxation.factor=.20
    relaxation.iterations=2
    bpy.ops.object.modifier_apply(modifier=relaxation.name)
    new_bounds=bounds(obj)
    for vertex in obj.data.vertices:
        for axis in range(3):
            t=(vertex.co[axis]-new_bounds[0][axis])/(new_bounds[1][axis]-new_bounds[0][axis])
            vertex.co[axis]=original_bounds[0][axis]+t*(original_bounds[1][axis]-original_bounds[0][axis])
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for attribute in list(obj.data.color_attributes):
        obj.data.color_attributes.remove(attribute)
    for layer in list(obj.data.uv_layers):
        obj.data.uv_layers.remove(layer)
    for face in obj.data.polygons:
        face.material_index=0
        face.use_smooth=True
    obj.data.update()
    # Separate top and underside at the equator: all visible upper rock is one island.
    midpoint=(original_bounds[0][2]+original_bounds[1][2])/2
    bm=bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    for edge in bm.edges:
        edge.seam=(len(edge.link_faces)==2 and
                   ((edge.link_faces[0].calc_center_median().z>midpoint) !=
                    (edge.link_faces[1].calc_center_median().z>midpoint)))
    bm.to_mesh(obj.data); bm.free()
    obj.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED',margin=.025)
    bpy.ops.uv.pack_islands(rotate=True,margin=.035)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    obj.data.update()
    validation=mesh_validation(obj)
    actual_bounds=bounds(obj)
    bounds_error=max(abs(actual_bounds[j][i]-original_bounds[j][i]) for j in range(2) for i in range(3))
    assert bounds_error < 1e-6
    assert list(obj.location)==original_location and list(obj.rotation_euler)==original_rotation and list(obj.scale)==original_scale
    uv=obj.data.uv_layers['UVMap']
    assert len(uv.data)>0 and all(math.isfinite(x) for loop in uv.data for x in loop.uv)
    # Require non-zero UV area for every face, not just existence of a UV layer.
    uv_areas=[]
    for face in obj.data.polygons:
        coords=[uv.data[loop].uv for loop in face.loop_indices]
        uv_areas.append(abs(sum(coords[i].x*coords[(i+1)%len(coords)].y-coords[(i+1)%len(coords)].x*coords[i].y for i in range(len(coords))))/2)
    assert min(uv_areas)>1e-10
    validation.update({'bounds_error_m':bounds_error,'origin_transform_preserved':True,
                       'finite_uv':True,'minimum_uv_face_area':min(uv_areas),
                       'uv_layout':'Angle-based unwrap, two islands split at equator; continuous top surface'})
    info={'original_asset_id':original_name,'asset_id':obj.name,'new_asset_id':obj.name,
          'file':f'ArtSource/Meshes/{obj.name}.fbx','collision':'complex',
          'original_ue_path':f'/Game/Astra/Meshes/{original_name}',
          'unreal_asset_path':f'/Game/Astra/Meshes/{original_name}',
          'unreal_import_target_asset_id':original_name,
          'independent_source_asset_id':obj.name,
          'origin':'Original local origin preserved; lower bound intentionally about +0.08 m',
          'blender_location':original_location,'blender_rotation_radians':original_rotation,'blender_scale':original_scale,
          'bounds_min_m':actual_bounds[0],'bounds_max_m':actual_bounds[1],
          'original_bounds_min_m':original_bounds[0],'original_bounds_max_m':original_bounds[1],
          'dimensions_m':[actual_bounds[1][i]-actual_bounds[0][i] for i in range(3)],
          'vertices':len(obj.data.vertices),'triangles':sum(len(face.vertices)-2 for face in obj.data.polygons),
          'material_slots':['M_ForestRockPaint'],'uv_channel':0,
          'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS','validation':validation}
    obj['original_asset_id']=original_name
    obj['asset_id']=obj.name
    obj['collision']='complex'
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{obj.name}.fbx'),
        use_selection=True,object_types={'MESH'},apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True,
        path_mode='STRIP',use_tspace=True,colors_type='LINEAR')
    obj.hide_render=True
    obj.hide_set(True)
    assets.append(obj); asset_info.append(info)

roundtrip=[]
for original,info in zip(assets,asset_info):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ART/'Meshes'/f'{original.name}.fbx'),use_custom_normals=True)
    imported=[obj for obj in set(bpy.data.objects)-before if obj.type=='MESH']
    assert len(imported)==1
    obj=imported[0]
    bpy.context.view_layer.update()
    actual=bounds(obj)
    error=max(abs(actual[j][i]-[info['bounds_min_m'],info['bounds_max_m']][j][i]) for j in range(2) for i in range(3))
    assert error<1e-5 and len(obj.data.materials)==1
    assert all(p.use_smooth for p in obj.data.polygons)
    assert obj.data.has_custom_normals
    uv=obj.data.uv_layers.active
    assert uv is not None and all(math.isfinite(x) for loop in uv.data for x in loop.uv)
    bm=bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    non_manifold=sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert non_manifold==0
    roundtrip.append({'asset_id':original.name,'bounds_error_m':error,'material_slots':1,
                      'smooth_faces':len(obj.data.polygons),'custom_normals_imported':True,
                      'uv_loops':len(uv.data),'finite_uv':True,'welded_non_manifold_edges':0})
    for item in set(bpy.data.objects)-before:
        bpy.data.objects.remove(item,do_unlink=True)

metadata={'source':'ArtSource/Blender/ForestSmoothRocks.blend',
          'original_source':'ArtSource/Blender/AstraWoodland.blend',
          'rebuild_baseline':'Preserved SOURCE_CAGE_SM_MossRock_01..05 objects inside ForestSmoothRocks.blend; fallback to main source only on first build',
          'script':'Scripts/build_smooth_forest_rocks.py','units':'metres',
          'unreal_conversion':'(Blender X, -Blender Y, Blender Z) * 100; existing actor transform stays unchanged',
          'replacement_map':{info['original_asset_id']:info['asset_id'] for info in asset_info},
          'material_properties':{'M_ForestRockPaint':{'base_color_texture':TEXTURE_RELATIVE,
             'base_color_formula':'sRGB-decoded TextureSample(UV0).rgb','texture_srgb':True,
             'roughness':.88,'metallic':0,'specular':.20,'uv_channel':0,'normal_texture':None,
             'emissive':0,'random_facet_colors':False}},
          'texture_present_at_build':texture_ready,
          'assets':asset_info,'fbx_roundtrip_validation':roundtrip,
          'placement_notes':'Reimport each new FBX into its original SM_MossRock UE asset path so existing actors and references are preserved. In Blender replace mesh data while retaining original asset IDs and transforms. Original bounds and local pivot offsets are retained.'}
(ART/'Layout'/'forest_smooth_rocks.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')

for index,original in enumerate(assets):
    obj=bpy.data.objects.new('Preview_'+original.name,original.data)
    presentation.objects.link(obj)
    obj.location=((-1.5 if index<3 else 2.2), ((index-1)*3.5 if index<3 else (index-3.5)*4),-.08)
    obj.rotation_euler.z=math.radians(index*22-20)
ground=bpy.data.materials.new('Preview_SmoothRockGround')
ground.use_nodes=True
ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.37,.40,.23,1)
ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.95
bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-.025))
bpy.context.object.name='PreviewGround'
bpy.context.object.data.materials.append(ground)
scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.65,.73,.9,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.65
bpy.ops.object.light_add(type='SUN',location=(-8,-7,15))
sun=bpy.context.object
sun.name='SoftSun_50deg'
sun.rotation_euler=(math.radians(23),math.radians(-25),math.radians(-35))
sun.data.energy=2.4
sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-12,-9,12))
camera=bpy.context.object
camera.rotation_euler=(Vector((0,0,.6))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=14.4
scene.camera=camera
scene.render.engine='CYCLES'
scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.render.resolution_x=1600
scene.render.resolution_y=1150
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ART/'Previews'/'Blender_SmoothForestRocks.png')
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'ForestSmoothRocks.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA SMOOTH FOREST ROCKS COMPLETE '+json.dumps({'texture_ready':texture_ready,'assets':asset_info}))
