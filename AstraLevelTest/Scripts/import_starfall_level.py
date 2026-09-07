"""Build only L_AstraStarfall from the exported Blender layout in full UE 5.7.

The woodland map and all non-Starfall Content files are read-only inputs.
Existing sky, water/reflection graphs, meshes and foliage types are reused as-is.
Run by -ExecutePythonScript; importing this module has no editing side effects.
"""
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
ART = ROOT / 'ArtSource'
MAP = '/Game/Astra/Maps/L_AstraStarfall'
TEMPLATE = '/Game/Astra/Maps/L_AstraWoodland'
MATERIAL_DIR = '/Game/Astra/Materials/Starfall'
MESH_DIR = '/Game/Astra/Meshes/Starfall'
TEXTURE_DIR = '/Game/Astra/Textures/Starfall'
FOLIAGE_DIR = '/Game/Astra/Foliage/Starfall'
WATER = '/Game/Astra/Materials/Shoreline/M_PuddleSkyReflection'
EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
ML = unreal.MaterialEditingLibrary


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_content():
    result = {}
    for path in (ROOT/'Content').rglob('*'):
        if not path.is_file() or path.suffix not in ('.uasset', '.umap', '.uexp', '.ubulk'):
            continue
        relative = path.relative_to(ROOT)
        if 'Starfall' in relative.parts or path.stem.startswith('L_AstraStarfall'):
            continue
        result[relative.as_posix()] = digest(path)
    return result


def check_protected(expected):
    return {path: (ROOT/path).is_file() and digest(ROOT/path) == value for path, value in expected.items()}


def asset_path(obj):
    return obj.get_path_name().split('.')[0] if obj else None


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def encode(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, unreal.LinearColor):
        return [value.r, value.g, value.b, value.a]
    if isinstance(value, unreal.Vector):
        return xyz(value)
    if isinstance(value, unreal.Rotator):
        return [value.pitch, value.yaw, value.roll]
    if all(hasattr(value, key) for key in ('r','g','b','a')):
        return [float(getattr(value,key)) for key in ('r','g','b','a')]
    if all(hasattr(value, key) for key in ('x','y','z','w')):
        return [float(getattr(value,key)) for key in ('x','y','z','w')]
    if isinstance(value, unreal.Object):
        return asset_path(value)
    return str(value)


def properties(obj, names):
    out = {}
    for name in names:
        try:
            out[name] = encode(obj.get_editor_property(name))
        except Exception:
            # Optional platform/version properties are recorded only when exposed.
            pass
    return out


def is_environment(actor):
    return isinstance(actor, (unreal.DirectionalLight, unreal.SkyLight, unreal.SkyAtmosphere,
        unreal.ExponentialHeightFog, unreal.PostProcessVolume)) or actor.get_actor_label() == 'CloudSkyDome'


def environment_state(actors):
    result = {}
    for actor in actors:
        if not is_environment(actor):
            continue
        state = {'class': actor.get_class().get_name(), 'position': xyz(actor.get_actor_location()),
                 'rotation': encode(actor.get_actor_rotation()), 'scale': xyz(actor.get_actor_scale3d())}
        if isinstance(actor, unreal.DirectionalLight):
            state['light'] = properties(actor.light_component, ['intensity','light_color','light_source_angle',
                  'light_source_soft_angle','cast_shadows','atmosphere_sun_light','indirect_lighting_intensity'])
        elif isinstance(actor, unreal.SkyLight):
            state['sky'] = properties(actor.light_component, ['intensity','light_color','real_time_capture',
                  'cubemap_resolution','source_type','cubemap','lower_hemisphere_is_solid_color','lower_hemisphere_color'])
        elif isinstance(actor, unreal.ExponentialHeightFog):
            state['fog'] = properties(actor.component, ['fog_density','fog_height_falloff','fog_max_opacity',
                   'start_distance','fog_inscattering_color','volumetric_fog'])
        elif isinstance(actor, unreal.PostProcessVolume):
            state['unbound'] = actor.get_editor_property('unbound')
            state['postprocess'] = properties(actor.get_editor_property('settings'), [
                 'auto_exposure_method','auto_exposure_min_brightness','auto_exposure_max_brightness',
                 'auto_exposure_bias','bloom_intensity','vignette_intensity','color_saturation','color_contrast',
                 'dynamic_global_illumination_method','reflection_method','lumen_reflection_quality',
                 'lumen_front_layer_translucency_reflections','override_lumen_front_layer_translucency_reflections'])
        elif isinstance(actor, unreal.StaticMeshActor):
            c = actor.static_mesh_component
            state['mesh'] = asset_path(c.static_mesh)
            state['materials'] = [asset_path(c.get_material(i)) for i in range(c.get_num_materials())]
            state['visible'] = c.is_visible()
        result[actor.get_actor_label()] = state
    return result


