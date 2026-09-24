"""Package the four existing waterfall actors as a reusable, native-component BP."""
import json
import shutil
from datetime import datetime
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
DEST = '/Game/VFX/Waterfall'
BP_PATH = DEST + '/Blueprints/BP_AnimeWaterfall'
LABELS = {'UpperStream': 'WF_UpperStream', 'WaterCurtain': 'WF_WaterCurtain',
          'ImpactApron': 'WF_ImpactApron', 'ImpactNiagara': 'WF_Impact_Niagara'}


def components(actor):
    return {c.get_name(): c for c in actor.get_components_by_class(unreal.SceneComponent)}


def check_instance(actor):
    cs = components(actor)
    assert set(LABELS).issubset(cs), list(cs)
    for name in ('UpperStream', 'WaterCurtain', 'ImpactApron'):
        assert cs[name].static_mesh == unreal.load_asset(DEST + '/Meshes/SM_WF_' + name)
    niagara = cs['ImpactNiagara']
    assert niagara.get_asset() == unreal.load_asset(DEST + '/NS_AnimeWaterfall')
    assert niagara.get_editor_property('auto_activate') and niagara.is_active()
    assert cs['ImpactApron'].get_editor_property('translucency_sort_priority') == 1
    assert niagara.get_editor_property('translucency_sort_priority') == 2
    return cs


