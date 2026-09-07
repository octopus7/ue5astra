"""Reimport rock geometry only. Existing map, material files and actors stay intact."""
import unreal,json,hashlib,shutil
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();ART=ROOT/'ArtSource'
EAL=unreal.EditorAssetLibrary;AT=unreal.AssetToolsHelpers.get_asset_tools()
ES=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);SM=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
meta=json.loads((ART/'Layout/forest_fractured_rocks.json').read_text(encoding='utf-8'))
names={a['original_asset_id'] for a in meta['assets']}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def asset_path(a):return a.get_path_name() if a else None
def vec(v):return [v.x,v.y,v.z]
def actor_state(actor):
    p=actor.get_actor_location();r=actor.get_actor_rotation();s=actor.get_actor_scale3d()
    result={'label':actor.get_actor_label(),'location':vec(p),'rotation':[r.pitch,r.yaw,r.roll],'scale':vec(s),
            'hidden':actor.get_editor_property('hidden'),'collision':actor.get_actor_enable_collision()}
    if isinstance(actor,unreal.StaticMeshActor):
        c=actor.static_mesh_component
        result.update(mesh=asset_path(c.static_mesh),materials=[asset_path(m) for m in c.get_editor_property('override_materials')],
          effective_materials=[asset_path(c.get_material(i)) for i in range(c.get_num_materials())],visible=c.is_visible(),profile=str(c.get_collision_profile_name()))
    return result
map_file=ROOT/'Content/Astra/Maps/L_AstraWoodland.umap';map_hash=digest(map_file)
protected={str(p.relative_to(ROOT)):digest(p) for folder in ['Content/Astra/Materials','Content/Astra/Textures','Content/Astra/Foliage'] for p in (ROOT/folder).rglob('*.uasset')}
backup=ART/'Backups/BeforeFracturedRocks/UnrealMeshes';backup.mkdir(parents=True,exist_ok=True)
for name in names:
    source=ROOT/f'Content/Astra/Meshes/{name}.uasset';target=backup/source.name
    if not target.exists():shutil.copy2(source,target)
if not unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland'):raise RuntimeError('Main map load failed')
actors=ES.get_all_level_actors();before={a.get_path_name():actor_state(a) for a in actors}
rock_actors=[a for a in actors if isinstance(a,unreal.StaticMeshActor) and a.static_mesh_component.static_mesh and a.static_mesh_component.static_mesh.get_name() in names]
unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
mesh_reports=[];checks={}
for item in meta['assets']:
    name=item['original_asset_id'];path='/Game/Astra/Meshes/'+name;mesh=EAL.load_asset(path)
    old_box=mesh.get_bounding_box();old_bounds=[vec(old_box.min),vec(old_box.max)]
    old_slots=list(mesh.get_editor_property('static_materials'))
    old_materials=[s.material_interface for s in old_slots]
    if not old_materials:raise RuntimeError('Missing existing material: '+name)
    task=unreal.AssetImportTask();task.filename=str(ROOT/item['file']);task.destination_name=name;task.destination_path='/Game/Astra/Meshes'
    task.automated=True;task.save=False;task.replace_existing=True;task.factory=unreal.FbxFactory()
    options=unreal.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=False
    options.import_materials=False;options.import_textures=False;options.import_animations=False
    options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    d=options.static_mesh_import_data;d.combine_meshes=True;d.generate_lightmap_u_vs=False
    d.auto_generate_collision=False;d.convert_scene=True;d.convert_scene_unit=True
    d.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
    task.options=options;AT.import_asset_tasks([task]);mesh=EAL.load_asset(path)
    mesh.set_editor_property('static_materials',old_slots)
    SM.set_lod_material_slot(mesh,0,0,0)
    mesh.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    if not EAL.save_loaded_asset(mesh):raise RuntimeError('Mesh save failed: '+name)
    box=mesh.get_bounding_box();actual=[vec(box.min),vec(box.max)]
    error=max(abs(actual[j][i]-old_bounds[j][i]) for j in range(2) for i in range(3))
    settings=SM.get_lod_build_settings(mesh,0)
    checks[name+'_bounds']=error<.02
    checks[name+'_triangles']=mesh.get_num_triangles(0)==item['triangles']
    checks[name+'_authored_normals']=not settings.get_editor_property('recompute_normals')
    checks[name+'_single_painted_section']=mesh.get_num_sections(0)==1 and SM.get_lod_material_slot(mesh,0,0)==0
    checks[name+'_material']=[s.material_interface for s in mesh.get_editor_property('static_materials')]==old_materials
    mesh_reports.append({'asset':name,'source_fbx':item['file'],'triangles':mesh.get_num_triangles(0),'bounds_error_cm':error,
      'material':asset_path(mesh.get_material(0)),'preserved_material_slot_count':len(old_slots),'imported_vertices':SM.get_number_verts(mesh,0),'bounds_cm':actual})
after={a.get_path_name():actor_state(a) for a in ES.get_all_level_actors()}
checks['all_actor_states_unchanged']=before==after
checks['saved_main_map_unchanged']=map_hash==digest(map_file)
checks['existing_material_texture_foliage_files_unchanged']=all(digest(ROOT/p)==h for p,h in protected.items())
report={'passed':all(checks.values()),'checks':checks,'meshes':mesh_reports,'existing_rock_actor_references':len(rock_actors),
        'visible_rock_actors':sum(not a.get_editor_property('hidden') for a in rock_actors),
        'preserved_actor_material_overrides':{a.get_actor_label():before[a.get_path_name()].get('effective_materials') for a in rock_actors},
        'all_level_actor_count':len(actors),'main_map_sha256':map_hash,'protected_asset_sha256':protected}
(ART/'Previews/UE_FracturedRocksValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['passed']:raise RuntimeError('Fractured rock import validation failed '+json.dumps(checks))
unreal.log('ASTRA FRACTURED ROCKS IMPORTED '+json.dumps({'passed':True,'rock_actors':len(rock_actors),'meshes':mesh_reports}))
