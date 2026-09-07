"""Execute with UnrealEditor-Cmd -ExecutePythonScript=<absolute script path>."""
import unreal

assets = unreal.EditorAssetLibrary
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
system_path = '/Game/VFX/NS_SimpleFountain'
source = '/Niagara/DefaultAssets/Templates/Systems/FountainLightweight'
system = assets.load_asset(system_path) if assets.does_asset_exist(system_path) else assets.duplicate_asset(source, system_path)
assert isinstance(system, unreal.NiagaraSystem), 'Niagara template duplication failed'
assert assets.save_loaded_asset(system)
if assets.does_asset_exist('/Game/Maps/L_Showcase'):
    assert levels.load_level('/Game/Maps/L_Showcase')
    for actor in actors.get_all_level_actors():
        if isinstance(actor, (unreal.StaticMeshActor, unreal.NiagaraActor, unreal.Light, unreal.SkyAtmosphere, unreal.PlayerStart, unreal.CameraActor)):
            actors.destroy_actor(actor)
else:
    assert levels.new_level('/Game/Maps/L_Showcase')

def mesh(name, asset, location, scale):
    unreal.log('ASTRA mesh begin: ' + name)
    actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*location))
    unreal.log('ASTRA mesh spawned: ' + name)
    actor.set_actor_label(name)
    actor.static_mesh_component.set_static_mesh(assets.load_asset(asset))
    actor.set_actor_scale3d(unreal.Vector(*scale))
    unreal.log('ASTRA mesh ready: ' + name)
    return actor

mesh('Showcase Floor', '/Engine/BasicShapes/Cube', (0, 0, -25), (16, 16, .5))
mesh('Fountain Pedestal', '/Engine/BasicShapes/Cylinder', (0, 0, 20), (2, 2, .4))
effect = actors.spawn_actor_from_class(unreal.NiagaraActor, unreal.Vector(0, 0, 45))
effect.set_actor_label('NS Simple Fountain - Auto Play')
component = effect.get_component_by_class(unreal.NiagaraComponent)
component.set_asset(system)
component.set_auto_activate(True)
light = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500), unreal.Rotator(-55, -35, 0))
light.light_component.set_editor_property('intensity', 4.0)
sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 400))
sky.light_component.set_editor_property('intensity', 1.0)
actors.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector())
actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(550, 0, 200), unreal.Rotator(-10, 180, 0))
camera = actors.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(650, -650, 380), unreal.Rotator(-17, 135, 0))
camera.set_actor_label('Showcase Camera')
camera.set_editor_property('auto_activate_for_player', unreal.AutoReceiveInput.PLAYER0)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(unreal.Vector(650, -650, 380), unreal.Rotator(-17, 135, 0))
assert levels.save_current_level()
assets.save_directory('/Game')
unreal.log('ASTRA_NIAGARA_BUILD_OK')
