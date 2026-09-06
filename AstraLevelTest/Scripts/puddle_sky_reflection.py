"""UE 5.7 native sky reflections for the five existing puddles only.

Explicit functions only: importing this module changes no assets or scene state.
Thin Translucent + Surface ForwardShading supplies the engine's Schlick Fresnel
and its real SkyLight/Lumen reflection path. No sky texture, emissive image,
reflection-vector cubemap sample, or opaque cloud plane is added to the material.

Sources verified against installed UE 5.7 ThinTranslucentCommon.ush,
LumenFrontLayerTranslucency.usf, and MaterialExpressionThinTranslucentMaterialOutput.h.
Epic: https://dev.epicgames.com/documentation/en-us/unreal-engine/lit-translucency-in-unreal-engine?application_version=5.7
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import unreal


DEFAULT_ASSET = "/Game/Astra/Materials/Shoreline/M_PuddleSkyReflection"


class _Graph:
    def __init__(self, material):
        self.material = material
        self.library = unreal.MaterialEditingLibrary
        self.defaults = {}

    def node(self, cls, description=""):
        node = self.library.create_material_expression(self.material, cls)
        if node is None:
            raise RuntimeError("Cannot create puddle expression: " + cls.__name__)
        if description:
            node.set_editor_property("desc", description)
        return node

    def constant(self, value):
        node = self.node(unreal.MaterialExpressionConstant)
        node.set_editor_property("r", float(value))
        return node

    def scalar(self, name, value, maximum, minimum=0.0):
        node = self.node(unreal.MaterialExpressionScalarParameter)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(value))
        node.set_editor_property("group", "Puddle Water")
        node.set_editor_property("slider_min", float(minimum))
        node.set_editor_property("slider_max", float(maximum))
        self.defaults[name] = float(value)
        return node

    def vector(self, name, value):
        node = self.node(unreal.MaterialExpressionVectorParameter)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", unreal.LinearColor(*value, 1.0))
        node.set_editor_property("group", "Puddle Water")
        return node

    def wire(self, source, target, input_name, output_name=""):
        if not self.library.connect_material_expressions(source, output_name, target, input_name):
            names = list(self.library.get_material_expression_input_names(target))
            raise RuntimeError("Cannot connect puddle input " + input_name + "; available=" + str(names))

    def custom(self, description, code, inputs, output_type):
        node = self.node(unreal.MaterialExpressionCustom, description)
        node.set_editor_property("code", code)
        node.set_editor_property("output_type", output_type)
        entries = []
        for name in inputs:
            entry = unreal.CustomInput()
            entry.set_editor_property("input_name", name)
            entries.append(entry)
        node.set_editor_property("inputs", entries)
        for name, source in inputs.items():
            self.wire(source, node, name)
        return node

    def output(self, node, property_):
        if not self.library.connect_material_property(node, "", property_):
            raise RuntimeError("Cannot connect puddle material output " + str(property_))


def build_puddle_material(asset_path=DEFAULT_ASSET) -> unreal.Material:
    """Build a clear dielectric puddle while preserving the requested identity.

    The default creates a separate material. Passing the original material path
    explicitly is supported, but the original is never touched by default.
    """
    if not isinstance(asset_path, str) or not re.fullmatch(r"/Game/[A-Za-z0-9_/]+", asset_path) or asset_path.endswith("/"):
        raise ValueError("asset_path must be a /Game/.../MaterialName package path")
    library = unreal.EditorAssetLibrary
    editing = unreal.MaterialEditingLibrary
    material = library.load_asset(asset_path) if library.does_asset_exist(asset_path) else None
    if material is not None and not isinstance(material, unreal.Material):
        raise TypeError("Refusing to replace non-Material: " + asset_path)
    if material is None:
        folder, name = asset_path.rsplit("/", 1)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        raise RuntimeError("Could not create native-reflection puddle material")
    editing.delete_all_material_expressions(material)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_THIN_TRANSLUCENT)
    material.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    material.set_editor_property("translucency_pass", unreal.MaterialTranslucencyPass.MTP_BEFORE_DOF)
    material.set_editor_property("allow_front_layer_translucency", True)
    material.set_editor_property("screen_space_reflections", True)
    material.set_editor_property("disable_depth_test", False)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("tangent_space_normal", False)
    graph = _Graph(material)
    float1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    float3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3
    f0 = graph.scalar("WaterF0", 0.02, 0.08, 0.001)
    specular = graph.custom("UE dielectric F0 = 0.08 * Specular; engine applies Fresnel once",
                            "return clamp(F0 / 0.08, 0.0, 1.0);", {"F0": f0}, float1)
    graph.output(specular, unreal.MaterialProperty.MP_SPECULAR)
    graph.output(graph.constant(0.0), unreal.MaterialProperty.MP_METALLIC)
    graph.output(graph.vector("DiffuseSurfaceTone", (0.0, 0.0, 0.0)), unreal.MaterialProperty.MP_BASE_COLOR)
    graph.output(graph.scalar("SurfaceRoughness", 0.045, 0.25, 0.01), unreal.MaterialProperty.MP_ROUGHNESS)

    world = graph.node(unreal.MaterialExpressionWorldPosition)
    time = graph.node(unreal.MaterialExpressionTime)
    strength = graph.scalar("WaveNormalStrength", 0.018, 0.06)
    speed = graph.scalar("WaveSpeed", 0.12, 0.6)
    normal = graph.custom("Small world-locked normal variation; native reflection responds to this normal",
                          """
