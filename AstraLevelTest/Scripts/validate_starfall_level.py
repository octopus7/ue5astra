"""Independently reload and verify the saved Starfall map and imported assets.

Read-only UE validation: no level, mesh, foliage type or material is saved.
The root also runs real-game movement/demo captures after this structural check.
"""
import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
import import_starfall_level as sf


def vector_error(a,b):
    return max(abs(x-y) for x,y in zip(a,b))


def angle_error(a,b):
    return abs((a-b+180)%360-180)


def transform_errors(actual,expected):
    return {'location_cm':vector_error(actual['location'],expected['location']),
            'scale':vector_error(actual['scale'],expected['scale']),
            'yaw_degrees':angle_error(actual['rotation']['yaw'],expected['rotation'].get('yaw',0)),
            'pitch_roll_degrees':max(angle_error(actual['rotation'][key],expected['rotation'].get(key,0))
                                     for key in ('pitch','roll'))}


def compare_foliage_transforms(actual,expected):
    """One-to-one spatial matching followed by direct numeric comparisons.

    Buckets only locate candidates; rounded keys are never used as the equality
    test. Neighbour cells cover positions on either side of a bucket boundary.
    """
    limits={'location_cm':.05,'scale':.0001,'yaw_degrees':.01,'pitch_roll_degrees':.01}
    total_max={key:0.0 for key in limits};by_asset={};passed=True
    for name in sorted(set(actual)|set(expected)):
        found=actual.get(name,[]);wanted=expected.get(name,[])
        buckets=defaultdict(list)
        for index,item in enumerate(found):
            buckets[tuple(math.floor(v/.5) for v in item['location'])].append(index)
        available=set(range(len(found)));failures=[];maximum={key:0.0 for key in limits};matched=0
        for item in wanted:
            key=tuple(math.floor(v/.5) for v in item['location'])
            candidates=[]
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
                # A failed candidate is only diagnostic and is never consumed as
                # a valid match. This preserves duplicate-instance multiplicity.
                if not metrics and available:
                    nearest=min(available,key=lambda index:vector_error(found[index]['location'],item['location']))
                    metrics=[(nearest,transform_errors(found[nearest],item))]
                if metrics:
                    index,error=min(metrics,key=lambda pair:tuple(pair[1][key] for key in limits))
                    failures.append({'expected':item.get('name'),'nearest_actual':found[index].get('name'),
                                     'errors':error})
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
            'method':'One-to-one matches in neighbouring 0.5 cm spatial buckets; direct coordinate, scale and wrapped-angle tolerances.'}


def native_foliage(actors):
    counts=Counter();positions=defaultdict(list);nonblocking=True
    for actor in actors:
        if not isinstance(actor,unreal.InstancedFoliageActor):
            continue
        for component in actor.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
            if not component.static_mesh:
                continue
            name=component.static_mesh.get_name()
            counts[name]+=component.get_instance_count()
            nonblocking=nonblocking and component.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
            for index in range(component.get_instance_count()):
                transform=component.get_instance_transform(index,world_space=True)
                if isinstance(transform,tuple):
                    transform=next(t for t in transform if isinstance(t,unreal.Transform))
                rotation=transform.rotation.rotator()
                positions[name].append({'name':component.get_path_name()+':'+str(index),
                    'location':sf.xyz(transform.translation),'scale':sf.xyz(transform.scale3d),
                    'rotation':{key:float(getattr(rotation,key)) for key in ('pitch','yaw','roll')}})
    return dict(counts),positions,nonblocking


