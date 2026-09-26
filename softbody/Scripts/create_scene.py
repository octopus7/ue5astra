"""Build the self-contained Softbody studio in Unreal Engine 5.7.

Run after compiling SoftbodyEditor:
  UnrealEditor-Cmd.exe softbody.uproject -run=pythonscript -script=<this file>

Only this map's SB_* actors and the generated /Game/Softbody materials are
replaced on subsequent runs. The ball's simulation mesh is built by C++.
"""
import json
import math
import traceback
from pathlib import Path

import unreal


ROOT = Path(unreal.Paths.project_dir()).resolve()
MAP = "/Game/Softbody/Maps/L_SoftbodyLab"
MATERIAL_DIR = "/Game/Softbody/Materials"
REPORT = ROOT / "Saved" / "SceneBuild.json"
ASSETS = unreal.EditorAssetLibrary
MATERIALS = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LEVELS = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
GENERATED_TAG = "SoftbodyGenerated"
CREATED = []
BALL_SPECS = (
    {"name": "Tennis", "display": "TENNIS", "position": (0, -80, 99.35),
     "radius": 3.35, "hand": True},
    {"name": "Double", "display": "DOUBLE", "position": (0, 65, 102.7),
     "radius": 6.7, "hand": True},
    {"name": "Body", "display": "BODY", "position": (210, 130, 50),
     "radius": 50.0, "hand": False},
)


def expression(material, expression_class, x=-300, y=0, **properties):
    result = MATERIALS.create_material_expression(material, expression_class, x, y)
    assert result, "Material expression creation failed"
    for key, value in properties.items():
        result.set_editor_property(key, value)
    return result


def constant(material, value, y=0):
    return expression(material, unreal.MaterialExpressionConstant, y=y, r=value)


def color(material, rgb, y=0):
    return expression(material, unreal.MaterialExpressionConstant3Vector, y=y,
                      constant=unreal.LinearColor(*rgb, 1.0))


def connect(node, prop, output=""):
    assert MATERIALS.connect_material_property(node, output, prop)


def wire(source, output, target, input_name):
    assert MATERIALS.connect_material_expressions(source, output, target, input_name), \
        "Material connection failed: %s.%s -> %s.%s" % (source.get_name(), output, target.get_name(), input_name)


