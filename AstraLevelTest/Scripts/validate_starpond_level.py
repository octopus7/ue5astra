"""Read-only fresh-reload validation for the saved Star Pond level in UE 5.7.

Reads the actual saved meshes, actor settings, native foliage transforms,
Landscape collision heights and persisted skeletal animation. It never saves or
changes a UE asset. The only output is ArtSource/Previews/UE_StarPondValidation.json.
Run real-game movement, interaction and idle captures separately after this check.
"""
import json
import math
import struct
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
import import_starpond_level as sp

REPORT_PATH=ROOT/'ArtSource/Previews/UE_StarPondValidation.json'


def vector_error(a,b):
    return max(abs(float(x)-float(y)) for x,y in zip(a,b))


def angle_error(a,b):
    return abs((float(a)-float(b)+180)%360-180)


def transform_errors(actual,expected):
    return {'location_cm':vector_error(actual['location'],expected['location']),
            'scale':vector_error(actual['scale'],expected['scale']),
            'yaw_degrees':angle_error(actual['rotation']['yaw'],expected['rotation'].get('yaw',0)),
            'pitch_roll_degrees':max(angle_error(actual['rotation'][key],expected['rotation'].get(key,0))
                                     for key in ('pitch','roll'))}


def actor_transform(actor):
    rotation=actor.get_actor_rotation()
    return {'location':sp.xyz(actor.get_actor_location()),'scale':sp.xyz(actor.get_actor_scale3d()),
            'rotation':{key:float(getattr(rotation,key)) for key in ('pitch','yaw','roll')}}


def compare_foliage_transforms(actual,expected):
    """Match each instance once using buckets, then compare unrounded values."""
    limits={'location_cm':.05,'scale':.0001,'yaw_degrees':.01,'pitch_roll_degrees':.01}
    total_max={key:0.0 for key in limits};by_asset={};passed=True
    for name in sorted(set(actual)|set(expected)):
        found=actual.get(name,[]);wanted=expected.get(name,[])
        buckets=defaultdict(list)
        for index,item in enumerate(found):
            buckets[tuple(math.floor(v/.5) for v in item['location'])].append(index)
        available=set(range(len(found)));failures=[];maximum={key:0.0 for key in limits};matched=0
        for item in wanted:
            key=tuple(math.floor(v/.5) for v in item['location']);candidates=[]
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for dz in (-1,0,1):
                        candidates.extend(index for index in buckets.get((key[0]+dx,key[1]+dy,key[2]+dz),()) if index in available)
            metrics=[(index,transform_errors(found[index],item)) for index in candidates]
            valid=[pair for pair in metrics if all(pair[1][key]<=limit for key,limit in limits.items())]
            if valid:
                index,error=min(valid,key=lambda pair:tuple(pair[1][key] for key in limits))
                available.remove(index);matched+=1
            else:
                if not metrics and available:
                    nearest=min(available,key=lambda index:vector_error(found[index]['location'],item['location']))
                    metrics=[(nearest,transform_errors(found[nearest],item))]
                if metrics:
                    index,error=min(metrics,key=lambda pair:tuple(pair[1][key] for key in limits))
                    failures.append({'expected':item.get('name'),'nearest_actual':found[index].get('name'),'errors':error})
                else:
                    error={key:0.0 for key in limits}
                    failures.append({'expected':item.get('name'),'reason':'No unused actual instance'})
            for key in limits:
                maximum[key]=max(maximum[key],error[key]);total_max[key]=max(total_max[key],error[key])
        okay=not failures and not available and len(found)==len(wanted)
        passed=passed and okay
        by_asset[name]={'passed':okay,'expected_instances':len(wanted),'actual_instances':len(found),
                        'matched_instances':matched,'maximum_errors':maximum,
                        'unmatched_expected_count':len(failures),'unmatched_actual_count':len(available),
                        'failure_examples':failures[:12]}
    return {'passed':passed,'tolerances':limits,'maximum_errors':total_max,'by_asset':by_asset,
            'method':'One-to-one matches in neighbouring 0.5 cm spatial buckets; direct coordinate, scale and wrapped-angle comparisons.'}


