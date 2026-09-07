"""Read-only validation of the saved level, independent of placement execution."""
import json,math,struct,sys,traceback
from collections import Counter,defaultdict
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import import_rootbelltower_level as rb
from validate_starpond_level import actor_transform,transform_errors,vector_error,native_foliage,compare_foliage_transforms

def material_path(name):return name.split('.')[0] if name.startswith('/') else rb.MATERIAL_DIR+'/'+name

def validate(checks,details):
    data=json.loads((ROOT/'ArtSource/Layout/rootbelltower_layout.json').read_text())
    imported=json.loads((ROOT/'ArtSource/Previews/UE_RootBelltowerImportValidation.json').read_text())
    before=rb.protected_content();map_file=ROOT/'Content/Astra/Maps/L_AstraRootBelltower.umap';map_hash=rb.digest(map_file)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(rb.MAP)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    names={a.get_actor_label():a for a in actors};labels=Counter(a.get_actor_label() for a in actors)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    checks['independent_root_belltower_map']=world.get_path_name().split('.')[0]==rb.MAP
    checks['successful_import']=imported['passed']
    checks['layout_matches_import']=rb.digest(ROOT/'ArtSource/Layout/rootbelltower_layout.json')==imported['layout_sha256']
    checks['heightmap_matches_import']=rb.digest(ROOT/data['terrain_file'])==imported['terrain_sha256']
    protected=rb.check_protected(imported['protected_asset_sha256'])
    checks['previous_maps_and_shared_assets_unchanged']=len(protected)>100 and all(protected.values())
    details['changed_protected_files']=[p for p,ok in protected.items() if not ok]
    checks['saved_lighting_matches_import']=rb.environment_state(actors)==imported['environment_state']
    suns=[a for a in actors if isinstance(a,unreal.DirectionalLight)]
    checks['soft_source_angle_50']=len(suns)==1 and abs(suns[0].light_component.get_editor_property('light_source_angle')-50)<.001
    meshes={};editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for name,item in data['assets'].items():
        mesh=rb.EAL.load_asset(item['unreal_asset_path']);checks[name+'_exists']=isinstance(mesh,unreal.StaticMesh)
        if not isinstance(mesh,unreal.StaticMesh) or item.get('reuse_existing'):continue
        build=editor.get_lod_build_settings(mesh,0);bounds=mesh.get_bounding_box()
        dims=[getattr(bounds.max,k)-getattr(bounds.min,k) for k in ('x','y','z')]
        error=vector_error(dims,[v*100 for v in item['dimensions_m']])
        source=mesh.get_static_mesh_description(0).get_triangle_count();render=mesh.get_num_triangles(0)
        slots=list(mesh.get_editor_property('static_materials'));actual=[rb.asset_path(s.material_interface) for s in slots]
        expected=[material_path(s) for s in item['materials']]
        checks[name+'_dimensions']=error<.05
        checks[name+'_source_triangles']=source==item['triangles']
        checks[name+'_render_geometry_retained']=source*.995<=render<=source
        checks[name+'_authored_normals']=not build.get_editor_property('recompute_normals')
        checks[name+'_imported_normals']=mesh.get_editor_property('asset_import_data').get_editor_property('normal_import_method')==unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        checks[name+'_uv0']=editor.get_num_uv_channels(mesh,0)>=1
        checks[name+'_material_slots']=Counter(actual)==Counter(expected)
        checks[name+'_material_slot_names']=all(str(s.material_slot_name) in item['materials'] and rb.asset_path(s.material_interface)==material_path(str(s.material_slot_name)) for s in slots)
        sections=[editor.get_lod_material_slot(mesh,0,i) for i in range(mesh.get_num_sections(0))]
        checks[name+'_section_material_bindings']=bool(sections) and all(0<=i<len(slots) for i in sections)
        if item['collision']=='complex':checks[name+'_complex_collision']=mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')==unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
        meshes[name]=dict(authored_triangles=item['triangles'],source_triangles=source,render_triangles=render,dimensions_cm=dims,bounds_error_cm=error,materials=actual)
    details['new_meshes']=meshes
    expected_foliage=Counter();positions=defaultdict(list);placement_errors=[]
    for item in data['objects']:
        if item['foliage']:
            expected_foliage[item['asset']]+=1
            positions[item['asset']].append(dict(name=item['name'],location=item['ue_location_cm'],scale=item['scale'],rotation=item['ue_rotation_deg']))
            checks[item['name']+'_native_foliage']=item['name'] not in names;continue
        actor=names.get(item['name']);okay=isinstance(actor,unreal.StaticMeshActor) and labels[item['name']]==1
        if okay:
            component=actor.static_mesh_component
            error=transform_errors(actor_transform(actor),dict(location=item['ue_location_cm'],scale=item['scale'],rotation=item['ue_rotation_deg']))
            okay=rb.asset_path(component.static_mesh)==data['assets'][item['asset']]['unreal_asset_path'] and error['location_cm']<.05 and error['scale']<.0001 and error['yaw_degrees']<.001 and error['pitch_roll_degrees']<.001
            collides=item['collision'] in ('complex','solid')
            okay=okay and actor.get_actor_enable_collision()==collides and str(component.get_collision_profile_name())==('BlockAll' if collides else 'NoCollision')
            okay=okay and component.get_editor_property('mobility')==(unreal.ComponentMobility.MOVABLE if item.get('movable') else unreal.ComponentMobility.STATIC)
            okay=okay and component.is_visible() and not actor.get_editor_property('hidden')
            if item['collision']=='trunk':
                blocker=names.get(item['name']+'_TrunkCollision')
                checks[item['name']+'_trunk_collision']=bool(blocker and blocker.get_actor_enable_collision() and not blocker.static_mesh_component.is_visible() and blocker.get_editor_property('hidden'))
        checks[item['name']+'_saved_placement']=bool(okay)
        if not okay:placement_errors.append(item['name'])
    actual,actual_positions,nonblocking=native_foliage(actors)
    comparison=compare_foliage_transforms(actual_positions,positions)
    checks['foliage_counts']=actual==dict(expected_foliage)
    checks['foliage_exact_transforms']=comparison['passed']
    checks['foliage_nonblocking']=nonblocking
    details['foliage']=dict(counts=actual,total=sum(actual.values()),transforms=comparison)
    details['placement_errors']=placement_errors
    landscapes=[a for a in actors if isinstance(a,unreal.Landscape)]
    checks['one_native_landscape']=len(landscapes)==1
    if len(landscapes)==1:
        landscape=landscapes[0];raw=struct.unpack('<16129H',(ROOT/data['terrain_file']).read_bytes());errors=[]
        for iy in range(1,126):
            for ix in range(1,126):
                expected=(raw[iy*127+ix]-32768)/128*100
                actual_height=unreal.AstraSceneLibrary.landscape_height_at(landscape,unreal.Vector(-5040+ix*80,-5040+iy*80,0))
                errors.append(abs(expected-actual_height))
        checks['landscape_15625_actual_height_samples']=len(errors)==15625 and max(errors)<.05
        checks['landscape_dimensions']=vector_error(rb.xyz(landscape.get_actor_location()),[-5040,-5040,0])<.01 and vector_error(rb.xyz(landscape.get_actor_scale3d()),[80,80,100])<.001
        checks['landscape_own_material']=rb.asset_path(landscape.get_editor_property('landscape_material'))==rb.MATERIAL_DIR+'/M_RB_Landscape'
        details['landscape']=dict(size_m=100.8,interior_samples=len(errors),maximum_height_error_cm=max(errors))
        starts=[a for a in actors if isinstance(a,unreal.PlayerStart)];checks['one_player_start']=len(starts)==1
        if len(starts)==1:
            p=starts[0].get_actor_location();z=unreal.AstraSceneLibrary.landscape_height_at(landscape,p)
            checks['player_start_saved_and_grounded']=vector_error(rb.xyz(p),data['spawn_cm'])<.01 and 88<=p.z-z<=130
    configs=[a for a in actors if isinstance(a,unreal.AstraLevelConfig)];checks['one_local_config']=len(configs)==1
    if len(configs)==1:
        config=configs[0];shots=config.get_editor_property('demo_shots')
        checks['seven_demo_shots']=len(shots)==7;checks['validation_prefix_RB']=config.get_editor_property('validation_prefix')=='RB'
        for shot,item in zip(shots,data['demo_shots']):
            checks[item['name']+'_route']=str(shot.get_editor_property('name'))==item['name'] and [[p.x,p.y] for p in shot.get_editor_property('waypoints')]==item['points']
            checks[item['name']+'_camera']=abs(shot.get_editor_property('ortho_width')-item['width'])<.01 and vector_error(rb.xyz(shot.get_editor_property('camera_offset')),item['offset'])<.01
    for item in data['review_cameras']:
        actor=names.get('Camera_'+item['name'])
        okay=isinstance(actor,unreal.CameraActor)
        if okay:
            p,y=map(math.radians,(item.get('pitch',-58),item.get('yaw',0)));look=item['look_cm']
            arm=item.get('arm',4200 if item['width']>5000 else min(2700,item['width']*.75))
            expected=[look[0]-arm*math.cos(p)*math.cos(y),look[1]-arm*math.cos(p)*math.sin(y),look[2]-arm*math.sin(p)]
            error=transform_errors(actor_transform(actor),dict(location=expected,scale=[1,1,1],rotation=dict(pitch=item.get('pitch',-58),yaw=item.get('yaw',0),roll=0)))
            okay=error['location_cm']<.05 and error['yaw_degrees']<.001 and error['pitch_roll_degrees']<.001
            okay=okay and actor.camera_component.get_editor_property('projection_mode')==unreal.CameraProjectionMode.ORTHOGRAPHIC and abs(actor.camera_component.get_editor_property('ortho_width')-item['width'])<.01
        checks[item['name']+'_review_camera']=okay
    effects=[a for a in actors if isinstance(a,unreal.AstraRootBelltower)]
    checks['one_belltower_resonance_actor']=len(effects)==1
    if len(effects)==1:
        effect=effects[0];bell=effect.get_editor_property('bell_actor');roots=effect.get_editor_property('root_actors');sound=effect.get_editor_property('chime_sound')
        checks['bell_reference_saved']=bell==names.get('RB_Bell')
        checks['root_glow_references_saved']=len(roots)>=3 and all(a and a.get_actor_label().startswith('RB_') for a in roots)
        checks['resonance_center_saved']=vector_error(rb.xyz(effect.get_editor_property('resonance_center')),data['resonance_center_cm'])<.01
        checks['original_chime_saved']=isinstance(sound,unreal.SoundWave) and rb.asset_path(sound)=='/Game/Astra/Audio/RootBelltower/A_RB_BronzeChime'
        details['resonance']=dict(bell=bell.get_actor_label() if bell else None,roots=[a.get_actor_label() for a in roots],sound=rb.asset_path(sound))
    checks['saved_map_unchanged_during_validation']=rb.digest(map_file)==map_hash
    checks['other_content_unchanged_during_validation']=all(rb.check_protected(before).values())
    details['actor_count']=len(actors)

def main():
    checks={};details={}
    try:validate(checks,details)
    except Exception as error:
        checks['validator_completed']=False;details['exception']=dict(error=str(error),traceback=traceback.format_exc())
    result=dict(passed=bool(checks) and all(checks.values()),check_count=len(checks),checks=checks,failed_checks=[n for n,ok in checks.items() if not ok],details=details)
    (ROOT/'ArtSource/Previews/UE_RootBelltowerSavedValidation.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['passed'],str(result['failed_checks'])+' '+str(details.get('exception',''))
    unreal.log('ROOT_BELLTOWER_SAVED_VALIDATED '+str(len(checks)))

if __name__=='__main__':main()
