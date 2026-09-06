"""Apply the water/sky revision to the existing map, preserving all placements."""
import unreal,json,importlib.util
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
spec=importlib.util.spec_from_file_location('astra_import',str(ROOT/'Scripts'/'import_unreal_scene.py'))
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
mats=builder.build_materials()
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
for name in ['SM_LakeSurface','SM_StreamSurface','SM_Puddle']:
    task=unreal.AssetImportTask();task.filename=str(ROOT/'ArtSource'/'Meshes'/f'{name}.fbx')
    task.destination_path='/Game/Astra/Meshes';task.destination_name=name
    task.automated=True;task.save=True;task.replace_existing=True;task.factory=unreal.FbxFactory()
    options=unreal.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=False
    options.import_materials=False;options.import_textures=False;options.import_animations=False
    options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    d=options.static_mesh_import_data;d.combine_meshes=True;d.generate_lightmap_u_vs=False
    d.auto_generate_collision=False;d.convert_scene=True;d.convert_scene_unit=True
    d.vertex_color_import_option=unreal.VertexColorImportOption.REPLACE
    task.options=options;builder.AT.import_asset_tasks([task])
    asset=builder.EAL.load_asset('/Game/Astra/Meshes/'+name)
    asset.set_material(0,mats['M_PuddleReflection' if name=='SM_Puddle' else 'M_Water'])
    if not builder.EAL.save_loaded_asset(asset):raise RuntimeError('Unable to save mesh: '+name)
builder.setup_cloud_sky(mats)
nonblocking={o['name'] for o in builder.DATA['objects'] if o['collision'] in ['none','trunk']}
for a in builder.ES.get_all_level_actors():
    if a.get_actor_label() in nonblocking and isinstance(a,unreal.StaticMeshActor):
        a.static_mesh_component.set_collision_profile_name('NoCollision')
        a.set_actor_enable_collision(False)
    if a.get_actor_label()=='StreamSurface_0001':
        a.set_actor_hidden_in_game(True)
        a.set_actor_enable_collision(False)
        a.static_mesh_component.set_visibility(False,True)
        a.set_folder_path('PreservedWaterParts')
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Unable to save woodland map')
result={'water_blend_mode':str(mats['M_Water'].get_editor_property('blend_mode')),
        'lake_shading_model':str(mats['M_Water'].get_editor_property('shading_model')),
        'lake_cloud_reflections':False,'lake_and_creek_single_surface':True,
        'water_edge_mask':'Blender vertex color red, smoothstep, multiplied by DepthFade',
        'puddle_sky_texture_input':False,'puddle_emissive_input':False,
        'sky':'CloudSkyDome / M_CloudSky','skylight_real_time_capture':True,
        'high_quality_translucency_reflections':True,'exponential_height_fog_density':.001,
        'puddle_shading_model':str(mats['M_PuddleReflection'].get_editor_property('shading_model')),
        'puddle_reflectance':'stylized metallic 1.0; replacement trick module in separate task',
        'underwater_terrain':'light sand instead of forest grass'}
out=ROOT/'ArtSource'/'Previews'/'UE_WaterValidation.json'
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('ASTRA WATER REVISION SAVED '+json.dumps(result))
