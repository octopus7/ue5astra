"""UE 5.7 lake/stream colour, sparse contact foam and shoreward wave bands.

Only build_foam_material() mutates assets. It rebuilds a separate target while
the source material, levels, meshes, lighting and project settings stay read-only.
The existing graph helper is shared with puddle_cloud_trick; no cloud texture or
reflection nodes from the puddle material are used here.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import unreal


def _upstream(material, root):
    pending, nodes = [root] if root else [], {}
    while pending:
        node = pending.pop()
        if node is None or node.get_path_name() in nodes:
            continue
        nodes[node.get_path_name()] = node
        pending.extend(unreal.MaterialEditingLibrary.get_inputs_for_material_expression(material, node))
    return list(nodes.values())


def _source_snapshot(source):
    library = unreal.MaterialEditingLibrary
    snapshot = {
        "source_asset": source.get_path_name(),
        "properties": {name: str(source.get_editor_property(name)) for name in
                       ("blend_mode", "shading_model", "two_sided", "screen_space_reflections")},
        "scalar_parameters": {str(name): library.get_material_default_scalar_parameter_value(source, name)
                              for name in library.get_scalar_parameter_names(source)},
        "vector_parameters": {}, "source_custom_code": [], "source_depth_fade_cm": [],
    }
    for name in library.get_vector_parameter_names(source):
        value = library.get_material_default_vector_parameter_value(source, name)
        snapshot["vector_parameters"][str(name)] = [value.r, value.g, value.b, value.a]
    nodes = {}
    for property_ in (unreal.MaterialProperty.MP_EMISSIVE_COLOR, unreal.MaterialProperty.MP_OPACITY):
        for node in _upstream(source, library.get_material_property_input_node(source, property_)):
            nodes[node.get_path_name()] = node
    for node in nodes.values():
        if isinstance(node, unreal.MaterialExpressionCustom):
            snapshot["source_custom_code"].append(node.get_editor_property("code"))
        elif isinstance(node, unreal.MaterialExpressionDepthFade):
            snapshot["source_depth_fade_cm"].append(node.get_editor_property("fade_distance_default"))
    return snapshot


def _contour_hlsl():
    """Read the authored site contour, never infer it from prop scene depth.

    Distance is the exact minimum over clamped projections onto every authored
    polyline segment. Monotone cubic Y determines only the water/land sign;
    its local slope never scales the contact line or wave spacing.
    """
    path = Path(unreal.Paths.project_dir()).resolve() / "ArtSource/Layout/shoreline_site.json"
    if not path.is_file():
        return "return float3(0.0, 0.0, 0.0);", {"available": False}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    contour_key = ("foam_shoreline_contour_ue_m" if data.get("foam_shoreline_contour_ue_m")
                   else "shoreline_contour_ue_m")
    points = sorted(tuple(float(value) for value in point[:3])
                    for point in data.get(contour_key, []))
    if len(points) < 2 or not all(len(point) == 3 and all(math.isfinite(v) for v in point) for point in points):
        return "return float3(0.0, 0.0, 0.0);", {"available": False}
    spans = [b[0] - a[0] for a, b in zip(points, points[1:])]
    if min(spans) <= 0:
        raise ValueError("Authored shoreline contour must have strictly increasing X coordinates")
    secants = [(b[1] - a[1]) / h for a, b, h in zip(points, points[1:], spans)]
    slopes = [secants[0]]
    for i in range(1, len(points) - 1):
        left, right = secants[i - 1], secants[i]
        if left * right <= 0:
            slopes.append(0.0)
        else:
            w1, w2 = 2 * spans[i] + spans[i - 1], spans[i] + 2 * spans[i - 1]
            slopes.append((w1 + w2) / (w1 / left + w2 / right))
    slopes.append(secants[-1])
    lines = ["float2 p = Pos.xy * 0.01;", "float y = 0.0;"]
    for i, (a, b) in enumerate(zip(points, points[1:])):
        h = spans[i]
        prefix = "if" if i == 0 else "else if"
        condition = f"(p.x <= {b[0]:.9f})" if i < len(points) - 2 else ""
        header = "if (true)" if len(points) == 2 else f"{prefix if condition else 'else'} {condition}"
        lines.append(header + " {")
        lines.append(f"float t = saturate((p.x - {a[0]:.9f}) / {h:.9f});")
        lines.append("float t2=t*t, t3=t2*t;")
        lines.append(f"y=(2*t3-3*t2+1)*{a[1]:.9f}+(t3-2*t2+t)*{h*slopes[i]:.9f}+(-2*t3+3*t2)*{b[1]:.9f}+(t3-t2)*{h*slopes[i+1]:.9f};")
        lines.append("}")
    lines.append("float minimumDistanceSquared = 1.0e20;")
    # Emit bounded blocks so no dynamic HLSL array or loop is required. These
    # 56 clamped projections give actual rounded, equally spaced offset curves.
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length_squared = dx * dx + dy * dy
        lines.append("{")
        lines.append(f"float2 segmentStart = float2({a[0]:.9f}, {a[1]:.9f});")
        lines.append(f"float2 segmentVector = float2({dx:.9f}, {dy:.9f});")
        lines.append(f"float along = saturate(dot(p-segmentStart,segmentVector) / {length_squared:.12f});")
        lines.append("float2 delta = p - (segmentStart + along*segmentVector);")
        lines.append("minimumDistanceSquared = min(minimumDistanceSquared, dot(delta,delta));")
        lines.append("}")
    low, high = points[0][0], points[-1][0]
    lines.append(f"float enabled=smoothstep({low:.9f},{low+.65:.9f},p.x)*(1-smoothstep({high-.65:.9f},{high:.9f},p.x));")
    lines.append("float waterSide = (y >= p.y) ? 1.0 : -1.0;")
    lines.append("float distance = sqrt(max(minimumDistanceSquared,0.0))*100.0*waterSide + OffsetCm;")
    lines.append("return float3(distance, enabled*saturate(Enabled), 0.0);")
    return "\n".join(lines), {"available": True, "path": str(path), "source_key": contour_key, "points_ue_m": points,
                               "interpolation": "exact polyline distance; monotone cubic sign", "segment_count": len(points)-1,
                               "water_side": "UE Y below contour"}


def build_foam_material(
    source_path="/Game/Astra/Materials/M_Water",
    asset_path="/Game/Astra/Materials/Shoreline/M_WaterFoam",
) -> unreal.Material:
    """Build a separate translucent, unlit water material and return it.

    Water colours and all distances are Material Instance parameters. Depth is
    a screen-derived vertical proxy, not a bathymetry texture: PerspectiveDepth
    and object silhouettes cannot provide perfect shoreline topology. The fixed
    gameplay camera is supported by DepthVerticalScale=sin(58 degrees).

    The authored site uses shoreline_site.json's actual world-XY contour, so
    underwater props cannot bend the foam field. Elsewhere shallow depth bands
    use a constant depth-to-distance ratio and reject abrupt depth changes.
    """
    from puddle_cloud_trick import _Graph

    if source_path.split(".")[0] == asset_path.split(".")[0]:
        raise ValueError("Foam target must be separate from the read-only source material")
    if not asset_path.startswith("/Game/") or "." in asset_path or asset_path.endswith("/"):
        raise ValueError("asset_path must be a /Game/.../MaterialName package path")
    assets = unreal.EditorAssetLibrary
    source = assets.load_asset(source_path)
    if not isinstance(source, unreal.Material):
        raise TypeError(f"Expected source Material: {source_path}")
    snapshot = _source_snapshot(source)
    contour_code, contour_info = _contour_hlsl()
    source_tags = assets.get_metadata_tag_values(source)
    material = assets.load_asset(asset_path) if assets.does_asset_exist(asset_path) else None
    if material is not None and not isinstance(material, unreal.Material):
        raise TypeError(f"Refusing to replace non-Material asset: {asset_path}")
    if material is None:
        material = assets.duplicate_asset(source_path, asset_path)
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Could not duplicate water material to {asset_path}")
    # Disconnect final roots first. Incremental expression deletion otherwise
    # briefly recompiles the old Custom graphs with half their inputs missing.
    editing = unreal.MaterialEditingLibrary
    for property_ in (unreal.MaterialProperty.MP_EMISSIVE_COLOR, unreal.MaterialProperty.MP_OPACITY):
        old_root = editing.get_material_property_input_node(material, property_)
        if old_root is not None:
            editing.delete_material_expression(material, old_root)
    editing.delete_all_material_expressions(material)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", source.get_editor_property("two_sided"))
    material.set_editor_property("screen_space_reflections", False)
    material.set_editor_property("disable_depth_test", False)
    graph = _Graph(material)
    s, v = graph.scalar, graph.vector
    float1 = unreal.CustomMaterialOutputType.CMOT_FLOAT1
    float3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3

    shallow = v("WaterShallowTint", (0.22, 0.48, 0.39, 1.0), "01 Water colour", "Linear pale mint; low alpha keeps the sand visible.")
    middle = v("WaterMiddleTint", (0.065, 0.32, 0.31, 1.0), "01 Water colour", "Linear middle-depth teal.")
    deep = v("WaterDeepTint", (0.018, 0.20, 0.23, 1.0), "01 Water colour", "Linear deeper turquoise, without sky reflection.")
    mid_depth = s("WaterMiddleDepthCm", 42.0, "01 Water colour", "Vertical depth at the middle colour.", 10.0, 100.0)
    deep_depth = s("WaterDeepDepthCm", 145.0, "01 Water colour", "Vertical depth at the deepest colour; smooth transition.", 50.0, 400.0)
    shallow_alpha = s("WaterShallowOpacity", 0.35, "02 Coverage", "Transparent shallows expose the real bed material.", 0.0, 0.75)
    middle_alpha = s("WaterMiddleOpacity", 0.55, "02 Coverage", "Middle-depth water alpha.", 0.0, 0.75)
    deep_alpha = s("WaterDeepOpacity", 0.74, "02 Coverage", "Deep water stays below the 0.75 opacity cap.", 0.0, 0.75)
    fade_distance = s("EdgeDepthFadeCm", 5.0, "02 Coverage", "DepthFade retained; 5cm lets a thin contact line remain readable. Source value is recorded in metadata.", 0.5, 40.0)
    foam_edge_end = s("FoamEdgeCoverageEndR", 0.35, "02 Coverage", "Foam reaches full edge coverage at this vertex-red value; exact red zero stays transparent. Water coverage is unchanged.", 0.05, 1.0)
    depth_scale = s("DepthVerticalScale", 0.8480481, "03 Depth mapping", "sin(58 degrees) corrects the fixed orthographic view-depth proxy.", 0.1, 1.0)
    fallback_scale = s("FallbackDistancePerDepth", 3.0, "03 Depth mapping", "Outside the authored contour: fixed cm-distance per cm-depth, never divided by screen gradients.", 1.0, 6.0)
    reject_depth = s("FallbackDepthJumpCm", 1.4, "03 Depth mapping", "Outside the site, reject rapid depth changes around rocks and floating props.", 0.5, 5.0)
    site_enabled = s("AuthoredShoreContourEnabled", 1.0, "03 Depth mapping", "Use the real site contour so foam does not wrap around underwater rocks.", 0.0, 1.0)
    site_offset = s("AuthoredShoreOffsetCm", 0.0, "03 Depth mapping", "Fine alignment of the contour distance; positive moves the crest landward.", -30.0, 30.0)
    foam_tint = v("FoamTint", (0.92, 0.90, 0.79, 1.0), "04 Contact foam", "Warm white below HDR; mixed through the same water alpha.")
    contact_strength = s("ContactFoamStrength", 0.95, "04 Contact foam", "Peak brightness mix of the narrow, interrupted contact line.", 0.0, 1.0)
    contact_width = s("ContactFoamWidthCm", 8.0, "04 Contact foam", "World-space full width; about 5 pixels at 2350cm/1600px.", 2.0, 16.0)
    contact_offset = s("ContactFoamOffsetCm", 14.0, "04 Contact foam", "Place the thin line just inside the water after its alpha transition.", 3.0, 30.0)
    break_amount = s("FoamBreakAmount", 0.40, "04 Contact foam", "Larger values leave more gaps along the shoreline.", 0.1, 0.9)
    wave_strength = s("ShoreWaveStrength", 0.85, "05 Shoreward waves", "Pale broken bands, weaker than contact foam.", 0.0, 1.0)
    wave_spacing = s("ShoreWaveSpacingCm", 92.0, "05 Shoreward waves", "Spacing chosen for one or two bands in the nearshore window.", 45.0, 160.0)
    wave_width = s("ShoreWaveWidthCm", 8.0, "05 Shoreward waves", "World-space full width of a wave crest.", 2.0, 16.0)
    wave_speed = s("ShoreWaveSpeedCmPerSecond", 4.0, "05 Shoreward waves", "Positive speed moves crest depth/distance toward zero, hence toward shore.", 0.0, 12.0)
    wave_range = s("ShoreWaveRangeCm", 185.0, "05 Shoreward waves", "Bands stop beyond this shoreline-distance window.", 80.0, 250.0)
    foam_depth = s("FoamDepthLimitCm", 48.0, "05 Shoreward waves", "Absolute shallow-depth limit prevents patterns in the lake centre.", 12.0, 90.0)
    noise_scale = s("FoamBreakScaleMeters", 1.6, "05 Shoreward waves", "Broad world-locked alongshore gaps; no high-frequency white noise.", 0.6, 4.0)
    fresnel_f0 = s("FresnelF0", 0.02, "06 View-angle response", "Water normal-incidence Fresnel value; controls colour/opacity only, never sky reflection.", 0.0, 0.1)
    fresnel_exponent = s("FresnelExponent", 5.0, "06 View-angle response", "Schlick-style view-angle falloff toward grazing angles.", 1.0, 8.0)
    fresnel_reference = s("FresnelReferenceNdotV", 0.8480481, "06 View-angle response", "sin(58 degrees): subtract this reference response to preserve the fixed top-down look.", 0.0, 1.0)
    fresnel_opacity = s("FresnelOpacityBoost", 0.12, "06 View-angle response", "Additional grazing-angle water alpha before the shared 0.75 cap and edge coverage.", 0.0, 0.25)
    fresnel_colour = s("FresnelWaterColourBoost", 0.06, "06 View-angle response", "Subtle grazing-angle water-colour strength; does not alter foam tint.", 0.0, 0.15)

    scene = graph.node(unreal.MaterialExpressionSceneDepth)
    pixel = graph.node(unreal.MaterialExpressionPixelDepth)
    world = graph.node(unreal.MaterialExpressionWorldPosition)
    time = graph.node(unreal.MaterialExpressionTime)
    camera_vector = graph.node(unreal.MaterialExpressionCameraVectorWS, "Actual surface-to-camera direction; uniform for a flat orthographic view.")
    pixel_normal = graph.node(unreal.MaterialExpressionPixelNormalWS, "Actual world-space pixel normal for angle-dependent water response.")
    edge = graph.node(unreal.MaterialExpressionVertexColor, "Original coverage red; exact perimeter remains zero.")
    fade = graph.node(unreal.MaterialExpressionDepthFade, "A real alpha fade, shared by water and both foam terms.")
    fade.set_editor_property("fade_distance_default", 5.0)
    fade.set_editor_property("opacity_default", 1.0)
    graph.wire(fade_distance, fade, "FadeDistance")
    depth = graph.custom("Vertical water-depth proxy in centimetres", "return max(Scene - Pixel, 0.0) * clamp(VerticalScale, 0.1, 1.0);",
                         {"Scene": scene, "Pixel": pixel, "VerticalScale": depth_scale}, float1)
    fresnel = graph.custom("Fresnel excess above the fixed top-down reference; colour and alpha only", """
