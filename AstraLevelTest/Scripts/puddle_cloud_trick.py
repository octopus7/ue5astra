"""UE 5.7: a bounded, animated cloud illusion for puddles only.

Importing this module does nothing to the project. Call build_puddle_material()
inside the editor to rebuild one material, preserving its asset identity and
references. No actors, maps, lighting, lake/stream materials or config are edited.

SM_Puddle is a roughly two-metre disc without authored UVs. Its vertex red
channel is one inside and zero at the perimeter. We derive UVs from local cm,
crop a single existing cloud image and gently distort it in world space. This
is deliberately a puddle illustration, not a reflection capture or sky lookup.
"""

from __future__ import annotations

import json
from pathlib import Path

import unreal


def _load_cloud_texture() -> unreal.Texture2D:
    library = unreal.EditorAssetLibrary
    path = "/Game/Astra/Textures/T_AnimeSkyReflection"
    texture = library.load_asset(path) if library.does_asset_exist(path) else None
    if texture is not None:
        if not isinstance(texture, unreal.Texture2D):
            raise TypeError(f"Expected Texture2D at {path}")
        return texture  # Do not change the shared sky texture's import settings.
    source = Path(unreal.Paths.project_dir()).resolve() / "ArtSource/Textures/T_AnimeSkyReflection.png"
    if not source.is_file():
        raise FileNotFoundError(f"Missing existing cloud texture and source image: {source}")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", "/Game/Astra/Textures")
    task.set_editor_property("destination_name", "T_AnimeSkyReflection")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = library.load_asset(path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError(f"Could not import puddle cloud source: {source}")
    return texture


class _Graph:
    """Per-call graph builder; custom HLSL receives every input explicitly."""

    def __init__(self, material: unreal.Material):
        self.material = material
        self.library = unreal.MaterialEditingLibrary
        self.parameter_defaults = {}

    def node(self, expression_class, description=""):
        node = self.library.create_material_expression(self.material, expression_class)
        if node is None:
            raise RuntimeError(f"Unable to create {expression_class.__name__}")
        if description:
            node.set_editor_property("desc", description)
        return node

    def wire(self, source, destination, input_name, output_name=""):
        if not self.library.connect_material_expressions(source, output_name, destination, input_name):
            available = list(self.library.get_material_expression_input_names(destination))
            raise RuntimeError(
                f"Could not connect {source.get_name()} to {destination.get_name()}.{input_name}; "
                f"available input names: {available}")

    def scalar(self, name, value, group, description, minimum, maximum):
        node = self.node(unreal.MaterialExpressionScalarParameter, description)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", value)
        node.set_editor_property("group", group)
        node.set_editor_property("slider_min", minimum)
        node.set_editor_property("slider_max", maximum)
        self.parameter_defaults[name] = value
        return node

    def vector(self, name, value, group, description):
        node = self.node(unreal.MaterialExpressionVectorParameter, description)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", unreal.LinearColor(*value))
        node.set_editor_property("group", group)
        self.parameter_defaults[name] = list(value)
        return node

    def custom(self, description, code, inputs, output_type):
        node = self.node(unreal.MaterialExpressionCustom, description)
        node.set_editor_property("code", code)
        node.set_editor_property("output_type", output_type)
        custom_inputs = []
        for name in inputs:
            custom_input = unreal.CustomInput()
            custom_input.set_editor_property("input_name", name)
            custom_inputs.append(custom_input)
        node.set_editor_property("inputs", custom_inputs)
        for name, source in inputs.items():
            self.wire(source, node, name)
        return node

    def output(self, node, property_):
        if not self.library.connect_material_property(node, "", property_):
            raise RuntimeError(f"Could not connect material output {property_}")


def build_puddle_material(asset_path="/Game/Astra/Materials/M_PuddleReflection") -> unreal.Material:
    """Rebuild and save only the requested puddle material; return Material.

    Defaults target one or two broad pale patches on the existing puddle mesh.
    CloudUVScale changes the amount of the source image visible (larger = more
    image / smaller clouds). CloudUVOffset and CloudRotationDegrees select the
    composition. All tint values are linear, and SurfaceBrightness is clamped
    to [0, 1] so this shader never deliberately emits HDR light.

    UVs do not rely on the mesh's missing UV0. PuddleLocalRadiusCm defaults to
    100 cm before actor scaling; other source meshes can override it in an MI.
    """
    if not asset_path.startswith("/Game/") or "." in asset_path or asset_path.endswith("/"):
        raise ValueError("asset_path must be a /Game/.../MaterialName package path")
    library = unreal.EditorAssetLibrary
    material = library.load_asset(asset_path) if library.does_asset_exist(asset_path) else None
    if material is not None and not isinstance(material, unreal.Material):
        raise TypeError(f"Refusing to replace non-Material asset: {asset_path}")
    texture = _load_cloud_texture()  # Validate the dependency before editing.
    if material is None:
        folder, name = asset_path.rsplit("/", 1)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.Material, unreal.MaterialFactoryNew())
        if material is None:
            raise RuntimeError(f"Could not create material: {asset_path}")
    else:
        unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("screen_space_reflections", False)
    material.set_editor_property("disable_depth_test", False)
    material.set_editor_property("translucency_pass", unreal.MaterialTranslucencyPass.MTP_BEFORE_DOF)

    graph = _Graph(material)
    scalar = graph.scalar
    vector = graph.vector
    float1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    float2 = unreal.CustomMaterialOutputType.CMOT_FLOAT2
    float3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3
    opacity = scalar("SurfaceOpacity", 0.86, "01 Surface", "Interior alpha; boundary fades the entire water/cloud result.", 0.0, 1.0)
    brightness = scalar("SurfaceBrightness", 0.85, "01 Surface", "Bounded non-HDR brightness of this unlit illustration.", 0.0, 1.0)
    water_tint = vector("WaterTint", (0.10, 0.28, 0.31, 1.0), "01 Surface", "Linear teal water colour between sparse cloud patches.")
    cloud_tint = vector("CloudTint", (0.48, 0.65, 0.67, 1.0), "02 Clouds", "Linear pale cloud tint; no texture sky-blue is added to water.")
    amount = scalar("CloudAmount", 0.60, "02 Clouds", "Mix strength of pale clouds over teal water.", 0.0, 1.0)
    uv_scale = scalar("CloudUVScale", 0.56, "02 Clouds", "Source image span across the puddle; higher means smaller/more clouds.", 0.2, 1.2)
    uv_offset = vector("CloudUVOffset", (0.62, 0.34, 0.0, 0.0), "02 Clouds", "RG selects a crop centred on one or two large cloud patches.")
    rotation = scalar("CloudRotationDegrees", 12.0, "02 Clouds", "Rotate the source crop around its centre.", -180.0, 180.0)
    threshold = scalar("CloudThreshold", 0.58, "02 Clouds", "Linear luminance threshold; larger leaves fewer pale patches.", 0.1, 0.9)
    softness = scalar("CloudSoftness", 0.18, "02 Clouds", "Soft luminance range at cloud edges; preserves broad painterly masses.", 0.02, 0.4)
    radius = scalar("PuddleLocalRadiusCm", 100.0, "03 Mapping", "Original mesh local radius before actor scale, in cm; does not require UV0.", 1.0, 1000.0)
    world_scale = scalar("RippleWorldScaleCm", 700.0, "04 Motion", "Broad world-space wave length scale; independent of camera or puddle UVs.", 100.0, 3000.0)
    ripple_amount = scalar("RippleUVAmplitude", 0.008, "04 Motion", "Small source-UV distortion; zero disables ripples.", 0.0, 0.03)
    ripple_speed = scalar("RippleSpeed", 0.055, "04 Motion", "Slow phase speed in radians per second.", 0.0, 0.3)
    drift_amount = scalar("CloudDriftUVAmplitude", 0.010, "04 Motion", "Bounded gentle drift; never scrolls across repeated image tiles.", 0.0, 0.04)
    drift_speed = scalar("CloudDriftSpeed", 0.018, "04 Motion", "Very slow bounded cloud drift, in radians per second.", 0.0, 0.1)
    depth_distance = scalar("EdgeDepthFadeCm", 7.0, "05 Edge", "Preserved seven-centimetre intersection fade.", 0.1, 25.0)
    edge_power = scalar("EdgeFadePower", 1.0, "05 Edge", "Power applied after vertex-red smoothstep; zero boundary always stays zero.", 0.25, 3.0)

    world = graph.node(unreal.MaterialExpressionWorldPosition, "Absolute world position drives camera-independent slow waves.")
    local = graph.node(unreal.MaterialExpressionTransformPosition, "World to local cm: existing SM_Puddle has no authored UVs.")
    local.set_editor_property("transform_source_type", unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
    local.set_editor_property("transform_type", unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    # MaterialEditingLibrary applies GetShortenPinName: literal "Input" becomes
    # NAME_None. An empty name deliberately selects TransformPosition input 0.
    graph.wire(world, local, "")
    time = graph.node(unreal.MaterialExpressionTime)
    uv = graph.custom("Single cropped cloud image, bounded drift and broad world-locked distortion", """
float2 p = LocalPos.xy / (2.0 * max(LocalRadius, 1.0));
float angle = RotationDegrees * 0.0174532925199433;
float cs = cos(angle), sn = sin(angle);
p = float2(cs * p.x - sn * p.y, sn * p.x + cs * p.y);
float2 w = WorldPos.xy / max(WorldScale, 1.0);
float phase = T * max(WaveSpeed, 0.0);
float2 wave = float2(sin(w.x * 6.283185 + w.y * 1.1 + phase),
                    cos(w.y * 5.1 - w.x * 0.8 - phase * 0.79));
float drift = T * max(DriftSpeed, 0.0);
float2 motion = clamp(WaveAmount, 0.0, 0.03) * wave
              + clamp(DriftAmount, 0.0, 0.04) * float2(sin(drift), sin(drift * 0.73 + 0.4));
return clamp(p * clamp(Scale, 0.05, 1.2) + Offset.xy + motion, 0.002, 0.998);
""", {"LocalPos": local, "WorldPos": world, "LocalRadius": radius, "RotationDegrees": rotation,
       "WorldScale": world_scale, "T": time, "WaveSpeed": ripple_speed, "WaveAmount": ripple_amount,
       "DriftSpeed": drift_speed, "DriftAmount": drift_amount, "Scale": uv_scale, "Offset": uv_offset}, float2)
    cloud_texture = graph.node(unreal.MaterialExpressionTextureSampleParameter2D, "Existing art texture; sampled once with clamped crop coordinates.")
    cloud_texture.set_editor_property("parameter_name", "CloudTexture")
    cloud_texture.set_editor_property("group", "02 Clouds")
    cloud_texture.set_editor_property("texture", texture)
    graph.wire(uv, cloud_texture, "UVs")
    cloud_mask = graph.custom("Extract pale cloud shapes; discard the source image's blue sky", """
float luminance = dot(Image.rgb, float3(0.2126, 0.7152, 0.0722));
float width = max(Softness, 0.01);
return smoothstep(saturate(Threshold) - width * 0.5,
                  saturate(Threshold) + width * 0.5, luminance);
""", {"Image": cloud_texture, "Threshold": threshold, "Softness": softness}, float1)
    colour = graph.custom("Bounded illustrated water and clouds; straight alpha fades both together", """
float mixAmount = saturate(CloudMask) * saturate(Amount);
return saturate(lerp(saturate(Water.rgb), saturate(Cloud.rgb), mixAmount)) * saturate(Brightness);
""", {"CloudMask": cloud_mask, "Amount": amount, "Water": water_tint, "Cloud": cloud_tint, "Brightness": brightness}, float3)
    graph.output(colour, unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    edge = graph.node(unreal.MaterialExpressionVertexColor, "Source WaterEdgeMask red: 0 at perimeter, 1 inside.")
    depth = graph.node(unreal.MaterialExpressionDepthFade, "Intersection alpha fade; default 7 cm.")
    depth.set_editor_property("fade_distance_default", 7.0)
    depth.set_editor_property("opacity_default", 1.0)
    graph.wire(depth_distance, depth, "FadeDistance")
    coverage = graph.custom("True coverage: every cloud and teal contribution vanishes at the same boundary", """
float boundary = pow(smoothstep(0.0, 1.0, saturate(Edge.r)), max(EdgePower, 0.01));
return saturate(Opacity) * boundary * saturate(Depth);
""", {"Edge": edge, "Depth": depth, "Opacity": opacity, "EdgePower": edge_power}, float1)
    graph.output(coverage, unreal.MaterialProperty.MP_OPACITY)
    # BLEND_TRANSLUCENT uses straight alpha. Do not multiply colour by coverage
    # again: that would double-fade and darken the shoreline into a visible ring.
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    library.set_metadata_tag(material, "AstraIntent", "Puddle-only cloud illustration; no sky reflection capture; vertex-red and 7cm depth coverage")
    library.set_metadata_tag(material, "AstraPuddleParameters", json.dumps(graph.parameter_defaults, sort_keys=True))
    library.set_metadata_tag(material, "AstraPuddleReference", "ArtSource/Textures/T_AnimeSkyReflection.png")
    if not library.save_loaded_asset(material):
        raise RuntimeError(f"Could not save material: {asset_path}")
    return material


def validate_created_material(asset_path="/Game/Astra/Materials/M_PuddleReflection") -> dict:
    """Read the saved graph contract without editing, saving or claiming GPU QA."""
    material = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not isinstance(material, unreal.Material):
        raise TypeError(f"Expected existing Material: {asset_path}")
    library = unreal.MaterialEditingLibrary
    roots = {
        "emissive": library.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR),
        "opacity": library.get_material_property_input_node(material, unreal.MaterialProperty.MP_OPACITY),
    }
    def upstream(root):
        pending, found = [root] if root else [], {}
        while pending:
            node = pending.pop()
            if node is None or node.get_path_name() in found:
                continue
            found[node.get_path_name()] = node
            pending.extend(library.get_inputs_for_material_expression(material, node))
        return list(found.values())
    colour_nodes = upstream(roots["emissive"])
    opacity_nodes = upstream(roots["opacity"])
    checks = {
        "translucent": material.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_TRANSLUCENT,
        "unlit": material.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_UNLIT,
        "no_ssr": not material.get_editor_property("screen_space_reflections"),
        "depth_test_enabled": not material.get_editor_property("disable_depth_test"),
        "colour_output_connected": roots["emissive"] is not None,
        "coverage_output_connected": roots["opacity"] is not None,
        "vertex_red_upstream_of_alpha": any(isinstance(node, unreal.MaterialExpressionVertexColor) for node in opacity_nodes),
        "depth_fade_upstream_of_alpha": any(isinstance(node, unreal.MaterialExpressionDepthFade) for node in opacity_nodes),
        "seven_cm_default": abs(library.get_material_default_scalar_parameter_value(material, "EdgeDepthFadeCm") - 7.0) < 1e-5,
        "cloud_texture_upstream_of_colour": any(isinstance(node, unreal.MaterialExpressionTextureSampleParameter2D) for node in colour_nodes),
        "local_mapping_upstream_of_colour": any(isinstance(node, unreal.MaterialExpressionTransformPosition) for node in colour_nodes),
    }
    return {
        "asset": material.get_path_name(), "checks": checks, "passed": all(checks.values()),
        "scalar_parameters": sorted(str(name) for name in library.get_scalar_parameter_names(material)),
        "vector_parameters": sorted(str(name) for name in library.get_vector_parameter_names(material)),
        "textures": [texture.get_path_name() for texture in library.get_used_textures(material)],
        "validation_scope": "Read-only graph contract. Shader compile logs and actual orthographic GPU preview must be checked separately.",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-path", default="/Game/Astra/Materials/M_PuddleReflection")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not args.validate_only:
        build_puddle_material(args.asset_path)
    unreal.log(json.dumps(validate_created_material(args.asset_path), indent=2))
