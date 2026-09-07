import unreal

MAP = "/Game/Maps/L_Main"
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if unreal.EditorAssetLibrary.does_asset_exist(MAP):
    raise RuntimeError("Main level already exists; refusing to overwrite.")
elif not levels.new_level(MAP):
    raise RuntimeError("Could not create main level")

def spawn(cls, label, location, rotation=unreal.Rotator()):
    actor = actors.spawn_actor_from_class(cls, unreal.Vector(*location), rotation)
    if not actor:
        raise RuntimeError("Failed to spawn " + label)
    actor.set_actor_label(label)
    return actor

sun = spawn(unreal.DirectionalLight, "Sun", (0, 0, 500), unreal.Rotator(-45, -30, 0))
sun.light_component.set_editor_property("intensity", 3.0)
sun.light_component.set_editor_property("atmosphere_sun_light", True)
spawn(unreal.SkyLight, "SkyLight", (0, 0, 300))
spawn(unreal.SkyAtmosphere, "SkyAtmosphere", (0, 0, 0))
spawn(unreal.PlayerStart, "PlayerStart", (0, 0, 120))
floor = spawn(unreal.StaticMeshActor, "Temporary_Test_Floor", (0, 0, -50))
floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube.Cube"))
floor.set_actor_scale3d(unreal.Vector(20, 20, 1))
if not levels.save_current_level():
    raise RuntimeError("Could not save main level")
unreal.log("BEASTCROSSING_SETUP_OK: " + MAP)