float ndv = saturate(abs(dot(normalize(ViewDir), normalize(SurfaceNormal))));
float f0 = saturate(F0);
float exponent = max(Power, 1.0);
float response = f0 + (1.0 - f0) * pow(1.0 - ndv, exponent);
float reference = f0 + (1.0 - f0) * pow(1.0 - saturate(ReferenceCos), exponent);
return max(response - reference, 0.0);
""", {"ViewDir": camera_vector, "SurfaceNormal": pixel_normal, "F0": fresnel_f0,
       "Power": fresnel_exponent, "ReferenceCos": fresnel_reference}, float1)
    contour = graph.custom("Authored world-XY shoreline; independent of rocks, flowers and scene-depth derivatives", contour_code,
                           {"Pos": world, "OffsetCm": site_offset, "Enabled": site_enabled}, float3)
    distance = graph.custom("Stable contour distance; conservative shallow-depth fallback elsewhere", """
float useContour = saturate(Contour.y);
float fallback = Depth * max(DepthRatio, 0.1);
float reject = 1.0-smoothstep(max(DepthJump,0.1),max(DepthJump,0.1)*2.5,fwidth(Depth));
return float3(lerp(fallback,Contour.x,useContour),lerp(reject,1.0,useContour),useContour);
""", {"Contour": contour, "Depth": depth, "DepthRatio": fallback_scale, "DepthJump": reject_depth}, float3)
    foam = graph.custom("Thin contact foam and 1-2 broken bands; positive phase advances toward shore", """
