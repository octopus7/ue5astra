"""Consistent soft daylight for the island and its UE preview."""
import unreal

def configure_island_lighting():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    cubemap = unreal.load_asset('/Engine/MapTemplates/Sky/DaylightAmbientCubemap')
    assert cubemap
    for actor in actors:
        if isinstance(actor, unreal.DirectionalLight):
            light = actor.light_component
            light.set_editor_property('intensity', 5.0)
            light.set_editor_property('light_source_angle', 5.0)
            actor.set_actor_rotation(unreal.Rotator(-55, -120, 0), False)
        elif isinstance(actor, unreal.SkyLight):
            sky = actor.light_component
            sky.set_editor_property('real_time_capture', False)
            sky.set_editor_property('source_type', unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
            sky.set_editor_property('cubemap', cubemap)
            sky.set_editor_property('intensity', 1.1)
            sky.set_editor_property('lower_hemisphere_is_black', False)
            sky.recapture_sky()
        elif actor.get_actor_label() == 'Island_Daylight':
            pp = actor.get_editor_property('settings')
            pp.set_editor_property('auto_exposure_bias', -0.5)
            actor.set_editor_property('settings', pp)

configure_island_lighting()
