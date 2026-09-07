"""Serial UE integration for the Star Pond skeletal elephant.

No side effects on import. In the intended, already open map:
    actor, report = import_and_place((x_cm, y_cm, z_cm), yaw_degrees)
    # caller owns map save and whole-level validation

Imports only /Game/Astra/Characters/StarPond. Uses persisted
SkeletalMeshComponent.override_animation_data, not transient PlayAnimation.
The FBX contains the mesh, 16-bone skeleton and baked 8-second idle.
"""
import json
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
DEST='/Game/Astra/Characters/StarPond/Guardian'
MESH_NAME='SK_SP_UnicornElephant'
ANIM_NAME='A_SP_UnicornElephant_Idle'
LABEL='SP_UnicornElephant'
# export_starpond_elephant_ue.py bakes centimetres into mesh and bone data.
SKELETAL_IMPORT_SCALE=1.0
EAL=unreal.EditorAssetLibrary
AT=unreal.AssetToolsHelpers.get_asset_tools()
ML=unreal.MaterialEditingLibrary

def _rgba(value):
    c=[int(value[i:i+2],16)/255 for i in (0,2,4)]
    c=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c]
    return unreal.LinearColor(c[0],c[1],c[2],1)

def _asset_path(obj):
    return obj.get_path_name().split('.')[0] if obj else None

