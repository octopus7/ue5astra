"""Import Blender FBX assemblies and place them in the existing main level."""
from pathlib import Path
import json
import shutil
import unreal

ROOT = Path(unreal.Paths.project_dir())
manifest = json.loads((ROOT / 'Art/Exports/manifest.json').read_text(encoding='utf-8'))
lib = unreal.EditorAssetLibrary
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
mel = unreal.MaterialEditingLibrary
assert levels.load_level('/Game/Maps/L_Main')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
backup = ROOT / 'Saved/Backups/L_Main_initial.umap'
backup.parent.mkdir(parents=True, exist_ok=True)
if not backup.exists():
    shutil.copy2(ROOT / 'Content/Maps/L_Main.umap', backup)

def solid_material(name, color, roughness):
    path = '/Game/Island/Materials/' + name
    mat = unreal.load_asset(path) if lib.does_asset_exist(path) else None
    if not mat:
        mat = asset_tools.create_asset(name, '/Game/Island/Materials', unreal.Material, unreal.MaterialFactoryNew())
    mel.delete_all_material_expressions(mat)
    rgb = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector)
    rgb.set_editor_property('constant', unreal.LinearColor(*color[:3], 1.0))
    mel.connect_material_property(rgb, '', unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant)
    rough.set_editor_property('r', roughness)
    mel.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    lib.save_loaded_asset(mat)
    return mat

materials = {name: solid_material(name, data['color'], data['roughness']) for name, data in manifest['materials'].items()}
loaded = {}
for item in manifest['assets']:
    task = unreal.AssetImportTask()
    task.filename = str(ROOT / 'Art/Exports' / (item['name'] + '.fbx'))
    task.destination_path = '/Game/Island/Meshes'
    task.destination_name = item['name']
    task.automated = True
    task.replace_existing = True
    task.save = True
    task.factory = unreal.FbxFactory()
    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.import_materials = False
    options.import_textures = False
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    options.automated_import_should_detect_type = False
    settings = options.static_mesh_import_data
    settings.combine_meshes = True
    settings.auto_generate_collision = False
    settings.generate_lightmap_u_vs = False
    settings.convert_scene = True
    settings.convert_scene_unit = True
    settings.force_front_x_axis = False
    settings.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    task.options = options
    asset_tools.import_asset_tasks([task])
    mesh = unreal.load_asset('/Game/Island/Meshes/' + item['name'])
    assert isinstance(mesh, unreal.StaticMesh), (item['name'], task.imported_object_paths)
    for index, slot in enumerate(mesh.get_editor_property('static_materials')):
        name = str(slot.get_editor_property('imported_material_slot_name'))
        assert name in materials, ('Unknown material', item['name'], name)
        mesh.set_material(index, materials[name])
    body = mesh.get_editor_property('body_setup')
    body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    lib.save_loaded_asset(mesh)
    loaded[item['name']] = mesh

# Replace only this phase's assemblies and the initial temporary floor.
for actor in actors.get_all_level_actors():
    if actor.get_actor_label() == 'Temporary_Test_Floor' or actor.get_actor_label().startswith('Island_'):
        actors.destroy_actor(actor)

def spawn(cls, label, location=(0, 0, 0), rotation=unreal.Rotator()):
    actor = actors.spawn_actor_from_class(cls, unreal.Vector(*location), rotation)
    actor.set_actor_label(label)
    actor.set_folder_path('Island')
    return actor

for name, mesh in loaded.items():
    actor = spawn(unreal.StaticMeshActor, 'Island_' + name)
    actor.static_mesh_component.set_static_mesh(mesh)

water_mat = solid_material('M_IslandOcean', [0.026, 0.39, 0.46, 1], 0.3)
# Two broad world-space waves provide a subtle water pattern without image textures.
mel.delete_all_material_expressions(water_mat)
def expr(cls):
    return mel.create_material_expression(water_mat, cls)
def constant(value):
    node = expr(unreal.MaterialExpressionConstant)
    node.set_editor_property('r', value)
    return node
def connect(a, b, pin, output=''):
    # Single-input nodes such as Sine expose an unnamed input in UE 5.7.
    inputs = [str(name) for name in mel.get_material_expression_input_names(b)]
    if pin not in inputs and len(inputs) == 1:
        pin = inputs[0]
    assert mel.connect_material_expressions(a, output, b, pin), (b.get_class().get_name(), pin, inputs)
