"""Apply only the new cottage/woodland life props and fishing dock to the saved map.

Run inside the full UE editor after reviewing life_props_placement.json.
Existing material graphs, terrain, water, sky, camp and shoreline scripts are untouched.
This module has no import-time mutations; call main() or use -ExecutePythonScript.
"""
import hashlib
import importlib.util
import json
import math
import shutil
import traceback
from collections import Counter
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
ART = ROOT/'ArtSource'
MAP = '/Game/Astra/Maps/L_AstraWoodland'
SPECIES = ('SM_Grass','SM_Fern','SM_Flowers','SM_Mushrooms','SM_Reeds')
EAL = unreal.EditorAssetLibrary
ES = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
AT = unreal.AssetToolsHelpers.get_asset_tools()
ML = unreal.MaterialEditingLibrary
PREVIEW = ART/'Previews'
BACKUP = ART/'Backups/BeforeLifeProps'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def material_hashes():
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha256(p)
            for p in sorted((ROOT/'Content/Astra/Materials').rglob('*.uasset'))}


def xyz(vector):
    return [float(vector.x),float(vector.y),float(vector.z)]


def snapshot(actor):
    rotation=actor.get_actor_rotation()
    result={'name':actor.get_actor_label(),'ue_location_cm':xyz(actor.get_actor_location()),
            'ue_rotation_deg':{'pitch':rotation.pitch,'yaw':rotation.yaw,'roll':rotation.roll},
            'scale':xyz(actor.get_actor_scale3d()),'folder':str(actor.get_folder_path()),
            'actor_collision':actor.get_actor_enable_collision(),
            'hidden_in_game':bool(actor.get_editor_property('hidden'))}
    if isinstance(actor,unreal.StaticMeshActor):
        c=actor.static_mesh_component
        result.update(mesh=c.static_mesh.get_path_name() if c.static_mesh else None,
                      collision_profile=str(c.get_collision_profile_name()),
                      collision_enabled=str(c.get_collision_enabled()))
    return result


def backup_saved_map():
    BACKUP.mkdir(parents=True,exist_ok=True)
    source=ROOT/'Content/Astra/Maps/L_AstraWoodland.umap'
    if not source.is_file():
        raise RuntimeError('Existing woodland map file is missing')
    target=BACKUP/source.name
    if not target.exists():
        shutil.copy2(source,target)
        if sha256(source)!=sha256(target):
            raise RuntimeError('BeforeLifeProps map backup verification failed')
    for sidecar in source.parent.glob('L_AstraWoodland_BuiltData.*'):
        if not (BACKUP/sidecar.name).exists():
            shutil.copy2(sidecar,BACKUP/sidecar.name)
    return str(target)


def load_helpers():
    spec=importlib.util.spec_from_file_location('astra_life_import_helpers',ROOT/'Scripts/import_unreal_scene.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_path(value):
    p=Path(value)
    if p.is_absolute():
        candidate=p.resolve()
    elif p.parts and p.parts[0].lower()=='artsource':
        candidate=(ROOT/p).resolve()
    else:
        candidate=(ART/p).resolve()
    if not candidate.is_relative_to(ART.resolve()) or not candidate.is_file():
        raise RuntimeError('Missing or out-of-ArtSource asset source: '+str(value))
    return candidate


def import_new_texture(value, cache, newly_created):
    file=source_path(value)
    name=file.stem
    if name in cache:
        return cache[name]
    path='/Game/Astra/Textures/'+name
    if EAL.does_asset_exist(path):
        tex=EAL.load_asset(path)  # Existing textures are also left unchanged.
    else:
        task=unreal.AssetImportTask()
        task.filename=str(file);task.destination_path='/Game/Astra/Textures';task.destination_name=name
        task.automated=True;task.save=True;task.replace_existing=False
        AT.import_asset_tasks([task])
        tex=EAL.load_asset(path)
        if not tex:
            raise RuntimeError('Texture import failed: '+str(file))
        tex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_DEFAULT)
        tex.set_editor_property('srgb',True)
        tex.set_editor_property('address_x',unreal.TextureAddress.TA_WRAP)
        tex.set_editor_property('address_y',unreal.TextureAddress.TA_WRAP)
        tex.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
        if not EAL.save_loaded_asset(tex):
            raise RuntimeError('New texture save failed: '+name)
        newly_created.append(path)
    if not isinstance(tex,unreal.Texture2D):
        raise RuntimeError('Texture path did not resolve to Texture2D: '+path)
    cache[name]=tex
    return tex