float d = Shore.x;
float2 p = Pos.xy * 0.01 / max(BreakScale, 0.1);
float n = saturate(0.5 + 0.25 * sin(p.x * 3.1 + p.y * 1.3 + sin(p.y * 1.7))
                      + 0.20 * sin(p.y * 4.3 - p.x * 0.9));
float gaps = smoothstep(saturate(Breaks) - 0.14, saturate(Breaks) + 0.14, n);
// Derivatives are only antialiasing, capped so prop discontinuities cannot
// broaden a thin crest into stretched white fragments.
float aa = clamp(fwidth(d) * 0.7, 0.7, max(1.0,min(ContactWidth,WaveWidth)*0.35));
float halfContact = max(ContactWidth, 1.0) * 0.5;
float contact = 1.0 - smoothstep(max(halfContact - aa, 0.0), halfContact + aa,
                                 abs(d - max(ContactOffset, halfContact)));
float spacing = max(Spacing, 10.0);
// Holding a phase crest constant gives d = constant - Time * Speed.
float phase = frac((d + T * max(Speed, 0.0)) / spacing);
float crestDistance = abs(phase - 0.5) * spacing;
float halfWave = max(WaveWidth, 1.0) * 0.5;
float wave = 1.0 - smoothstep(max(halfWave - aa, 0.0), halfWave + aa, crestDistance);
float window = smoothstep(25.0, 40.0, d)
             * (1.0 - smoothstep(max(Range - 25.0, 45.0), max(Range, 70.0), d));