def make_material(name, rgb, roughness=0.6, metallic=0.0, emission=None,
                  vertex_color=False, clearcoat=False, specular=0.5, tennis_tint=None):
    path = MATERIAL_DIR + "/" + name
    material = ASSETS.load_asset(path) if ASSETS.does_asset_exist(path) else TOOLS.create_asset(
        name, MATERIAL_DIR, unreal.Material, unreal.MaterialFactoryNew())
    assert material, path
    MATERIALS.delete_all_material_expressions(material)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_CLEAR_COAT
                                 if clearcoat else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    if vertex_color:
        base = expression(material, unreal.MaterialExpressionVertexColor)
        if tennis_tint is not None:
            # Yellow-green tennis vertices have R-B > .25; ivory seams and teal do not.
            # This keeps the 1 m ball and seams at their existing albedos.
            yellow = expression(material, unreal.MaterialExpressionSubtract, x=-900)
            wire(base, "R", yellow, "A")
            wire(base, "B", yellow, "B")
            threshold = expression(material, unreal.MaterialExpressionSubtract, x=-750, const_b=.25)
            wire(yellow, "", threshold, "A")
            scale = expression(material, unreal.MaterialExpressionMultiply, x=-600, const_b=4.0)
            wire(threshold, "", scale, "A")
            mask = expression(material, unreal.MaterialExpressionSaturate, x=-450)
            wire(scale, "", mask, "")
            tint = expression(material, unreal.MaterialExpressionVectorParameter, x=-900, y=-250,
                              parameter_name="TennisTint", default_value=unreal.LinearColor(*tennis_tint, 1.0))
            tinted = expression(material, unreal.MaterialExpressionMultiply, x=-450, y=-250)
            wire(base, "", tinted, "A")
            wire(tint, "RGB", tinted, "B")
            mix = expression(material, unreal.MaterialExpressionLinearInterpolate, x=-100)
            wire(base, "", mix, "A")
            wire(tinted, "", mix, "B")
            wire(mask, "", mix, "Alpha")
            connect(mix, unreal.MaterialProperty.MP_BASE_COLOR)
        else:
            connect(base, unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        connect(color(material, rgb), unreal.MaterialProperty.MP_BASE_COLOR)
    connect(constant(material, roughness, 160), unreal.MaterialProperty.MP_ROUGHNESS)
    connect(constant(material, metallic, 220), unreal.MaterialProperty.MP_METALLIC)
    connect(constant(material, specular, 270), unreal.MaterialProperty.MP_SPECULAR)
    if emission:
        connect(color(material, emission, 300), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if clearcoat:
        connect(constant(material, 0.28, 370), unreal.MaterialProperty.MP_CUSTOM_DATA_0)
        connect(constant(material, 0.22, 440), unreal.MaterialProperty.MP_CUSTOM_DATA_1)
    MATERIALS.recompile_material(material)
    assert ASSETS.save_loaded_asset(material), path
    return material


def spawn(actor_class, label, position=(0, 0, 0), rotation=None, folder="Studio"):
    actor = ACTORS.spawn_actor_from_class(actor_class, unreal.Vector(*position),
                                          rotation or unreal.Rotator())
    assert actor, label
    actor.set_actor_label(label)
    actor.set_editor_property("tags", [unreal.Name(GENERATED_TAG)])
    actor.set_folder_path("Softbody/" + folder)
    CREATED.append(actor)
    return actor


def mesh(label, shape, position, dimensions, material, rotation=None, collision=False):
    """Engine shapes are 100 cm across; dimensions are world-space centimeters."""
    actor = spawn(unreal.StaticMeshActor, label, position, rotation)
    component = actor.static_mesh_component
    assert component.set_static_mesh(ASSETS.load_asset("/Engine/BasicShapes/" + shape))
    component.set_material(0, material)
    component.set_collision_profile_name("BlockAll" if collision else "NoCollision")
    component.set_editor_property("cast_shadow", True)
    actor.set_actor_scale3d(unreal.Vector(*(d / 100.0 for d in dimensions)))
    return actor


def text(label, words, position, size, rgb=(200, 222, 230), rotation=None, spacing=1.0):
    actor = spawn(unreal.TextRenderActor, label, position,
                  rotation or unreal.Rotator(pitch=0, yaw=-90, roll=0), "Typography")
    component = actor.get_component_by_class(unreal.TextRenderComponent)
    component.set_text(words)
    component.set_world_size(size)
    component.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
    component.set_vertical_alignment(unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
    component.set_horiz_spacing_adjust(spacing)
    component.set_text_render_color(unreal.Color(*rgb, 255))
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_editor_property("cast_shadow", False)
    return actor


def look_at(position, target):
    return unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position), unreal.Vector(*target))


def camera(label, position, target, fov):
    actor = spawn(unreal.CameraActor, label, position, look_at(position, target), "Cameras")
    actor.camera_component.set_editor_property("field_of_view", fov)
    actor.camera_component.set_editor_property("aspect_ratio", 16.0 / 9.0)
    actor.camera_component.set_editor_property("constrain_aspect_ratio", True)
    actor.set_editor_property("tags", [unreal.Name(GENERATED_TAG), unreal.Name(label)])
    return actor


def rect_light(label, position, target, intensity, rgb, width, height):
    actor = spawn(unreal.RectLight, label, position, look_at(position, target), "Lighting")
    light = actor.light_component
    light.set_mobility(unreal.ComponentMobility.MOVABLE)
    light.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    light.set_intensity(intensity)
    light.set_light_color(unreal.LinearColor(*rgb, 1.0))
    light.set_source_width(width)
    light.set_source_height(height)
    light.set_attenuation_radius(1000)
    return actor


def build_ball_material():
    return make_material("M_Ball", (0.035, 0.42, 0.32), .78,
                         vertex_color=True, specular=.18, tennis_tint=(.33, .48, .40))


def build_materials():
    return {
        "ball": build_ball_material(),
        "floor": make_material("M_Floor", (.037, .049, .067), .7, .12),
        "wall": make_material("M_Backdrop", (.018, .034, .052), .77),
        "panel": make_material("M_Panel", (.055, .083, .108), .55, .18),
        "dark": make_material("M_Graphite", (.024, .031, .038), .42, .45),
        "top": make_material("M_Ceramic", (.42, .52, .55), .4, .1),
        "metal": make_material("M_BrushedMetal", (.30, .37, .40), .30, .78),
        "brass": make_material("M_Brass", (.36, .23, .085), .30, .75),
        "cyan": make_material("M_CyanAccent", (.025, .32, .36), .33, .18,
                              emission=(.10, 2.6, 3.0)),
        "white": make_material("M_Softbox", (.65, .78, .80), .5,
                               emission=(1.8, 2.0, 2.0)),
    }


def build_architecture(m):
    mesh("SB_Floor", "Cube", (0, 0, -5), (1400, 1400, 10), m["floor"], collision=True)
    mesh("SB_Backdrop", "Cube", (60, 265, 185), (1040, 12, 370), m["wall"])
    # Thin slotted panels add depth without filling the close-up with detail.
    for index, x in enumerate((-350, -270, -190, 190, 270, 350)):
        mesh("SB_BackPanel_%02d" % index, "Cube", (x + 60, 256, 184), (72, 5, 346), m["panel"])
        mesh("SB_PanelSeam_%02d" % index, "Cube", (x + 95, 251, 184), (0.7, 1, 326), m["metal"])
    mesh("SB_BackSkirting", "Cube", (60, 255, 11), (1035, 4, 18), m["dark"])
    mesh("SB_BackSkirtingGlow", "Cube", (60, 251, 22), (1035, 1, .7), m["cyan"])
    # Concentric solid cylinders make a clean, thin vertical ring using only
    # the engine's cooked shapes. The front inset hides the circle's center.
    vertical = unreal.Rotator(pitch=0, yaw=0, roll=90)
    mesh("SB_BackHalo", "Cylinder", (60, 246, 147), (215, 215, 1.2), m["cyan"], vertical)
    mesh("SB_BackHaloInset", "Cylinder", (60, 244.9, 147), (212, 212, 1.3), m["wall"], vertical)
    mesh("SB_StageRing", "Cylinder", (70, 20, .09), (460, 460, .18), m["cyan"])
    mesh("SB_StageSurface", "Cylinder", (70, 20, .19), (458.6, 458.6, .18), m["floor"])
    # Ground stays essentially flush; the capsule walks over a collision floor
    # at exactly z=0, while these shallow disks are decorative.
    for index in range(12):
        angle = math.tau * index / 12
        x, y = 70 + 220 * math.cos(angle), 20 + 220 * math.sin(angle)
        mesh("SB_StageTick_%02d" % index, "Cube", (x, y, .3), (3, .5, .025), m["metal"],
             unreal.Rotator(pitch=0, yaw=math.degrees(angle), roll=0))
    # Narrow supports and Pawn-ignore collision leave the demonstrator free to
    # approach both stations while balls can still collide with the stands.
    for station in BALL_SPECS[:2]:
        name, y = station["name"], station["position"][1]
        parts = (
            ("Foot", 4, (36, 36, 8), "dark"),
            ("FootTrim", 8.2, (32, 32, .8), "brass"),
            ("Column", 49, (18, 18, 80), "dark"),
            ("Neck", 88.5, (22, 22, 6), "metal"),
            ("Underlight", 91.9, (33, 33, .8), "cyan"),
            ("Rim", 93.4, (36, 36, 2.2), "metal"),
            ("Tabletop", 95, (35, 35, 2), "top"),
        )
        for part, z, dimensions, material in parts:
            actor = mesh("SB_" + name + "_" + part, "Cylinder", (0, y, z), dimensions,
                         m[material], collision=True)
            actor.static_mesh_component.set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_PAWN, unreal.CollisionResponseType.ECR_IGNORE)
        for index in range(7):
            mesh("SB_" + name + "_Tick_%02d" % index, "Cube", (-9 + index * 3, y - 13, 96.02),
                 (.12, 1.3 if index % 2 == 0 else .65, .025), m["dark"])
        # Lettering is on a low sign, kept clear of the hands and contact area.
        mesh("SB_" + name + "_Plaque", "Cube", (0, y - 21, 30), (46, 2.2, 20), m["panel"])
        text("SB_" + name + "_Label", station["display"], (0, y - 22.2, 34.2), 4.8,
             (210, 227, 232), spacing=.5)
        text("SB_" + name + "_Size", "6.7 CM" if name == "Tennis" else "13.4 CM",
             (0, y - 22.3, 25.8), 3.1, (80, 197, 207), spacing=.3)
    text("SB_Title", "SOFTBODY", (-165, 249, 174), 26, spacing=2.4)
    text("SB_Subtitle", "T A C T I L E   L A B", (-165, 248.9, 150), 7, (85, 183, 197), spacing=.5)
    text("SB_Body_Label", "BODY / 1 M", (274, 247, 137), 10, (184, 204, 212))
    text("SB_Process", "TOUCH   /   DEFORM   /   RELEASE", (274, 247, 118), 3.6,
         (127, 158, 172), spacing=.2)
    # Off-axis display plinths establish scale in the overview.
    for side, x in (("Left", -235), ("Right", 375)):
        mesh("SB_" + side + "DisplayBase", "Cube", (x, 177, 27), (47, 40, 54), m["dark"])
        mesh("SB_" + side + "DisplayTrim", "Cube", (x, 177, 54.6), (48, 41, 1.2), m["brass"])
        mesh("SB_" + side + "DisplayTop", "Cube", (x, 177, 56.3), (46, 39, 2.2), m["panel"])
    mesh("SB_ReferencePuck", "Cylinder", (-235, 177, 61.4), (23, 23, 8), m["metal"])
    mesh("SB_ReferenceBlock", "Cube", (375, 177, 67.4), (18, 18, 20), m["top"],
         unreal.Rotator(pitch=0, yaw=22, roll=0))


