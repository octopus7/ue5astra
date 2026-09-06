"""Apply the camp hill, modular cliffs, shoreline and corrected panoramic sky in place."""
import unreal,json,math,sys,shutil,importlib.util
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
backup=ROOT/'ArtSource/Backups/BeforeForestExpansion'
backup.mkdir(parents=True,exist_ok=True)
if not (backup/'L_AstraWoodland.umap').exists():
    shutil.copy2(ROOT/'Content/Astra/Maps/L_AstraWoodland.umap',backup/'L_AstraWoodland.umap')
if not unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland'):
    raise RuntimeError('Cannot load the existing woodland map')
spec=importlib.util.spec_from_file_location('astra_import',str(ROOT/'Scripts/import_unreal_scene.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
changes=json.loads((ROOT/'ArtSource/Layout/forest_expansion.json').read_text(encoding='utf-8'))
mats=b.build_materials()
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
all_assets=b.DATA['assets'];b.DATA['assets']={n:all_assets[n] for n in changes['asset_ids']}
meshes=b.import_meshes(mats);b.DATA['assets']=all_assets
actors=b.ES.get_all_level_actors();by_name={a.get_actor_label():a for a in actors}
for entry in changes['hidden_original_instances']:
    for name in [entry['name'],entry['name']+'_TrunkCollision']:
        a=by_name.get(name)
        if a is None:continue
        a.set_actor_hidden_in_game(True);a.set_actor_enable_collision(False)
        a.set_is_temporarily_hidden_in_editor(True);a.set_folder_path('PreservedBeforeForestExpansion')
        if isinstance(a,unreal.StaticMeshActor):
            c=a.static_mesh_component;c.set_visibility(False,True);c.set_hidden_in_game(True)
            c.set_collision_profile_name('NoCollision')
for entry in changes['modified_existing_instances']:
    a=by_name.get(entry['name'])
    if a is None:continue
    loc=unreal.Vector(*entry['ue_location_cm']);dz=loc.z-a.get_actor_location().z
    a.set_actor_location(loc,False,False)
    trunk=by_name.get(entry['name']+'_TrunkCollision')
    if trunk:
        p=trunk.get_actor_location();p.z+=dz;trunk.set_actor_location(p,False,False)
for entry in changes['new_instances']:
    a=by_name.get(entry['name'])
    if a is None:a=b.spawn(unreal.StaticMeshActor,entry['ue_location_cm'],label=entry['name'],folder=entry['group'])
    c=a.static_mesh_component;c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_static_mesh(meshes[entry['asset']]);a.set_actor_location(unreal.Vector(*entry['ue_location_cm']),False,False)
    a.set_actor_rotation(unreal.Rotator(**entry['ue_rotation_deg']),False)
    a.set_actor_scale3d(unreal.Vector(*entry['scale']));a.set_actor_hidden_in_game(False)
    a.set_is_temporarily_hidden_in_editor(False);c.set_visibility(True);c.set_hidden_in_game(False)
    blocking=entry['collision']!='none'
    c.set_collision_profile_name('BlockAll' if blocking else 'NoCollision');a.set_actor_enable_collision(blocking)
    c.set_mobility(unreal.ComponentMobility.STATIC)
    by_name[entry['name']]=a
land=next((a for a in actors if isinstance(a,unreal.Landscape)),None)
if not land or not unreal.AstraSceneLibrary.update_terrain_heights(land):
    raise RuntimeError('In-place Landscape height update failed')
b.setup_cloud_sky(mats)
for name,look,width,pitch,yaw in [
    ('Camp',[3430,-300,370],2450,-58,0),('Cliffs',[2900,-230,300],2200,-35,0),
    ('Sign',[-210,-1300,120],800,-40,0),('Sky',[0,0,0],3000,20,0),
    ('SkySeam',[0,0,0],3000,20,180),('SkyZenith',[0,0,0],3000,89,0)]:
    a=by_name.get('Camera_'+name);p=math.radians(pitch);y=math.radians(yaw);arm=2700
    loc=[look[0]-arm*math.cos(p)*math.cos(y),look[1]-arm*math.cos(p)*math.sin(y),look[2]-arm*math.sin(p)]
    if name.startswith('Sky'):loc=[-800,0,450]
    if a is None:a=b.spawn(unreal.CameraActor,loc,label='Camera_'+name,folder='ReviewCameras')
    a.set_actor_location(unreal.Vector(*loc),False,False);a.set_actor_rotation(unreal.Rotator(pitch=pitch,yaw=yaw),False)
    cc=a.camera_component;cc.set_editor_property('projection_mode',unreal.CameraProjectionMode.PERSPECTIVE if name.startswith('Sky') else unreal.CameraProjectionMode.ORTHOGRAPHIC)
    cc.set_editor_property('ortho_width',width);cc.set_editor_property('field_of_view',90)
    cc.set_editor_property('constrain_aspect_ratio',False)
for name,pos,intensity,radius in [('CampfireGlow',[3300,60,580],25,450),('CampLanternGlow',[3580,-540,565],3,180)]:
    a=by_name.get(name)
    if a is None:a=b.spawn(unreal.PointLight,pos,label=name,folder='Lighting/Camp')
    c=a.light_component;c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_editor_property('intensity_units',unreal.LightUnits.LUMENS)
    c.set_intensity(intensity);c.set_light_color(unreal.LinearColor(1,.48,.15,1))
    c.set_editor_property('attenuation_radius',radius);c.set_editor_property('source_radius',20);c.set_cast_shadows(False)
import import_shoreline_site,puddle_cloud_trick
shore=import_shoreline_site.apply_site(save=True)
puddle=puddle_cloud_trick.validate_created_material()
if not puddle['passed']:raise RuntimeError('Puddle graph validation failed')
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Cannot save woodland expansion')
measured=[]
for entry in changes['new_instances']:
    a=by_name[entry['name']];c=a.static_mesh_component;box=meshes[entry['asset']].get_bounding_box()
    p=a.get_actor_location()
    measured.append({'name':entry['name'],'asset':entry['asset'],'position_cm':[p.x,p.y,p.z],
                     'mesh_height_cm':box.max.z-box.min.z,'collision_profile':str(c.get_collision_profile_name()),
                     'actor_collision':a.get_actor_enable_collision()})
heights={str(y):unreal.AstraSceneLibrary.landscape_height_at(land,unreal.Vector(3300,y,0)) for y in range(-2000,-799,200)}
result={'status':'success','main_map':'/Game/Astra/Maps/L_AstraWoodland','new_meshes':len(meshes),
        'new_instances':measured,'preserved_hidden_originals':len(changes['hidden_original_instances']),
        'moved_existing_instances':len(changes['modified_existing_instances']),
        'landscape_actor_preserved':True,'camp_ramp_heights_cm':heights,
        'sky_texture':'T_AnimeSkyPanorama','sky_mapping':'longitude/latitude with smooth pole and wrap caps',
        'shoreline_actors':shore['placed_actor_count'],'puddle_checks_passed':puddle['passed'],
        'actor_count':len(b.ES.get_all_level_actors()),'backup_map':str(backup/'L_AstraWoodland.umap')}
(ROOT/'ArtSource/Previews/UE_ForestExpansionValidation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(ROOT/'ArtSource/Previews/UE_PuddleMainValidation.json').write_text(json.dumps(puddle,indent=2),encoding='utf-8')
(ROOT/'ArtSource/Previews/UE_ShorelineMainValidation.json').write_text(json.dumps(shore,indent=2),encoding='utf-8')
unreal.log('ASTRA FOREST EXPANSION SAVED '+json.dumps(result))