def new_materials_only(b, selected_assets):
    # Never call build_materials(), build_water_materials(), newmat(), or delete expressions.
    names=sorted({name for meta in selected_assets.values() for name in meta['materials']})
    mats={};created=[];reused=[];texture_cache={};new_textures=[];texture_links={}
    palette=b.DATA['palette_srgb_hex']
    props_all=b.DATA.get('material_properties',{})
    for name in names:
        path='/Game/Astra/Materials/'+name
        if EAL.does_asset_exist(path):
            mats[name]=EAL.load_asset(path)
            if not mats[name]:raise RuntimeError('Existing material failed to load: '+path)
            reused.append(path)
            continue
        if name not in palette:
            raise RuntimeError('Palette entry missing for new material: '+name)
        # Only the new kit namespaces are eligible; old missing materials are not rebuilt.
        if not name.startswith(('M_HomeLife_','M_WoodlandLife_','M_Fishing_','M_Dock')):
            raise RuntimeError('Refusing to create material outside the new life-prop kit: '+name)
        m=AT.create_asset(name,'/Game/Astra/Materials',unreal.Material,unreal.MaterialFactoryNew())
        if not m:raise RuntimeError('New material create failed: '+name)
        props=props_all.get(name,{})
        base=b.color(m,b.linear(palette[name]))
        if props.get('base_color_texture'):
            tex=import_new_texture(props['base_color_texture'],texture_cache,new_textures)
            sample=b.expression(m,unreal.MaterialExpressionTextureSample)
            sample.set_editor_property('texture',tex)
            tint=props.get('tint_linear',[1.0,1.0,1.0])
            base=b.custom(m,'return TexColour * Tint;',{'TexColour':sample,'Tint':b.color(m,tint)})
            texture_links[name]={'texture':tex.get_path_name(),'tint_linear':tint}
        b.connect(base,unreal.MaterialProperty.MP_BASE_COLOR)
        for prop,key,default in ((unreal.MaterialProperty.MP_ROUGHNESS,'roughness',.86),
                                 (unreal.MaterialProperty.MP_SPECULAR,'specular',.15),
                                 (unreal.MaterialProperty.MP_METALLIC,'metallic',0.0)):
            b.connect(b.const(m,float(props.get(key,default))),prop)
        if props.get('emissive_strength',0)>0:
            strength=float(props['emissive_strength'])
            b.connect(b.color(m,[v*strength for v in b.linear(palette[name])]),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        if props.get('two_sided',False):m.set_editor_property('two_sided',True)
        mats[name]=b.finish(m)
        created.append(path)
    # Dock planks must have texture metadata, even when rerunning with existing materials.
    for name in ('M_DockWood','M_DockWoodLight','M_DockWoodDark'):
        if name not in mats or not props_all.get(name,{}).get('base_color_texture'):
            raise RuntimeError('Required dock wood albedo is missing: '+name)
    return mats,{'created':created,'reused_unchanged':reused,'new_textures':new_textures,'texture_links':texture_links}


def normalize_assets(data, ids):
    selected={}
    for name in ids:
        raw=dict(data['assets'][name])
        raw['materials']=list(raw.get('materials',raw.get('material_slots',[])))
        if not raw['materials']:raise RuntimeError('No material slots: '+name)
        raw['file']=str(source_path(raw['file']).relative_to(ART)).replace('\\','/')
        if raw.get('normal_import_method')=='FBXNIM_IMPORT_NORMALS_AND_TANGENTS':
            raw['normal_import_method']='IMPORT_NORMALS_AND_TANGENTS'
        selected[name]=raw
    return selected


def hidden_originals(index, entries):
    report=[]
    for entry in entries:
        for name in (entry['name'],entry['name']+'_TrunkCollision'):
            actor=index.get(name)
            if actor is None:
                if name==entry['name']:
                    raise RuntimeError('Original actor to preserve is missing: '+name)
                continue
            before=snapshot(actor)
            actor.set_actor_hidden_in_game(True)
            actor.set_actor_enable_collision(False)
            actor.set_is_temporarily_hidden_in_editor(True)
            actor.set_folder_path('PreservedBeforeLifeProps')
            if isinstance(actor,unreal.StaticMeshActor):
                c=actor.static_mesh_component
                c.set_visibility(False,True);c.set_hidden_in_game(True)
                c.set_collision_profile_name('NoCollision')
                c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            after=snapshot(actor)
            report.append({'name':name,'before':before,'after':after,
                           'transform_preserved':all(before[k]==after[k] for k in ('ue_location_cm','ue_rotation_deg','scale'))})
    return report


def place_new_actors(b,index,entries,meshes):
    measured=[]
    for entry in entries:
        actor=index.get(entry['name'])
        if actor is not None and not isinstance(actor,unreal.StaticMeshActor):
            raise RuntimeError('New placement label belongs to a non-mesh actor: '+entry['name'])
        if actor is None:
            actor=b.spawn(unreal.StaticMeshActor,entry['ue_location_cm'],label=entry['name'],folder=entry['group'])
        c=actor.static_mesh_component
        c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_static_mesh(meshes[entry['asset']])
        actor.set_actor_location(unreal.Vector(*entry['ue_location_cm']),False,False)
        actor.set_actor_rotation(unreal.Rotator(**entry['ue_rotation_deg']),False)
        actor.set_actor_scale3d(unreal.Vector(*entry['scale']))
        actor.set_folder_path(entry['group'])
        actor.set_actor_hidden_in_game(False);actor.set_is_temporarily_hidden_in_editor(False)
        c.set_visibility(True);c.set_hidden_in_game(False)
        blocking=entry['collision'] in ('complex','solid')
        c.set_collision_profile_name('BlockAll' if blocking else 'NoCollision')
        c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS if blocking else unreal.CollisionEnabled.NO_COLLISION)
        actor.set_actor_enable_collision(blocking)
        c.set_mobility(unreal.ComponentMobility.STATIC)
        index[entry['name']]=actor
        item=snapshot(actor);item['asset_id']=entry['asset']
        item['position_error_cm']=max(abs(item['ue_location_cm'][i]-entry['ue_location_cm'][i]) for i in range(3))
        measured.append(item)
    return measured


