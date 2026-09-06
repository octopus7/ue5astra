import unreal
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
task=unreal.AssetImportTask();task.filename=str(ROOT/'ArtSource'/'Meshes'/'SM_BridgeIntact.fbx')
task.destination_path='/Game/Astra/Meshes';task.destination_name='SM_BridgeIntact'
task.automated=True;task.save=True;task.replace_existing=True;task.factory=unreal.FbxFactory()
options=unreal.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=False;options.import_materials=False;options.import_textures=False
options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
options.static_mesh_import_data.combine_meshes=True;options.static_mesh_import_data.generate_lightmap_u_vs=False
options.static_mesh_import_data.auto_generate_collision=False;options.static_mesh_import_data.convert_scene=True;options.static_mesh_import_data.convert_scene_unit=True
task.options=options;unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
asset=unreal.EditorAssetLibrary.load_asset('/Game/Astra/Meshes/SM_BridgeIntact')
asset.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
for i,s in enumerate(asset.get_editor_property('static_materials')):
    mat=unreal.EditorAssetLibrary.load_asset('/Game/Astra/Materials/'+str(s.material_slot_name))
    if mat:asset.set_material(i,mat)
unreal.EditorAssetLibrary.save_loaded_asset(asset)
unreal.EditorLevelLibrary.save_current_level()
unreal.log('ASTRA BRIDGE RAMPS REIMPORTED')
