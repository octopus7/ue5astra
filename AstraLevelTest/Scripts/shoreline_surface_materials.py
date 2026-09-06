"""UE 5.7 shoreline ground materials; explicit calls only, no import side effects.

World-space colour variation requires no UVs. Site-bed VertexColor.B is the
authored blend back to the existing landscape (kit interiors keep B=0). The
fixed water level is a scalar parameter in centimetres. Wetness marks only a
narrow strip above the water, not the entire submerged cliff or lake bed.
All changes are confined to /Game/Astra/Materials/Shoreline.
"""

from __future__ import annotations

import json
import re

import unreal


DESTINATION = "/Game/Astra/Materials/Shoreline"
REVISION = "shoreline-surface-1"
DEFAULTS = {
    "WaterLevelCm": 10.0,
    "WetBandHeightCm": 15.0,
    "WetDarkening": 0.24,
    "WetRoughness": 0.59,
    "DepthFadeStartCm": 15.0,
    "DepthFadeEndCm": 110.0,
    "DepthBlend": 0.86,
    "BroadContrast": 0.014,
    "GrainContrast": 0.004,
}


def _linear(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError("Expected six-digit sRGB palette colour: " + str(value))
    channels = [int(value[index:index + 2], 16) / 255.0 for index in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels)


class _Graph:
    def __init__(self, material):
        self.material = material
        self.library = unreal.MaterialEditingLibrary
        self.defaults = {}

    def node(self, cls, description=""):
        node = self.library.create_material_expression(self.material, cls)
        if node is None:
            raise RuntimeError("Cannot create material expression: " + cls.__name__)
        if description:
            node.set_editor_property("desc", description)
        return node

    def constant(self, value):
        node = self.node(unreal.MaterialExpressionConstant)
        node.set_editor_property("r", float(value))
        return node

    def scalar(self, name, value, group, maximum=1.0, minimum=0.0):
        node = self.node(unreal.MaterialExpressionScalarParameter)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(value))
        node.set_editor_property("group", group)
        node.set_editor_property("slider_min", float(minimum))
        node.set_editor_property("slider_max", float(maximum))
        self.defaults[name] = float(value)
        return node

    def vector(self, name, color, group):
        node = self.node(unreal.MaterialExpressionVectorParameter)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", unreal.LinearColor(*color, 1.0))
        node.set_editor_property("group", group)
        return node

    def custom(self, description, code, inputs, output_type):
        node = self.node(unreal.MaterialExpressionCustom, description)
        node.set_editor_property("code", code)
        node.set_editor_property("output_type", output_type)
        custom_inputs = []
        for name in inputs:
            entry = unreal.CustomInput()
            entry.set_editor_property("input_name", name)
            custom_inputs.append(entry)
        node.set_editor_property("inputs", custom_inputs)
        for name, source in inputs.items():
            expression, output_name = source if isinstance(source, tuple) else (source, "")
            if not self.library.connect_material_expressions(expression, output_name, node, name):
                raise RuntimeError("Cannot connect shoreline graph input: " + name)
        return node

    def output(self, node, material_property):
        if not self.library.connect_material_property(node, "", material_property):
            raise RuntimeError("Cannot connect shoreline material output: " + str(material_property))


def _wet_mask(graph, world_position):
    water = graph.scalar("WaterLevelCm", DEFAULTS["WaterLevelCm"], "01 Waterline", 500.0, -500.0)
    height = graph.scalar("WetBandHeightCm", DEFAULTS["WetBandHeightCm"], "01 Waterline", 30.0, 1.0)
    return graph.custom(
        "Narrow damp strip from the waterline to 15 cm above it; dry again underwater",
        """
float2 p = Pos.xy * 0.01;
float edgeShift = 0.65 * sin(p.x * 0.63 + p.y * 0.42) + 0.35 * sin(p.y * 0.9);
float h = Pos.z - WaterLevel - edgeShift;
float bandHeight = max(BandHeight, 1.0);
float lower = smoothstep(-1.0, 1.5, h);
float upper = 1.0 - smoothstep(bandHeight * 0.52, bandHeight, h);
return saturate(lower * upper);
""", {"Pos": world_position, "WaterLevel": water, "BandHeight": height},
        unreal.CustomMaterialOutputType.CMOT_FLOAT1)


