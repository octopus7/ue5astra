"""Read back the saved shoreline scene; never modify assets or actor state."""
import json
from pathlib import Path

import unreal


def inspect_current_map():
    import shoreline_foam
    import shoreline_surface_materials
    root = Path(unreal.Paths.project_dir()).resolve()
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    manifest = json.loads((root/'ArtSource/Layout/shoreline_site.json').read_text(encoding='utf-8-sig'))
    site = []
    for label, actor in actors.items():
        if not label.startswith('AST_Shoreline_') or not isinstance(actor, unreal.StaticMeshActor):
            continue
        component = actor.static_mesh_component
        site.append({'actor': label, 'mesh': component.static_mesh.get_path_name(),
                     'collision_profile': str(component.get_collision_profile_name()),
                     'actor_collision_enabled': actor.get_actor_enable_collision()})
    assert len(site) == 16, site
    assert all(a['collision_profile'] == 'NoCollision' and not a['actor_collision_enabled'] for a in site), site
    water = []
    for label, actor in actors.items():
        if not isinstance(actor, unreal.StaticMeshActor):
            continue
        component = actor.static_mesh_component
        if component.static_mesh and component.static_mesh.get_name() in ('SM_LakeSurface', 'SM_StreamSurface'):
            path = component.get_material(0).get_path_name()
            assert path.startswith('/Game/Astra/Materials/Shoreline/M_WaterFoam.'), (label, path)
            water.append({'actor': label, 'material': path})
    assert len(water) >= 2, water
    wet = []
    layout = json.loads((root/'ArtSource/Layout/woodland_layout.json').read_text(encoding='utf-8-sig'))
    for record in layout['objects']:
        if record['group'] != 'Rocks/LakeShore':
            continue
        actor = actors[record['name']]
        component = actor.static_mesh_component
        paths = [component.get_material(i).get_path_name() for i in range(component.get_num_materials())]
        assert all(p.startswith('/Game/Astra/Materials/Shoreline/Wet_') for p in paths), (record['name'], paths)
        wet.append({'actor': record['name'], 'materials': paths})
    assert len(wet) == 39, len(wet)
    library = unreal.EditorAssetLibrary
    names = json.loads((root/'ArtSource/Layout/shoreline_assets.json').read_text(encoding='utf-8-sig'))['palette_srgb_hex']
    surfaces = shoreline_surface_materials.inspect_materials({name: library.load_asset('/Game/Astra/Materials/Shoreline/'+name) for name in names})
    norms = {}
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for path in ('/Game/Astra/Meshes/ShorelineSite/SM_ShorelineSite_CurvedBed',
                 '/Game/Astra/Meshes/Shoreline/SM_SubmergedRock_Round_01',
                 '/Game/Astra/Meshes/Shoreline/SM_SubmergedRock_Flat_01',
                 '/Game/Astra/Meshes/Shoreline/SM_SubmergedRock_Small_01',
                 '/Game/Astra/Meshes/Shoreline/SM_SubmergedPebbles_01'):
        norms[path] = not subsystem.get_lod_build_settings(library.load_asset(path), 0).get_editor_property('recompute_normals')
    assert all(norms.values()), norms
    foam = shoreline_foam.validate_created_material()
    assert foam['passed'], foam
    material = library.load_asset('/Game/Astra/Materials/Shoreline/M_WaterFoam')
    defaults = json.loads(library.get_metadata_tag(material, 'AstraFoamParameters'))
    contour = json.loads(library.get_metadata_tag(material, 'AstraFoamContour'))
    assert len(contour['points_ue_m']) == len(manifest['foam_shoreline_contour_ue_m']) == 57
    return {'passed': True, 'scope': 'Saved map reopened in fresh UE process; actual actors, slots, collision profiles and material graphs',
            'site_actors': site, 'water_actors': water, 'wet_rocks': wet, 'surface_materials': surfaces,
            'authored_normals_preserved': norms, 'foam_graph': foam, 'foam_parameters': defaults, 'foam_contour': contour}


if __name__ == '__main__':
    import sys
    root = Path(unreal.Paths.project_dir()).resolve()
    sys.path.insert(0, str(root/'Scripts'))
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level('/Game/Astra/Maps/L_AstraShorelinePolishModuleReview'):
        raise RuntimeError('Saved shoreline polish review is missing')
    result = inspect_current_map()
    (root/'Saved/Shoreline/PolishSavedState.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('SAVED SHORELINE POLISH VERIFIED')