def _materials(metadata):
    result={}
    for name,props in metadata['materials'].items():
        path=DEST+'/Materials/'+name
        mat=EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        ML.delete_all_material_expressions(mat)
        color=ML.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-400,-100)
        color.set_editor_property('constant',_rgba(props['base_color']))
        ML.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
        for offset,(key,prop) in enumerate([('roughness',unreal.MaterialProperty.MP_ROUGHNESS),('metallic',unreal.MaterialProperty.MP_METALLIC)]):
            node=ML.create_material_expression(mat,unreal.MaterialExpressionConstant,-400,100+offset*150)
            node.set_editor_property('r',float(props.get(key,0)))
            ML.connect_material_property(node,'',prop)
        ML.set_material_usage(mat,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
        ML.recompile_material(mat)
        EAL.save_loaded_asset(mat)
        result[name]=mat
    return result

def _import_assets(metadata):
    # This module can also run in a placement-only editor session. Select the
    # legacy FBX importer explicitly so FbxImportUI options are actually used.
    unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
    options=unreal.FbxImportUI()
    # Epic 5.7 Python API lists these as Editor Properties. In particular
    # use_t0_as_ref_pose has no direct Python attribute descriptor; use the
    # reflected editor-property API consistently for all import settings.
    # https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/FbxSkeletalMeshImportData?application_version=5.7
    for name,value in {
        'automated_import_should_detect_type':False,
        'mesh_type_to_import':unreal.FBXImportType.FBXIT_SKELETAL_MESH,
        'original_import_type':unreal.FBXImportType.FBXIT_SKELETAL_MESH,
        'import_mesh':True,'import_as_skeletal':True,'import_animations':True,
        'import_materials':False,'import_textures':False,'create_physics_asset':False,
        'override_full_name':True,'override_animation_name':ANIM_NAME,
    }.items():options.set_editor_property(name,value)
    mesh_settings=options.get_editor_property('skeletal_mesh_import_data')
    for name,value in {
        'import_uniform_scale':SKELETAL_IMPORT_SCALE,'convert_scene':True,'convert_scene_unit':True,
        'force_front_x_axis':True,
        'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
        'use_t0_as_ref_pose':True,
        'update_skeleton_reference_pose':True,
    }.items():mesh_settings.set_editor_property(name,value)
    # https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/FbxAnimSequenceImportData?application_version=5.7
    anim_settings=options.get_editor_property('anim_sequence_import_data')
    for name,value in {
        'import_uniform_scale':SKELETAL_IMPORT_SCALE,'convert_scene':True,'convert_scene_unit':True,
        'force_front_x_axis':True,'use_default_sample_rate':False,
        'custom_sample_rate':30,'import_bone_tracks':True,
        'preserve_local_transform':False,
        'animation_length':unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME,
    }.items():anim_settings.set_editor_property(name,value)
    task=unreal.AssetImportTask()
    task.filename=str(ROOT/metadata['ue_fbx'])
    task.destination_path=DEST
    task.destination_name=MESH_NAME
    task.automated=True
    task.replace_existing=True
    task.replace_existing_settings=True
    task.save=True
    task.options=options
    task.factory=unreal.FbxFactory()
    AT.import_asset_tasks([task])
    imported=[EAL.load_asset(path) for path in task.imported_object_paths]
    meshes=[asset for asset in imported if isinstance(asset,unreal.SkeletalMesh)]
    animations=[asset for asset in imported if isinstance(asset,unreal.AnimSequence)]
    if not meshes:
        candidate=EAL.load_asset(DEST+'/'+MESH_NAME)
        if isinstance(candidate,unreal.SkeletalMesh):meshes=[candidate]
    if not animations:
        for path in EAL.list_assets(DEST,recursive=False):
            asset=EAL.load_asset(path)
            if isinstance(asset,unreal.AnimSequence):animations.append(asset)
    assert len(meshes)==1, 'A single real SkeletalMesh must be imported'
    assert len(animations)==1, 'A single real idle AnimSequence must be imported'
    mesh,animation=meshes[0],animations[0]
    # Reimports consult the saved asset import data, not just the task options.
    # Preserving raw local FBX transforms left the animation in Blender axes
    # while the mesh bind pose used UE axes (90-degree root mismatch).
    saved_anim_settings=animation.get_editor_property('asset_import_data')
    for name,value in {
        'import_uniform_scale':SKELETAL_IMPORT_SCALE,'convert_scene':True,'convert_scene_unit':True,
        'force_front_x_axis':True,'preserve_local_transform':False,
        'use_default_sample_rate':False,'custom_sample_rate':30,'import_bone_tracks':True,
    }.items():saved_anim_settings.set_editor_property(name,value)
    EAL.save_loaded_asset(animation)
    # The FBX task returns mesh/animation but can leave newly created dependent
    # packages dirty. Persist the owned skeleton and physics asset explicitly.
    for property_name in ('skeleton','physics_asset'):
        dependency=mesh.get_editor_property(property_name)
        if dependency:
            assert _asset_path(dependency).startswith(DEST+'/'), 'Unexpected shared skeletal dependency'
            assert EAL.save_loaded_asset(dependency), 'Could not save '+_asset_path(dependency)
    # Reimport the animation explicitly: updating a skeletal mesh alone can
    # retain the old clip's import transform. Reconstruct local bone transforms
    # from the converted FBX globals so unit conversion also reaches bones.
    options.set_editor_property('mesh_type_to_import',unreal.FBXImportType.FBXIT_ANIMATION)
    options.set_editor_property('original_import_type',unreal.FBXImportType.FBXIT_ANIMATION)
    options.set_editor_property('import_mesh',False)
    options.set_editor_property('skeleton',mesh.get_editor_property('skeleton'))
    anim_task=unreal.AssetImportTask()
    anim_task.filename=task.filename
    anim_task.destination_path=DEST
    anim_task.destination_name=ANIM_NAME
    anim_task.automated=True
    anim_task.replace_existing=True
    anim_task.replace_existing_settings=True
    anim_task.save=True
    anim_task.options=options
    anim_task.factory=unreal.FbxFactory()
    AT.import_asset_tasks([anim_task])
    animation=EAL.load_asset(DEST+'/'+ANIM_NAME)
    assert isinstance(animation,unreal.AnimSequence),'Animation-only reimport failed'
    if animation.get_name()!=ANIM_NAME:
        assert EAL.rename_asset(_asset_path(animation),DEST+'/'+ANIM_NAME)
        animation=EAL.load_asset(DEST+'/'+ANIM_NAME)
    assert float(animation.get_editor_property('sequence_length'))>7.95, 'Idle clip is missing or truncated'
    animation.set_editor_property('enable_root_motion',False)
    align_stationary_root(mesh,animation)
    EAL.save_loaded_asset(animation)
    return mesh,animation,list(task.imported_object_paths)

def align_stationary_root(mesh,animation):
    """Match the fixed idle root to the mesh after FBX axis conversion.

    The armature helper is removed by legacy FBX import. Its 90-degree
    transform can remain on the animation root while all child local tracks
    already match the mesh. Change only the proven stationary root track.
    """
    validate_animation(animation)  # Requires a stationary root and four feet.
    library=unreal.AnimationLibrary
    tracks=library.get_animation_track_names(animation)
    root=next(name for name in tracks if str(name).casefold()=='root')
    times=[0.,1.,2.,2.4,3.,4.,5.,6.,6.166666667,7.,8.]
    def values(name,time):
        t=library.get_bone_pose_for_time(animation,name,time,False)
        return [getattr(t.translation,k) for k in ('x','y','z')]+[getattr(t.rotation,k) for k in ('x','y','z','w')]+[getattr(t.scale3d,k) for k in ('x','y','z')]
    children={str(n):[values(n,t) for t in times] for n in tracks if n!=root}
    options=unreal.AnimPoseEvaluationOptions();options.optional_skeletal_mesh=mesh
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(animation,0.,options)
    reference=unreal.AnimPoseExtensions.get_ref_bone_pose(pose,root,unreal.AnimPoseSpaces.LOCAL)
    controller=animation.get_editor_property('controller')
    model=animation.get_editor_property('data_model_interface')
    count=model.get_number_of_keys()
    assert count>=241,'Expected the complete baked idle clip'
    assert controller.set_bone_track_keys(root,[reference.translation]*count,
        [reference.rotation]*count,[reference.scale3d]*count,False),'Could not align idle root'
    for name,before in children.items():
        after=[values(name,t) for t in times]
        assert max(abs(a-b) for aa,bb in zip(before,after) for a,b in zip(aa,bb))<1e-6,'Root correction changed child motion: '+name
    validate_bind_pose(mesh,animation)
    unreal.log('STARPOND_ROOT_ALIGNED '+str(count)+' keys; all child tracks preserved')

def validate_actor(actor):
    """May also be run after re-opening the saved map to verify persistence."""
    component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
    data=component.get_editor_property('animation_data')
    animation=data.get_editor_property('anim_to_play')
    mesh=component.get_skeletal_mesh_asset()
    result={
        'actor':actor.get_actor_label(),
        'mesh':_asset_path(mesh),'mesh_class':mesh.get_class().get_name(),
        'animation':_asset_path(animation),'animation_class':animation.get_class().get_name(),
        'animation_mode':str(component.get_animation_mode()),
        'saved_looping':bool(data.get_editor_property('saved_looping')),
        'saved_playing':bool(data.get_editor_property('saved_playing')),
        'saved_play_rate':float(data.get_editor_property('saved_play_rate')),
        'duration_seconds':float(animation.get_editor_property('sequence_length')),
        'root_motion':bool(animation.get_editor_property('enable_root_motion')),
        'skeletal_bone_count':component.get_num_bones(),
        'location_cm':[actor.get_actor_location().x,actor.get_actor_location().y,actor.get_actor_location().z],
    }
    assert result['saved_looping'] and result['saved_playing']
    assert result['mesh_class']=='SkeletalMesh' and result['animation_class']=='AnimSequence'
    assert result['skeletal_bone_count']>=16
    assert 7.95<=result['duration_seconds']<=8.05
    assert not result['root_motion']
    return result

def validate_physical_actor(actor, metadata=None):
    """Validate imported centimetre dimensions and actual placed foot bones."""
    if metadata is None:
        metadata=json.loads((ROOT/'ArtSource/Layout/starpond_elephant.json').read_text(encoding='utf-8'))
    component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
    mesh=component.get_skeletal_mesh_asset()
    bounds=mesh.get_imported_bounds()
    extent=bounds.box_extent;origin=bounds.origin
    location=actor.get_actor_location();rotation=actor.get_actor_rotation();scale=actor.get_actor_scale3d()
    height=float(extent.z)*2
    floor=float(origin.z-extent.z)
    assert abs(height-metadata['overall_height_m']*100)<15, 'Elephant import height is not approximately 252 cm: '+str(height)
    assert abs(floor)<1,'Imported elephant feet are not at local ground: '+str(floor)
    assert abs(rotation.pitch)<.001 and abs(rotation.roll)<.001,'Elephant must have yaw rotation only'
    assert max(abs(scale.x-1),abs(scale.y-1),abs(scale.z-1))<1e-6,'Elephant actor scale must stay 1'
    feet={name:component.get_socket_location(name) for name in metadata['bones'] if name.startswith('Foot_')}
    errors={name:abs(pos.z-location.z-metadata['bones'][name]['head_m'][2]*100) for name,pos in feet.items()}
    assert max(errors.values())<1,'Elephant foot bone grounding error exceeds 1 cm: '+repr(errors)
    def distance(a,b):
        return ((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2)**.5
    distances={}
    for a,b in [('Foot_Front_L','Foot_Front_R'),('Foot_Back_L','Foot_Back_R'),('Foot_Front_L','Foot_Back_L')]:
        actual=distance(feet[a],feet[b])
        av=metadata['bones'][a]['head_m'];bv=metadata['bones'][b]['head_m']
        expected=sum((av[i]-bv[i])**2 for i in range(3))**.5*100
        assert abs(actual-expected)<1,'Imported foot spacing scale mismatch: '+str((a,b,actual,expected))
        distances[a+'__'+b]={'actual_cm':actual,'expected_cm':expected}
    return {'import_uniform_scale':SKELETAL_IMPORT_SCALE,'imported_height_cm':height,
            'imported_local_ground_z_cm':floor,'actor_scale':[scale.x,scale.y,scale.z],
            'actor_rotation':{'roll':rotation.roll,'pitch':rotation.pitch,'yaw':rotation.yaw},
            'foot_world_positions_cm':{name:[p.x,p.y,p.z] for name,p in feet.items()},
            'foot_grounding_errors_cm':errors,'foot_spacing':distances}

def validate_animation(animation):
    """Sample the imported UE AnimSequence itself, including root and feet."""
    # Confirmed in Epic's 5.7 Python API (AnimationLibrary, editor module):
    # get_animation_track_names, get_bone_pose_for_time and get_num_frames.
    library=unreal.AnimationLibrary
    imported_tracks=[str(name) for name in library.get_animation_track_names(animation)]
    # FName identity is case-insensitive. UE 5.7 reports lower-case animation
    # track strings while preserving the authored case on skeletal bones.
    # The actual editor diagnostics contain all 16 tracks, including Root and
    # every foot; no missing-track or planted-foot checks are skipped here.
    track_by_identity={name.casefold():name for name in imported_tracks}
    metadata=json.loads((ROOT/'ArtSource/Layout/starpond_elephant.json').read_text(encoding='utf-8'))
    tracks=list(metadata['bones'])
    missing=[name for name in tracks if name.casefold() not in track_by_identity]
    assert not missing,'Missing authored UE animation bone tracks: '+repr(missing)
    def sampled(name,time):
        pose=library.get_bone_pose_for_time(animation,track_by_identity[name.casefold()],time,False)
        t=pose.translation;r=pose.rotation;s=pose.scale3d
        return [t.x,t.y,t.z,r.x,r.y,r.z,r.w,s.x,s.y,s.z]
    def difference(a,b):
        # q and -q represent the same rotation. Compare both hemispheres.
        q_delta=min(max(abs(a[i]-b[i]) for i in range(3,7)),
                    max(abs(a[i]+b[i]) for i in range(3,7)))
        return max(q_delta,max(abs(a[i]-b[i]) for i in [0,1,2,7,8,9]))
    times=[0,1,2,2.4,3,4,5,6,6.166666667,7,8]
    sampled_tracks={name:[sampled(name,time) for time in times] for name in tracks}
    loop_error=max(difference(values[0],values[-1]) for values in sampled_tracks.values())
    planted=['Root','Foot_Front_L','Foot_Front_R','Foot_Back_L','Foot_Back_R']
    assert all(name in sampled_tracks for name in planted)
    planted_error=max(difference(row,sampled_tracks[name][0]) for name in planted for row in sampled_tracks[name])
    changed={name:max(difference(row,rows[0]) for row in rows) for name,rows in sampled_tracks.items()}
    assert loop_error<.001,'UE animation loop endpoints differ'
    assert planted_error<.001,'UE root or feet drift during idle'
    assert changed.get('Body',0)>.001 and changed.get('Trunk_1',0)>.001,'UE bone tracks must animate'
    assert all(changed[name]>.001 for name in ['Ear_L','Ear_R','Tail']), 'UE secondary-motion tracks must animate'
    assert all(changed[name]>.5 for name in ['Blink_L','Blink_R']), 'UE blinking tracks must close the eyes'
    return {'num_frames':library.get_num_frames(animation),'track_names':tracks,
            'imported_track_names':imported_tracks,
            'sample_times_seconds':times,'loop_endpoint_max_component_error':loop_error,
            'planted_bone_max_component_error':planted_error,'sampled_change_by_bone':changed}


def validate_bind_pose(mesh,animation):
    """The first animation pose must use the same axes as the mesh bind pose."""
    import math
    options=unreal.AnimPoseEvaluationOptions();options.optional_skeletal_mesh=mesh
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(animation,0.,options)
    rows={}
    for name in unreal.AnimPoseExtensions.get_bone_names(pose):
        a=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.LOCAL)
        r=unreal.AnimPoseExtensions.get_ref_bone_pose(pose,name,unreal.AnimPoseSpaces.LOCAL)
        position=max(abs(getattr(a.translation,k)-getattr(r.translation,k)) for k in ('x','y','z'))
        dot=sum(getattr(a.rotation,k)*getattr(r.rotation,k) for k in ('x','y','z','w'))
        angle=math.degrees(2*math.acos(min(1.,abs(dot))))
        scale=max(abs(getattr(a.scale3d,k)-getattr(r.scale3d,k)) for k in ('x','y','z'))
        rows[str(name)]={'position_error_cm':position,'rotation_error_degrees':angle,'scale_error':scale}
    assert all(r['position_error_cm']<.1 and r['rotation_error_degrees']<.2 and r['scale_error']<.001 for r in rows.values()), 'Mesh/animation bind pose mismatch: '+repr(rows)
    return rows

def import_and_place(location_cm, yaw=0):
    """Import/update this kit and return (actor, report), leaving map save to caller.

    location_cm is the bottom-of-feet position. Front is +X after FBX scene
    conversion; yaw is the intended UE actor yaw. No collision is enabled on
    the display mesh; place a navigation blocker if desired in the level.
    """
    metadata=json.loads((ROOT/'ArtSource/Layout/starpond_elephant.json').read_text(encoding='utf-8'))
    materials=_materials(metadata)
    mesh,animation,imported=_import_assets(metadata)
    slots=list(mesh.get_editor_property('materials'))
    assigned=[]
    for index,slot in enumerate(slots):
        name=str(slot.get_editor_property('material_slot_name'))
        if name not in materials:
            name=str(slot.get_editor_property('imported_material_slot_name'))
        assert name in materials, 'Unexpected material slot: '+name
        slot.set_editor_property('material_interface',materials[name])
        assigned.append(name)
    mesh.set_editor_property('materials',slots)
    EAL.save_loaded_asset(mesh)
    subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing=[a for a in subsystem.get_all_level_actors() if a.get_actor_label()==LABEL]
    assert len(existing)<=1, 'Duplicate SP elephant actors require review'
    actor=existing[0] if existing else subsystem.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(*location_cm),unreal.Rotator(yaw=float(yaw)))
    actor.set_actor_label(LABEL)
    actor.set_actor_location(unreal.Vector(*location_cm),False,True)
    actor.set_actor_rotation(unreal.Rotator(yaw=float(yaw)),True)
    actor.set_actor_scale3d(unreal.Vector(1,1,1))
    actor.set_folder_path('StarPond/Characters')
    component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_skeletal_mesh_asset(mesh)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    component.override_animation_data(animation,True,True,0.0,1.0)
    for index,name in enumerate(assigned):component.set_material(index,materials[name])
    report=validate_actor(actor)
    report['physical_dimensions_and_grounding']=validate_physical_actor(actor,metadata)
    report['imported_animation_samples']=validate_animation(animation)
    report['mesh_animation_bind_pose']=validate_bind_pose(mesh,animation)
    report['imported_assets']=imported
    report['material_slots']=assigned
    report['serialized_method']='SkeletalMeshComponent.override_animation_data'
    report['source_validation']='ArtSource/Previews/Blender_StarPondElephant_Validation.json'
    report['map_saved_by_module']=False
    report['fbx_source_units']=metadata['ue_fbx_units']
    report['blender_source_units']=metadata['units']
    report['skeletal_import_uniform_scale']=SKELETAL_IMPORT_SCALE
    path=ROOT/'ArtSource/Previews/UE_StarPondElephant_ImportValidation.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('STARPOND_ELEPHANT_IMPORTED '+json.dumps(report))
    return actor,report
