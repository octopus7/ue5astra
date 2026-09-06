"""Review actual sky reflection in a separate woodland level and sky material."""
import importlib
import json
import math
import sys
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT/'Scripts'))
EAL = unreal.EditorAssetLibrary
ML = unreal.MaterialEditingLibrary
ES = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
AT = unreal.AssetToolsHelpers.get_asset_tools()


def build_review_sky():
    from puddle_cloud_trick import _Graph
    texture_path = '/Game/Astra/Textures/T_AnimeSkyPanorama'
    if not EAL.does_asset_exist(texture_path):
        task = unreal.AssetImportTask()
        task.filename = str(ROOT/'ArtSource/Textures/T_AnimeSkyPanorama.png')
        task.destination_path = '/Game/Astra/Textures'
        task.destination_name = 'T_AnimeSkyPanorama'
        task.automated = True
        task.save = True
        AT.import_asset_tasks([task])
    texture = EAL.load_asset(texture_path)
    texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_DEFAULT)
    texture.set_editor_property('srgb', True)
    texture.set_editor_property('address_x', unreal.TextureAddress.TA_WRAP)
    texture.set_editor_property('address_y', unreal.TextureAddress.TA_CLAMP)
    EAL.save_loaded_asset(texture)
    target = '/Game/Astra/Materials/ModuleReview/M_PuddleReviewSky'
    material = EAL.load_asset(target) if EAL.does_asset_exist(target) else AT.create_asset(
        'M_PuddleReviewSky', '/Game/Astra/Materials/ModuleReview', unreal.Material, unreal.MaterialFactoryNew())
    ML.delete_all_material_expressions(material)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', True)
    material.set_editor_property('is_sky', True)
    graph = _Graph(material)
    position = graph.node(unreal.MaterialExpressionWorldPosition)
    uv = graph.custom('Same panorama mapping as the source task sky dome',
        'float3 d=normalize(Pos); return float2(atan2(d.y,d.x)/6.28318530718+.5,acos(clamp(d.z,-1,1))/3.14159265359);',
        {'Pos': position}, unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    def sample(coords):
        result = graph.node(unreal.MaterialExpressionTextureSample)
        result.set_editor_property('texture', texture)
        graph.wire(coords, result, 'UVs')
        return result
    sky = sample(uv)
    inputs = {'Sky': sky, 'UV': uv}
    for name, code in (('West', 'return float2(.002,UV.y);'), ('East', 'return float2(.998,UV.y);'),
                       ('Top', 'return float2(.5,.005);'), ('Bottom', 'return float2(.5,.65);')):
        inputs[name] = sample(graph.custom(name, code, {'UV': uv}, unreal.CustomMaterialOutputType.CMOT_FLOAT2))
    colour = graph.custom('Source panorama wrap and polar blending',
        'float wrap=smoothstep(0,.024,min(UV.x,1-UV.x)); float3 c=lerp((West+East)*.5,Sky,wrap); c=lerp(Top,c,smoothstep(.015,.09,UV.y)); c=lerp(c,Bottom,smoothstep(.50,.68,UV.y)); return c*1.15;',
        inputs, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    graph.output(colour, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ML.recompile_material(material)
    EAL.save_loaded_asset(material)
    return material


def main():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    target = '/Game/Astra/Maps/L_AstraPuddleSkyModuleReview'
    if EAL.does_asset_exist(target):
        if not levels.load_level(target): raise RuntimeError('Could not load puddle sky review')
    elif not levels.new_level_from_template(target, '/Game/Astra/Maps/L_AstraWoodland'):
        raise RuntimeError('Could not create puddle sky review')
    sky = build_review_sky()
    for actor in ES.get_all_level_actors():
        if actor.get_actor_label() == 'CloudSkyDome':
            actor.static_mesh_component.set_material(0, sky)
    puddles = importlib.import_module('puddle_sky_reflection')
    applied = puddles.apply_puddles(save=False)
    material = EAL.load_asset(puddles.DEFAULT_ASSET)
    assigned = []
    for actor in ES.get_all_level_actors():
        if isinstance(actor, unreal.StaticMeshActor):
            mesh = actor.static_mesh_component.static_mesh
            if mesh and mesh.get_name() == 'SM_Puddle':
                actor.static_mesh_component.set_material(0, material)
                assigned.append(actor.get_actor_label())
        if actor.get_actor_label() in ('Camera_Puddle', 'Camera_PuddleSkyTop'):
            actor.set_actor_label('Camera_PuddleSkyTop')
            actor.camera_component.set_editor_property('ortho_width', 1000.0)
    environment = puddles.configure_reflection_environment()
    low = next((a for a in ES.get_all_level_actors() if a.get_actor_label() == 'Camera_PuddleSkyLow'), None)
    location, look = (-2780, -1680, 230), (-1950, -1600, 68)
    dx, dy, dz = [look[i]-location[i] for i in range(3)]
    rotation = unreal.Rotator(pitch=math.degrees(math.atan2(dz, math.hypot(dx, dy))),
                              yaw=math.degrees(math.atan2(dy, dx)), roll=0)
    if low is None:
        low = ES.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*location), rotation)
        low.set_actor_label('Camera_PuddleSkyLow')
    low.set_actor_location(unreal.Vector(*location), False, False)
    low.set_actor_rotation(rotation, False)
    low.camera_component.set_editor_property('projection_mode', unreal.CameraProjectionMode.PERSPECTIVE)
    low.camera_component.set_editor_property('field_of_view', 60.0)
    low.camera_component.set_editor_property('constrain_aspect_ratio', False)
    low.set_folder_path('ReviewCameras')
    if not unreal.EditorLevelLibrary.save_current_level(): raise RuntimeError('Puddle sky review save failed')
    report = {'map': target, 'puddle_actors': assigned, 'material': material.get_path_name(),
              'environment': environment, 'sky_material': sky.get_path_name(), 'applied': applied}
    output = ROOT/'Saved/Shoreline/PuddleSkyImport.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('PUDDLE SKY REVIEW READY ' + str(report))


if __name__ == '__main__': main()
