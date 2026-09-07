"""Create project materials, four-emitter systems, and a calibrated showcase."""
import json
import runpy
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
EAL = unreal.EditorAssetLibrary
ML = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LEVELS = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
MATERIAL_DIR = '/Game/VFX/SmallDestruction/Materials'


def node(material, cls, x=0, y=0):
    return ML.create_material_expression(material, cls, x, y)


def scalar(material, value):
    result = node(material, unreal.MaterialExpressionConstant)
    result.set_editor_property('r', value)
    return result


def color(material, values):
    result = node(material, unreal.MaterialExpressionConstant3Vector)
    result.set_editor_property('constant', unreal.LinearColor(*values, 1))
    return result


def connect(material, expression, prop, output=''):
    assert ML.connect_material_property(expression, output, prop)


def custom(material, code, inputs, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1):
    result = node(material, unreal.MaterialExpressionCustom, -200, 0)
    result.set_editor_property('code', code)
    result.set_editor_property('output_type', output_type)
    pins = []
    for name in inputs:
        pin = unreal.CustomInput()
        pin.set_editor_property('input_name', name)
        pins.append(pin)
    result.set_editor_property('inputs', pins)
    for name, expression in inputs.items():
        source, output = expression if isinstance(expression, tuple) else (expression, '')
        assert ML.connect_material_expressions(source, output, result, name)
    return result


def material(name, blend=unreal.BlendMode.BLEND_OPAQUE, unlit=True):
    path = MATERIAL_DIR + '/' + name
    result = EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(name, MATERIAL_DIR, unreal.Material, unreal.MaterialFactoryNew())
    assert result
    ML.delete_all_material_expressions(result)
    result.set_editor_property('blend_mode', blend)
    result.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT if unlit else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    result.set_editor_property('two_sided', True)
    return result


def finish(result):
    ML.recompile_material(result)
    assert EAL.save_loaded_asset(result)
    return result