def require_new(path, directory):
    if not path.startswith(directory + '/'):
        raise RuntimeError('Refusing to edit an existing shared asset: ' + path)


def save_new(asset, directory):
    require_new(asset_path(asset), directory)
    if not EAL.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Could not save ' + asset_path(asset))


def srgb(color):
    if isinstance(color, str):
        color = color.lstrip('#')
        color = [int(color[i:i+2],16)/255 for i in (0,2,4)]
    return [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in color[:3]]


def expression(material, cls, x=0, y=0):
    return ML.create_material_expression(material, cls, x, y)


def constant(material, number):
    node = expression(material, unreal.MaterialExpressionConstant)
    node.set_editor_property('r', float(number))
    return node


def color_node(material, rgb):
    node = expression(material, unreal.MaterialExpressionConstant3Vector)
    node.set_editor_property('constant', unreal.LinearColor(*rgb, 1))
    return node


def custom(material, code, inputs, output=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    node = expression(material, unreal.MaterialExpressionCustom)
    node.set_editor_property('code', code)
    node.set_editor_property('output_type', output)
    args = []
    for name in inputs:
        arg = unreal.CustomInput(); arg.set_editor_property('input_name', name); args.append(arg)
    node.set_editor_property('inputs', args)
    for name, input_node in inputs.items():
        ML.connect_material_expressions(input_node, '', node, name)
    return node


def new_material(name):
    if not name.startswith('M_SF_'):
        raise RuntimeError('New materials must use M_SF_: '+name)
    path = MATERIAL_DIR+'/'+name
    material = EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(
        name, MATERIAL_DIR, unreal.Material, unreal.MaterialFactoryNew())
    require_new(path, MATERIAL_DIR)
    ML.delete_all_material_expressions(material)
    return material


def finish_material(material):
    ML.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    ML.recompile_material(material)
    save_new(material, MATERIAL_DIR)
    return material


def texture_from_file(relative):
    source = ROOT/relative
    if not source.is_file():
        raise RuntimeError('Missing texture '+str(source))
    old_path = '/Game/Astra/Textures/'+source.stem
    if EAL.does_asset_exist(old_path):
        return EAL.load_asset(old_path)  # Existing sky/floor/rock sources stay byte-exact.
    path = TEXTURE_DIR+'/'+source.stem
    task = unreal.AssetImportTask()
    task.filename = str(source); task.destination_path = TEXTURE_DIR; task.destination_name = source.stem
    task.automated = True; task.save = False; task.replace_existing = True
    AT.import_asset_tasks([task])
    texture = EAL.load_asset(path)
    if not texture:
        raise RuntimeError('Texture import failed: '+path)
    texture.set_editor_property('srgb', True)
    texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_DEFAULT)
    save_new(texture, TEXTURE_DIR)
    return texture


