"""Apply native puddle reflections to the saved main map and add two QA views."""
import unreal,json,sys,math
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
import puddle_sky_reflection as puddles
if not unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland'):
    raise RuntimeError('Cannot load woodland map')
report=puddles.apply_puddles(save=False)
if not report['material']['passed']:raise RuntimeError('Native puddle material validation failed')
es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors={a.get_actor_label():a for a in es.get_all_level_actors()}
top_source=actors['Camera_Puddle']
for name in ['PuddleSkyTop','PuddleSkyLow']:
    camera=actors.get('Camera_'+name)
    if camera is None:
        camera=es.spawn_actor_from_class(unreal.CameraActor,unreal.Vector())
        camera.set_actor_label('Camera_'+name);camera.set_folder_path('ReviewCameras')
    if name=='PuddleSkyTop':
        camera.set_actor_location(top_source.get_actor_location(),False,False)
        camera.set_actor_rotation(top_source.get_actor_rotation(),False)
        camera.camera_component.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC)
        camera.camera_component.set_editor_property('ortho_width',top_source.camera_component.get_editor_property('ortho_width'))
    else:
        location=(-2780,-1680,230);look=(-1950,-1600,68)
        dx,dy,dz=[look[i]-location[i] for i in range(3)]
        camera.set_actor_location(unreal.Vector(*location),False,False)
        camera.set_actor_rotation(unreal.Rotator(pitch=math.degrees(math.atan2(dz,math.hypot(dx,dy))),yaw=math.degrees(math.atan2(dy,dx))),False)
        camera.camera_component.set_editor_property('projection_mode',unreal.CameraProjectionMode.PERSPECTIVE)
        camera.camera_component.set_editor_property('field_of_view',65)
    camera.camera_component.set_editor_property('constrain_aspect_ratio',False)
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Native puddles map save failed')
report['saved']=True
(ROOT/'ArtSource/Previews/UE_PuddleMainValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('ASTRA NATIVE PUDDLES SAVED '+json.dumps(report))
