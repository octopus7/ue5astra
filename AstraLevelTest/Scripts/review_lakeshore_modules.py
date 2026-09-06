"""Exercise independent modules in disposable copies of the woodland map.

Run in the full UE editor with -ExecutePythonScript and -AstraModuleReview=Puddle
or Shoreline. No changes are made to L_AstraWoodland or its material assets.
"""
import importlib
import json
import math
import re
import sys
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT/'Scripts'))
ART = ROOT/'ArtSource'
OUT = ROOT/'Saved'/'Shoreline'
OUT.mkdir(parents=True, exist_ok=True)
EAL = unreal.EditorAssetLibrary
ML = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
ES = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def linear(value):
    values = [int(value[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values)


def solid_material(name, color):
    path = '/Game/Astra/Materials/ModuleReview/' + name
    mat = EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(name, '/Game/Astra/Materials/ModuleReview', unreal.Material, unreal.MaterialFactoryNew())
    ML.delete_all_material_expressions(mat)
    node = ML.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector)
    node.set_editor_property('constant', unreal.LinearColor(*linear(color), 1))
    ML.connect_material_property(node, '', unreal.MaterialProperty.MP_BASE_COLOR)
    rough = ML.create_material_expression(mat, unreal.MaterialExpressionConstant)
    rough.set_editor_property('r', .86)
    ML.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
    ML.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    return mat


def import_context_mesh(name, file, material_map=None):
    folder = '/Game/Astra/Meshes/ModuleReview'
    task = unreal.AssetImportTask()
    task.filename = str(file)
    task.destination_path = folder
    task.destination_name = name
    task.automated = True
    task.save = True
    task.replace_existing = True
    task.factory = unreal.FbxFactory()
    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.import_materials = False
    options.import_textures = False
    options.import_animations = False
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    data = options.static_mesh_import_data
    data.combine_meshes = True
    data.generate_lightmap_u_vs = False
    data.auto_generate_collision = False
    data.convert_scene = True
    data.convert_scene_unit = True
    data.vertex_color_import_option = unreal.VertexColorImportOption.REPLACE
    task.options = options
    AT.import_asset_tasks([task])
    asset = EAL.load_asset(folder + '/' + name)
    if not asset: raise RuntimeError('Context FBX import failed: ' + name)
    for i, slot in enumerate(asset.get_editor_property('static_materials')):
        key = str(slot.material_slot_name)
        if material_map and key in material_map:
            asset.set_material(i, material_map[key])
    EAL.save_loaded_asset(asset)
    return asset


def spawn(cls, label, location, rotation=None):
    obj = ES.spawn_actor_from_class(cls, unreal.Vector(*location), rotation or unreal.Rotator())
    obj.set_actor_label(label)
    return obj


def copy_review_map(kind):
    path = '/Game/Astra/Maps/L_Astra' + kind + 'ModuleReview'
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not EAL.does_asset_exist(path):
        # The level subsystem loads a template into an untitled world before
        # saving. Generic asset duplication leaves a second live World behind.
        if not levels.new_level_from_template(path, '/Game/Astra/Maps/L_AstraWoodland'):
            raise RuntimeError('Unable to create review map from template')
    elif not levels.load_level(path):
        raise RuntimeError('Unable to open review map')
    return path


def puddle_review():
    path = copy_review_map('Puddle')
    module = importlib.import_module('puddle_cloud_trick')
    mat = module.build_puddle_material('/Game/Astra/Materials/ModuleReview/M_PuddleCloudReview')
    mesh = import_context_mesh('SM_PuddleCloudReview', ART/'Meshes'/'SM_Puddle.fbx')
    mesh.set_material(0, mat)
    EAL.save_loaded_asset(mesh)
    count = 0
    for actor in ES.get_all_level_actors():
        if isinstance(actor, unreal.StaticMeshActor):
            old = actor.static_mesh_component.static_mesh
            if old and ('Puddle' in old.get_name()):
                actor.static_mesh_component.set_static_mesh(mesh)
                actor.static_mesh_component.set_material(0, mat)
                count += 1
    camera = next(a for a in ES.get_all_level_actors() if a.get_actor_label() in ('Camera_Puddle', 'Camera_PuddleCloud'))
    camera.set_actor_label('Camera_PuddleCloud')
    camera.camera_component.set_editor_property('ortho_width', 1000)
    if not count: raise RuntimeError('No puddles in the review map')
    if not unreal.EditorLevelLibrary.save_current_level(): raise RuntimeError('Review save failed')
    checks = module.validate_created_material(mat.get_path_name().split('.')[0])
    if not checks['passed']: raise RuntimeError('Puddle graph verification failed: ' + repr(checks))
    return {'map': path, 'puddle_components': count, 'material': mat.get_path_name(), 'review_camera': 'PuddleCloud', 'material_checks': checks}


def verify_saved_shoreline():
    path = '/Game/Astra/Maps/L_AstraShorelineModuleReview'
    if not EAL.does_asset_exist(path): return {'available': False}
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(path):
        raise RuntimeError('Could not reload shoreline review map')
    actors = [a for a in ES.get_all_level_actors() if a.get_actor_label().startswith('AST_Shoreline_')]
    expected = json.loads((ART/'Layout'/'shoreline_site.json').read_text(encoding='utf-8'))
    if len(actors) != len(expected['objects']): raise RuntimeError('Saved shoreline actor count mismatch')
    for actor in actors:
        component = actor.static_mesh_component
        if (actor.get_actor_enable_collision()
                or str(component.get_collision_profile_name()) != 'NoCollision'
                or component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION):
            raise RuntimeError('Collision state not preserved: ' + actor.get_actor_label())
    return {'available': True, 'passed': True, 'reloaded_actor_count': len(actors), 'collision_profiles_persisted': True}


def shoreline_review():
    path = copy_review_map('Shoreline')
    layout = json.loads((ART/'Layout'/'woodland_layout.json').read_text(encoding='utf-8'))
    site = json.loads((ART/'Layout'/'shoreline_site.json').read_text(encoding='utf-8'))
    actors = {a.get_actor_label(): a for a in ES.get_all_level_actors()}
    # The copied baseline predates the committed house terrain grading.
    # Replace only this review world's Landscape from the committed heightmap.
    for actor in list(actors.values()):
        if isinstance(actor, unreal.Landscape): ES.destroy_actor(actor)
    if not unreal.AstraSceneLibrary.create_terrain(EAL.load_asset('/Game/Astra/Materials/M_Landscape')):
        raise RuntimeError('Review Landscape generation failed')
    house_spec = json.loads((ART/'Layout'/'pink_house_assets.json').read_text(encoding='utf-8'))
    mats = {}
    for name, color in house_spec['palette_srgb_hex'].items():
        source = '/Game/Astra/Materials/' + name
        mats[name] = EAL.load_asset(source) if EAL.does_asset_exist(source) else solid_material(name, color)
    houses = {name: import_context_mesh(name, ART/'Meshes'/(name+'.fbx'), mats)
              for name in ('SM_PinkRoofHouse', 'SM_FrontWell')}
    desired = {o['name']: o for o in layout['objects']}
    old_layout = json.loads((ART/'Layout'/'pink_house_placement.json').read_text(encoding='utf-8'))
    for name in old_layout['removed_existing_actor_names']:
        for label in (name, name+'_TrunkCollision'):
            if label in actors:
                actors[label].set_actor_hidden_in_game(True)
                actors[label].set_actor_enable_collision(False)
    for name, record in desired.items():
        actor = actors.get(name)
        if record['asset'] in houses:
            if actor is None: actor = spawn(unreal.StaticMeshActor, name, record['ue_location_cm'])
            actor.static_mesh_component.set_static_mesh(houses[record['asset']])
            actor.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        if actor:
            actor.set_actor_location(unreal.Vector(*record['ue_location_cm']), False, False)
            actor.set_actor_scale3d(unreal.Vector(*record['scale']))
            actor.set_actor_rotation(unreal.Rotator(**record['ue_rotation_deg']), False)
    # A deliberately simple transparent review film lets the geometry be judged.
    # The original task owns the final lake/stream material and its integration.
    mat = solid_material('M_ShorelineReviewFilm', '3A929E')
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    ML.delete_all_material_expressions(mat)
    color = ML.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector)
    color.set_editor_property('constant', unreal.LinearColor(*linear('54A9B1'), 1))
    ML.connect_material_property(color, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    depth = ML.create_material_expression(mat, unreal.MaterialExpressionDepthFade)
    depth.set_editor_property('fade_distance_default', 70)
    fade = ML.create_material_expression(mat, unreal.MaterialExpressionMultiply)
    fade.set_editor_property('const_b', .28)
    ML.connect_material_expressions(depth, '', fade, 'A')
    ML.connect_material_property(fade, '', unreal.MaterialProperty.MP_OPACITY)
    ML.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    for actor in ES.get_all_level_actors():
        if isinstance(actor, unreal.StaticMeshActor):
            mesh = actor.static_mesh_component.static_mesh
            if mesh and mesh.get_name() in ('SM_LakeSurface', 'SM_StreamSurface'):
                actor.static_mesh_component.set_material(0, mat)
    report = importlib.import_module('import_shoreline_site').apply_site(save=True)
    return {'map': path, 'site': report, 'review_water': 'Unlit transparent geometry-review film; final water owned by source task'}


def main():
    mode = re.search(r'-AstraModuleReview=(\w+)', unreal.SystemLibrary.get_command_line())
    kind = mode.group(1) if mode else 'Puddle'
    unreal.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
    try:
        if kind == 'Puddle':
            report = puddle_review()
            report['shoreline_saved_state'] = verify_saved_shoreline()
        elif kind == 'Shoreline': report = shoreline_review()
        else: raise ValueError('Unknown review mode: ' + kind)
        report['passed'] = True
        (OUT/(kind+'_ModuleReview.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        unreal.log('ASTRA MODULE REVIEW READY ' + json.dumps(report, ensure_ascii=False))
    except Exception:
        import traceback
        (OUT/(kind+'_ModuleReview.json')).write_text(json.dumps({'passed': False, 'error': traceback.format_exc()}, indent=2), encoding='utf-8')
        raise


if __name__ == '__main__': main()
