"""Import the shoreline kit and apply its site to an already loaded UE map.

Run with UE 5.7 editor Python after the caller loads the intended woodland map.
Importing this module does not read manifests, import assets, or edit the level.
All source paths are resolved below the current Unreal project's ArtSource.
"""

import hashlib
import json
import math
from pathlib import Path
import re

import unreal


MATERIAL_DEST = "/Game/Astra/Materials/Shoreline"
KIT_DEST = "/Game/Astra/Meshes/Shoreline"
SITE_DEST = "/Game/Astra/Meshes/ShorelineSite"
ACTOR_PREFIX = "AST_Shoreline_"


def _finite(value, where="manifest"):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite number at " + where)
    if isinstance(value, dict):
        for key, item in value.items():
            _finite(item, where + "." + str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _finite(item, where + "[" + str(index) + "]")


def _vec(value, where, positive=False):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(where + " must contain three numbers")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("Invalid vector: " + where)
    if positive and any(v <= 0 for v in value):
        raise ValueError("Non-positive vector: " + where)
    return [float(v) for v in value]


def _source(art, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("ArtSource file must be a relative path")
    path = (art / relative).resolve()
    try:
        path.relative_to(art)
    except ValueError:
        raise ValueError("Source path escapes ArtSource: " + relative)
    if not path.is_file():
        raise FileNotFoundError("Missing shoreline source: " + str(path))
    return path


def _read_manifests(require_site=False):
    project = Path(unreal.Paths.project_dir()).resolve()
    art = (project / "ArtSource").resolve()
    kit_path = _source(art, "Layout/shoreline_assets.json")
    kit = json.loads(kit_path.read_text(encoding="utf-8-sig"))
    _finite(kit)
    site_path = art / "Layout" / "shoreline_site.json"
    if require_site and not site_path.is_file():
        raise FileNotFoundError("Build place_shoreline_blender.py first; missing " + str(site_path))
    site = json.loads(_source(art, "Layout/shoreline_site.json").read_text(encoding="utf-8-sig")) if site_path.is_file() else {}
    _finite(site)
    palette = dict(kit["palette_srgb_hex"])
    for key, value in site.get("palette_srgb_hex", {}).items():
        if key in palette and palette[key] != value:
            raise ValueError("Site changes the shared palette: " + key)
        palette[key] = value
    for key, value in palette.items():
        if not re.fullmatch(r"M_[A-Za-z0-9_]+", key) or not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
            raise ValueError("Invalid shoreline palette entry: " + str(key))
    specs = {}
    for manifest_name, manifest in (("shoreline_assets.json", kit), ("shoreline_site.json", site)):
        for name, meta in manifest.get("assets", {}).items():
            if not re.fullmatch(r"SM_[A-Za-z0-9_]+", name):
                raise ValueError("Invalid mesh name: " + name)
            source = _source(art, meta["file"])
            if source.suffix.lower() != ".fbx":
                raise ValueError("Only FBX shoreline meshes may be imported")
            _vec(meta["dimensions_m"], name + ".dimensions_m")
            if any(v < 0 for v in meta["dimensions_m"]):
                raise ValueError("Negative mesh dimensions: " + name)
            if not meta.get("materials") or any(key not in palette for key in meta["materials"]):
                raise ValueError("Missing material palette entry: " + name)
            if name in specs:
                if specs[name]["meta"]["file"] != meta["file"]:
                    raise ValueError("Conflicting FBX definitions: " + name)
                continue
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if meta.get("sha256") and digest != meta["sha256"]:
                raise ValueError("FBX differs from recorded SHA256: " + name)
            specs[name] = {"meta": meta, "source": source, "sha256": digest,
                           "manifest": "Layout/" + manifest_name,
                           "destination": KIT_DEST if name in kit["assets"] else SITE_DEST}
    return project, art, site, palette, specs


def _linear(hex_rgb):
    values = [int(hex_rgb[index:index + 2], 16) / 255.0 for index in (0, 2, 4)]
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]


def _materials(palette):
    library = unreal.EditorAssetLibrary
    editing = unreal.MaterialEditingLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    result = {}
    for name, color in palette.items():
        path = MATERIAL_DEST + "/" + name
        material = library.load_asset(path) if library.does_asset_exist(path) else None
        if material is None:
            material = asset_tools.create_asset(name, MATERIAL_DEST, unreal.Material, unreal.MaterialFactoryNew())
        if not isinstance(material, unreal.Material):
            raise TypeError("Expected a Material: " + path)
        editing.delete_all_material_expressions(material)
        material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        material.set_editor_property("two_sided", False)
        node = editing.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -400, 0)
        node.set_editor_property("constant", unreal.LinearColor(*_linear(color), 1.0))
        editing.connect_material_property(node, "", unreal.MaterialProperty.MP_BASE_COLOR)
        for index, (value, prop) in enumerate(((0.88, unreal.MaterialProperty.MP_ROUGHNESS),
                                             (0.12, unreal.MaterialProperty.MP_SPECULAR),
                                             (0.0, unreal.MaterialProperty.MP_METALLIC))):
            node = editing.create_material_expression(material, unreal.MaterialExpressionConstant, -400, 150 + index * 100)
            node.set_editor_property("r", value)
            editing.connect_material_property(node, "", prop)
        editing.recompile_material(material)
        library.set_metadata_tag(material, "AstraShorelineSRGB", color)
        library.save_loaded_asset(material)
        result[name] = material
    return result


