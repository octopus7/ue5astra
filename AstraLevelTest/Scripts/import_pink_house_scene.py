"""Apply Blender's house placement and local terrain edits to the existing UE map."""
import unreal,json,importlib.util,math
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
# Keep the complete pre-placement map, including its embedded Landscape textures.
from datetime import datetime
backup=ROOT/'ArtSource'/'Backups'/('BeforePinkHouse_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
backup.mkdir(parents=True,exist_ok=False)
import shutil
shutil.copy2(ROOT/'Content/Astra/Maps/L_AstraWoodland.umap',backup/'L_AstraWoodland.umap')
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
spec=importlib.util.spec_from_file_location('astra_import',str(ROOT/'Scripts'/'import_unreal_scene.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
changes=json.loads((ROOT/'ArtSource/Layout/pink_house_placement.json').read_text(encoding='utf-8'))
house=json.loads((ROOT/'ArtSource/Layout/pink_house_assets.json').read_text(encoding='utf-8'))
mats=b.build_materials()
for name,props in house['material_properties'].items():
    if name not in ['M_CottageGlass','M_WellWater']:continue
    m=b.newmat(name);b.connect(b.color(m,b.linear(house['palette_srgb_hex'][name])),unreal.MaterialProperty.MP_BASE_COLOR)
    b.connect(b.const(m,props['roughness']),unreal.MaterialProperty.MP_ROUGHNESS)
    b.connect(b.const(m,props['metallic']),unreal.MaterialProperty.MP_METALLIC)
    mats[name]=b.finish(m)
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
all_assets=b.DATA['assets'];b.DATA['assets']={n:all_assets[n] for n in ['SM_PinkRoofHouse','SM_FrontWell']}
meshes=b.import_meshes(mats);b.DATA['assets']=all_assets
actors=b.ES.get_all_level_actors();by_name={a.get_actor_label():a for a in actors}
for name in changes['removed_existing_actor_names']:
    for label in [name,name+'_TrunkCollision']:
        if label in by_name:
            a=by_name[label]
            a.set_actor_hidden_in_game(True)
            a.set_actor_enable_collision(False)
            a.set_folder_path('PreservedBeforePinkHouse')
            if isinstance(a,unreal.StaticMeshActor):a.static_mesh_component.set_visibility(False,True)
for entry in changes['modified_existing_instances']:
    if entry['name'] in by_name:by_name[entry['name']].set_actor_location(unreal.Vector(*entry['ue_location_cm']),False,False)
for entry in changes['new_instances']:
    a=by_name.get(entry['name'])
    if a is None:a=b.spawn(unreal.StaticMeshActor,entry['ue_location_cm'],label=entry['name'],folder=entry['group'])
    a.set_actor_location(unreal.Vector(*entry['ue_location_cm']),False,False)
    a.set_actor_rotation(unreal.Rotator(),False);a.set_actor_scale3d(unreal.Vector(*entry['scale']))
    a.static_mesh_component.set_static_mesh(meshes[entry['asset']])
    a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
land=next((a for a in actors if isinstance(a,unreal.Landscape)),None)
if not land or not unreal.AstraSceneLibrary.update_terrain_heights(land):raise RuntimeError('In-place Landscape height update failed')
b.setup_cloud_sky(mats)
for name,look,width,pitch in [('House',[1700,3900,160],2100,-58),('Sky',[0,0,0],3000,58)]:
    label='Camera_'+name;a=by_name.get(label)
    arm=2700;rad=math.radians(abs(pitch))
    loc=[look[0]-arm*math.cos(rad),look[1],look[2]+arm*math.sin(rad)]
    if a is None:a=b.spawn(unreal.CameraActor,loc,unreal.Rotator(pitch=pitch),label,'ReviewCameras')
    cc=a.camera_component
    cc.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC if name=='House' else unreal.CameraProjectionMode.PERSPECTIVE)
    cc.set_editor_property('ortho_width',width);cc.set_editor_property('constrain_aspect_ratio',False)
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Unable to save house scene')
result={'house_instances':changes['new_instances'],'preserved_hidden_instances':len(changes['removed_existing_actor_names']),
        'backup_map':str(backup/'L_AstraWoodland.umap'),'terrain_update':'in-place, existing actor preserved',
        'updated_instances':len(changes['modified_existing_instances']),'native_landscape':True,
        'actors':len(b.ES.get_all_level_actors()),'house_camera':'Camera_House','door_faces':'-X / toward game camera'}
(ROOT/'ArtSource/Previews/UE_HouseValidation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('ASTRA HOUSE SCENE SAVED '+json.dumps(result))
