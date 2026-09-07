import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level("/Game/Maps/L_Main"), "Map load failed"
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
labels = [a.get_actor_label() for a in actors]
for expected in ["Sun", "SkyLight", "SkyAtmosphere", "PlayerStart"]:
    assert labels.count(expected) == 1, (expected, labels)
if "Island_SM_IslandTerrain" in labels:
    from pathlib import Path
    exec((Path(__file__).parent / "verify_island.py").read_text(encoding="utf-8"))
else:
    floor = next(a for a in actors if a.get_actor_label() == "Temporary_Test_Floor")
    assert floor.static_mesh_component.static_mesh.get_path_name() == "/Engine/BasicShapes/Cube.Cube"
unreal.log("BEASTCROSSING_VERIFY_OK: " + str(labels))