def _wet_outputs(graph, base, dry_roughness, world_position):
    mask = _wet_mask(graph, world_position)
    darkening = graph.scalar("WetDarkening", DEFAULTS["WetDarkening"], "01 Waterline", 0.45)
    roughness = graph.scalar("WetRoughness", DEFAULTS["WetRoughness"], "01 Waterline", 0.95, 0.45)
    color = graph.custom("Slight damp darkening; no submerged-wide black band",
                         "return saturate(Base.rgb * (1.0 - saturate(Wet) * clamp(Darkening, 0.0, 0.45)));",
                         {"Base": base, "Wet": mask, "Darkening": darkening},
                         unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    rough = graph.custom("Damp stone/soil remains broadly rough",
                         "return lerp(clamp(Dry, 0.45, 1.0), clamp(Damp, 0.45, 0.95), saturate(Wet));",
                         {"Dry": dry_roughness, "Damp": roughness, "Wet": mask},
                         unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    graph.output(color, unreal.MaterialProperty.MP_BASE_COLOR)
    graph.output(rough, unreal.MaterialProperty.MP_ROUGHNESS)
    graph.output(graph.constant(0.14), unreal.MaterialProperty.MP_SPECULAR)


def _sand_outputs(graph, base, reference, world_position):
    inputs = {"Base": base, "Reference": reference, "Pos": world_position}
    boundary = graph.node(unreal.MaterialExpressionVertexColor,
                          "Site-bed B: zero in sand interior, one where mesh meets original landscape")
    inputs["Boundary"] = (boundary, "B")
    inputs["LandscapeBedTone"] = graph.vector("LandscapeBedTone", (0.31, 0.39, 0.28), "04 Boundary Match")
    for name, group, maximum in (("WaterLevelCm", "01 Waterline", 500.0),
                                  ("DepthFadeStartCm", "02 Depth", 300.0),
                                  ("DepthFadeEndCm", "02 Depth", 400.0),
                                  ("DepthBlend", "02 Depth", 1.0),
                                  ("BroadContrast", "03 Sand", 0.05),
                                  ("GrainContrast", "03 Sand", 0.02)):
        inputs[name] = graph.scalar(name, DEFAULTS[name], group, maximum, -500.0 if name == "WaterLevelCm" else 0.0)
    color = graph.custom(
        "Low-contrast sand; B=1 exactly matches the existing M_Landscape submerged branch",
        """
float2 p = Pos.xy * 0.01;
float depthCm = max(WaterLevelCm - Pos.z, 0.0);
float depth = smoothstep(DepthFadeStartCm, max(DepthFadeEndCm, DepthFadeStartCm + 1.0), depthCm);
float broad = 0.68 * sin(p.x * 1.1 + sin(p.y * 0.65)) * cos(p.y * 0.9 + p.x * 0.37)
            + 0.32 * sin(p.x * 0.48 - p.y * 0.76 + 1.2);
float grain = sin(p.x * 91.7 + p.y * 37.1) * sin(p.y * 83.9 - p.x * 29.3);
float grainAA = saturate(1.0 - max(fwidth(Pos.x), fwidth(Pos.y)) / 7.0);
// Identical to import_unreal_scene.build_materials' M_Landscape submerged
// branch below world Z=-25 cm. Use the same centimetre->metre mapping and
// phase: at B=1 no additional grain, tint or brightness multiplier remains.
float3 landscapeBed = LandscapeBedTone.rgb * (0.94 + 0.06 * sin(p.x * 0.55) * cos(p.y * 0.61));
float3 deepColour = landscapeBed;
float3 colour = lerp(Base.rgb, deepColour, depth * saturate(DepthBlend));
float contrast = lerp(1.0, 0.25, depth);
float variation = 1.0 + contrast * (broad * clamp(BroadContrast, 0.0, 0.05)
                                  + grain * grainAA * clamp(GrainContrast, 0.0, 0.02));
float boundaryBlend = smoothstep(0.0, 1.0, saturate(Boundary));
return saturate(lerp(colour * variation, landscapeBed, boundaryBlend));
""", inputs, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    graph.output(color, unreal.MaterialProperty.MP_BASE_COLOR)
    roughness = graph.custom("Match M_Landscape roughness at the buried boundary",
                             "return lerp(0.92, 0.95, smoothstep(0.0, 1.0, saturate(Boundary)));",
                             {"Boundary": (boundary, "B")}, unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    specular = graph.custom("Match M_Landscape specular at the buried boundary",
                            "return lerp(0.12, 0.08, smoothstep(0.0, 1.0, saturate(Boundary)));",
                            {"Boundary": (boundary, "B")}, unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    graph.output(roughness, unreal.MaterialProperty.MP_ROUGHNESS)
    graph.output(specular, unreal.MaterialProperty.MP_SPECULAR)


def _finish(material, graph, family):
    editing = unreal.MaterialEditingLibrary
    library = unreal.EditorAssetLibrary
    editing.layout_material_expressions(material)
    editing.recompile_material(material)
    library.set_metadata_tag(material, "AstraShorelineSurfaceRevision", REVISION)
    library.set_metadata_tag(material, "AstraShorelineSurfaceFamily", family)
    library.set_metadata_tag(material, "AstraShorelineScalarDefaults", json.dumps(graph.defaults, sort_keys=True))
    if not library.save_loaded_asset(material):
        raise RuntimeError("Could not save shoreline material: " + material.get_path_name())
    return material


def build_materials(palette: dict) -> dict[str, unreal.Material]:
    """Rebuild existing palette assets in place and return their identities."""
    if not palette or "M_ShoreSand" not in palette:
        raise ValueError("The shared shoreline palette must contain M_ShoreSand")
    colors = {}
    for name, value in palette.items():
        if not re.fullmatch(r"M_(?:Shore|Submerged)[A-Za-z0-9_]+", name):
            raise ValueError("Unexpected shoreline material name: " + str(name))
        colors[name] = _linear(value)
    library = unreal.EditorAssetLibrary
    editing = unreal.MaterialEditingLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    existing = {}
    # Validate every existing identity before deleting any expression graph.
    for name in colors:
        path = DESTINATION + "/" + name
        material = library.load_asset(path) if library.does_asset_exist(path) else None
        if material is not None and not isinstance(material, unreal.Material):
            raise TypeError("Expected a Material, refusing replacement: " + path)
        existing[name] = material
    sand_reference = colors["M_ShoreSand"]
    output = {}
    for name, color in colors.items():
        material = existing[name]
        if material is None:
            material = asset_tools.create_asset(name, DESTINATION, unreal.Material, unreal.MaterialFactoryNew())
        if material is None:
            raise RuntimeError("Could not create shoreline material: " + name)
        editing.delete_all_material_expressions(material)
        material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        material.set_editor_property("two_sided", False)
        graph = _Graph(material)
        position = graph.node(unreal.MaterialExpressionWorldPosition, "Absolute world position, in centimetres")
        is_sand = name in ("M_ShoreSand", "M_ShoreSandLight", "M_ShoreSandDark")
        is_submerged_stone = name in ("M_SubmergedStone", "M_SubmergedStoneLight", "M_SubmergedStoneDark")
        if is_sand:
            # ±2% linear brightness, about 4.1% max difference between slots.
            factor = {"M_ShoreSand": 1.0, "M_ShoreSandLight": 1.02, "M_ShoreSandDark": 0.98}[name]
            color = tuple(channel * factor for channel in sand_reference)
        elif is_submerged_stone:
            # Keep all imported slot identities, but remove their per-face tint
            # difference so authored smooth stone normals read as a single form.
            color = colors["M_SubmergedStone"]
        base = graph.vector("BaseTone", color, "00 Colour")
        if is_submerged_stone:
            base = graph.custom("Shared continuous stone tone; independent of triangle/material slot",
                                "float2 p=Pos.xy*.01; float variation=sin(p.x*.77+sin(p.y*.59))*cos(p.y*.68-p.x*.21); return saturate(Base.rgb*(1.0+.012*variation));",
                                {"Base": base, "Pos": position}, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        if is_sand:
            reference = graph.vector("SharedSandTone", sand_reference, "00 Colour")
            _sand_outputs(graph, base, reference, position)
            family = "continuous_sand"
        elif name.startswith("M_ShoreEarth") or name.startswith("M_SubmergedStone"):
            _wet_outputs(graph, base, graph.constant(0.88), position)
            family = "wet_earth_or_stone"
        else:
            # Grass and moss remain simple; no additional band or roof-like strip.
            graph.output(base, unreal.MaterialProperty.MP_BASE_COLOR)
            graph.output(graph.constant(0.94), unreal.MaterialProperty.MP_ROUGHNESS)
            graph.output(graph.constant(0.12), unreal.MaterialProperty.MP_SPECULAR)
            family = "grass_or_moss"
        graph.output(graph.constant(0.0), unreal.MaterialProperty.MP_METALLIC)
        library.set_metadata_tag(material, "AstraShorelineSRGB", palette[name])
        library.set_metadata_tag(material, "AstraShorelineBaseToneLinear", json.dumps(list(color)))
        output[name] = _finish(material, graph, family)
    return output


def build_wet_variant(source_material: unreal.Material, asset_path: str) -> unreal.Material:
    """Duplicate a source rock material and wrap its outputs; never edit source.

    Existing variants are reused, preventing nested wet bands and preserving the
    actor's material identity on reapplication. Their original copied graph is
    intentionally retained; later source graph changes require a new variant name.
    """
    if not isinstance(source_material, unreal.Material):
        raise TypeError("Wet variants require a Material source")
    if not re.fullmatch(re.escape(DESTINATION) + r"/Wet_[A-Za-z0-9_]+", asset_path):
        raise ValueError("Wet variant must be a /Game/Astra/Materials/Shoreline/Wet_* asset")
    library = unreal.EditorAssetLibrary
    source_path = source_material.get_path_name()
    if source_path.startswith(DESTINATION + "/Wet_"):
        raise ValueError("Refusing to wrap a wet variant in another wet variant")
    if source_material.get_editor_property("blend_mode") != unreal.BlendMode.BLEND_OPAQUE:
        raise ValueError("Wet rock source must be an opaque material")
    if library.does_asset_exist(asset_path):
        material = library.load_asset(asset_path)
        if (not isinstance(material, unreal.Material)
                or library.get_metadata_tag(material, "AstraShorelineWetSource") != source_path
                or library.get_metadata_tag(material, "AstraShorelineSurfaceRevision") != REVISION):
            raise RuntimeError("Existing Wet_* asset has a different source/revision: " + asset_path)
        return material
    editing = unreal.MaterialEditingLibrary
    if editing.get_material_property_input_node(source_material, unreal.MaterialProperty.MP_BASE_COLOR) is None:
        raise ValueError("Wet rock source must have a connected Base Color expression")
    material = library.duplicate_asset(source_path, asset_path)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Could not duplicate wet rock material: " + asset_path)
    graph = _Graph(material)
    base_property = unreal.MaterialProperty.MP_BASE_COLOR
    rough_property = unreal.MaterialProperty.MP_ROUGHNESS
    base = editing.get_material_property_input_node(material, base_property)
    base_output = editing.get_material_property_input_node_output_name(material, base_property)
    rough = editing.get_material_property_input_node(material, rough_property)
    rough_output = editing.get_material_property_input_node_output_name(material, rough_property) if rough else ""
    if rough is None:
        rough = graph.constant(0.88)
    position = graph.node(unreal.MaterialExpressionWorldPosition)
    _wet_outputs(graph, (base, base_output), (rough, rough_output), position)
    graph.output(graph.constant(0.0), unreal.MaterialProperty.MP_METALLIC)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    library.set_metadata_tag(material, "AstraShorelineWetSource", source_path)
    return _finish(material, graph, "existing_rock_wet_variant")


def inspect_materials(materials: dict) -> dict:
    """Return actual material modes and scalar defaults for the caller's report."""
    editing = unreal.MaterialEditingLibrary
    library = unreal.EditorAssetLibrary
    report = {}
    for name, material in materials.items():
        recorded = json.loads(library.get_metadata_tag(material, "AstraShorelineScalarDefaults") or "{}")
        report[name] = {
            "asset_path": material.get_path_name(),
            "opaque": material.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_OPAQUE,
            "default_lit": material.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
            "family": library.get_metadata_tag(material, "AstraShorelineSurfaceFamily"),
            "scalar_defaults": {key: float(editing.get_material_default_scalar_parameter_value(material, key)) for key in recorded},
        }
        if not report[name]["opaque"] or not report[name]["default_lit"]:
            raise RuntimeError("Unexpected shoreline material mode: " + name)
    return report