def foliage_counts():
    counts={s:0 for s in SPECIES};components=[];actors=[]
    for actor in ES.get_all_level_actors():
        if isinstance(actor,unreal.InstancedFoliageActor):
            actors.append(actor)
            for c in actor.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
                if c.static_mesh and c.static_mesh.get_name() in counts:
                    counts[c.static_mesh.get_name()]+=c.get_instance_count()
                    components.append(c)
    return counts,components,actors


def refresh_native_foliage(filtered,removed):
    records=filtered['instances']
    if any(r['asset'] not in SPECIES for r in records+removed):
        raise RuntimeError('Filtered foliage contains an unexpected species')
    wanted={s:sum(r['asset']==s for r in records) for s in SPECIES}
    removed_counts={s:sum(r['asset']==s for r in removed) for s in SPECIES}
    baseline={s:wanted[s]+removed_counts[s] for s in SPECIES}
    before,_,_=foliage_counts()
    if before!=baseline and before!=wanted:
        raise RuntimeError('Existing native foliage differs from the reviewed source: '+json.dumps({'actual':before,'before_expected':baseline,'after_expected':wanted}))
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    plans=[];type_settings=[]
    for kind in SPECIES:
        path='/Game/Astra/Foliage/FT_Astra_'+kind.removeprefix('SM_')
        ft=EAL.load_asset(path)
        if not isinstance(ft,unreal.FoliageType_InstancedStaticMesh):
            raise RuntimeError('Existing native foliage type is missing: '+path)
        ft_mesh=ft.get_editor_property('mesh')
        if not ft_mesh or ft_mesh.get_name()!=kind:
            raise RuntimeError('Foliage type mesh mismatch: '+path)
        items=[unreal.Transform(location=unreal.Vector(*r['ue_location_cm']),
                  rotation=unreal.Rotator(**r['ue_rotation_deg']),scale=unreal.Vector(*r['scale']))
               for r in records if r['asset']==kind]
        plans.append((ft,items))
        type_settings.append({'path':path,'mesh':ft_mesh.get_path_name(),
            'density':ft.get_editor_property('density'),
            'enable_density_scaling':ft.get_editor_property('enable_density_scaling')})
    # Complete reviewed instance records and the original map are retained in the backup.
    if not (BACKUP/'foliage_before_records.json').exists():
        write_json(BACKUP/'foliage_before_records.json',{'settings':filtered.get('settings',{}),'instances':records+removed})
    if before!=wanted:
        for ft,items in plans:
            unreal.InstancedFoliageActor.remove_all_instances(world,ft)
            unreal.InstancedFoliageActor.add_instances(world,ft,items)
    actual,components,actors=foliage_counts()
    if actual!=wanted:raise RuntimeError('Native foliage count check failed')
    for c in components:
        c.set_collision_profile_name('NoCollision')
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    no_collision=all(c.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION for c in components)
    report=dict(filtered.get('settings',{}))
    report.update(status='success',counts=actual,native_foliage_actor_count=len(actors),
        foliage_types=[t['path'] for t in type_settings],actual_type_settings=type_settings,
        converted_original_actors=sum(r.get('kind')=='converted' for r in records),
        additional_instances=sum(r.get('kind')=='additional' for r in records),
        additional_habitats=dict(Counter(r.get('habitat','unspecified') for r in records if r.get('kind')=='additional')),
        counts_before_life_props=baseline,life_props_removed_counts=removed_counts,
        life_props_removed_instances=len(removed),plant_collision='NoCollision',
        actual_collision_check=no_collision,source_actors_preserved_hidden=True,
        placement_layer='ArtSource/Layout/foliage_placement.json')
    return report,{'before_this_run':before,'baseline_before_life_props':baseline,'removed':removed_counts,
                   'expected':wanted,'actual':actual,'total':sum(actual.values()),'nonblocking':no_collision}


