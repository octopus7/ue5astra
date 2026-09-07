"""Capture real placed boulders with a temporary editor camera; never save the map."""
import unreal,math,time,json,hashlib,struct
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
out=ROOT/'ArtSource/Previews/UE_RockShapes.png'
map_file=ROOT/'Content/Astra/Maps/L_AstraWoodland.umap'
before=hashlib.sha256(map_file.read_bytes()).hexdigest()
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
look=[2530,3350,80];arm=2700;p=math.radians(58)
camera=es.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(look[0]-arm*math.cos(p),look[1],look[2]+arm*math.sin(p)),unreal.Rotator(pitch=-58))
camera.set_actor_label('Temporary_RockShapeDetail')
camera.camera_component.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC)
camera.camera_component.set_editor_property('ortho_width',1050)
camera.camera_component.set_editor_property('constrain_aspect_ratio',False)
es.set_selected_level_actors([])
unreal.EditorLevelLibrary.pilot_level_actor(camera)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_game_view(True)
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
started=time.monotonic();capture=None;submitted=None
original_mtime=out.stat().st_mtime_ns if out.exists() else 0
def tick(delta):
    global capture,submitted,camera
    elapsed=time.monotonic()-started
    if capture is None and elapsed>15:
        capture=unreal.AutomationLibrary.take_high_res_screenshot(1600,1000,str(out),camera=camera,delay=2.0)
        submitted=time.monotonic()
    ready=out.exists() and out.stat().st_mtime_ns!=original_mtime and capture and capture.is_task_done() and submitted and time.monotonic()-submitted>5
    if ready or elapsed>90:
        raw=out.read_bytes() if ready else b''
        report={'passed':bool(ready) and hashlib.sha256(map_file.read_bytes()).hexdigest()==before,
                'capture':'Unreal editor GPU screenshot; temporary camera; main map not saved',
                'look_at_cm':look,'pitch':-58,'ortho_width_cm':1050,'main_map_sha256':before,
                'size_px':list(struct.unpack('>II',raw[16:24])) if raw else None,
                'sha256':hashlib.sha256(raw).hexdigest() if raw else None}
        (out.parent/'UE_RockShapesCapture.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        unreal.log('ASTRA ROCK DETAIL '+json.dumps(report))
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.EditorLevelLibrary.eject_pilot_level_actor()
        es.destroy_actor(camera)
        camera=None
        capture=None
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        unreal.SystemLibrary.quit_editor()
handle=unreal.register_slate_post_tick_callback(tick)
