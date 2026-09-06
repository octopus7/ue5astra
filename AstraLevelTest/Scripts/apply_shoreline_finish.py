"""Integrate the independent shoreline finish into the current woodland map."""
import unreal,json,sys
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
if not unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland'):
    raise RuntimeError('Cannot load woodland map')
es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
def snapshot():
    actors=es.get_all_level_actors()
    placements={}
    for actor in actors:
        if actor.get_actor_label().startswith('ForestExpansion_'):
            p=actor.get_actor_location();r=actor.get_actor_rotation();s=actor.get_actor_scale3d()
            placements[actor.get_actor_label()]=[p.x,p.y,p.z,r.pitch,r.yaw,r.roll,s.x,s.y,s.z]
    foliage={}
    for actor in actors:
        if isinstance(actor,unreal.InstancedFoliageActor):
            for c in actor.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
                if c.static_mesh:
                    name=c.static_mesh.get_name();foliage[name]=foliage.get(name,0)+c.get_instance_count()
    return {'forest_placements':placements,'foliage':foliage,
            'landscape':[a.get_path_name() for a in actors if isinstance(a,unreal.Landscape)]}
before=snapshot()
import apply_shoreline_polish,puddle_sky_reflection
report=apply_shoreline_polish.apply_polish(save=False)
report['native_puddles']=puddle_sky_reflection.validate_created_material()
after=snapshot()
report['forest_and_foliage_preserved']=before==after
report['protected_state']=after
report['passed']=report['water_material_checks']['passed'] and report['native_puddles']['passed'] and before==after
if not report['passed']:raise RuntimeError('Shoreline integration validation failed')
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Shoreline main map save failed')
report['saved']=True
(ROOT/'ArtSource/Previews/UE_ShorelinePolishMainValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('ASTRA SHORELINE FINISH SAVED '+json.dumps(report))