def _measure_mesh(mesh, spec):
    bounds = mesh.get_bounding_box()
    measured = [(getattr(bounds.max, axis) - getattr(bounds.min, axis)) / 100.0 for axis in ("x", "y", "z")]
    expected = spec["meta"]["dimensions_m"]
    for index, (actual, reference) in enumerate(zip(measured, expected)):
        if abs(actual - reference) > max(abs(reference) * 0.02, 0.00005):
            raise RuntimeError("Imported bounds differ by >2%: " + mesh.get_name() + " axis " + str(index)
                               + " expected=" + str(reference) + " measured=" + str(actual))
    slots = []
    for slot in mesh.get_editor_property("static_materials"):
        name = str(slot.material_slot_name)
        material = slot.material_interface
        if name not in spec["meta"]["materials"] or material is None or material.get_name() != name:
            raise RuntimeError("Imported material slot mismatch: " + mesh.get_name() + ":" + name)
        slots.append(name)
    if set(slots) != set(spec["meta"]["materials"]) or len(slots) != len(spec["meta"]["materials"]):
        raise RuntimeError("Imported slot count/labels differ: " + mesh.get_name())
    return {"asset_path": mesh.get_path_name(), "dimensions_m": measured, "material_slots": slots}


def _import(palette, specs):
    unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    mats = _materials(palette)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    library = unreal.EditorAssetLibrary
    mesh_tools = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    tasks = []
    for name, spec in specs.items():
        task = unreal.AssetImportTask()
        task.filename = str(spec["source"])
        task.destination_path = spec["destination"]
        task.destination_name = name
        task.automated = True
        task.save = True
        task.replace_existing = True
        task.replace_existing_settings = True
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
        data.force_front_x_axis = False
        data.import_uniform_scale = 1.0
        data.import_translation = unreal.Vector(0.0, 0.0, 0.0)
        data.import_rotation = unreal.Rotator(0.0, 0.0, 0.0)
        data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        # FBX was exported with LINEAR vertex colours; legacy import copies these
        # values directly (8-bit quantisation) without a second sRGB conversion.
        data.vertex_color_import_option = unreal.VertexColorImportOption.REPLACE
        task.options = options
        tasks.append(task)
    asset_tools.import_asset_tasks(tasks)
    result = {}
    for name, spec in specs.items():
        mesh = library.load_asset(spec["destination"] + "/" + name)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("Static mesh import failed: " + name)
        for index, slot in enumerate(mesh.get_editor_property("static_materials")):
            key = str(slot.material_slot_name)
            if key not in spec["meta"]["materials"]:
                raise RuntimeError("Unrecognised imported slot: " + name + ":" + key)
            mesh.set_material(index, mats[key])
        mesh_tools.remove_collisions(mesh)
        library.set_metadata_tag(mesh, "AstraShorelineSource", spec["meta"]["file"])
        library.set_metadata_tag(mesh, "AstraShorelineManifest", spec["manifest"])
        library.set_metadata_tag(mesh, "AstraShorelineSHA256", spec["sha256"])
        _measure_mesh(mesh, spec)
        library.save_loaded_asset(mesh)
        result[name] = mesh
    return result


def import_assets() -> dict[str, unreal.StaticMesh]:
    """Import kit assets and site assets when a site manifest is present."""
    _, _, _, palette, specs = _read_manifests()
    return _import(palette, specs)


def _actor_record(actor):
    location = actor.get_actor_location()
    rotation = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    components = []
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        components.append({"name": component.get_name(), "mesh": mesh.get_path_name() if mesh else None,
                           "visible": bool(component.get_editor_property("visible")),
                           "hidden_in_game": bool(component.get_editor_property("hidden_in_game")),
                           "collision_profile_name": str(component.get_collision_profile_name()),
                           "collision_enabled": str(component.get_collision_enabled())})
    return {"name": actor.get_actor_label(), "object_path": actor.get_path_name(),
            "ue_location_cm": [location.x, location.y, location.z],
            "ue_rotation_deg": {"pitch": rotation.pitch, "yaw": rotation.yaw, "roll": rotation.roll},
            "scale": [scale.x, scale.y, scale.z],
            "hidden_in_game": bool(actor.get_editor_property("hidden")),
            "hidden_in_editor": bool(actor.is_temporarily_hidden_in_editor()),
            "collision_enabled": bool(actor.get_actor_enable_collision()), "components": components}


