"""Independently reload the saved map and verify the authored life-prop layer."""
import unreal,json,hashlib
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();ART=ROOT/'ArtSource'
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors();index={a.get_actor_label():a for a in actors}
manifest=json.loads((ART/'Layout/life_props_placement.json').read_text(encoding='utf-8'))
checks={};details=[]
for entry in manifest['new_instances']:
    a=index.get(entry['name']);ok=isinstance(a,unreal.StaticMeshActor)
    if ok:
        c=a.static_mesh_component;p=a.get_actor_location();r=a.get_actor_rotation();s=a.get_actor_scale3d()
        profile='NoCollision' if entry['collision']=='none' else 'BlockAll'
        ok=c.static_mesh is not None and c.static_mesh.get_name()==entry['asset'] and not a.get_editor_property('hidden') and c.is_visible()
        ok=ok and str(c.get_collision_profile_name())==profile and a.get_actor_enable_collision()==(profile=='BlockAll')
        ok=ok and max(abs(x-y) for x,y in zip([p.x,p.y,p.z],entry['ue_location_cm']))<.1
        ok=ok and max(abs(x-y) for x,y in zip([s.x,s.y,s.z],entry['scale']))<.001
        ok=ok and max(abs(getattr(r,k)-entry['ue_rotation_deg'][k]) for k in ['pitch','yaw','roll'])<.1
        details.append({'name':entry['name'],'asset':c.static_mesh.get_name(),'location_cm':[p.x,p.y,p.z],'collision':profile})
    checks[entry['name']]=bool(ok)
for entry in manifest['hidden_original_instances']:
    a=index.get(entry['name']);checks['preserved_'+entry['name']]=a is not None and a.get_editor_property('hidden') and not a.get_actor_enable_collision()
for kit in ['fishing_dock','fishing_props','home_life_props','woodland_life_props']:
    meta=json.loads((ART/f'Layout/{kit}.json').read_text(encoding='utf-8'))
    for spec in meta['assets']:
        mesh=unreal.EditorAssetLibrary.load_asset('/Game/Astra/Meshes/'+spec['asset_id'])
        slots=[str(s.material_interface.get_name()) for s in mesh.get_editor_property('static_materials')]
        settings=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).get_lod_build_settings(mesh,0)
        box=mesh.get_bounding_box();dims=[box.max.x-box.min.x,box.max.y-box.min.y,box.max.z-box.min.z]
        checks[spec['asset_id']+'_mesh']=mesh.get_num_triangles(0)==spec['triangles'] and slots==spec['material_slots'] and max(abs(a-b*100) for a,b in zip(dims,spec['dimensions_m']))<.15
        checks[spec['asset_id']+'_authored_normals']=not settings.get_editor_property('recompute_normals')
texture=unreal.EditorAssetLibrary.load_asset('/Game/Astra/Textures/T_FishingDockWood')
checks['wood_texture_srgb']=texture is not None and texture.get_editor_property('srgb') and texture.get_editor_property('compression_settings')==unreal.TextureCompressionSettings.TC_DEFAULT
checks['native_landscape_unchanged']=hashlib.sha256((ART/'Layout/landscape_height.r16').read_bytes()).hexdigest()==manifest['landscape_sha256']
checks['review_cameras']=all('Camera_'+name in index for name in ['Fishing','HomeLife','Picnic','Repair','CampLife'])
expected=json.loads((ART/'Layout/foliage_placement.json').read_text(encoding='utf-8'))['settings']['counts'];actual={k:0 for k in expected}
for a in actors:
    if isinstance(a,unreal.InstancedFoliageActor):
        for c in a.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
            if c.static_mesh and c.static_mesh.get_name() in actual:actual[c.static_mesh.get_name()]+=c.get_instance_count()
checks['filtered_foliage_saved']=actual==expected and sum(actual.values())==manifest['foliage_survivors']
report={'passed':all(checks.values()),'validation':'Independent full-editor reload; actual saved mesh/actor state','checks':checks,'new_instances':details,'foliage_counts':actual,'actor_count':len(actors)}
(ART/'Previews/UE_LifePropsReloadValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['passed']:raise RuntimeError('Life props reload failed: '+json.dumps({k:v for k,v in checks.items() if not v}))
unreal.log('ASTRA LIFE PROPS RELOAD VALIDATED '+json.dumps({'passed':True,'actors':len(actors),'checks':len(checks)}))