def build_materials():
    debris = material('M_Debris', unlit=False)
    debris.set_editor_property('used_with_niagara_mesh_particles', True)
    connect(debris, color(debris, (.13, .085, .045)), unreal.MaterialProperty.MP_BASE_COLOR)
    connect(debris, scalar(debris, .9), unreal.MaterialProperty.MP_ROUGHNESS)
    finish(debris)

    # Procedural soft, irregular billboards: no downloaded flipbook dependency.
    mask_code = '''float2 p=UV*2-1;
float r=length(p);
float turbulence=0.75+0.18*sin(p.x*16+sin(p.y*12)+T*7)+0.07*sin(p.y*31-p.x*13-T*9);
return pow(saturate((1-r)*turbulence),1.4);'''
    flame = material('M_Flame', unreal.BlendMode.BLEND_ADDITIVE)
    flame.set_editor_property('used_with_niagara_sprites', True)
    uv = node(flame, unreal.MaterialExpressionTextureCoordinate)
    particle = node(flame, unreal.MaterialExpressionParticleColor)
    mask = custom(flame, mask_code, {'UV': uv, 'T': node(flame, unreal.MaterialExpressionTime)})
    emit = custom(flame, 'return lerp(float3(1.0,0.09,0.005),float3(1.0,0.85,0.22),Mask*Mask)*5.0;', {'Mask': mask}, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    connect(flame, emit, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    connect(flame, custom(flame, 'return Mask*A;', {'Mask': mask, 'A': (particle, 'A')}), unreal.MaterialProperty.MP_OPACITY)
    finish(flame)

    smoke = material('M_Smoke', unreal.BlendMode.BLEND_TRANSLUCENT)
    smoke.set_editor_property('used_with_niagara_sprites', True)
    uv = node(smoke, unreal.MaterialExpressionTextureCoordinate)
    particle = node(smoke, unreal.MaterialExpressionParticleColor)
    mask = custom(smoke, mask_code, {'UV': uv, 'T': node(smoke, unreal.MaterialExpressionTime)})
    connect(smoke, color(smoke, (.008, .010, .012)), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    connect(smoke, custom(smoke, 'return saturate(Mask*A*1.25);', {'Mask': mask, 'A': (particle, 'A')}), unreal.MaterialProperty.MP_OPACITY)
    finish(smoke)

    heat = material('M_HeatDistortion', unreal.BlendMode.BLEND_TRANSLUCENT)
    heat.set_editor_property('used_with_niagara_sprites', True)
    heat.set_editor_property('refraction_method', unreal.RefractionMode.RM_2D_OFFSET)
    uv = node(heat, unreal.MaterialExpressionTextureCoordinate)
    particle = node(heat, unreal.MaterialExpressionParticleColor)
    distortion = custom(heat, 'float2 p=UV*2-1; float m=pow(saturate(1-length(p)),2); return p*m*A*0.016;', {'UV': uv, 'A': (particle, 'A')}, unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    connect(heat, distortion, unreal.MaterialProperty.MP_REFRACTION)
    connect(heat, scalar(heat, 0), unreal.MaterialProperty.MP_OPACITY)
    connect(heat, color(heat, (0, 0, 0)), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(heat)

    stage = material('M_Stage')
    position = node(stage, unreal.MaterialExpressionWorldPosition)
    floor_pattern = custom(stage, 'float2 cell=abs(frac(Pos.xy/10)-0.5); float gridEdge=step(0.465,max(cell.x,cell.y)); return lerp(float3(0.035,0.045,0.06),float3(0.13,0.17,0.21),gridEdge);', {'Pos':position}, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    connect(stage, floor_pattern, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(stage)
    grid = material('M_ScaleGrid')
    position = node(grid, unreal.MaterialExpressionWorldPosition)
    pattern = custom(grid, 'float2 cell=abs(frac(Pos.yz/10)-0.5); float gridEdge=step(0.465,max(cell.x,cell.y)); return lerp(float3(0.055,0.075,0.10),float3(0.26,0.34,0.40),gridEdge);', {'Pos':position}, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    connect(grid, pattern, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(grid)
    rim = material('M_MeterRim')
    connect(rim, color(rim, (.8, .33, .045)), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(rim)
    return [debris, flame, smoke, heat], stage, grid, rim


def mesh(label, asset, position, scale, mat):
    actor = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*position))
    actor.set_actor_label(label)
    actor.static_mesh_component.set_static_mesh(EAL.load_asset(asset))
    actor.static_mesh_component.set_material(0, mat)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    return actor


def build():
    LEVELS.eject_pilot_level_actor()
    materials, stage, grid, rim = build_materials()
    library = unreal.AstraNiagaraLibrary
    one_shot = library.create_small_destruction('/Game/VFX/SmallDestruction/NS_SmallDestruction', materials, False)
    looping = library.create_small_destruction('/Game/VFX/SmallDestruction/NS_SmallDestruction_Showcase', materials, True)
    assert one_shot and looping
    assert EAL.save_loaded_asset(one_shot)
    assert EAL.save_loaded_asset(looping)
    map_path = '/Game/Maps/L_SmallDestructionShowcase'
    if EAL.does_asset_exist(map_path):
        assert LEVELS.load_level(map_path)
        # Only replace generated actors. Other project maps and user actors are untouched.
        for actor in ACTORS.get_all_level_actors():
            if actor.get_actor_label().startswith('SD_'):
                ACTORS.destroy_actor(actor)
    else:
        assert LEVELS.new_level(map_path)

    mesh('SD_Floor', '/Engine/BasicShapes/Cube', (0, 0, -8), (5, 5, .1), stage)
    mesh('SD_100cm_Diameter', '/Engine/BasicShapes/Cylinder', (0, 0, 2), (1, 1, .08), rim)
    mesh('SD_Platform', '/Engine/BasicShapes/Cylinder', (0, 0, 6), (.98, .98, .02), stage)
    mesh('SD_10cm_Grid_Backdrop', '/Engine/BasicShapes/Cube', (-70, 0, 75), (.025, 2.5, 1.5), grid)
    effect = ACTORS.spawn_actor_from_class(unreal.NiagaraActor, unreal.Vector(0, 0, 12))
    effect.set_actor_label('SD_SmallDestruction_Looping')
    component = effect.get_component_by_class(unreal.NiagaraComponent)
    component.set_asset(looping)
    component.set_auto_activate(True)

    camera_pos = unreal.Vector(185, -210, 125)
    camera_rot = unreal.MathLibrary.find_look_at_rotation(camera_pos, unreal.Vector(0, 0, 32))
    camera = ACTORS.spawn_actor_from_class(unreal.CameraActor, camera_pos, camera_rot)
    camera.set_actor_label('SD_Showcase_Camera')
    camera.camera_component.set_editor_property('field_of_view', 42)
    camera.set_editor_property('auto_activate_for_player', unreal.AutoReceiveInput.PLAYER0)
    light = ACTORS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 200), unreal.Rotator(pitch=-50, yaw=-30, roll=0))
    light.set_actor_label('SD_KeyLight')
    light.light_component.set_editor_property('intensity', 6)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_pos, camera_rot)
    ACTORS.set_selected_level_actors([])
    LEVELS.editor_set_game_view(True)
    library.enable_viewport_realtime()
    assert LEVELS.save_current_level()
    report = {'map': map_path, 'one_shot': json.loads(library.describe_system(one_shot)), 'showcase': json.loads(library.describe_system(looping))}
    out = ROOT / 'Saved' / 'SmallDestruction'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'build_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    runpy.run_path(str(ROOT / 'Scripts' / 'validate_small_destruction.py'))
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_pos, camera_rot)
    for actor in ACTORS.get_all_level_actors():
        if actor.get_actor_label() == 'SD_Showcase_Camera':
            unreal.EditorLevelLibrary.pilot_level_actor(actor)
            break
    LEVELS.editor_set_game_view(True)
    library.enable_viewport_realtime()
    unreal.log('ASTRA_SMALL_DESTRUCTION_BUILD_OK')
    runpy.run_path(str(ROOT / 'Scripts' / 'editor_status.py'))


build()
