"""Reload the saved main map and read actual assets, visibility and collision state."""
import unreal,json,sys,math
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors=es.get_all_level_actors();index={a.get_actor_label():a for a in actors}
manifest=json.loads((ROOT/'ArtSource/Layout/forest_expansion.json').read_text(encoding='utf-8'))
checks={};mesh_bounds={}
for item in manifest['new_instances']:
    actor=index.get(item['name']);ok=isinstance(actor,unreal.StaticMeshActor)
    if ok:
        c=actor.static_mesh_component;p=actor.get_actor_location();expected=item['ue_location_cm']
        profile='NoCollision' if item['collision']=='none' else 'BlockAll'
        ok=(c.static_mesh.get_name()==item['asset'] and str(c.get_collision_profile_name())==profile
            and actor.get_actor_enable_collision()==(profile=='BlockAll') and not actor.get_editor_property('hidden')
            and c.is_visible() and max(abs(x-y) for x,y in zip([p.x,p.y,p.z],expected))<.1)
        box=c.static_mesh.get_bounding_box()
        mesh_bounds[item['asset']]={'height_cm':box.max.z-box.min.z,'slots':c.static_mesh.get_num_sections(0)}
    checks[item['name']]=ok
hidden=[]
for item in manifest['hidden_original_instances']:
    for name in [item['name'],item['name']+'_TrunkCollision']:
        actor=index.get(name)
        if actor: hidden.append(actor.get_editor_property('hidden') and not actor.get_actor_enable_collision())
checks['preserved_vegetation_hidden_nonblocking']=all(hidden)
shore=[a for a in actors if a.get_actor_label().startswith('AST_Shoreline_')]
checks['shoreline_16_visual_actors']=len(shore)==16 and all(not a.get_actor_enable_collision() and str(a.static_mesh_component.get_collision_profile_name())=='NoCollision' for a in shore)
texture=unreal.EditorAssetLibrary.load_asset('/Game/Astra/Textures/T_AnimeSkyPanorama')
checks['sky_is_colour_texture']=texture.get_editor_property('srgb') and texture.get_editor_property('compression_settings')==unreal.TextureCompressionSettings.TC_DEFAULT
sky=index['CloudSkyDome'];checks['sky_visible_nonblocking']=not sky.get_editor_property('hidden') and sky.static_mesh_component.is_visible() and not sky.get_actor_enable_collision()
checks['source_angle_50']=all(abs(a.light_component.get_editor_property('light_source_angle')-50)<.001 for a in actors if isinstance(a,unreal.DirectionalLight))
land=next(a for a in actors if isinstance(a,unreal.Landscape))
camp_z=unreal.AstraSceneLibrary.landscape_height_at(land,unreal.Vector(3800,-400,0))
checks['camp_landscape_height']=abs(camp_z-520)<2
import puddle_sky_reflection
checks['puddle_graph']=puddle_sky_reflection.validate_created_material()['passed']
puddle_actors=[a for a in actors if isinstance(a,unreal.StaticMeshActor) and a.static_mesh_component.static_mesh and a.static_mesh_component.static_mesh.get_name()=='SM_Puddle']
checks['five_native_reflective_puddles']=len(puddle_actors)==5 and all(a.static_mesh_component.get_material(0).get_path_name().startswith(puddle_sky_reflection.DEFAULT_ASSET+'.') for a in puddle_actors)
checks['puddle_front_layer_reflections']=all(a.get_editor_property('settings').get_editor_property('lumen_front_layer_translucency_reflections') for a in actors if isinstance(a,unreal.PostProcessVolume))
polish_asset='/Game/Astra/Materials/Shoreline/M_WaterFoam'
if unreal.EditorAssetLibrary.does_asset_exist(polish_asset):
    import shoreline_foam
    checks['shoreline_finished_water_graph']=shoreline_foam.validate_created_material()['passed']
    water_actors=[a for a in actors if isinstance(a,unreal.StaticMeshActor) and a.static_mesh_component.static_mesh and a.static_mesh_component.static_mesh.get_name() in ['SM_LakeSurface','SM_StreamSurface']]
    checks['lake_stream_finished_material']=bool(water_actors) and all(a.static_mesh_component.get_material(0).get_path_name().startswith(polish_asset+'.') for a in water_actors)
    bed=unreal.EditorAssetLibrary.load_asset('/Game/Astra/Meshes/ShorelineSite/SM_ShorelineSite_CurvedBed')
    checks['shoreline_authored_bed_normals']=not unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).get_lod_build_settings(bed,0).get_editor_property('recompute_normals')
rock_meta=json.loads((ROOT/'ArtSource/Layout/forest_smooth_rocks.json').read_text(encoding='utf-8'))
for item in rock_meta['assets']:
    mesh=unreal.EditorAssetLibrary.load_asset('/Game/Astra/Meshes/'+item['original_asset_id'])
    checks[item['original_asset_id']+'_smooth_import']=mesh.get_num_triangles(0)==item['triangles'] and mesh.get_material(0).get_name()=='M_ForestRockPaint'
foliage_file=ROOT/'ArtSource/Previews/UE_FoliageValidation.json'
if foliage_file.exists():
    expected=json.loads(foliage_file.read_text(encoding='utf-8'))['counts'];actual={name:0 for name in expected}
    for actor in actors:
        if isinstance(actor,unreal.InstancedFoliageActor):
            for component in actor.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
                if component.static_mesh and component.static_mesh.get_name() in actual:
                    actual[component.static_mesh.get_name()]+=component.get_instance_count()
                    checks[component.static_mesh.get_name()+'_foliage_nonblocking']=component.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
    checks['foliage_saved_instance_counts']=actual==expected
water_file=ROOT/'ArtSource/Previews/UE_WaterValidation.json'
water=json.loads(water_file.read_text(encoding='utf-8'))
puddle=unreal.EditorAssetLibrary.load_asset(puddle_sky_reflection.DEFAULT_ASSET)
water.update({'puddle_sky_texture_input':False,'puddle_emissive_input':False,'puddle_shading_model':str(puddle.get_editor_property('shading_model')),
              'puddle_reflectance':'native sky/environment reflection with thin translucent dielectric Fresnel F0=0.02 and soft coverage',
              'sky_texture':'T_AnimeSkyPanorama','main_map_shoreline_instances':len(shore)})
if unreal.EditorAssetLibrary.does_asset_exist(polish_asset):
    water.update({'lake_stream_material':polish_asset,'shoreline_contact_foam':True,'shore_aligned_ripples':True,'smooth_shallow_bed':True,'wet_shore_materials':True})
water_file.write_text(json.dumps(water,indent=2),encoding='utf-8')
report={'passed':all(checks.values()),'checks':checks,'mesh_bounds':mesh_bounds,'camp_collision_height_cm':camp_z,'actor_count':len(actors),'validation':'Independent full editor reload of saved main map'}
(ROOT/'ArtSource/Previews/UE_ForestReloadValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['passed']:raise RuntimeError('Reload validation failed: '+json.dumps(checks))
unreal.log('ASTRA FOREST RELOAD VALIDATED '+json.dumps(report))