def resolve_material(name, materials):
    if name in materials:
        return materials[name]
    if name in ('M_PuddleReflection','M_PuddleSkyReflection'):
        path = WATER
    elif name.startswith('/Game/'):
        path = name
    else:
        path = '/Game/Astra/Materials/'+name
    material = EAL.load_asset(path)
    if not material:
        raise RuntimeError('Missing reused material '+path)
    return material


def build_materials(data):
    result = {}
    for name, props in data['materials'].items():
        if name == 'M_SF_Landscape':
            continue
        if props.get('reuse_existing') or not name.startswith('M_SF_'):
            result[name] = resolve_material(props.get('unreal_asset_path',name), {})
            continue
        material = new_material(name)
        base = color_node(material, srgb(props.get('base_color','FFFFFF')))
        if props.get('base_color_texture'):
            base = expression(material, unreal.MaterialExpressionTextureSample)
            base.set_editor_property('texture', texture_from_file(props['base_color_texture']))
        ML.connect_material_property(base, '', unreal.MaterialProperty.MP_BASE_COLOR)
        ML.connect_material_property(constant(material, props.get('roughness',.85)), '', unreal.MaterialProperty.MP_ROUGHNESS)
        ML.connect_material_property(constant(material, props.get('metallic',0)), '', unreal.MaterialProperty.MP_METALLIC)
        if props.get('emissive_color') and props.get('emissive_strength',0):
            emissive = color_node(material, [x*props['emissive_strength'] for x in srgb(props['emissive_color'])])
            ML.connect_material_property(emissive, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        if props.get('two_sided'):
            material.set_editor_property('two_sided', True)
        result[name] = finish_material(material)
    result['M_SF_Landscape'] = build_ground_material()
    return result


def build_ground_material():
    material = new_material('M_SF_Landscape')
    position = expression(material, unreal.MaterialExpressionWorldPosition)
    uv = custom(material, 'return Pos.xy*0.003;', {'Pos':position}, unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    texture = expression(material, unreal.MaterialExpressionTextureSample)
    texture.set_editor_property('texture', EAL.load_asset('/Game/Astra/Textures/T_ForestFloor'))
    ML.connect_material_expressions(uv, '', texture, 'UVs')
    code = (ART/'Layout/starfall_ground.hlsl').read_text(encoding='utf-8')
    base = custom(material, code, {'Pos':position, 'Tex':texture})
    ML.connect_material_property(base, '', unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(constant(material,.9), '', unreal.MaterialProperty.MP_ROUGHNESS)
    return finish_material(material)


def import_meshes(data, materials):
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    result = {}
    unreal.SystemLibrary.execute_console_command(None, 'Interchange.FeatureFlags.Import.FBX 0')
    for name, item in data['assets'].items():
        path = item.get('unreal_asset_path', MESH_DIR+'/'+name)
        if item.get('reuse_existing'):
            result[name] = EAL.load_asset(path)
            if not result[name]:
                raise RuntimeError('Missing reused mesh '+path)
            continue
        require_new(path, MESH_DIR)
        task = unreal.AssetImportTask()
        task.filename = str(ROOT/item['file']); task.destination_path, task.destination_name = path.rsplit('/',1)
        task.automated = True; task.save = False; task.replace_existing = True; task.factory = unreal.FbxFactory()
        options = unreal.FbxImportUI()
        options.import_mesh = True; options.import_as_skeletal = False
        options.import_materials = False; options.import_textures = False; options.import_animations = False
        options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        settings = options.static_mesh_import_data
        settings.combine_meshes = True; settings.generate_lightmap_u_vs = False; settings.auto_generate_collision = False
        settings.convert_scene = True; settings.convert_scene_unit = True
        settings.vertex_color_import_option = unreal.VertexColorImportOption.REPLACE
        settings.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        task.options = options; AT.import_asset_tasks([task])
        mesh = EAL.load_asset(path)
        if not mesh:
            raise RuntimeError('FBX import failed '+path)
        for index, slot in enumerate(mesh.get_editor_property('static_materials')):
            key = str(slot.material_slot_name)
            if key not in item['materials']:
                key = item['materials'][min(index,len(item['materials'])-1)]
            mesh.set_material(index, resolve_material(key,materials))
        # Section-to-material bindings from FBX are retained; never collapse multi-material kits.
        body = mesh.get_editor_property('body_setup')
        body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        save_new(mesh, MESH_DIR)
        result[name] = mesh
        unreal.log('STARFALL imported '+name)
    return result


def clear_new_level(data):
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.load_level(TEMPLATE):
        raise RuntimeError('Could not load woodland environment template')
    baseline = environment_state(actors.get_all_level_actors())
    file = ROOT/'Content/Astra/Maps/L_AstraStarfall.umap'
    if file.exists():
        backup = ROOT/'Saved/AstraBuild/BeforeStarfallRebuild'; backup.mkdir(parents=True,exist_ok=True)
        if not (backup/file.name).exists():
            shutil.copy2(file, backup/file.name)
        if not levels.load_level(MAP):
            raise RuntimeError('Could not load existing Starfall map')
    elif not levels.new_level_from_template(MAP,TEMPLATE):
        raise RuntimeError('Could not create independent Starfall map from template')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split('.')[0] != MAP:
        raise RuntimeError('Refusing to delete actors outside the new map: '+world.get_path_name())
    for actor in list(actors.get_all_level_actors()):
        if is_environment(actor) or isinstance(actor,unreal.WorldSettings):
            continue
        # Generated level-script and world partition support actors belong to the map itself.
        if isinstance(actor,unreal.LevelScriptActor) or actor.get_class().get_name() in ('WorldPartitionMiniMap','WorldDataLayers'):
            continue
        if not actors.destroy_actor(actor):
            raise RuntimeError('Could not remove duplicated actor '+actor.get_actor_label())
    current = environment_state(actors.get_all_level_actors())
    if current != baseline:
        raise RuntimeError('Template environment settings differ in Starfall')
    return world, baseline


def spawn(actor_class, location, label, rotation=None, folder='Starfall'):
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        actor_class, unreal.Vector(*location), unreal.Rotator(**(rotation or {})))
    if not actor:
        raise RuntimeError('Failed to spawn '+label)
    actor.set_actor_label(label); actor.set_folder_path(folder)
    return actor


def make_foliage(data, meshes, world):
    by_mesh = defaultdict(list)
    for item in data['objects']:
        if item.get('foliage'):
            by_mesh[item['asset']].append(unreal.Transform(location=unreal.Vector(*item['ue_location_cm']),
                rotation=unreal.Rotator(**item['ue_rotation_deg']),scale=unreal.Vector(*item['scale'])))
    paths = {}
    for name, transforms in by_mesh.items():
        legacy = '/Game/Astra/Foliage/FT_Astra_'+name.removeprefix('SM_')
        if data['assets'][name].get('reuse_existing') and EAL.does_asset_exist(legacy):
            foliage = EAL.load_asset(legacy)
        else:
            path = FOLIAGE_DIR+'/FT_'+name.removeprefix('SM_')
            foliage = EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(
                path.rsplit('/',1)[1],FOLIAGE_DIR,unreal.FoliageType_InstancedStaticMesh,
                unreal.FoliageType_InstancedStaticMeshFactory())
            foliage.set_editor_property('mesh',meshes[name])
            foliage.set_editor_property('density',40.0)
            foliage.set_editor_property('enable_density_scaling',False)
            body = foliage.get_editor_property('body_instance')
            body.set_editor_property('collision_profile_name','NoCollision')
            body.set_editor_property('collision_enabled',unreal.CollisionEnabled.NO_COLLISION)
            foliage.set_editor_property('body_instance',body)
            save_new(foliage,FOLIAGE_DIR)
        unreal.InstancedFoliageActor.add_instances(world,foliage,transforms)
        paths[name] = asset_path(foliage)
    return {'counts':{name:len(items) for name,items in by_mesh.items()},'types':paths}


def place_level(data, materials, meshes, world):
    landscape = unreal.AstraSceneLibrary.create_terrain_from_heightmap(
        materials['M_SF_Landscape'],str(ROOT/data['terrain_file']))
    if not isinstance(landscape,unreal.Landscape):
        raise RuntimeError('Starfall native Landscape creation failed')
    landscape.set_actor_label('Landscape_100m_Starfall'); landscape.set_folder_path('Terrain')
    cylinder = EAL.load_asset('/Engine/BasicShapes/Cylinder')
    for item in data['objects']:
        if item.get('foliage'):
            continue
        actor = spawn(unreal.StaticMeshActor,item['ue_location_cm'],item['name'],
                      item['ue_rotation_deg'],item['group'])
        component = actor.static_mesh_component
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_static_mesh(meshes[item['asset']])
        actor.set_actor_scale3d(unreal.Vector(*item['scale']))
        collides = item.get('collision','none') in ('complex','solid')
        component.set_collision_profile_name('BlockAll' if collides else 'NoCollision')
        actor.set_actor_enable_collision(collides)
        if item.get('material_override'):
            component.set_material(0,resolve_material(item['material_override'],materials))
            component.set_cast_shadow(False)
        component.set_mobility(unreal.ComponentMobility.STATIC)
        if item.get('collision') == 'trunk':
            meta = data['assets'][item['asset']].get('trunk_collision',{})
            radius = meta.get('radius_m',.33 if item['asset'].startswith('SM_SF_Pink') else .28)
            height = meta.get('height_m',2.8 if item['asset'].startswith('SM_SF_Pink') else 2.4)
            centre = meta.get('centre_xy_m',[0,0])
            location = unreal.MathLibrary.transform_location(actor.get_actor_transform(),
                unreal.Vector(centre[0]*100,-centre[1]*100,height*50))
            blocker = spawn(unreal.StaticMeshActor,xyz(location),item['name']+'_TrunkCollision',
                            item['ue_rotation_deg'],'Collision/StarfallTrunks')
            bc = blocker.static_mesh_component; bc.set_mobility(unreal.ComponentMobility.MOVABLE)
            bc.set_static_mesh(cylinder)
            blocker.set_actor_scale3d(unreal.Vector(radius*2*item['scale'][0],radius*2*item['scale'][1],height*item['scale'][2]))
            blocker.set_actor_hidden_in_game(True); bc.set_visibility(False)
            bc.set_collision_profile_name('BlockAll'); bc.set_mobility(unreal.ComponentMobility.STATIC)
    foliage = make_foliage(data,meshes,world)
    spawn(unreal.PlayerStart,data['spawn_cm'],'PlayerStart_Starfall',{'yaw':155},'Gameplay')
    config = spawn(unreal.AstraLevelConfig,[0,0,0],'StarfallLevelConfig',folder='Gameplay')
    shots = []
    for item in data['demo_shots']:
        shot = unreal.AstraDemoShot()
        shot.set_editor_property('name',item['name'])
        shot.set_editor_property('waypoints',[unreal.Vector2D(*p[:2]) for p in item.get('points',item.get('waypoints',[]))])
        shot.set_editor_property('minimum_seconds',float(item.get('seconds',item.get('minimum_seconds',9))))
        shot.set_editor_property('ortho_width',float(item.get('width',item.get('ortho_width',2600))))
        shot.set_editor_property('camera_offset',unreal.Vector(*item.get('offset',item.get('camera_offset',[0,0,0]))))
        shot.set_editor_property('walk_speed',float(item.get('walk_speed',180)))
        shots.append(shot)
    config.set_editor_property('demo_shots',shots); config.set_editor_property('validation_prefix','SF')
    for item in data['review_cameras']:
        pitch,yaw = item.get('pitch',-58),item.get('yaw',0)
        p,y = math.radians(pitch),math.radians(yaw)
        look=item['look_cm']; arm=4200 if item['width']>5000 else 2700
        position=[look[0]-arm*math.cos(p)*math.cos(y),look[1]-arm*math.cos(p)*math.sin(y),look[2]-arm*math.sin(p)]
        name=item['name'] if item['name'].startswith('Camera_') else 'Camera_'+item['name']
        actor=spawn(unreal.CameraActor,position,name,{'pitch':pitch,'yaw':yaw},'ReviewCameras/Starfall')
        camera=actor.camera_component
        camera.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC)
        camera.set_editor_property('ortho_width',item['width']);camera.set_editor_property('constrain_aspect_ratio',False)
    for item in data.get('lights',[]):
        actor=spawn(unreal.PointLight,item['ue_location_cm'],item['name'],folder='Lighting/StarfallGlow')
        light=actor.light_component;light.set_mobility(unreal.ComponentMobility.MOVABLE)
        light.set_editor_property('intensity_units',unreal.LightUnits.LUMENS)
        light.set_intensity(item.get('intensity',15)); light.set_light_color(unreal.LinearColor(*item.get('color',[.20,.78,1]),1))
        light.set_editor_property('attenuation_radius',item.get('radius',250));light.set_cast_shadows(False)
    world.get_world_settings().set_editor_property('default_game_mode',unreal.AstraGameMode.static_class())
    return foliage


def main():
    data=json.loads((ART/'Layout/starfall_layout.json').read_text(encoding='utf-8'))
    (ART/'Previews').mkdir(parents=True,exist_ok=True)
    before=protected_content()
    baseline_file=ROOT/'Saved/AstraBuild/StarfallProtection.json';baseline_file.parent.mkdir(parents=True,exist_ok=True)
    baseline_file.write_text(json.dumps(before,indent=2),encoding='utf-8')
    report={'passed':False,'map':MAP,'protected_asset_sha256':before}
    try:
        world, environment=clear_new_level(data)
        if '-AstraStarfallPlacementOnly' in unreal.SystemLibrary.get_command_line():
            materials={'M_SF_Landscape':build_ground_material()}
            meshes={name:EAL.load_asset(item['unreal_asset_path']) for name,item in data['assets'].items()}
            if not all(meshes.values()):
                raise RuntimeError('Placement-only refresh requires a complete initial import.')
        else:
            materials=build_materials(data); meshes=import_meshes(data,materials)
        foliage=place_level(data,materials,meshes,world)
        actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        if environment_state(actors)!=environment:
            raise RuntimeError('Original lighting/sky parameters changed')
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise RuntimeError('Could not save Starfall map')
        unchanged=check_protected(before)
        report.update({'passed':all(unchanged.values()),'old_content_unchanged':all(unchanged.values()),
             'changed_protected_files':[p for p,ok in unchanged.items() if not ok],
             'environment_state':environment,'new_meshes':sum(not a.get('reuse_existing') for a in data['assets'].values()),
             'reused_meshes':sum(bool(a.get('reuse_existing')) for a in data['assets'].values()),
             'static_placements':sum(not o.get('foliage') for o in data['objects']),
             'foliage':foliage,'actor_count':len(actors),'layout_sha256':digest(ART/'Layout/starfall_layout.json'),
             'terrain_sha256':digest(ROOT/data['terrain_file']),'saved_only_new_map_and_starfall_assets':True})
        if not report['passed']:
            raise RuntimeError('Existing Content changed: '+str(report['changed_protected_files']))
    except Exception as error:
        report['error']=str(error)
        report['protected_files_unchanged_on_failure']=all(check_protected(before).values())
        raise
    finally:
        (ART/'Previews/UE_StarfallImportValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('STARFALL IMPORT COMPLETE '+json.dumps({k:v for k,v in report.items() if k not in ('protected_asset_sha256','environment_state')}))


if __name__ == '__main__':
    main()