def build_lighting():
    key = spawn(unreal.DirectionalLight, "SB_BroadKey", (0, -80, 320),
                unreal.Rotator(pitch=-48, yaw=135, roll=0), "Lighting")
    key.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    key.light_component.set_intensity(3.2)
    key.light_component.set_light_color(unreal.LinearColor(1.0, .94, .86, 1.0))
    key.light_component.set_editor_property("light_source_angle", 8.0)
    rect_light("SB_KeySoftbox", (60, -140, 235), (-20, 0, 105), 300, (1, .94, .86), 160, 120)
    rect_light("SB_CoolFill", (-180, -70, 150), (-25, 0, 102), 160, (.64, .83, 1), 140, 160)
    rect_light("SB_RimSoftbox", (65, 100, 223), (-10, 0, 110), 450, (.71, .93, 1), 90, 145)
    sky = spawn(unreal.SkyLight, "SB_EnvironmentFill", (0, 0, 300), folder="Lighting")
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    # Commandlets can reach this before the engine Asset Registry scan ends;
    # direct package loading works without relying on that asynchronous scan.
    cubemap = unreal.load_object(None, "/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap")
    assert isinstance(cubemap, unreal.TextureCube), "Studio ambient cubemap did not load"
    sky.light_component.set_editor_property("cubemap", cubemap)
    sky.light_component.set_editor_property("lower_hemisphere_is_black", False)
    sky.light_component.set_intensity(.45)
    pp = spawn(unreal.PostProcessVolume, "SB_ManualExposure", folder="Lighting")
    pp.set_editor_property("unbound", True)
    settings = pp.get_editor_property("settings")
    for key, value in {
        "override_auto_exposure_method": True,
        "auto_exposure_method": unreal.AutoExposureMethod.AEM_MANUAL,
        "override_auto_exposure_apply_physical_camera_exposure": True,
        "auto_exposure_apply_physical_camera_exposure": False,
        "override_auto_exposure_bias": True, "auto_exposure_bias": -2.8,
        "override_motion_blur_amount": True, "motion_blur_amount": 0.0,
        "override_bloom_intensity": True, "bloom_intensity": .15,
        "override_vignette_intensity": True, "vignette_intensity": .14,
    }.items():
        settings.set_editor_property(key, value)
    pp.set_editor_property("settings", settings)