def main():
    data=json.loads((sf.ART/'Layout/starfall_layout.json').read_text(encoding='utf-8'))
    imported=json.loads((sf.ART/'Previews/UE_StarfallImportValidation.json').read_text(encoding='utf-8'))
    checks={};details={}
    before=sf.protected_content()
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(sf.MAP):
        raise RuntimeError('Saved Starfall map could not be loaded')
    editor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mesh_editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=editor.get_all_level_actors();by_name={a.get_actor_label():a for a in actors}
    checks['independent_new_map']=world.get_path_name().split('.')[0]==sf.MAP
    checks['import_report_passed']=imported.get('passed',False)
    checks['layout_matches_import']=sf.digest(sf.ART/'Layout/starfall_layout.json')==imported['layout_sha256']
    checks['existing_content_matches_preimport']=all(sf.check_protected(imported['protected_asset_sha256']).values())
    checks['exact_environment_settings_reused']=sf.environment_state(actors)==imported['environment_state']
    checks['sun_source_angle_50']=any(isinstance(a,unreal.DirectionalLight) for a in actors) and all(
        abs(a.light_component.get_editor_property('light_source_angle')-50)<.001
        for a in actors if isinstance(a,unreal.DirectionalLight))
    checks['reused_puddle_reflection_asset_exists']=sf.EAL.does_asset_exist(sf.WATER)
    mesh_details={}
    for name,item in data['assets'].items():
        path=item.get('unreal_asset_path',sf.MESH_DIR+'/'+name)
        mesh=sf.EAL.load_asset(path)
        checks[name+'_exists']=isinstance(mesh,unreal.StaticMesh)
        if not mesh or item.get('reuse_existing'):
            continue
        build=mesh_editor.get_lod_build_settings(mesh,0)
        box=mesh.get_bounding_box();dimensions=[box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z]
        errors=[abs(dimensions[i]-item['dimensions_m'][i]*100) for i in range(3)]
        slots=list(mesh.get_editor_property('static_materials'))
        expected=[sf.asset_path(sf.resolve_material(m,{})) if not m.startswith('M_SF_') else sf.MATERIAL_DIR+'/'+m for m in item['materials']]
        actual=[sf.asset_path(slot.material_interface) for slot in slots]
        checks[name+'_triangles']=mesh.get_num_triangles(0)==item['triangles']
        checks[name+'_authored_normals']=not build.get_editor_property('recompute_normals')
        checks[name+'_dimensions']=max(errors)<.05
        checks[name+'_material_slots']=Counter(actual)==Counter(expected)
        section_indices=[mesh_editor.get_lod_material_slot(mesh,0,i) for i in range(mesh.get_num_sections(0))]
        checks[name+'_section_bindings']=bool(section_indices) and all(0<=i<len(actual) and actual[i] in expected for i in section_indices)
        mesh_details[name]={'triangles':mesh.get_num_triangles(0),'dimensions_cm':dimensions,
               'bounds_error_cm':max(errors),'materials':actual,'section_material_indices':section_indices,
               'recompute_normals':bool(build.get_editor_property('recompute_normals'))}
    details['new_meshes']=mesh_details

    expected_foliage=Counter();expected_positions=defaultdict(list)
    reflection_actors=[];actor_errors=[]
    for item in data['objects']:
        if item.get('foliage'):
            expected_foliage[item['asset']]+=1
            expected_positions[item['asset']].append({'name':item['name'],'location':item['ue_location_cm'],
                'scale':item['scale'],'rotation':item['ue_rotation_deg']})
            checks[item['name']+'_is_native_instance']=item['name'] not in by_name
            continue
        actor=by_name.get(item['name'])
        okay=isinstance(actor,unreal.StaticMeshActor)
        if okay:
            c=actor.static_mesh_component;rotation=actor.get_actor_rotation();wanted=item['ue_rotation_deg']
            okay=(sf.asset_path(c.static_mesh)==data['assets'][item['asset']]['unreal_asset_path']
                   and vector_error(sf.xyz(actor.get_actor_location()),item['ue_location_cm'])<.05
                   and vector_error(sf.xyz(actor.get_actor_scale3d()),item['scale'])<.0001
                   and max(angle_error(getattr(rotation,key),wanted.get(key,0)) for key in ('pitch','yaw','roll'))<.001
                   and not actor.get_editor_property('hidden') and c.is_visible())
            collides=item.get('collision') in ('complex','solid')
            okay=okay and actor.get_actor_enable_collision()==collides
            okay=okay and str(c.get_collision_profile_name())==('BlockAll' if collides else 'NoCollision')
            if item.get('material_override'):
                okay=okay and sf.asset_path(c.get_material(0))==item['material_override'].split('.')[0]
                if item['material_override'].split('.')[0]==sf.WATER:
                    reflection_actors.append(item['name'])
                    checks[item['name']+'_water_nonblocking']=not actor.get_actor_enable_collision()
                    import_settings=c.static_mesh.get_editor_property('asset_import_data')
                    checks[item['name']+'_vertex_mask_imported']=import_settings.get_editor_property('vertex_color_import_option')==unreal.VertexColorImportOption.REPLACE
            if item.get('collision')=='trunk':
                blocker=by_name.get(item['name']+'_TrunkCollision')
                checks[item['name']+'_trunk_only_collision']=bool(blocker and blocker.get_actor_enable_collision()
                    and not blocker.static_mesh_component.is_visible() and blocker.get_editor_property('hidden')
                    and str(blocker.static_mesh_component.get_collision_profile_name())=='BlockAll')
        checks[item['name']+'_saved_placement']=okay
        if not okay:actor_errors.append(item['name'])
    actual_foliage,actual_positions,nonblocking=native_foliage(actors)
    foliage_transforms=compare_foliage_transforms(actual_positions,expected_positions)
    checks['native_foliage_counts']=actual_foliage==dict(expected_foliage)
    checks['native_foliage_saved_transforms']=foliage_transforms['passed']
    checks['native_foliage_nonblocking']=nonblocking
    checks['four_reflective_water_surfaces']=len(reflection_actors)==4
    details['foliage']={'counts':actual_foliage,'total':sum(actual_foliage.values()),
        'native_actors':sum(isinstance(a,unreal.InstancedFoliageActor) for a in actors),'transform_comparison':foliage_transforms}
    details['reflection_water_actors']=reflection_actors
    details['actor_errors']=actor_errors

    landscapes=[a for a in actors if isinstance(a,unreal.Landscape)]
    checks['one_native_landscape']=len(landscapes)==1
    terrain_error=1e20;sample_count=0
    if landscapes:
        landscape=landscapes[0]
        heights=struct.unpack('<16129H',(ROOT/data['terrain_file']).read_bytes())
        errors=[]
        # GetHeightAtLocation is reliable within the collision extent; native edge
        # vertices are deliberately not claimed as sampled by this public API.
        for iy in range(1,126):
            for ix in range(1,126):
                expected=(heights[iy*127+ix]-32768)/128*100
                actual=unreal.AstraSceneLibrary.landscape_height_at(landscape,unreal.Vector(-5040+ix*80,-5040+iy*80,0))
                errors.append(abs(expected-actual))
        terrain_error=max(errors);sample_count=len(errors)
        checks['native_landscape_15625_height_samples']=terrain_error<.05
        checks['landscape_100_8m_grid']=vector_error(sf.xyz(landscape.get_actor_location()),[-5040,-5040,0])<.01 and vector_error(sf.xyz(landscape.get_actor_scale3d()),[80,80,100])<.001
        checks['landscape_uses_new_ground_material']=sf.asset_path(landscape.get_editor_property('landscape_material'))==sf.MATERIAL_DIR+'/M_SF_Landscape'
        start=by_name.get('PlayerStart_Starfall')
        if start:
            position=sf.xyz(start.get_actor_location())
            ground=unreal.AstraSceneLibrary.landscape_height_at(landscape,unreal.Vector(*position))
            checks['player_start_saved']=vector_error(position,data['spawn_cm'])<.01
            checks['player_start_above_walkable_landscape']=ground>-9990 and 88<=position[2]-ground<=250
            # The playable route must not start on a steep edge or puddle bowl.
            neighbours=[unreal.AstraSceneLibrary.landscape_height_at(landscape,unreal.Vector(position[0]+dx,position[1]+dy,0)) for dx,dy in ((30,0),(-30,0),(0,30),(0,-30))]
            checks['player_start_ground_slope']=max(abs(z-ground) for z in neighbours)<20
            details['player_start']={'position_cm':position,'landscape_z_cm':ground,'clearance_cm':position[2]-ground}
        else:
            checks['player_start_saved']=False
        ship_items=[o for o in data['objects'] if o['asset']=='SM_SF_LandedSpaceship']
        ship_meta=json.loads((sf.ART/'Layout/starfall_spaceship.json').read_text(encoding='utf-8'))['assets'][0]
        checks['one_landed_spaceship']=len(ship_items)==1
        checks['ship_baked_16deg_tilt']=abs(ship_meta.get('hull_lean_degrees',0)-16)<.01
        if len(ship_items)==1:
            actor=by_name[ship_items[0]['name']]
            rotation=actor.get_actor_rotation()
            checks['ship_not_double_tilted']=abs(rotation.pitch)<.01 and abs(rotation.roll)<.01
            pads=ship_meta.get('landing_pad_centres_m',[])
            pad_errors=[];pad_reports=[]
            for p in pads:
                # Metadata centres describe pad thickness; underside is local Z=0.
                contact=unreal.MathLibrary.transform_location(actor.get_actor_transform(),unreal.Vector(p[0]*100,-p[1]*100,0))
                ground=unreal.AstraSceneLibrary.landscape_height_at(landscape,contact)
                pad_errors.append(abs(contact.z-ground));pad_reports.append({'contact_cm':sf.xyz(contact),'ground_cm':ground,'error_cm':abs(contact.z-ground)})
            checks['three_grounded_landing_feet']=len(pads)==3 and max(pad_errors)<1.0
            details['landing_feet']=pad_reports
    details['landscape']={'size_m':100.8,'interior_samples':sample_count,'maximum_height_error_cm':terrain_error,'heightmap_sha256':sf.digest(ROOT/data['terrain_file'])}

    zones=data['zones']
    checks['mushroom_zone_15_by_15m']=zones['mushroom_meadow']['size_m']==[15,15]
    checks['glow_zone_5_by_5m']=zones['glow_grove']['size_m']==[5,5]
    checks['spring_small_water_radius']=abs(zones['spring']['water_radius_m']-2.05)<.001
    regular=[o for o in data['objects'] if 'SM_SF_Mushroom' in o['asset'] or 'SM_SF_Fungi' in o['asset']]
    glow=[o for o in data['objects'] if 'Glow' in o['asset']]
    pink=[o for o in data['objects'] if o['asset'].startswith('SM_SF_PinkTree')]
    checks['pink_trees_around_spring']=len(pink)>=3 and all(math.hypot(o['ue_location_cm'][0]/100-zones['spring']['center_m'][0],o['ue_location_cm'][1]/100-zones['spring']['center_m'][1])<12 for o in pink)
    checks['small_glow_colony_present']=len(glow)>0
    checks['regular_mushroom_colony_present']=len(regular)>0
    details['zones']=zones

    configs=[a for a in actors if isinstance(a,unreal.AstraLevelConfig)]
    checks['one_level_local_runtime_config']=len(configs)==1
    if configs:
        config=configs[0];shots=config.get_editor_property('demo_shots')
        checks['validation_prefix_SF']=config.get_editor_property('validation_prefix')=='SF'
        checks['seven_demo_routes']=len(shots)==len(data['demo_shots'])==7
        for shot,item in zip(shots,data['demo_shots']):
            points=[[v.x,v.y] for v in shot.get_editor_property('waypoints')]
            checks[item['name']+'_route']=str(shot.get_editor_property('name'))==item['name'] and points==item['points']
            checks[item['name']+'_camera']=abs(shot.get_editor_property('ortho_width')-item['width'])<.01 and vector_error(sf.xyz(shot.get_editor_property('camera_offset')),item['offset'])<.01
    game_mode=world.get_world_settings().get_editor_property('default_game_mode')
    checks['AstraGameMode_enabled']=bool(game_mode and game_mode.get_name()=='AstraGameMode')
    for item in data['review_cameras']:
        name=item['name'] if item['name'].startswith('Camera_') else 'Camera_'+item['name']
        camera=by_name.get(name)
        checks[name+'_orthographic']=isinstance(camera,unreal.CameraActor) and camera.camera_component.get_editor_property('projection_mode')==unreal.CameraProjectionMode.ORTHOGRAPHIC and abs(camera.camera_component.get_editor_property('ortho_width')-item['width'])<.01
    checks['existing_content_unchanged_during_validation']=all(sf.check_protected(before).values())
    report={'passed':all(checks.values()),'map':sf.MAP,'checks':checks,
        'failed_checks':[name for name,passed in checks.items() if not passed],
        'check_count':len(checks),'actor_count':len(actors),'details':details,
        'validation':'Fresh full-editor reload; saved asset/actor data and 15,625 native Landscape samples read without saving.'}
    (sf.ART/'Previews/UE_StarfallReloadValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not report['passed']:
        raise RuntimeError('Starfall reload validation failed: '+json.dumps(report['failed_checks']))
    unreal.log('STARFALL RELOAD VALIDATED '+json.dumps({'passed':True,'checks':len(checks),'actor_count':len(actors),'foliage_total':sum(actual_foliage.values())}))


if __name__=='__main__':
    main()