float2 p = Pos.xy * 0.01;
float phase = T * max(Speed, 0.0);
float nx = sin(p.x * 1.05 + p.y * 0.33 + phase);
float ny = cos(p.y * 0.91 - p.x * 0.27 - phase * 0.79);
return normalize(float3(float2(nx, ny) * clamp(Strength, 0.0, 0.06), 1.0));
""", {"Pos": world, "T": time, "Strength": strength, "Speed": speed}, float3)
    graph.output(normal, unreal.MaterialProperty.MP_NORMAL)
    edge = graph.node(unreal.MaterialExpressionVertexColor, "Existing SM_Puddle vertex red: zero at perimeter")
    depth = graph.node(unreal.MaterialExpressionDepthFade)
    depth.set_editor_property("opacity_default", 1.0)
    depth.set_editor_property("fade_distance_default", 4.0)
    depth_distance = graph.scalar("EdgeDepthFadeCm", 4.0, 12.0, 0.5)
    graph.wire(depth_distance, depth, "FadeDistance")
    coverage = graph.custom("Real thin-surface coverage; reflection and transmission share this boundary",
                            "return smoothstep(0.0, 1.0, saturate(Edge.r)) * saturate(Depth);",
                            {"Edge": edge, "Depth": depth}, float1)
    thin_output = graph.node(unreal.MaterialExpressionThinTranslucentMaterialOutput,
                             "Physical thin dielectric; white reflection over nearly clear ground transmission")
    transmittance = graph.vector("TransmissionTint", (0.985, 0.992, 0.986))
    graph.wire(transmittance, thin_output, "TransmittanceColor")
    graph.wire(coverage, thin_output, "SurfaceCoverage")
    # UE Thin Translucent's root Opacity is the opaque layer ON TOP of the clear
    # sheet. A value of 1 would hide the ground; sheet coverage is separate above.
    # LumenFrontLayerTranslucency.usf explicitly exempts Thin Translucent from
    # the ordinary Opacity<=0 clip, so this retains native front-layer reflection.
    graph.output(graph.constant(0.0), unreal.MaterialProperty.MP_OPACITY)
    # No emissive and no refraction output: avoid a second photographic layer or
    # screen-space displacement of shallow ground while testing real reflections.
    editing.layout_material_expressions(material)
    editing.recompile_material(material)
    library.set_metadata_tag(material, "AstraPuddleMode", "native_sky_lumen_thin_translucent_fresnel")
    library.set_metadata_tag(material, "AstraPuddleParameters", json.dumps(graph.defaults, sort_keys=True))
    library.set_metadata_tag(material, "AstraPuddleCoverage", "ThinTranslucent.SurfaceCoverage=vertexRed*DepthFade; rootOpacity=0")
    if not library.save_loaded_asset(material):
        raise RuntimeError("Could not save native puddle material: " + asset_path)
    return material


def configure_reflection_environment(recapture_sky=False) -> dict:
    """Enable existing post-process front-layer reflection; no project config edit.

    The caller owns the sky image/capture content. This never edits a sky material
    or either lake/stream water material and does not create reflection planes.
    """
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    sky_lights = [actor for actor in actors if isinstance(actor, unreal.SkyLight)]
    if not sky_lights:
        raise RuntimeError("A native SkyLight reflection environment must exist before puddle review")
    volumes = [actor for actor in actors if isinstance(actor, unreal.PostProcessVolume)]
    if not volumes:
        raise RuntimeError("Expected the existing woodland post-process volume")
    for volume in volumes:
        settings = volume.get_editor_property("settings")
        settings.set_editor_property("override_lumen_front_layer_translucency_reflections", True)
        settings.set_editor_property("lumen_front_layer_translucency_reflections", True)
        settings.set_editor_property("override_lumen_reflection_quality", True)
        settings.set_editor_property("lumen_reflection_quality", 2.0)
        volume.set_editor_property("settings", settings)
    if recapture_sky:
        for sky in sky_lights:
            sky.light_component.recapture_sky()
    return {"post_process_volumes": [actor.get_actor_label() for actor in volumes],
            "sky_lights": [actor.get_actor_label() for actor in sky_lights],
            "front_layer_enabled": all(bool(actor.get_editor_property("settings").get_editor_property("lumen_front_layer_translucency_reflections")) for actor in volumes),
            "sky_recapture_requested": bool(recapture_sky), "project_config_changed": False}


def apply_puddles(save=False, asset_path=DEFAULT_ASSET) -> dict:
    """Override materials on exactly the five source-layout puddles, preserving assets."""
    project = Path(unreal.Paths.project_dir()).resolve()
    data = json.loads((project / "ArtSource/Layout/woodland_layout.json").read_text(encoding="utf-8-sig"))
    names = [obj["name"] for obj in data["objects"] if obj["asset"] == "SM_Puddle" and obj["group"] == "Water/Puddles"]
    if len(names) != 5 or len(set(names)) != 5:
        raise RuntimeError("Expected exactly five source puddles; refusing broader material assignment")
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    selected = []
    for name in names:
        matches = [actor for actor in actors if actor.get_actor_label() == name]
        if len(matches) != 1 or not isinstance(matches[0], unreal.StaticMeshActor):
            raise RuntimeError("Missing or ambiguous existing puddle actor: " + name)
        component = matches[0].static_mesh_component
        mesh = component.get_editor_property("static_mesh")
        if mesh is None or mesh.get_name() != "SM_Puddle":
            raise RuntimeError("Unexpected mesh on puddle label: " + name)
        selected.append(matches[0])
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or not world.get_path_name().startswith("/Game/"):
        raise RuntimeError("Load the intended saved review/woodland map first")
    key = hashlib.sha256(world.get_path_name().encode("utf-8")).hexdigest()[:12]
    backup = project / "Saved/Shoreline" / ("puddle_material_originals_" + key + ".json")
    if not backup.exists():
        states = {actor.get_actor_label(): [actor.static_mesh_component.get_material(index).get_path_name()
                  if actor.static_mesh_component.get_material(index) else None
                  for index in range(actor.static_mesh_component.get_num_materials())] for actor in selected}
        backup.parent.mkdir(parents=True, exist_ok=True)
        with backup.open("x", encoding="utf-8") as handle:
            json.dump({"map": world.get_path_name(), "materials": states}, handle, indent=2)
    environment = configure_reflection_environment()
    material = build_puddle_material(asset_path)
    for actor in selected:
        component = actor.static_mesh_component
        for index in range(component.get_num_materials()):
            component.set_material(index, material)
    if save and not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError("Puddles updated but map save failed")
    return {"map": world.get_path_name(), "saved": bool(save), "puddle_count": len(selected),
            "actors": {actor.get_actor_label(): [actor.static_mesh_component.get_material(index).get_path_name()
                       for index in range(actor.static_mesh_component.get_num_materials())] for actor in selected},
            "material": validate_created_material(asset_path), "environment": environment,
            "original_materials_snapshot": str(backup)}


def validate_created_material(asset_path=DEFAULT_ASSET) -> dict:
    """Read material properties/parameters; GPU reflection visibility is separate QA."""
    material = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not isinstance(material, unreal.Material):
        raise TypeError("Expected built puddle Material: " + asset_path)
    library = unreal.MaterialEditingLibrary
    opacity = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_OPACITY)
    checks = {
        "thin_translucent": material.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_THIN_TRANSLUCENT,
        "surface_forward_shading": material.get_editor_property("translucency_lighting_mode") == unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING,
        "front_layer_allowed": bool(material.get_editor_property("allow_front_layer_translucency")),
        "native_reflections_enabled": bool(material.get_editor_property("screen_space_reflections")),
        "zero_opaque_top_layer": isinstance(opacity, unreal.MaterialExpressionConstant) and abs(float(opacity.get_editor_property("r"))) < 1e-8,
        "water_f0_002": abs(float(library.get_material_default_scalar_parameter_value(material, "WaterF0")) - 0.02) < 1e-6,
        "no_emissive_output": library.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None,
        "no_texture_samples": len(library.get_used_textures(material)) == 0,
    }
    return {"asset": material.get_path_name(), "checks": checks, "passed": all(checks.values()),
            "scalar_defaults": {str(name): float(library.get_material_default_scalar_parameter_value(material, name))
                                for name in library.get_scalar_parameter_names(material)},
            "validation_scope": "Actual material contract only; inspect native compile logs plus top-down/grazing GPU captures."}