def native_foliage(actors):
    counts=Counter();positions=defaultdict(list);nonblocking=True
    for actor in actors:
        if not isinstance(actor,unreal.InstancedFoliageActor):continue
        for component in actor.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
            if not component.static_mesh:continue
            name=component.static_mesh.get_name()
            counts[name]+=component.get_instance_count()
            nonblocking=nonblocking and component.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
            for index in range(component.get_instance_count()):
                transform=component.get_instance_transform(index,world_space=True)
                if isinstance(transform,tuple):transform=next(t for t in transform if isinstance(t,unreal.Transform))
                rotation=transform.rotation.rotator()
                positions[name].append({'name':component.get_path_name()+':'+str(index),
                    'location':sp.xyz(transform.translation),'scale':sp.xyz(transform.scale3d),
                    'rotation':{key:float(getattr(rotation,key)) for key in ('pitch','yaw','roll')}})
    return dict(counts),positions,nonblocking


def expected_material(name):
    if name.startswith('/'):return name.split('.')[0]
    if name.startswith('M_SP_'):return sp.MATERIAL_DIR+'/'+name
    # Read-only path resolution: never call the importer's material builder.
    return '/Game/Astra/Materials/'+name


def validate_elephant(data,actors,checks,details):
    metadata=json.loads((ROOT/'ArtSource/Layout/starpond_elephant.json').read_text(encoding='utf-8-sig'))
    candidates=[]
    for actor in actors:
        component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
        if component:
            mesh=component.get_editor_property('skeletal_mesh_asset')
            if mesh and mesh.get_name()=='SK_SP_UnicornElephant':candidates.append((actor,component,mesh))
    checks['one_real_skeletal_unicorn_elephant']=len(candidates)==1
    if len(candidates)!=1:
        details['elephant']={'matching_actors':[a.get_actor_label() for a,c,m in candidates]}
        return
    actor,component,mesh=candidates[0]
    dest='/Game/Astra/Characters/StarPond/Guardian'
    play=component.get_editor_property('animation_data')
    animation=play.get_editor_property('anim_to_play')
    bone_names=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
    skeleton=mesh.get_editor_property('skeleton')
    expected_bones=metadata['bones']
    checks['elephant_mesh_saved_in_own_directory']=sp.asset_path(mesh)==dest+'/SK_SP_UnicornElephant'
    checks['elephant_skeleton_contains_authored_bones']=bool(skeleton) and set(expected_bones)<=set(bone_names)
    extra_bones=set(bone_names)-set(expected_bones)
    root_parent=str(component.get_parent_bone('Root'))
    container_root=(extra_bones=={root_parent} and str(component.get_parent_bone(root_parent))=='None')
    checks['elephant_bone_hierarchy']=(root_parent=='None' and not extra_bones or container_root) and all(
        str(component.get_parent_bone(name))==item['parent']
        for name,item in expected_bones.items() if item['parent'] is not None)
    checks['elephant_saved_transform']=all(value<=limit for value,limit in zip(
        transform_errors(actor_transform(actor),{'location':data['elephant']['ue_location_cm'],'scale':[1,1,1],
            'rotation':{'yaw':data['elephant']['yaw'],'pitch':0,'roll':0}}).values(),[.05,.0001,.001,.001]))
    checks['elephant_visible']=not actor.get_editor_property('hidden') and component.is_visible()
    checks['elephant_nonblocking']=component.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
    checks['elephant_saved_animation_asset']=isinstance(animation,unreal.AnimSequence) and sp.asset_path(animation)==dest+'/'+metadata['animation']
    checks['elephant_saved_single_node_mode']=component.get_animation_mode()==unreal.AnimationMode.ANIMATION_SINGLE_NODE
    checks['elephant_saved_idle_loop']=bool(play.get_editor_property('saved_looping'))
    checks['elephant_saved_idle_playing']=bool(play.get_editor_property('saved_playing'))
    checks['elephant_saved_play_rate']=abs(float(play.get_editor_property('saved_play_rate'))-1)<1e-6
    slots=list(mesh.get_editor_property('materials'))
    material_paths=[sp.asset_path(s.get_editor_property('material_interface')) for s in slots]
    checks['elephant_material_bindings']=Counter(material_paths)==Counter(dest+'/Materials/'+name for name in metadata['material_slots'])
    details['elephant']={'actor':actor.get_actor_label(),'mesh':sp.asset_path(mesh),'skeleton':sp.asset_path(skeleton),
                         'animation':sp.asset_path(animation),'bone_names':bone_names,'materials':material_paths,
                         'saved_looping':bool(play.get_editor_property('saved_looping')),
                         'saved_playing':bool(play.get_editor_property('saved_playing')),
                         'transform':actor_transform(actor)}
    from import_starpond_elephant import validate_physical_actor,validate_bind_pose
    details['elephant']['physical_dimensions_and_grounding']=validate_physical_actor(actor,metadata)
    checks['elephant_centimetre_scale_and_grounded_feet']=True
    details['elephant']['mesh_animation_bind_pose']=validate_bind_pose(mesh,animation)
    checks['elephant_animation_matches_mesh_bind_pose']=True
    if not isinstance(animation,unreal.AnimSequence):return
    duration=float(animation.get_editor_property('sequence_length'))
    checks['elephant_eight_second_idle']=abs(duration-metadata['animation_duration_seconds'])<.05
    checks['elephant_root_motion_disabled']=not animation.get_editor_property('enable_root_motion')
    checks['elephant_animation_uses_same_skeleton']=sp.asset_path(animation.get_editor_property('skeleton'))==sp.asset_path(skeleton)
    details['elephant']['duration_seconds']=duration
    # These pose evaluations read imported animation data without ticking or changing
    # the world. Endpoints must agree, feet/root must be stationary, and body, ears,
    # trunk, tail and blink tracks must contain observable movement.
    options=unreal.AnimPoseEvaluationOptions()
    options.set_editor_property('optional_skeletal_mesh',mesh)
    times=[0.,.5,1.,2.,2.4,3.,4.,5.,6.,6.16,7.,duration]
    poses=[]
    for time in times:
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(animation,time,options)
        if isinstance(pose,tuple):pose=next(p for p in pose if isinstance(p,unreal.AnimPose))
        if not unreal.AnimPoseExtensions.is_valid(pose):raise RuntimeError('Invalid imported elephant pose at '+str(time))
        sample={}
        for name in expected_bones:
            transform=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.LOCAL)
            rotation=transform.rotation.rotator()
            sample[name]={'location':sp.xyz(transform.translation),'scale':sp.xyz(transform.scale3d),
                          'rotation':{key:float(getattr(rotation,key)) for key in ('pitch','yaw','roll')}}
        poses.append(sample)
    loop_errors={name:transform_errors(poses[-1][name],poses[0][name]) for name in expected_bones}
    checks['elephant_idle_endpoint_loop_continuity']=all(error['location_cm']<.05 and error['scale']<.001
        and error['yaw_degrees']<.05 and error['pitch_roll_degrees']<.05 for error in loop_errors.values())
    fixed=['Root']+[name for name in expected_bones if name.startswith('Foot_')]
    fixed_errors={name:{key:max(transform_errors(p[name],poses[0][name])[key] for p in poses)
                       for key in ('location_cm','scale','yaw_degrees','pitch_roll_degrees')} for name in fixed}
    checks['elephant_idle_root_and_feet_stationary']=all(error['location_cm']<.05 and error['scale']<.001
        and error['yaw_degrees']<.05 and error['pitch_roll_degrees']<.05 for error in fixed_errors.values())
    motion={name:max(max(transform_errors(p[name],poses[0][name]).values()) for p in poses) for name in expected_bones}
    checks['elephant_idle_breathes']=max(transform_errors(p['Body'],poses[0]['Body'])['scale'] for p in poses)>.003
    checks['elephant_idle_ears_move']=all(motion[name]>.1 for name in ('Ear_L','Ear_R'))
    checks['elephant_idle_trunk_moves']=all(motion['Trunk_'+str(i)]>.1 for i in range(1,5))
    checks['elephant_idle_tail_moves']=motion['Tail']>.1
    checks['elephant_idle_blinks']=all(max(transform_errors(p[name],poses[0][name])['scale'] for p in poses)>.2 for name in ('Blink_L','Blink_R'))
    details['elephant']['pose_evaluation']={'times_seconds':times,'loop_endpoint_errors':loop_errors,
        'stationary_root_and_foot_errors':fixed_errors,'maximum_track_changes':motion,
        'source':'Read-only AnimPoseExtensions evaluation of imported raw animation data; runtime screenshots are a separate check.'}


