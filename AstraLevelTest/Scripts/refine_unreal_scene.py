import unreal,json,importlib.util
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
level='/Game/Astra/Maps/L_AstraWoodland'
unreal.EditorLevelLibrary.load_level(level)
spec=importlib.util.spec_from_file_location('astra_import',str(ROOT/'Scripts'/'import_unreal_scene.py'))
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
builder.build_materials()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
results={}
for a in actors:
    if isinstance(a,unreal.PostProcessVolume):
        s=a.get_editor_property('settings')
        s.set_editor_property('override_auto_exposure_apply_physical_camera_exposure',True)
        s.set_editor_property('auto_exposure_apply_physical_camera_exposure',False)
        s.set_editor_property('override_auto_exposure_method',True)
        s.set_editor_property('auto_exposure_method',unreal.AutoExposureMethod.AEM_MANUAL)
        s.set_editor_property('override_auto_exposure_bias',True)
        s.set_editor_property('auto_exposure_bias',0.0)
        a.set_editor_property('settings',s)
        results['physical_camera_exposure']=False
    if isinstance(a,unreal.DirectionalLight):
        results['source_angle']=a.light_component.get_editor_property('light_source_angle')
        results['sun_intensity']=a.light_component.get_editor_property('intensity')
    if isinstance(a,unreal.Landscape):
        results['landscape']=a.get_actor_label()
    if isinstance(a,unreal.CameraActor) and a.get_actor_label()=='Camera_Overview':
        a.camera_component.set_editor_property('ortho_width',15500)
results['actors']=len(actors)
unreal.EditorLevelLibrary.save_current_level()
(ROOT/'Saved'/'AstraBuild'/'scene_settings.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
unreal.log('ASTRA SETTINGS '+json.dumps(results))