float waveGaps = smoothstep(saturate(Breaks) - 0.02, saturate(Breaks) + 0.20,
                           saturate(n + 0.10 * sin(p.x * 1.4 - p.y * 2.3)));
float depthGate = smoothstep(0.2, 0.8, Depth)
                * (1.0 - smoothstep(max(DepthLimit * 0.75, 1.0), max(DepthLimit, 2.0), Depth));
return saturate(max(contact * gaps * saturate(ContactAmount),
                    wave * window * waveGaps * saturate(WaveAmount))) * depthGate * Shore.y;
""", {"Shore": distance, "Pos": world, "T": time, "Depth": depth,
       "BreakScale": noise_scale, "Breaks": break_amount, "ContactWidth": contact_width,
       "ContactOffset": contact_offset, "Spacing": wave_spacing, "Speed": wave_speed,
       "WaveWidth": wave_width, "Range": wave_range, "DepthLimit": foam_depth,
       "ContactAmount": contact_strength, "WaveAmount": wave_strength}, float1)
    weights = graph.custom("Matched water/foam alpha contributions; exact perimeter zero and total cap 0.75", """
float mid = max(MidDepth, 1.0), deep = max(DeepDepth, mid + 1.0);
float water = lerp(ShallowAlpha, MiddleAlpha, smoothstep(0.0, mid, Depth));
water = lerp(water, DeepAlpha, smoothstep(mid, deep, Depth));
water += clamp(OpacityBoost, 0.0, 0.25) * saturate(ViewFresnel);
float coverage = smoothstep(0.0, 1.0, saturate(Edge.r));
float foamCoverage = smoothstep(0.0, clamp(FoamEdgeEnd, 0.05, 1.0), saturate(Edge.r));
float blend = saturate(Foam);
float waterWeight = (1.0 - blend) * clamp(water, 0.0, 0.75) * coverage * saturate(Fade);
float foamWeight = blend * 0.75 * foamCoverage * saturate(Fade);
// This convex combination is <= 0.75 before the defensive final clamp.
return float3(waterWeight, foamWeight, min(waterWeight + foamWeight, 0.75));
""", {"Depth": depth, "MidDepth": mid_depth, "DeepDepth": deep_depth,
       "ShallowAlpha": shallow_alpha, "MiddleAlpha": middle_alpha, "DeepAlpha": deep_alpha,
       "Edge": edge, "Fade": fade, "Foam": foam, "FoamEdgeEnd": foam_edge_end,
       "OpacityBoost": fresnel_opacity, "ViewFresnel": fresnel}, float3)
    colour = graph.custom("Straight-alpha colour from matching water and foam contributions", """
