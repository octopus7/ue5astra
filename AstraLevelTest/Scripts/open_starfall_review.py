"""Open Starfall in the editor for review and Play without changing startup defaults."""
import json
import re
from pathlib import Path
import unreal

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not levels.load_level('/Game/Astra/Maps/L_AstraStarfall'):
    raise RuntimeError('Starfall map has not been imported.')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
match=re.search(r'-AstraEditorReview=(SF\w+)',unreal.SystemLibrary.get_command_line())
name=match.group(1) if match else 'SFOverview'
camera=next(a for a in actors if a.get_actor_label()=='Camera_'+name)
unreal.EditorLevelLibrary.pilot_level_actor(camera)
unreal.get_editor_subsystem(unreal.EditorActorSubsystem).set_selected_level_actors([])
output=Path(unreal.Paths.project_saved_dir())/'AstraBuild/StarfallEditorReady.json'
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps({'editor_ready':True,'map':'/Game/Astra/Maps/L_AstraStarfall',
    'review_camera':name,'actors':len(actors)},indent=2),encoding='utf-8')
unreal.log('STARFALL EDITOR READY')