def dependencies():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    options = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,
        include_hard_package_references=True, include_searchable_names=False,
        include_soft_management_references=False, include_hard_management_references=False)
    visited, pending = set(), [BP_PATH]
    while pending:
        package = pending.pop()
        if package in visited:
            continue
        visited.add(package)
        if package.startswith('/Script/'):
            continue
        pending.extend(str(p) for p in registry.get_dependencies(package, options))
    game = sorted(p for p in visited if p.startswith('/Game/'))
    assert all(p.startswith(DEST + '/') for p in game), game
    assert not any('AstraNigaraTools' in p for p in visited), sorted(visited)
    for p in game:
        assert unreal.EditorAssetLibrary.does_asset_exist(p), p
    return sorted(visited)


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert world.get_name() == 'L_AnimeWaterfall', 'Open L_AnimeWaterfall first'
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    by_label = {a.get_actor_label(): a for a in actors.get_all_level_actors()}
    previous = by_label.get('WF_AnimeWaterfall')
    if not any(label in by_label for label in LABELS.values()):
        assert previous, 'Source waterfall actors are missing'
        check_instance(previous)
        unreal.EditorAssetLibrary.sync_browser_to_objects([BP_PATH])
        unreal.log('WATERFALL_BLUEPRINT_ALREADY_PACKAGED')
        return
    assert all(label in by_label for label in LABELS.values()), 'Partial source actor set'
    sources = {name: by_label[label] for name, label in LABELS.items()}
    backup = ROOT / 'Saved' / 'WaterfallBlueprintBackup' / datetime.now().strftime('%Y%m%d_%H%M%S')
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'Content/Maps/L_AnimeWaterfall.umap', backup / 'L_AnimeWaterfall.umap')
    foliage_before = {a.get_path_name(): [c.get_instance_count() for c in
        a.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent)]
        for a in by_label.values() if isinstance(a, unreal.InstancedFoliageActor)}
    preserved = {a.get_path_name(): a.get_actor_transform().export_text() for a in by_label.values()
                 if a not in sources.values() and a != previous}
    eal = unreal.EditorAssetLibrary
    bp = unreal.load_asset(BP_PATH) if eal.does_asset_exist(BP_PATH) else None
    if bp is None:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property('parent_class', unreal.Actor)
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            'BP_AnimeWaterfall', DEST + '/Blueprints', unreal.Blueprint, factory)
    assert bp
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = subsystem.k2_gather_subobject_data_for_blueprint(bp)
    root_handle = next(h for h in handles if lib.is_root_component(lib.get_data(h)))
    root_component = lib.get_object_for_blueprint(lib.get_data(root_handle), bp)
    root_component.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    # Preserve the existing origin, orientation and each component's world transform.
    pivot = sources['WaterCurtain'].get_actor_transform()
    expected = {}
    for name, source in sources.items():
        cls = unreal.NiagaraComponent if name == 'ImpactNiagara' else unreal.StaticMeshComponent
        src = source.get_component_by_class(cls)
        expected[name] = src.get_world_transform()
        existing = {str(lib.get_variable_name(lib.get_data(h))): h
                    for h in subsystem.k2_gather_subobject_data_for_blueprint(bp)}
        handle = existing.get(name)
        if handle is None:
            handle, failure = subsystem.add_new_subobject(unreal.AddNewSubobjectParams(
                parent_handle=root_handle, new_class=cls, blueprint_context=bp))
            assert not str(failure), str(failure)
            assert subsystem.rename_subobject(handle, name)
        component = lib.get_object_for_blueprint(lib.get_data(handle), bp)
        component.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
        relative = unreal.MathLibrary.make_relative_transform(expected[name], pivot)
        component.set_editor_property('relative_location', relative.translation)
        component.set_editor_property('relative_rotation', relative.rotation.rotator())
        component.set_editor_property('relative_scale3d', relative.scale3d)
        for prop in ('cast_shadow', 'visible', 'hidden_in_game', 'translucency_sort_priority'):
            component.set_editor_property(prop, src.get_editor_property(prop))
        component.set_collision_enabled(src.get_collision_enabled())
        if name == 'ImpactNiagara':
            component.set_asset(src.get_asset())
            component.set_auto_activate(True)
        else:
            component.set_static_mesh(src.static_mesh)
            for index in range(src.get_num_materials()):
                component.set_material(index, src.get_material(index))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert eal.save_loaded_asset(bp)
    generated = bp.generated_class()
    assert generated
    with unreal.ScopedEditorTransaction('Package waterfall actors as BP_AnimeWaterfall'):
        instance = actors.spawn_actor_from_class(generated, pivot.translation, pivot.rotation.rotator())
        instance.set_actor_scale3d(pivot.scale3d)
        instance.set_actor_label('WF_AnimeWaterfall')
        try:
            actual = check_instance(instance)
            for name, original in expected.items():
                assert actual[name].get_world_transform().is_near_equal(original, 0.01, 0.001, 0.001), name
            # Exercise a non-zero translation and rotation before restoring the placement.
            instance.set_actor_location(pivot.translation + unreal.Vector(300, 200, 100), False, False)
            instance.set_actor_rotation(unreal.Rotator(0, 45, 0), False)
            for name in LABELS:
                component = actual[name]
                relative = unreal.MathLibrary.make_relative_transform(expected[name], pivot)
                target = unreal.MathLibrary.compose_transforms(relative, instance.get_actor_transform())
                assert component.get_world_transform().is_near_equal(target, 0.01, 0.001, 0.001), name
            instance.set_actor_transform(pivot, False, False)
            deps = dependencies()
        except Exception:
            actors.destroy_actor(instance)
            raise
        for source in sources.values():
            assert actors.destroy_actor(source)
        if previous:
            assert actors.destroy_actor(previous)
        actors.set_selected_level_actors([instance])
    after = {a.get_path_name(): a for a in actors.get_all_level_actors()}
    assert all(after[path].get_actor_transform().export_text() == transform
               for path, transform in preserved.items())
    for path, counts in foliage_before.items():
        assert [c.get_instance_count() for c in after[path].get_components_by_class(
            unreal.FoliageInstancedStaticMeshComponent)] == counts
    assert levels.save_current_level()
    report = {'passed': True, 'blueprint': BP_PATH, 'parent': '/Script/Engine.Actor',
              'components': list(LABELS), 'world_transforms_preserved': True,
              'move_rotate_check': True, 'foliage_preserved': True,
              'dependencies': deps, 'backup': str(backup)}
    (ROOT / 'Saved/waterfall_blueprint_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    eal.sync_browser_to_objects([BP_PATH])
    unreal.log('WATERFALL_BLUEPRINT_PACKAGED_OK')


if __name__ == '__main__':
    main()
