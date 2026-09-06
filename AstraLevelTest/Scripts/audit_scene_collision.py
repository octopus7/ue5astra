import unreal,json
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rows=[]
for a in actors:
    center,extent=a.get_actor_bounds(False)
    if max(extent.x,extent.y,extent.z)>10000 or isinstance(a,unreal.PlayerStart):
        row={'actor':a.get_actor_label(),'position':str(a.get_actor_location()),'extent':str(extent),'collision':a.get_actor_enable_collision()}
        if isinstance(a,unreal.StaticMeshActor):
            c=a.static_mesh_component
            row.update(component_collision=str(c.get_collision_enabled()),profile=str(c.get_collision_profile_name()))
        rows.append(row)
sun=next(a for a in actors if isinstance(a,unreal.DirectionalLight))
fog=next(a for a in actors if isinstance(a,unreal.ExponentialHeightFog))
dome=next(a for a in actors if a.get_actor_label()=='CloudSkyDome')
land=next(a for a in actors if isinstance(a,unreal.Landscape))
result={'large_actors':rows,'actor_count':len(actors),
        'directional_source_angle':sun.light_component.get_editor_property('light_source_angle'),
        'fog_density':fog.component.get_editor_property('fog_density'),
        'landscape_count':sum(isinstance(a,unreal.Landscape) for a in actors),
        'well_ground_cm':unreal.AstraSceneLibrary.landscape_height_at(land,unreal.Vector(1250,4130,0))}
assert not dome.get_actor_enable_collision()
assert dome.static_mesh_component.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
assert result['directional_source_angle']==50
assert abs(result['well_ground_cm']-98.4375)<1
result['passed']=True
(root/'ArtSource/Previews/UE_SceneValidation.json').write_text(json.dumps(result,indent=2))
unreal.log('ASTRA COLLISION AUDIT '+str(result))
