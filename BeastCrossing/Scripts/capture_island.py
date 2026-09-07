"""Capture actual UE geometry through SceneCapture2D, independent of viewport mode."""
from pathlib import Path
import time
import unreal

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
ROOT = Path(unreal.Paths.project_dir())
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/L_Main')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
camera = next(a for a in actors if a.get_actor_label() == 'Island_OverviewCamera')
camera.set_actor_location(unreal.Vector(7800, 12800, 10400), False, False)
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(), unreal.Vector(0, 300, 150)), False)
camera.camera_component.set_editor_property('projection_mode', unreal.CameraProjectionMode.PERSPECTIVE)
camera.camera_component.set_editor_property('field_of_view', 39.5)
for actor in actors:
    if isinstance(actor, unreal.PlayerStart):
        actor.set_actor_location(unreal.Vector(0, 800, 380), False, False)
        actor.set_actor_rotation(unreal.Rotator(-10, -90, 0), False)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
editor.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
world = editor.get_editor_world()
exec((ROOT / 'Scripts/configure_island_lighting.py').read_text(encoding='utf-8'))
levels.save_current_level()
for command in ['viewmode lit', 'ShowFlag.Wireframe 0', 'r.ScreenPercentage 100', 'r.ViewDistanceScale 2', 'r.ShadowQuality 4', 'r.TextureStreaming 0']:
    unreal.SystemLibrary.execute_console_command(world, command)
actor_tools = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
capture = actor_tools.spawn_actor_from_class(unreal.SceneCapture2D, camera.get_actor_location(), camera.get_actor_rotation(), transient=True)
component = capture.get_component_by_class(unreal.SceneCaptureComponent2D)
target = unreal.RenderingLibrary.create_render_target2d(world, 1600, 1200, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
component.set_editor_property('texture_target', target)
component.set_editor_property('capture_source', unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
component.set_editor_property('fov_angle', 39.5)
component.set_editor_property('capture_every_frame', True)
component.set_editor_property('capture_on_movement', False)
started = time.monotonic()
started_wall = time.time()
output = ROOT / 'Art/Previews/island_unreal_overview.png'
def tick(delta):
    elapsed = time.monotonic() - started
    if elapsed > 20:
        unreal.RenderingLibrary.export_render_target(world, target, str(output.parent), output.name)
        unreal.log('BEAST_RENDER_CAPTURED ' + str(output))
        actor_tools.destroy_actor(capture)
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
handle = unreal.register_slate_post_tick_callback(tick)