def validate(materials, ball_class, game_mode):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    settings = world.get_world_settings()
    actors = ACTORS.get_all_level_actors()
    labels = [actor.get_actor_label() for actor in actors]
    start = next(actor for actor in actors if actor.get_actor_label() == "SB_PlayerStart")
    checks = {
        "map_saved": ASSETS.does_asset_exist(MAP),
        "materials_saved": all(ASSETS.does_asset_exist(m.get_path_name()) for m in materials.values()),
        "three_balls": sum(actor.get_class() == ball_class for actor in actors) == 3,
        "player_start": (start.get_actor_location() - unreal.Vector(-130, -80, 96)).length() < .01,
        "native_game_mode": settings.get_editor_property("default_game_mode") == game_mode,
        "normal_gravity": not settings.get_editor_property("global_gravity_set"),
        "camera_overview": labels.count("Overview") == 1,
        "camera_closeup": labels.count("HandCloseup") == 1,
        "ambient_cubemap": all(a.light_component.get_editor_property("cubemap") is not None
                               for a in actors if isinstance(a, unreal.SkyLight)),
        "no_duplicate_generated_labels": len({a.get_actor_label() for a in CREATED}) == len(CREATED),
    }
    ball_report = []
    for spec in BALL_SPECS:
        ball = next(actor for actor in actors if actor.get_actor_label() == "SB_Ball_" + spec["name"])
        checks[spec["name"] + "_position"] = (ball.get_actor_location() - unreal.Vector(*spec["position"])).length() < .01
        checks[spec["name"] + "_radius"] = abs(ball.get_editor_property("ball_radius") - spec["radius"]) < .001
        checks[spec["name"] + "_interaction"] = ball.get_editor_property("hand_interactable") == spec["hand"]
        if spec["hand"]:
            tabletop = next(actor for actor in actors if actor.get_actor_label() == "SB_" + spec["name"] + "_Tabletop")
            origin, extent = tabletop.get_actor_bounds(False)
            checks[spec["name"] + "_tabletop_96_cm"] = abs(origin.z + extent.z - 96.0) < .02
            checks[spec["name"] + "_stand_ignores_pawn"] = tabletop.static_mesh_component.get_collision_response_to_channel(
                unreal.CollisionChannel.ECC_PAWN) == unreal.CollisionResponseType.ECR_IGNORE
        ball_report.append({"label": ball.get_actor_label(), "center_cm": list(spec["position"]),
                            "radius_cm": spec["radius"], "diameter_cm": 2 * spec["radius"],
                            "hand_interactable": spec["hand"], "support_z_cm": 96 if spec["hand"] else 0})
    return {
        "success": all(checks.values()), "passed": all(checks.values()), "map": MAP, "checks": checks,
        "material_assets": [m.get_path_name() for m in materials.values()],
        "actor_count": len(actors), "generated_actor_count": len(CREATED),
        "generated_actors": [{"label": a.get_actor_label(), "class": a.get_class().get_path_name()}
                             for a in CREATED],
        "balls": ball_report,
        "camera_tags": ["Overview", "HandCloseup"],
    }