def dock_guards(b,index,deck):
    moved=[]
    for name in ('LakeBoundary_18','LakeBoundary_19','LakeBoundary_20'):
        actor=index.get(name)
        if not isinstance(actor,unreal.StaticMeshActor):
            raise RuntimeError('Required lake safety boundary is missing: '+name)
        before=snapshot(actor)
        if abs(before['ue_location_cm'][2]-65)>.01 and abs(before['ue_location_cm'][2]+135)>.01:
            raise RuntimeError('Lake boundary has an unexpected edited height: '+name)
        p=actor.get_actor_location();p.z=-135
        actor.set_actor_location(p,False,False)
        after=snapshot(actor)
        moved.append({'name':name,'before':before,'after':after,'target_z_cm':-135,
                      'xy_rotation_scale_preserved':before['ue_location_cm'][:2]==after['ue_location_cm'][:2]
                       and before['ue_rotation_deg']==after['ue_rotation_deg'] and before['scale']==after['scale']})
    default={'name':'FishingDock_FrontSafetyGuard','ue_location_cm':[1030,2800,145],
             'scale':[.18,4.6,1.8],'ue_rotation_deg':{'pitch':0,'yaw':0,'roll':0}}
    definitions={default['name']:default}
    for entry in deck.get('guards',[]):definitions[entry['name']]=entry
    guards=[]
    cube=EAL.load_asset('/Engine/BasicShapes/Cube')
    if not cube:raise RuntimeError('Engine collision cube missing')
    for entry in definitions.values():
        actor=index.get(entry['name'])
        if actor is None:actor=b.spawn(unreal.StaticMeshActor,entry['ue_location_cm'],label=entry['name'],folder='Collision/FishingDock')
        if not isinstance(actor,unreal.StaticMeshActor):raise RuntimeError('Guard label type conflict')
        c=actor.static_mesh_component;c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_static_mesh(cube);actor.set_actor_location(unreal.Vector(*entry['ue_location_cm']),False,False)
        actor.set_actor_rotation(unreal.Rotator(**entry.get('ue_rotation_deg',{})),False)
        actor.set_actor_scale3d(unreal.Vector(*entry['scale']))
        actor.set_folder_path('Collision/FishingDock');actor.set_actor_hidden_in_game(True)
        actor.set_actor_enable_collision(True);c.set_visibility(False);c.set_hidden_in_game(True)
        c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        c.set_cast_shadow(False);c.set_mobility(unreal.ComponentMobility.STATIC)
        index[entry['name']]=actor;guards.append(snapshot(actor))
    return moved,guards


