"""Reload saved assets, validate import scale, materials and level collision."""
from pathlib import Path
import json
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/L_Main')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
labels = [a.get_actor_label() for a in actors]
report = {'level': '/Game/Maps/L_Main', 'assets': []}
assert 'Temporary_Test_Floor' not in labels
for name in ['SM_IslandTerrain', 'SM_IslandVillage', 'SM_IslandNature']:
    assert labels.count('Island_' + name) == 1
    mesh = unreal.load_asset('/Game/Island/Meshes/' + name)
    assert isinstance(mesh, unreal.StaticMesh)
    bbox = mesh.get_bounding_box()
    size = bbox.max - bbox.min
    assert 1000 < size.x < 15000, (name, 'wrong meter-to-centimeter scale', size)
    assert 1000 < size.y < 15000, (name, 'wrong meter-to-centimeter scale', size)
    materials = mesh.get_editor_property('static_materials')
    assert materials
    assert all(s.material_interface and s.material_interface.get_path_name().startswith('/Game/Island/Materials/') for s in materials)
    assert mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag') == unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    report['assets'].append({'name': name, 'size_cm': [size.x, size.y, size.z], 'material_slots': len(materials)})
assert labels.count('Island_OverviewCamera') == 1
assert labels.count('Island_Ocean') == 1
report['actor_count'] = len(actors)
report['status'] = 'passed'
path = Path(unreal.Paths.project_dir()) / 'Art/Previews/ue_validation.json'
path.write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('BEAST_ISLAND_VERIFY_OK ' + json.dumps(report))