position = expr(unreal.MaterialExpressionWorldPosition)
waves = []
for axis, frequency in [('r', .003), ('g', .0047)]:
    mask = expr(unreal.MaterialExpressionComponentMask)
    mask.set_editor_property('r', axis == 'r')
    mask.set_editor_property('g', axis == 'g')
    mask.set_editor_property('b', False)
    mask.set_editor_property('a', False)
    connect(position, mask, 'Input')
    mul = expr(unreal.MaterialExpressionMultiply)
    connect(mask, mul, 'A')
    connect(constant(frequency), mul, 'B')
    sine = expr(unreal.MaterialExpressionSine)
    connect(mul, sine, 'Input')
    waves.append(sine)
mult = expr(unreal.MaterialExpressionMultiply)
connect(waves[0], mult, 'A')
connect(waves[1], mult, 'B')
amount = expr(unreal.MaterialExpressionMultiply)
connect(mult, amount, 'A')
connect(constant(.12), amount, 'B')
offset = expr(unreal.MaterialExpressionAdd)
connect(amount, offset, 'A')
connect(constant(.45), offset, 'B')
lerp = expr(unreal.MaterialExpressionLinearInterpolate)
for pin, color in [('A', (.025, .32, .4, 1)), ('B', (.06, .5, .53, 1))]:
    rgb = expr(unreal.MaterialExpressionConstant3Vector)
    rgb.set_editor_property('constant', unreal.LinearColor(*color))
    connect(rgb, lerp, pin)
connect(offset, lerp, 'Alpha')
mel.connect_material_property(lerp, '', unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(constant(.32), '', unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(water_mat)
lib.save_loaded_asset(water_mat)
water = spawn(unreal.StaticMeshActor, 'Island_Ocean')
water.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
water.static_mesh_component.set_material(0, water_mat)
water.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
water.set_actor_scale3d(unreal.Vector(1500, 1500, 1))

# UE's FBX handedness conversion flips Blender Y.
camera_location = unreal.Vector(7800, 12800, 10400)
camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, unreal.Vector(0, 300, 150))
camera = spawn(unreal.CameraActor, 'Island_OverviewCamera', (camera_location.x, camera_location.y, camera_location.z), camera_rotation)
camera.camera_component.set_editor_property('projection_mode', unreal.CameraProjectionMode.PERSPECTIVE)
camera.camera_component.set_editor_property('field_of_view', 39.5)
camera.camera_component.set_editor_property('aspect_ratio', 4.0 / 3.0)

pp = spawn(unreal.PostProcessVolume, 'Island_Daylight')
pp.set_editor_property('unbound', True)
settings = pp.get_editor_property('settings')
settings.set_editor_property('override_auto_exposure_method', True)
settings.set_editor_property('auto_exposure_method', unreal.AutoExposureMethod.AEM_MANUAL)
settings.set_editor_property('override_auto_exposure_bias', True)
settings.set_editor_property('auto_exposure_bias', 0)
settings.set_editor_property('override_auto_exposure_apply_physical_camera_exposure', True)
settings.set_editor_property('auto_exposure_apply_physical_camera_exposure', False)
pp.set_editor_property('settings', settings)
for actor in actors.get_all_level_actors():
    if isinstance(actor, unreal.DirectionalLight):
        actor.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        actor.light_component.set_editor_property('intensity', 3.0)
        actor.set_actor_rotation(unreal.Rotator(-45, -30, 0), False)
    elif isinstance(actor, unreal.SkyLight):
        actor.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        actor.light_component.set_editor_property('intensity', .85)
        actor.light_component.set_editor_property('real_time_capture', True)
    elif isinstance(actor, unreal.PlayerStart):
        actor.set_actor_location(unreal.Vector(0, 800, 380), False, False)
        actor.set_actor_rotation(unreal.Rotator(-10, -90, 0), False)
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(camera_location, camera_rotation)
exec((ROOT / 'Scripts/configure_island_lighting.py').read_text(encoding='utf-8'))
assert levels.save_current_level()
lib.save_directory('/Game/Island', only_if_is_dirty=True, recursive=True)
unreal.log('BEAST_ISLAND_IMPORT_OK')
