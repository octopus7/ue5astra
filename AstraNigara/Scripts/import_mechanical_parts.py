"""Import the authored centimeter-scale FBX parts for Niagara (inside UE 5.7)."""
import json
from pathlib import Path
import unreal

NAMES = ('SM_HexBolt', 'SM_HexNut', 'SM_CoilSpring', 'SM_SpurGear',
         'SM_Washer', 'SM_ShaftCoupler')
MESH_DIR = '/Game/VFX/SmallDestruction/Meshes'


def import_mechanical_parts(material):
    root = Path(unreal.Paths.project_dir()).resolve()
    source = root / 'ArtSource' / 'MechanicalParts'
    manifest = json.loads((source / 'mechanical_parts_report.json').read_text(encoding='utf-8'))
    entries = {entry['name']: entry for entry in manifest['assets']}
    assert set(entries) == set(NAMES), 'The source kit must contain all six mechanical parts'
    tasks = []
    for name in NAMES:
        filename = (source / entries[name]['fbx']).resolve()
        assert filename.is_relative_to(source.resolve()) and filename.is_file(), str(filename)
        task = unreal.AssetImportTask()
        task.filename = str(filename)
        task.destination_path = MESH_DIR
        task.destination_name = name
        task.automated = True
        task.save = False
        task.replace_existing = True
        task.factory = unreal.FbxFactory()
        options = unreal.FbxImportUI()
        options.import_mesh = True
        options.import_as_skeletal = False
        options.import_materials = False
        options.import_textures = False
        options.import_animations = False
        options.automated_import_should_detect_type = False
        options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        settings = options.static_mesh_import_data
        settings.combine_meshes = True
        settings.build_nanite = False
        settings.generate_lightmap_u_vs = False
        settings.auto_generate_collision = False
        settings.convert_scene = True
        settings.convert_scene_unit = True
        settings.import_uniform_scale = 1.0
        settings.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        task.options = options
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    report = {'units': 'centimeters', 'assets': []}
    for name in NAMES:
        mesh = unreal.load_asset(MESH_DIR + '/' + name)
        assert isinstance(mesh, unreal.StaticMesh), 'FBX import failed: ' + name
        bounds = mesh.get_bounding_box()
        dimensions = [float(getattr(bounds.max, axis) - getattr(bounds.min, axis)) for axis in ('x', 'y', 'z')]
        # Axis conversion may permute dimensions; their sorted sizes must agree.
        expected = sorted(entries[name]['dimensions_cm'])
        assert all(abs(a-b) < 0.03 for a, b in zip(sorted(dimensions), expected)), (name, dimensions, expected)
        vertices = subsystem.get_number_verts(mesh, 0)
        assert vertices > 0 and max(dimensions) <= 5.0, (name, dimensions, vertices)
        reduction = unreal.StaticMeshReductionOptions()
        reduction.auto_compute_lod_screen_size = False
        tiers = []
        for ratio, screen_size in ((1.0, 1.0), (.5, .025), (.2, .008)):
            tier = unreal.StaticMeshReductionSettings()
            tier.percent_triangles = ratio
            tier.screen_size = screen_size
            tiers.append(tier)
        reduction.reduction_settings = tiers
        assert subsystem.set_lods(mesh, reduction) == 3, 'Could not generate three LODs for ' + name
        for index in range(subsystem.get_number_materials(mesh)):
            mesh.set_material(index, material)
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        report['assets'].append({'name': name, 'asset': mesh.get_path_name(),
                                 'dimensions_cm': dimensions, 'render_vertices': vertices,
                                 'source_triangles': entries[name]['triangles'],
                                 'lod_render_vertices': [subsystem.get_number_verts(mesh, lod) for lod in range(3)],
                                 'lod_triangle_targets': [1.0, .5, .2],
                                 'lod_screen_sizes': [1.0, .025, .008]})
    output = root / 'Saved' / 'SmallDestruction' / 'mechanical_parts_import.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('ASTRA_MECHANICAL_PARTS_IMPORT_OK')
    return report