def main():
    ball_class = unreal.load_class(None, "/Script/Softbody.SoftBodyBall")
    game_mode = unreal.load_class(None, "/Script/Softbody.SoftbodyGameMode")
    assert ball_class and game_mode, "Build SoftbodyEditor before generating the scene"
    if ASSETS.does_asset_exist(MAP):
        assert LEVELS.load_level(MAP)
        for actor in ACTORS.get_all_level_actors():
            if GENERATED_TAG in [str(tag) for tag in actor.tags] or actor.get_actor_label().startswith("SB_"):
                ACTORS.destroy_actor(actor)
    else:
        assert LEVELS.new_level(MAP)
    materials = build_materials()
    build_architecture(materials)
    build_lighting()
    for spec in BALL_SPECS:
        ball = spawn(ball_class, "SB_Ball_" + spec["name"], spec["position"], folder="Simulation")
        ball.set_editor_property("ball_radius", spec["radius"])
        ball.set_editor_property("hand_interactable", spec["hand"])
        ball.set_editor_property("display_name", spec["display"])
    spawn(unreal.PlayerStart, "SB_PlayerStart", (-130, -80, 96), unreal.Rotator(), "Simulation")
    overview = camera("Overview", (400, -450, 300), (70, 0, 80), 50)
    camera("HandCloseup", (50, -5, 145), (0, 65, 110), 42)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world_settings = world.get_world_settings()
    world_settings.set_editor_property("default_game_mode", game_mode)
    world_settings.set_editor_property("global_gravity_set", False)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
        overview.get_actor_location(), overview.get_actor_rotation())
    ACTORS.set_selected_level_actors([])
    assert LEVELS.save_current_level(), "Map save failed"
    assert ASSETS.save_directory("/Game/Softbody", only_if_is_dirty=False, recursive=True)
    report = validate(materials, ball_class, game_mode)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert report["success"], "Scene verification failed: " + json.dumps(report["checks"])
    unreal.log("SOFTBODY_SCENE_BUILD_OK " + str(REPORT))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"success": False, "passed": False, "map": MAP, "error": traceback.format_exc()},
                                     indent=2), encoding="utf-8")
        raise
