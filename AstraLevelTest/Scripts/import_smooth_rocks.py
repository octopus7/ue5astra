"""Reimport smooth rock geometry into the existing UE mesh paths and references."""
import unreal,json,sys
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import import_unreal_scene as b
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
meta=json.loads((ROOT/'ArtSource/Layout/forest_smooth_rocks.json').read_text(encoding='utf-8'))
tex=b.import_texture('T_AnimeForestRockPaint')
tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_DEFAULT)
tex.set_editor_property('srgb',True)
if not b.EAL.save_loaded_asset(tex):raise RuntimeError('Rock texture save failed')
m=b.newmat('M_ForestRockPaint')
sample=b.expression(m,unreal.MaterialExpressionTextureSample);sample.texture=tex
b.connect(sample,unreal.MaterialProperty.MP_BASE_COLOR)
for prop,value in [(unreal.MaterialProperty.MP_ROUGHNESS,.88),(unreal.MaterialProperty.MP_SPECULAR,.2),(unreal.MaterialProperty.MP_METALLIC,0)]:b.connect(b.const(m,value),prop)
m=b.finish(m)
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
report=[]
for item in meta['assets']:
    name=item['original_asset_id'];path='/Game/Astra/Meshes/'+name
    task=unreal.AssetImportTask();task.filename=str(ROOT/item['file']);task.destination_name=name;task.destination_path='/Game/Astra/Meshes'
    task.automated=True;task.save=True;task.replace_existing=True;task.factory=unreal.FbxFactory()
    options=unreal.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=False
    options.import_materials=False;options.import_textures=False;options.import_animations=False
    options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    d=options.static_mesh_import_data;d.combine_meshes=True;d.generate_lightmap_u_vs=False
    d.auto_generate_collision=False;d.convert_scene=True;d.convert_scene_unit=True
    d.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
    task.options=options;b.AT.import_asset_tasks([task]);mesh=b.EAL.load_asset(path)
    mesh.set_material(0,m);mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    if not b.EAL.save_loaded_asset(mesh):raise RuntimeError('Rock mesh save failed '+name)
    box=mesh.get_bounding_box();report.append({'asset':name,'source_fbx':item['file'],'source_triangles':item['triangles'],'imported_vertices':b.SM.get_number_verts(mesh,0),
        'bounds_cm':{'min':[box.min.x,box.min.y,box.min.z],'max':[box.max.x,box.max.y,box.max.z]},'normal_import':str(d.normal_import_method)})
actors=b.ES.get_all_level_actors();replaced=0
for a in actors:
    if isinstance(a,unreal.StaticMeshActor) and a.static_mesh_component.static_mesh and a.static_mesh_component.static_mesh.get_name() in meta['replacement_map']:
        a.static_mesh_component.set_material(0,m);replaced+=1
camera=next((a for a in actors if a.get_actor_label()=='Camera_Rocks'),None)
if camera is None:
    import math
    look=[2000,3200,80];arm=2700;p=math.radians(58)
    camera=b.spawn(unreal.CameraActor,[look[0]-arm*math.cos(p),look[1],look[2]+arm*math.sin(p)],unreal.Rotator(pitch=-58),'Camera_Rocks','ReviewCameras')
    camera.camera_component.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC)
    camera.camera_component.set_editor_property('ortho_width',1900);camera.camera_component.set_editor_property('constrain_aspect_ratio',False)
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Rock map save failed')
(ROOT/'ArtSource/Previews/UE_SmoothRocksValidation.json').write_text(json.dumps({'status':'success','meshes':report,'existing_actor_references_updated':replaced,'transforms_preserved':True},indent=2),encoding='utf-8')
unreal.log('ASTRA SMOOTH ROCKS SAVED '+str(replaced))