def review_cameras(b,index):
    result=[]
    for name,look,width in (('Fishing',[620,2800,90],1800),('HomeLife',[1540,3840,120],2400),
                            ('Picnic',[-800,-1650,80],1000),('Repair',[-2800,-1100,90],1000),
                            ('CampLife',[3800,210,570],1200)):
        actor=index.get('Camera_'+name)
        p=math.radians(58);arm=2700
        loc=[look[0]-arm*math.cos(p),look[1],look[2]+arm*math.sin(p)]
        if actor is None:actor=b.spawn(unreal.CameraActor,loc,label='Camera_'+name,folder='ReviewCameras')
        if not isinstance(actor,unreal.CameraActor):raise RuntimeError('Camera label type conflict: '+name)
        actor.set_actor_location(unreal.Vector(*loc),False,False)
        actor.set_actor_rotation(unreal.Rotator(pitch=-58,yaw=0,roll=0),False)
        cc=actor.camera_component
        cc.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC)
        cc.set_editor_property('ortho_width',width);cc.set_editor_property('constrain_aspect_ratio',False)
        actor.set_folder_path('ReviewCameras');index['Camera_'+name]=actor
        result.append({'name':actor.get_actor_label(),'look_at_cm':look,'ortho_width_cm':cc.get_editor_property('ortho_width')})
    return result


