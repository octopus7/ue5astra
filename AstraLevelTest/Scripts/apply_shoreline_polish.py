"""Apply the approved shoreline improvements to the currently loaded UE map.

Only the imported site actors, lake/stream component material overrides and
shore-rock material overrides are changed. Existing source water, puddle,
Landscape and rock material assets are preserved. No import-time side effects.
"""
import json
from pathlib import Path

import unreal


def apply_polish(save=True, refresh_site=True):
    root = Path(unreal.Paths.project_dir()).resolve()
    es = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or not world.get_path_name().startswith('/Game/Astra/Maps/'):
        raise RuntimeError('Open the intended existing Astra woodland map first')
    import import_shoreline_site
    import shoreline_foam
    import shoreline_surface_materials
    site_report = import_shoreline_site.apply_site(save=False) if refresh_site else None
    material = shoreline_foam.build_foam_material()
    water = []
    actors = {a.get_actor_label(): a for a in es.get_all_level_actors()}
    for actor in actors.values():
        if not isinstance(actor, unreal.StaticMeshActor):
            continue
        component = actor.static_mesh_component
        mesh = component.static_mesh
        if mesh and mesh.get_name() in ('SM_LakeSurface', 'SM_StreamSurface'):
            component.set_material(0, material)
            water.append({'actor': actor.get_actor_label(), 'mesh': mesh.get_path_name(),
                          'material': component.get_material(0).get_path_name(),
                          'hidden_in_game': bool(actor.get_editor_property('hidden'))})
    if not water:
        raise RuntimeError('No lake or stream surface found in the current map')
    wet_rocks = []
    if refresh_site and hasattr(shoreline_surface_materials, 'build_wet_variant'):
        layout = json.loads((root/'ArtSource/Layout/woodland_layout.json').read_text(encoding='utf-8'))
        variants = {}
        for record in layout['objects']:
            if record['group'] != 'Rocks/LakeShore':
                continue
            actor = actors.get(record['name'])
            if not isinstance(actor, unreal.StaticMeshActor):
                continue
            component = actor.static_mesh_component
            mesh = component.static_mesh
            if not mesh:
                continue
            assigned = []
            # Use the shared mesh's original slots, not a prior actor override.
            for index, slot in enumerate(mesh.get_editor_property('static_materials')):
                source = slot.material_interface
                if not isinstance(source, unreal.Material):
                    continue
                key = source.get_path_name()
                if key not in variants:
                    target = '/Game/Astra/Materials/Shoreline/Wet_' + source.get_name()
                    variants[key] = shoreline_surface_materials.build_wet_variant(source, target)
                component.set_material(index, variants[key])
                assigned.append(variants[key].get_path_name())
            wet_rocks.append({'actor': actor.get_actor_label(), 'materials': assigned})
    if save and not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError('Could not save the shoreline polish map')
    checks = shoreline_foam.validate_created_material(material.get_path_name().split('.')[0])
    if not checks['passed']:
        raise RuntimeError('Foam material graph validation failed: ' + repr(checks))
    surface_assets = {name: unreal.EditorAssetLibrary.load_asset('/Game/Astra/Materials/Shoreline/' + name)
                      for name in json.loads((root/'ArtSource/Layout/shoreline_assets.json').read_text(encoding='utf-8'))['palette_srgb_hex']}
    surfaces = shoreline_surface_materials.inspect_materials(surface_assets)
    bed = unreal.EditorAssetLibrary.load_asset('/Game/Astra/Meshes/ShorelineSite/SM_ShorelineSite_CurvedBed')
    settings = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).get_lod_build_settings(bed, 0)
    if settings.get_editor_property('recompute_normals'):
        raise RuntimeError('UE is recomputing authored smooth bed normals')
    report = {'map': world.get_path_name(), 'saved': bool(save), 'site': site_report,
              'ground_materials': surfaces, 'authored_bed_normals_preserved': True,
              'water_actors': water, 'wet_shore_rocks': wet_rocks, 'water_material_checks': checks}
    output = root/'Saved/Shoreline/polish_apply_result.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(apply_polish(), ensure_ascii=False, indent=2))
