"""Open the completed woodland map for interactive editor review and Play."""
import unreal,json
from pathlib import Path

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
overview=next(a for a in actors if a.get_actor_label()=='Camera_Overview')
unreal.EditorLevelLibrary.pilot_level_actor(overview)
unreal.get_editor_subsystem(unreal.EditorActorSubsystem).set_selected_level_actors([])
result={'editor_ready':True,'map':'/Game/Astra/Maps/L_AstraWoodland','actors':len(actors),
        'landscapes':sum(isinstance(a,unreal.Landscape) for a in actors),
        'source_angles':[a.light_component.get_editor_property('light_source_angle') for a in actors if isinstance(a,unreal.DirectionalLight)]}
out=Path(unreal.Paths.project_saved_dir())/'AstraBuild'/'editor_ready.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('ASTRA EDITOR READY '+json.dumps(result))