def main():
    changes=read_json(ART/'Layout/life_props_placement.json')
    filtered=read_json(ART/'Layout/foliage_placement.json')
    ids=changes['asset_ids'];entries=changes['new_instances']
    if len(ids)!=15 or len(set(ids))!=15:
        raise RuntimeError('Expected exactly 15 distinct reviewed life-prop meshes')
    if len({e['name'] for e in entries})!=len(entries):raise RuntimeError('Duplicate placement labels')
    if any(e['asset'] not in ids for e in entries):raise RuntimeError('Placement references an unreviewed mesh')
    before_materials=material_hashes()
    backup_map=backup_saved_map()
    if not unreal.EditorLevelLibrary.load_level(MAP):raise RuntimeError('Unable to load woodland map')
    b=load_helpers()
    selected=normalize_assets(b.DATA,ids)
    index={a.get_actor_label():a for a in ES.get_all_level_actors()}
    tracked={e['name'] for e in changes.get('hidden_original_instances',[])}
    tracked.update(n+'_TrunkCollision' for n in list(tracked))
    tracked.update(('LakeBoundary_18','LakeBoundary_19','LakeBoundary_20'))
    if not (BACKUP/'actors_before.json').exists():
        write_json(BACKUP/'actors_before.json',[snapshot(index[n]) for n in sorted(tracked) if n in index])
    mats,material_report=new_materials_only(b,selected)
    unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
    complete_assets=b.DATA['assets']
    try:
        b.DATA['assets']=selected
        meshes=b.import_meshes(mats)
    finally:
        b.DATA['assets']=complete_assets
    for mesh in meshes.values():
        if not EAL.save_loaded_asset(mesh):raise RuntimeError('New mesh save failed: '+mesh.get_name())
    preserved=hidden_originals(index,changes.get('hidden_original_instances',[]))
    placements=place_new_actors(b,index,entries,meshes)
    foliage_report,foliage=refresh_native_foliage(filtered,changes.get('foliage_removed_instances',[]))
    barriers,guards=dock_guards(b,index,changes.get('deck',{}))
    cameras=review_cameras(b,index)
    current_hashes=material_hashes()
    modified_materials=[p for p,h in before_materials.items() if current_hashes.get(p)!=h]
    checks={'exactly_15_meshes':len(meshes)==15,
            'all_new_actors_placed':len(placements)==len(entries),
            'placement_positions_match':all(p['position_error_cm']<.01 for p in placements),
            'original_transforms_preserved':all(p['transform_preserved'] for p in preserved),
            'native_foliage_counts_match':foliage['actual']==foliage['expected'],
            'native_foliage_nonblocking':foliage['nonblocking'],
            'barrier_xy_rotation_scale_preserved':all(p['xy_rotation_scale_preserved'] for p in barriers),
            'dock_front_guard_blocks':any(p['name']=='FishingDock_FrontSafetyGuard' and p['actor_collision'] for p in guards),
            'existing_material_files_unchanged':not modified_materials}
    if not all(checks.values()):raise RuntimeError('Life-prop validation failed: '+json.dumps(checks))
    if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Life-prop map save failed')
    # No broad save_directory: only the map and explicitly created assets are saved.
    report={'status':'success','map':MAP,'backup_map':backup_map,'new_mesh_count':len(meshes),
        'new_actor_count':len(placements),'placements':placements,'preserved_originals':preserved,
        'foliage':foliage,'moved_barriers':barriers,'dock_guards':guards,'review_cameras':cameras,
        'materials':material_report,'preserved_existing_material_files':before_materials,
        'preserved_existing_material_paths':['/Game/Astra/Materials/'+Path(p).stem for p in before_materials],
        'modified_existing_material_files':modified_materials,'checks':checks,
        'meshes':[{'asset':name,'path':mesh.get_path_name(),
                   'bounds_cm':{'min':xyz(mesh.get_bounding_box().min),'max':xyz(mesh.get_bounding_box().max)},
                   'material_paths':[s.material_interface.get_path_name() if s.material_interface else None
                                     for s in mesh.get_editor_property('static_materials')]}
                  for name,mesh in meshes.items()]}
    foliage_report['actor_count']=len(ES.get_all_level_actors())
    write_json(PREVIEW/'UE_FoliageValidation.json',foliage_report)
    write_json(PREVIEW/'UE_LifePropsValidation.json',report)
    unreal.log('ASTRA LIFE PROPS SAVED '+json.dumps({'meshes':len(meshes),'actors':len(placements),'foliage':foliage['total'],'checks':checks}))
    return report


if __name__=='__main__':
    try:
        main()
    except Exception:
        failure={'status':'failed','error':traceback.format_exc()}
        write_json(PREVIEW/'UE_LifePropsValidation.json',failure)
        unreal.log_error(failure['error'])
        raise