def validate(checks,details):
    data=json.loads((sp.ART/'Layout/starpond_layout.json').read_text(encoding='utf-8-sig'))
    imported=json.loads((sp.ART/'Previews/UE_StarPondImportValidation.json').read_text(encoding='utf-8-sig'))
    before=sp.protected_content()
    map_file=ROOT/'Content/Astra/Maps/L_AstraStarPond.umap'
    saved_map_hash=sp.digest(map_file)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(sp.MAP):
        raise RuntimeError('Saved Star Pond map could not be loaded')
    editor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mesh_editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=editor.get_all_level_actors();by_name={a.get_actor_label():a for a in actors}
    labels=Counter(a.get_actor_label() for a in actors)
    checks['independent_new_map']=world.get_path_name().split('.')[0]==sp.MAP=='/Game/Astra/Maps/L_AstraStarPond'
    checks['import_report_passed']=imported.get('passed',False)
    checks['layout_matches_import']=sp.digest(sp.ART/'Layout/starpond_layout.json')==imported['layout_sha256']
    checks['heightmap_matches_import']=sp.digest(ROOT/data['terrain_file'])==imported['terrain_sha256']
    protected=imported.get('protected_asset_sha256',{})
    checks['nonempty_original_content_baseline']=bool(protected) and 'Content/Astra/Maps/L_AstraWoodland.umap' in protected
    protected_results=sp.check_protected(protected)
    checks['original_woodland_and_shared_content_preserved']=bool(protected_results) and all(protected_results.values())
    details['protected_content']={'count':len(protected),'changed_files':[p for p,ok in protected_results.items() if not ok]}
    checks['exact_environment_settings_reused']=sp.environment_state(actors)==imported['environment_state']
    suns=[a for a in actors if isinstance(a,unreal.DirectionalLight)]
    checks['sun_source_angle_50']=bool(suns) and all(abs(a.light_component.get_editor_property('light_source_angle')-50)<.001 for a in suns)
    mesh_details={}
    for name,item in data['assets'].items():
        path=item.get('unreal_asset_path',sp.MESH_DIR+'/'+name);mesh=sp.EAL.load_asset(path)
        checks[name+'_exists']=isinstance(mesh,unreal.StaticMesh)
        if not isinstance(mesh,unreal.StaticMesh) or item.get('reuse_existing'):continue
        build=mesh_editor.get_lod_build_settings(mesh,0)
        box=mesh.get_bounding_box();dimensions=[box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z]
        errors=[abs(dimensions[i]-item['dimensions_m'][i]*100) for i in range(3)]
        slots=list(mesh.get_editor_property('static_materials'))
        expected=[expected_material(m) for m in item['materials']]
        actual=[sp.asset_path(slot.material_interface) for slot in slots]
        # Compare the imported source topology. UE's render build can remove
        # collapsed slivers even when the complete source mesh is preserved.
        source_triangles=mesh.get_static_mesh_description(0).get_triangle_count()
        render_triangles=mesh.get_num_triangles(0)
        microscopic_faces=0
        if name=='SM_SP_CrescentGate':
            inspection=json.loads((ROOT/'ArtSource/Previews/StarPondGate_TopologyInspection.json').read_text())
            assert inspection['triangles']==item['triangles'],'Gate inspection must match the current Blender source'
            microscopic_faces=inspection['microscopic_triangle_count']
        checks[name+'_triangles']=item['triangles']-microscopic_faces<=source_triangles<=item['triangles']
        checks[name+'_render_topology_retained']=source_triangles*.99<=render_triangles<=source_triangles
        checks[name+'_authored_normals']=not build.get_editor_property('recompute_normals')
        import_settings=mesh.get_editor_property('asset_import_data')
        checks[name+'_normal_import_mode']=import_settings.get_editor_property('normal_import_method')==unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        checks[name+'_dimensions']=max(errors)<.05
        checks[name+'_material_slots']=Counter(actual)==Counter(expected)
        checks[name+'_material_slot_name_bindings']=all(str(slot.material_slot_name) in item['materials']
            and actual[i]==expected_material(str(slot.material_slot_name)) for i,slot in enumerate(slots))
        checks[name+'_uv0_present']=mesh_editor.get_num_uv_channels(mesh,0)>=1
        if item.get('collision') in ('complex','solid'):
            checks[name+'_complex_collision_ready']=mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')==unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
        section_indices=[mesh_editor.get_lod_material_slot(mesh,0,i) for i in range(mesh.get_num_sections(0))]
        checks[name+'_section_bindings']=bool(section_indices) and all(0<=i<len(actual) and actual[i] in expected for i in section_indices)
        mesh_details[name]={'triangles':render_triangles,'source_triangles':source_triangles,
                           'authored_triangles':item['triangles'],'import_removed_source_triangles':item['triangles']-source_triangles,
                           'measured_microscopic_source_triangles':microscopic_faces,
                           'render_build_removed_triangles':source_triangles-render_triangles,
                           'dimensions_cm':dimensions,'bounds_error_cm':max(errors),
                           'materials':actual,'section_material_indices':section_indices,
                           'recompute_normals':bool(build.get_editor_property('recompute_normals'))}
    details['new_meshes']=mesh_details
    expected_foliage=Counter();expected_positions=defaultdict(list);actor_errors=[];water_actors=[]
    water_path=sp.MATERIAL_DIR+'/M_SP_StarWater'
    for item in data['objects']:
        if item.get('foliage'):
            expected_foliage[item['asset']]+=1
            expected_positions[item['asset']].append({'name':item['name'],'location':item['ue_location_cm'],
                'scale':item['scale'],'rotation':item['ue_rotation_deg']})
            checks[item['name']+'_is_native_instance']=item['name'] not in by_name
            continue
        actor=by_name.get(item['name']);okay=isinstance(actor,unreal.StaticMeshActor) and labels[item['name']]==1
        if okay:
            component=actor.static_mesh_component
            errors=transform_errors(actor_transform(actor),{'location':item['ue_location_cm'],'scale':item['scale'],'rotation':item['ue_rotation_deg']})
            okay=(sp.asset_path(component.static_mesh)==data['assets'][item['asset']]['unreal_asset_path']
                  and errors['location_cm']<.05 and errors['scale']<.0001 and errors['yaw_degrees']<.001
                  and errors['pitch_roll_degrees']<.001 and not actor.get_editor_property('hidden') and component.is_visible())
            collides=item.get('collision') in ('complex','solid')
            okay=okay and actor.get_actor_enable_collision()==collides
            okay=okay and str(component.get_collision_profile_name())==('BlockAll' if collides else 'NoCollision')
            if item.get('material_override'):
                override=item['material_override'].split('.')[0]
                okay=okay and sp.asset_path(component.get_material(0))==override
                if override==water_path:
                    water_actors.append(actor)
                    checks[item['name']+'_water_nonblocking']=not actor.get_actor_enable_collision() and component.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
                    import_settings=component.static_mesh.get_editor_property('asset_import_data')
                    checks[item['name']+'_edge_vertex_mask_imported']=import_settings.get_editor_property('vertex_color_import_option')==unreal.VertexColorImportOption.REPLACE
            if item.get('collision')=='trunk':
                blocker=by_name.get(item['name']+'_TrunkCollision')
                checks[item['name']+'_trunk_only_collision']=bool(blocker and blocker.get_actor_enable_collision()
                    and not blocker.static_mesh_component.is_visible() and blocker.get_editor_property('hidden')
                    and str(blocker.static_mesh_component.get_collision_profile_name())=='BlockAll')
        checks[item['name']+'_saved_placement']=okay
        if not okay:actor_errors.append(item['name'])
    actual_foliage,actual_positions,nonblocking=native_foliage(actors)
    foliage_transforms=compare_foliage_transforms(actual_positions,expected_positions)
    checks['native_foliage_counts']=actual_foliage==dict(expected_foliage) and sum(actual_foliage.values())>0
    checks['native_foliage_saved_transforms']=foliage_transforms['passed']
    checks['native_foliage_nonblocking']=nonblocking
    checks['one_star_water_mesh']=len(water_actors)==1 and water_actors[0].static_mesh_component.static_mesh.get_name()=='SM_SP_StarPondSurface'
    checks['star_water_material_exists']=isinstance(sp.EAL.load_asset(water_path),unreal.Material)
    details['foliage']={'counts':actual_foliage,'total':sum(actual_foliage.values()),
        'native_actors':sum(isinstance(a,unreal.InstancedFoliageActor) for a in actors),'transform_comparison':foliage_transforms}
    import starpond_layout as design
    lilies=[p for name,items in actual_positions.items() if name.startswith('SM_SP_StarLily_') for p in items]
    bank_plants=[p for name,items in actual_positions.items() if not name.startswith('SM_SP_StarLily_') for p in items]
    lily_radii=[design.pond_distance(p['location'][0]/100,p['location'][1]/100) for p in lilies]
    bank_radii=[design.pond_distance(p['location'][0]/100,p['location'][1]/100) for p in bank_plants]
    checks['star_lilies_native_foliage_inside_pond']=bool(lily_radii) and max(lily_radii)<1.0
    checks['all_other_native_plants_outside_water']=bool(bank_radii) and min(bank_radii)>1.0
    details['foliage']['habitat_bounds']={'lily_maximum_normalized_pond_radius':max(lily_radii) if lily_radii else None,
        'other_plants_minimum_normalized_pond_radius':min(bank_radii) if bank_radii else None}
    details['water_actors']=[a.get_actor_label() for a in water_actors];details['actor_errors']=actor_errors
    for asset,check_name,minimum,exact in [('SM_SP_ViewingDais','viewing_dais',1,True),
            ('SM_SP_CrescentGate','crescent_gate',1,True),('SM_SP_StarMenhir_','star_menhirs',2,False)]:
        placed=[o for o in data['objects'] if (o['asset']==asset if exact else o['asset'].startswith(asset))]
        checks[check_name+'_present']=len(placed)==minimum if exact else len(placed)>=minimum
        checks[check_name+'_saved']=bool(placed) and all(checks.get(o['name']+'_saved_placement',False) for o in placed)

    landscapes=[a for a in actors if isinstance(a,unreal.Landscape)]
    checks['one_native_landscape']=len(landscapes)==1
    terrain_error=None;sample_count=0
    checks['native_landscape_15625_height_samples']=False
    checks['player_start_saved']=False
    if len(landscapes)==1:
        landscape=landscapes[0]
        heights=struct.unpack('<16129H',(ROOT/data['terrain_file']).read_bytes());errors=[]
        for iy in range(1,126):
            for ix in range(1,126):
                expected=(heights[iy*127+ix]-32768)/128*100
                actual=unreal.AstraSceneLibrary.landscape_height_at(landscape,unreal.Vector(-5040+ix*80,-5040+iy*80,0))
                errors.append(abs(expected-actual))
        terrain_error=max(errors);sample_count=len(errors)
        checks['native_landscape_15625_height_samples']=terrain_error<.05 and sample_count==15625
        checks['landscape_100_8m_grid']=vector_error(sp.xyz(landscape.get_actor_location()),[-5040,-5040,0])<.01 and vector_error(sp.xyz(landscape.get_actor_scale3d()),[80,80,100])<.001
        checks['landscape_new_ground_material']=sp.asset_path(landscape.get_editor_property('landscape_material'))==sp.MATERIAL_DIR+'/M_SP_Landscape'
        starts=[a for a in actors if isinstance(a,unreal.PlayerStart)]
        checks['one_player_start']=len(starts)==1
        if len(starts)==1:
            start=starts[0];position=sp.xyz(start.get_actor_location())
            ground=unreal.AstraSceneLibrary.landscape_height_at(landscape,unreal.Vector(*position))
            checks['player_start_saved']=vector_error(position,data['spawn_cm'])<.01
            checks['player_start_above_walkable_landscape']=ground>-9990 and 88<=position[2]-ground<=250
            neighbours=[unreal.AstraSceneLibrary.landscape_height_at(landscape,unreal.Vector(position[0]+dx,position[1]+dy,0)) for dx,dy in ((30,0),(-30,0),(0,30),(0,-30))]
            checks['player_start_ground_slope']=max(abs(z-ground) for z in neighbours)<20
            details['player_start']={'label':start.get_actor_label(),'position_cm':position,'landscape_z_cm':ground,'clearance_cm':position[2]-ground}
        if len(water_actors)==1:
            checks['water_saved_level_matches_design']=abs(water_actors[0].get_actor_location().z-data['zones']['pond']['water_z_m']*100)<.01
    details['landscape']={'size_m':100.8,'interior_samples':sample_count,'maximum_height_error_cm':terrain_error,
                           'heightmap_sha256':sp.digest(ROOT/data['terrain_file'])}
    configs=[a for a in actors if isinstance(a,unreal.AstraLevelConfig)]
    checks['one_level_local_runtime_config']=len(configs)==1
    if len(configs)==1:
        config=configs[0];shots=config.get_editor_property('demo_shots')
        checks['validation_prefix_SP']=config.get_editor_property('validation_prefix')=='SP'
        checks['seven_demo_routes']=len(shots)==len(data['demo_shots'])==7
        for shot,item in zip(shots,data['demo_shots']):
            points=[[v.x,v.y] for v in shot.get_editor_property('waypoints')]
            checks[item['name']+'_route']=str(shot.get_editor_property('name'))==item['name'] and points==item['points']
            checks[item['name']+'_camera']=abs(shot.get_editor_property('ortho_width')-item['width'])<.01 and vector_error(sp.xyz(shot.get_editor_property('camera_offset')),item['offset'])<.01
            checks[item['name']+'_duration']=abs(shot.get_editor_property('minimum_seconds')-item['seconds'])<.001
    game_mode=world.get_world_settings().get_editor_property('default_game_mode')
    checks['AstraGameMode_enabled']=bool(game_mode and game_mode.get_name()=='AstraGameMode')
    for item in data['review_cameras']:
        name=item['name'] if item['name'].startswith('Camera_') else 'Camera_'+item['name'];camera=by_name.get(name)
        checks[name+'_orthographic']=isinstance(camera,unreal.CameraActor) and camera.camera_component.get_editor_property('projection_mode')==unreal.CameraProjectionMode.ORTHOGRAPHIC and abs(camera.camera_component.get_editor_property('ortho_width')-item['width'])<.01
    pond_class=getattr(unreal,'AstraStarPond',None)
    pond_actors=[a for a in actors if pond_class and isinstance(a,pond_class)]
    checks['one_starpond_runtime_actor']=len(pond_actors)==1
    details['starpond_runtime_actor']=[{'label':a.get_actor_label(),'class':a.get_class().get_name()} for a in pond_actors]
    if len(pond_actors)==1:
        mystery=pond_actors[0]
        linked_water=mystery.get_editor_property('water_actor')
        observatory=sp.xyz(mystery.get_editor_property('observatory'))
        checks['starpond_runtime_water_reference']=len(water_actors)==1 and linked_water==water_actors[0]
        checks['starpond_runtime_observatory_saved']=vector_error(observatory,[-1600,0,148])<.01
        checks['starpond_saved_alignment_initially_zero']=abs(mystery.get_editor_property('alignment'))<.001
        details['starpond_runtime_actor'][0].update({'water_actor':linked_water.get_actor_label() if linked_water else None,'observatory_cm':observatory})
    boundary=[a for a in actors if a.get_actor_label().startswith('SP_WaterBoundary_')]
    checks['96_saved_water_boundary_segments']=len(boundary)==96 and {a.get_actor_label() for a in boundary}=={f'SP_WaterBoundary_{i:03}' for i in range(96)}
    boundary_ok=True
    ignored_channels=[unreal.CollisionChannel.ECC_WORLD_STATIC,unreal.CollisionChannel.ECC_WORLD_DYNAMIC,
        unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionChannel.ECC_CAMERA,
        unreal.CollisionChannel.ECC_PHYSICS_BODY,unreal.CollisionChannel.ECC_VEHICLE,unreal.CollisionChannel.ECC_DESTRUCTIBLE]
    for actor in boundary:
        if not isinstance(actor,unreal.StaticMeshActor):boundary_ok=False;continue
        component=actor.static_mesh_component
        boundary_ok=boundary_ok and actor.get_editor_property('hidden') and not component.is_visible() and actor.get_actor_enable_collision()
        boundary_ok=boundary_ok and component.get_collision_enabled()==unreal.CollisionEnabled.QUERY_ONLY
        boundary_ok=boundary_ok and component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)==unreal.CollisionResponseType.ECR_BLOCK
        boundary_ok=boundary_ok and all(component.get_collision_response_to_channel(channel)==unreal.CollisionResponseType.ECR_IGNORE for channel in ignored_channels)
    checks['water_boundaries_hidden_and_pawn_only']=bool(boundary) and boundary_ok
    try:
        validate_elephant(data,actors,checks,details)
    except Exception as error:
        checks['elephant_complete_readonly_validation']=False
        details['elephant_validation_error']={'error':str(error),'traceback':traceback.format_exc()}
    checks['existing_content_unchanged_during_validation']=all(sp.check_protected(before).values())
    checks['saved_starpond_map_unchanged_during_validation']=sp.digest(map_file)==saved_map_hash
    details['actor_count']=len(actors)


def main():
    checks={};details={};exception=None
    try:
        validate(checks,details)
    except Exception as error:
        checks['validator_completed']=False
        exception={'error':str(error),'traceback':traceback.format_exc()}
    report={'passed':bool(checks) and all(checks.values()),'map':'/Game/Astra/Maps/L_AstraStarPond',
        'checks':checks,'failed_checks':[name for name,passed in checks.items() if not passed],
        'check_count':len(checks),'details':details,
        'validation':'Fresh full-editor saved-map reload, actual mesh/actor/foliage values, 15,625 native Landscape samples and imported skeletal poses; no UE saves.'}
    if exception:report['exception']=exception
    REPORT_PATH.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not report['passed']:raise RuntimeError('Star Pond saved-level validation failed: '+json.dumps(report['failed_checks']))
    unreal.log('STAR_POND_SAVED_LEVEL_VALIDATED '+json.dumps({'passed':True,'checks':len(checks),'actor_count':details.get('actor_count')}))


if __name__=='__main__':
    main()