def _snapshots(project, world_path, labels, actor_index):
    """Immutable per-actor originals; later applications cannot overwrite them."""
    map_key = hashlib.sha256(world_path.encode("utf-8")).hexdigest()[:12]
    directory = project / "Saved" / "Shoreline" / ("original_actor_states_" + map_key)
    directory.mkdir(parents=True, exist_ok=True)
    for label in sorted(set(labels)):
        digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]
        path = directory / (digest + ".json")
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8"))
            if previous["map"] != world_path or previous["label"] != label:
                raise RuntimeError("Snapshot identity mismatch: " + str(path))
            continue
        actor = actor_index.get(label)
        payload = {"map": world_path, "label": label, "existed": actor is not None,
                   "state": _actor_record(actor) if actor is not None else None}
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
    return directory


def _validate_site(site, specs):
    objects = site.get("objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError("shoreline_site.json must define nonempty objects")
    names = set()
    for obj in objects:
        name = obj["name"]
        if not name.startswith(ACTOR_PREFIX) or not re.fullmatch(r"[A-Za-z0-9_]+", name) or name in names:
            raise ValueError("Unsafe or duplicate shoreline actor name: " + name)
        names.add(name)
        if obj["asset"] not in specs:
            raise ValueError("Unknown site asset: " + obj["asset"])
        _vec(obj["ue_location_cm"], name + ".ue_location_cm")
        _vec(obj["scale"], name + ".scale", positive=True)
        rotation = obj["ue_rotation_deg"]
        _vec([rotation[key] for key in ("pitch", "yaw", "roll")], name + ".rotation")
    hidden = site.get("hide_existing_actor_names", [])
    if not isinstance(hidden, list) or any(not isinstance(name, str) or not name for name in hidden):
        raise ValueError("hide_existing_actor_names must be a list of actor labels")
    if names.intersection(hidden):
        raise ValueError("The site cannot both show and hide the same actor")
    camera = site["review_camera"]
    _vec(camera["look_ue_cm"], "review_camera.look_ue_cm")
    if camera["width_cm"] <= 0 or camera.get("arm_cm", 2700.0) <= 0:
        raise ValueError("Review camera width and arm must be positive")
    _vec([camera.get("pitch_deg", -58.0), camera.get("yaw_deg", 0.0), 0.0], "review_camera.rotation")
    return objects, hidden, camera


def apply_site(save=True) -> dict:
    """Apply only manifest-owned meshes/actors; preserve hidden source actors."""
    project, _, site, palette, specs = _read_manifests(require_site=True)
    objects, hidden_names, camera_spec = _validate_site(site, specs)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or not world.get_path_name().startswith("/Game/Astra/Maps/"):
        raise RuntimeError("Load the intended existing /Game/Astra/Maps/ woodland map before applying the shoreline")
    actors = list(subsystem.get_all_level_actors())
    if not any(isinstance(actor, unreal.StaticMeshActor) and not actor.get_actor_label().startswith(ACTOR_PREFIX) for actor in actors):
        raise RuntimeError("Refusing to apply shoreline to an empty editor level")
    actor_index = {}
    controlled = {obj["name"] for obj in objects} | set(hidden_names) | {"Camera_Shoreline"}
    controlled |= {name + "_TrunkCollision" for name in hidden_names}
    for actor in actors:
        label = actor.get_actor_label()
        if label in controlled and label in actor_index:
            raise RuntimeError("Ambiguous duplicate actor label: " + label)
        actor_index[label] = actor
    missing_hidden = [name for name in hidden_names if name not in actor_index]
    if missing_hidden:
        raise RuntimeError("Source actors to hide are missing: " + ", ".join(missing_hidden))
    hidden = list(hidden_names)
    hidden += [name + "_TrunkCollision" for name in hidden_names if name + "_TrunkCollision" in actor_index]
    for obj in objects:
        actor = actor_index.get(obj["name"])
        if actor is not None and not isinstance(actor, unreal.StaticMeshActor):
            raise TypeError("Site label is occupied by a non-mesh actor: " + obj["name"])
    camera = actor_index.get("Camera_Shoreline")
    if camera is not None and not isinstance(camera, unreal.CameraActor):
        raise TypeError("Camera_Shoreline label is occupied by a non-camera actor")
    backup = _snapshots(project, world.get_path_name(), controlled, actor_index)
    meshes = _import(palette, specs)
    for name in hidden:
        actor = actor_index[name]
        actor.set_actor_hidden_in_game(True)
        actor.set_is_temporarily_hidden_in_editor(True)
        actor.set_actor_enable_collision(False)
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            component.set_visibility(False)
            component.set_hidden_in_game(True)
            component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    placed = []
    for obj in objects:
        actor = actor_index.get(obj["name"])
        rotation = unreal.Rotator(**obj["ue_rotation_deg"])
        location = unreal.Vector(*obj["ue_location_cm"])
        if actor is None:
            actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
            if actor is None:
                raise RuntimeError("Failed to spawn: " + obj["name"])
            actor.set_actor_label(obj["name"])
        component = actor.static_mesh_component
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_static_mesh(meshes[obj["asset"]])
        actor.set_actor_location(location, False, False)
        actor.set_actor_rotation(rotation, False)
        actor.set_actor_scale3d(unreal.Vector(*obj["scale"]))
        actor.set_folder_path("Shoreline/Site")
        actor.set_actor_hidden_in_game(False)
        actor.set_is_temporarily_hidden_in_editor(False)
        actor.set_actor_enable_collision(False)
        component.set_visibility(True)
        component.set_hidden_in_game(False)
        # Persist the visual-only policy in the profile as well as the transient
        # collision mode; BlockAll can otherwise restore collision after reload.
        component.set_collision_profile_name("NoCollision")
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        component.set_mobility(unreal.ComponentMobility.STATIC)
        placed.append(actor)
    pitch = float(camera_spec.get("pitch_deg", -58.0))
    yaw = float(camera_spec.get("yaw_deg", 0.0))
    arm = float(camera_spec.get("arm_cm", 2700.0))
    look = camera_spec["look_ue_cm"]
    p, y = math.radians(pitch), math.radians(yaw)
    camera_location = unreal.Vector(look[0] - arm * math.cos(p) * math.cos(y),
                                    look[1] - arm * math.cos(p) * math.sin(y), look[2] - arm * math.sin(p))
    camera_rotation = unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0)
    if camera is None:
        camera = subsystem.spawn_actor_from_class(unreal.CameraActor, camera_location, camera_rotation)
        if camera is None:
            raise RuntimeError("Failed to spawn Camera_Shoreline")
        camera.set_actor_label("Camera_Shoreline")
    camera.set_actor_location(camera_location, False, False)
    camera.set_actor_rotation(camera_rotation, False)
    camera.set_folder_path("ReviewCameras")
    camera.camera_component.set_editor_property("projection_mode", unreal.CameraProjectionMode.ORTHOGRAPHIC)
    camera.camera_component.set_editor_property("ortho_width", float(camera_spec["width_cm"]))
    camera.camera_component.set_editor_property("constrain_aspect_ratio", False)
    saved = bool(unreal.EditorLevelLibrary.save_current_level()) if save else False
    if save and not saved:
        raise RuntimeError("Shoreline applied but saving the current level failed")
    measured_actors = [_actor_record(actor) for actor in placed]
    for actor in placed:
        component = actor.static_mesh_component
        if (actor.get_actor_enable_collision()
                or str(component.get_collision_profile_name()) != "NoCollision"
                or component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION):
            raise RuntimeError("Visual shoreline collision policy was not applied: " + actor.get_actor_label())
    measured_hidden = [_actor_record(actor_index[name]) for name in hidden]
    actual_names = [actor.get_actor_label() for actor in subsystem.get_all_level_actors() if actor.get_actor_label().startswith(ACTOR_PREFIX)]
    report = {"status": "success", "map": world.get_path_name(), "saved": saved,
              "original_states_directory": str(backup), "imported_mesh_count": len(meshes),
              "meshes": {name: _measure_mesh(mesh, specs[name]) for name, mesh in meshes.items()},
              "placed_actor_count": len(measured_actors), "actors": measured_actors,
              "visual_actor_collision_policy_verified": True,
              "all_shoreline_actor_count": len(actual_names), "all_shoreline_actor_labels": sorted(actual_names),
              "hidden_source_actor_count": len(measured_hidden), "hidden_source_actors": measured_hidden,
              "review_camera": _actor_record(camera),
              "review_camera_ortho_width_cm": float(camera.camera_component.get_editor_property("ortho_width"))}
    _finite(report, "measured_report")
    output = project / "Saved" / "Shoreline" / "site_import_result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(apply_site(save=True), ensure_ascii=False, indent=2, allow_nan=False))