float mid = max(MidDepth, 1.0), deep = max(DeepDepth, mid + 1.0);
float3 c = lerp(Shallow.rgb, Middle.rgb, smoothstep(0.0, mid, Depth));
c = lerp(c, Deep.rgb, smoothstep(mid, deep, Depth));
c *= 1.0 + clamp(ColourBoost, 0.0, 0.15) * saturate(ViewFresnel);
float3 premultiplied = saturate(c) * Weights.x + saturate(FoamColour.rgb) * Weights.y;
return saturate(premultiplied / max(Weights.z, 0.000001));
""", {"Depth": depth, "MidDepth": mid_depth, "DeepDepth": deep_depth, "Shallow": shallow,
       "Middle": middle, "Deep": deep, "FoamColour": foam_tint, "Weights": weights,
       "ColourBoost": fresnel_colour, "ViewFresnel": fresnel}, float3)
    alpha = graph.custom("Total water and foam coverage, matching the straight-alpha colour", "return Weights.z;",
                         {"Weights": weights}, float1)
    graph.output(colour, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    graph.output(alpha, unreal.MaterialProperty.MP_OPACITY)
    # Straight-alpha translucency applies coverage once. Multiplying colour by
    # coverage as well would create an unwanted dark double-fade around the bank.
    for key, value in source_tags.items():
        assets.set_metadata_tag(material, str(key), value)
    assets.set_metadata_tag(material, "AstraFoamSourceSnapshot", json.dumps(snapshot, sort_keys=True))
    assets.set_metadata_tag(material, "AstraFoamContour", json.dumps(contour_info, sort_keys=True))
    assets.set_metadata_tag(material, "AstraFoamParameters", json.dumps(graph.parameter_defaults, sort_keys=True))
    assets.set_metadata_tag(material, "AstraFoamIntent", "Lake/stream only: shallow mint/teal, thin interrupted contact foam, shoreward bands. View-angle Fresnel affects water colour/alpha above the fixed top-down reference. No sky/cloud/reflection.")
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not assets.save_loaded_asset(material):
        raise RuntimeError(f"Could not save foam target: {asset_path}")
    return material


def validate_created_material(asset_path="/Game/Astra/Materials/Shoreline/M_WaterFoam") -> dict:
    """Inspect the existing graph without mutation; GPU appearance is separate."""
    material = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not isinstance(material, unreal.Material):
        raise TypeError(f"Expected Material: {asset_path}")
    library = unreal.MaterialEditingLibrary
    alpha_nodes = _upstream(material, library.get_material_property_input_node(material, unreal.MaterialProperty.MP_OPACITY))
    colour_nodes = _upstream(material, library.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR))
    all_nodes = {node.get_path_name(): node for node in alpha_nodes + colour_nodes}.values()
    codes = [node.get_editor_property("code") for node in all_nodes if isinstance(node, unreal.MaterialExpressionCustom)]
    scalar_names = set(str(name) for name in library.get_scalar_parameter_names(material))
    checks = {
        "unlit": material.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_UNLIT,
        "translucent": material.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_TRANSLUCENT,
        "no_ssr": not material.get_editor_property("screen_space_reflections"),
        "no_textures_or_clouds": len(library.get_used_textures(material)) == 0,
        "vertex_colour_in_alpha": any(isinstance(node, unreal.MaterialExpressionVertexColor) for node in alpha_nodes),
        "depth_fade_in_alpha": any(isinstance(node, unreal.MaterialExpressionDepthFade) for node in alpha_nodes),
        "scene_depth_in_colour": any(isinstance(node, unreal.MaterialExpressionSceneDepth) for node in colour_nodes),
        "pixel_depth_in_colour": any(isinstance(node, unreal.MaterialExpressionPixelDepth) for node in colour_nodes),
        "time_in_foam": any(isinstance(node, unreal.MaterialExpressionTime) for node in colour_nodes),
        "foam_controls": {"ContactFoamWidthCm", "ShoreWaveSpeedCmPerSecond", "FoamDepthLimitCm"}.issubset(scalar_names),
        "shoreward_phase": any("d + T * max(Speed, 0.0)" in code for code in codes),
        "no_inverse_depth_gradient": not any("Depth / max(slope" in code for code in codes),
        "no_local_slope_distance_scaling": not any("sqrt(1.0+slope*slope)" in code for code in codes),
        "authored_contour_control": "AuthoredShoreContourEnabled" in scalar_names,
        "alpha_capped_at_075": any("clamp(water, 0.0, 0.75)" in code for code in codes),
        "foam_edge_coverage_control": "FoamEdgeCoverageEndR" in scalar_names,
        "matched_colour_alpha_weights": any("premultiplied / max(Weights.z" in code for code in codes) and any("return Weights.z;" in code for code in codes),
        "camera_vector_in_alpha_and_colour": all(any(isinstance(node, unreal.MaterialExpressionCameraVectorWS) for node in nodes) for nodes in (alpha_nodes, colour_nodes)),
        "pixel_normal_in_alpha_and_colour": all(any(isinstance(node, unreal.MaterialExpressionPixelNormalWS) for node in nodes) for nodes in (alpha_nodes, colour_nodes)),
        "fresnel_controls": {"FresnelF0", "FresnelExponent", "FresnelReferenceNdotV", "FresnelOpacityBoost", "FresnelWaterColourBoost"}.issubset(scalar_names),
        "fresnel_preserves_reference": any("max(response - reference, 0.0)" in code for code in codes),
    }
    return {"asset": material.get_path_name(), "passed": all(checks.values()), "checks": checks,
            "scalar_parameters": sorted(scalar_names),
            "validation_scope": "Read-only graph contract; compile logs, shoreline stability and fixed-camera GPU appearance require root integration testing."}
