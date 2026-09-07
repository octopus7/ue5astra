"""Project-local editor heartbeat and viewport screenshot request bridge (UE 5.7).

Run through init_unreal.py, runpy.run_path(), or -ExecutePythonScript. No sockets,
desktop capture, or arbitrary command execution. Asset rebuilds require an
explicit request for the one project-owned small-destruction build script.
"""
import datetime
import json
import os
from pathlib import Path
import re
import runpy
import time
import traceback
import uuid

import unreal


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(".tmp.{}".format(os.getpid()))
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def object_path(value):
    return value.get_path_name() if value else None


def xyz(value):
    return {axis: float(getattr(value, axis)) for axis in ("x", "y", "z")}


class EditorStatusBridge:
    INTERVAL = 2.0
    SCREENSHOT_TIMEOUT = 45.0

    def __init__(self):
        self.project = Path(unreal.Paths.project_dir()).resolve()
        command_line = unreal.SystemLibrary.get_command_line()
        log_argument = re.search(r'(?:^|\s)"-abslog=([^\"]+)"', command_line, re.IGNORECASE)
        if not log_argument:
            log_argument = re.search(r'(?:^|\s)-abslog=(?:"([^\"]+)"|(\S+))', command_line, re.IGNORECASE)
        self.log_path = Path(next(value for value in log_argument.groups() if value)).resolve() if log_argument else self.project / "Saved" / "Logs" / "AstraNigara.log"
        self.log_path_source = "command_line_abslog" if log_argument else "project_default"
        self.folder = self.project / "Saved" / "EditorBridge"
        for directory in (self.folder, self.folder / "requests", self.folder / "responses", self.folder / "screenshots"):
            directory.mkdir(parents=True, exist_ok=True)
        self.session_id = str(uuid.uuid4())
        self.started_utc = utc_now()
        self.sequence = 0
        self.next_tick = 0.0
        self.pending_screenshot = None
        self.last_screenshot = None
        self.last_request = None
        self.handle = None
        self.last_tick_error = None
        self.in_tick = False
        self.busy_action = None
        self.capture_performance_state = None
        self.pending_close = None

    def stop(self):
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if self.pending_screenshot:
            self.restore_niagara(self.pending_screenshot.get("restore", []))
            self.pending_screenshot = None
        for error in self.restore_background_rendering():
            unreal.log_error("ASTRA_EDITOR_BRIDGE_RESTORE_ERROR: " + error)

    def start(self):
        # Opt in only for interactive scripted launches. Automatic startup must
        # not prevent command-line build/validation scripts from exiting.
        command_line = unreal.SystemLibrary.get_command_line()
        keep_open = re.search(r'(?:^|\s)"?-AstraKeepEditorOpen"?(?=\s|$)', command_line, re.IGNORECASE)
        if keep_open and "-executepythonscript" in command_line.lower():
            unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.publish()
        unreal.log("ASTRA_EDITOR_BRIDGE_STARTED: {}".format(self.folder))

    def snapshot(self):
        errors = []

        def read(name, function, default=None):
            try:
                return function()
            except Exception as exc:
                errors.append("{}: {}".format(name, exc))
                return default

        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        actors_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        in_pie = read("pie", levels.is_in_play_in_editor)
        # These editor-only APIs log native errors during PIE rather than raising
        # Python exceptions. Query the game world instead and mark omitted fields.
        editor_world = None if in_pie else read("editor_world", editor.get_editor_world)
        editor_actors = [] if in_pie else read("editor_actors", actors_subsystem.get_all_level_actors, [])
        selected = [] if in_pie else read("selected_actors", actors_subsystem.get_selected_level_actors, [])
        game_world = read("game_world", editor.get_game_world)
        game_actors = read("game_actors", lambda: unreal.GameplayStatics.get_all_actors_of_class(game_world, unreal.Actor), []) if game_world else []
        camera_info = read("viewport_camera", editor.get_level_viewport_camera_info)
        camera = None
        if camera_info:
            location, rotation = camera_info
            camera = {"location_cm": xyz(location), "rotation_degrees": {
                "pitch": float(rotation.pitch), "yaw": float(rotation.yaw), "roll": float(rotation.roll)}}

        niagara = []
        for world_kind, actors in (("editor", editor_actors), ("game", game_actors)):
            for actor in actors:
                components = read("components", lambda: actor.get_components_by_class(unreal.NiagaraComponent), [])
                for component in components:
                    niagara.append({
                        "world": world_kind,
                        "actor": object_path(actor),
                        "label": read("actor_label", actor.get_actor_label, actor.get_name()),
                        "location_cm": read("location", lambda: xyz(actor.get_actor_location())),
                        "component": object_path(component),
                        "asset": read("niagara_asset", lambda: object_path(component.get_asset())),
                        "active": read("niagara_active", component.is_active),
                        "auto_activate": read("niagara_auto_activate", lambda: bool(component.get_editor_property("auto_activate"))),
                        "visible": read("niagara_visible", component.is_visible),
                    })
        return {
            "schema_version": 1,
            "timestamp_utc": utc_now(),
            "pid": os.getpid(),
            "session_id": self.session_id,
            "started_utc": self.started_utc,
            "sequence": self.sequence,
            "heartbeat_interval_seconds": self.INTERVAL,
            "project_directory": str(self.project),
            "log_path": str(self.log_path),
            "log_path_source": self.log_path_source,
            "engine_version": unreal.SystemLibrary.get_engine_version(),
            "editor_map": object_path(editor_world),
            "game_map": object_path(game_world),
            "pie": in_pie,
            "editor_queries_skipped_during_pie": bool(in_pie),
            "editor_actor_count": None if in_pie else len(editor_actors),
            "game_actor_count": len(game_actors),
            "selected_actors": [object_path(actor) for actor in selected],
            "viewport_camera": camera,
            "niagara": niagara,
            "last_request": self.last_request,
            "last_screenshot": self.last_screenshot,
            "screenshot_pending": self.pending_screenshot["id"] if self.pending_screenshot else None,
            "busy_action": self.busy_action,
            "close_pending": self.pending_close is not None,
            "background_throttle_temporarily_disabled": self.capture_performance_state is not None,
            "errors": errors,
        }

    def publish(self):
        self.sequence += 1
        write_json(self.folder / "status.json", self.snapshot())

    def respond(self, request_id, state, **extra):
        response = {"id": request_id, "state": state, "timestamp_utc": utc_now(),
                    "pid": os.getpid(), "session_id": self.session_id, **extra}
        write_json(self.folder / "responses" / (request_id + ".json"), response)
        self.last_request = response
        return response

    def poll_screenshot(self):
        pending = self.pending_screenshot
        if not pending:
            return
        try:
            path = pending["path"]
            if pending["task"].is_task_done() and path.is_file() and path.stat().st_size > 0:
                state, extra = "complete", {"path": str(path), "bytes": path.stat().st_size}
            elif time.monotonic() - pending["started"] > self.SCREENSHOT_TIMEOUT:
                state, extra = "error", {"error": "Viewport capture did not complete within 45 seconds. Check the editor viewport and log."}
            else:
                return
        except Exception as exc:
            state, extra = "error", {"error": "Viewport capture failed: " + str(exc)}
        restore_errors = self.restore_niagara(pending["restore"]) + self.restore_background_rendering()
        self.pending_screenshot = None
        response = self.respond(pending["id"], state, action="screenshot", niagara_age_seconds=pending["age"],
                                niagara_components=pending["components"], restore_errors=restore_errors, **extra)
        if state == "complete":
            self.last_screenshot = response

    def prepare_background_rendering(self):
        if self.capture_performance_state is not None:
            raise RuntimeError("Previous screenshot performance setting has not been restored")
        # This native class is not exported as unreal.EditorPerformanceSettings
        # in all UE builds, but its CDO still exposes reflected editor properties.
        settings = unreal.load_object(None, "/Script/UnrealEd.Default__EditorPerformanceSettings")
        if settings is None:
            raise RuntimeError("Cannot load UnrealEd EditorPerformanceSettings default object")
        previous = bool(settings.get_editor_property("bThrottleCPUWhenNotForeground"))
        self.capture_performance_state = (settings, previous)
        # EditorEngine reads this CDO each tick. NEVER avoids settings-change
        # notifications; no SaveConfig, preference save, or viewport default edit.
        settings.set_editor_property("bThrottleCPUWhenNotForeground", False,
                                     notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)

    def restore_background_rendering(self):
        if self.capture_performance_state is None:
            return []
        settings, previous = self.capture_performance_state
        try:
            settings.set_editor_property("bThrottleCPUWhenNotForeground", previous,
                                         notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
            self.capture_performance_state = None
            return []
        except Exception as exc:
            # Retain the original value so the next tick or stop can retry.
            return ["Background throttle restore: " + str(exc)]

    @staticmethod
    def restore_niagara(states):
        errors = []
        for component, mode, age, active, solo in states:
            try:
                component.set_desired_age(age)
                component.set_age_update_mode(mode)
                component.set_force_solo(solo)
                if not active:
                    component.deactivate()
                elif not component.is_active():
                    # A one-shot may have completed during manual advancement.
                    component.activate(reset=True)
            except Exception as exc:
                errors.append(str(exc))
        return errors

    def prepare_niagara(self, request):
        if "niagara_age_seconds" not in request:
            return [], None
        age = float(request["niagara_age_seconds"])
        if not 0.0 <= age <= 3.0:
            raise ValueError("niagara_age_seconds must be within 0..3 seconds")
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if levels.is_in_play_in_editor():
            raise ValueError("Capture at a specific Niagara age requires stopping PIE first")
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        label = request.get("niagara_actor_label")
        states = []
        try:
            for actor in subsystem.get_all_level_actors():
                if label and actor.get_actor_label() != label:
                    continue
                for component in actor.get_components_by_class(unreal.NiagaraComponent):
                    states.append((component, component.get_age_update_mode(), component.get_desired_age(), component.is_active(), component.get_force_solo()))
                    component.set_force_solo(True)
                    component.set_age_update_mode(unreal.NiagaraAgeUpdateMode.DESIRED_AGE)
                    component.activate(reset=True)
                    if age > 0:
                        steps = max(1, round(age * 60))
                        component.advance_simulation(steps, age / steps)
                    component.set_desired_age(age)
            if not states:
                raise ValueError("No matching Niagara components in the current editor world")
        except Exception:
            self.restore_niagara(states)
            raise
        return states, age

    def check_close_preconditions(self):
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if levels.is_in_play_in_editor():
            raise ValueError("Stop PIE before closing the editor")
        if self.pending_screenshot or self.busy_action or self.capture_performance_state is not None:
            raise ValueError("Wait for the current capture, rebuild or settings restoration before closing")
        # These reflected UE APIs inspect loaded packages; no save/discard API is
        # called. Include plugin/engine packages too if edited in this editor.
        dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
        dirty.extend(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        return sorted({package.get_path_name() for package in dirty if package})

    def finish_close(self):
        request_id = self.pending_close
        self.pending_close = None
        try:
            # Recheck immediately before quitting in case a package changed
            # after the closing acknowledgement was persisted on the last tick.
            dirty = self.check_close_preconditions()
            if dirty:
                self.respond(request_id, "error", action="close_editor", closing=False,
                             error="Editor close refused because packages have unsaved changes", dirty_packages=dirty)
                self.publish()
                return
            self.busy_action = "close_editor"
            self.publish()
            # UE dispatches QUIT_EDITOR through its normal editor shutdown path.
            unreal.SystemLibrary.quit_editor()
            self.stop()
        except Exception as exc:
            self.busy_action = None
            self.respond(request_id, "error", action="close_editor", closing=False, error=str(exc))
            self.publish()
            unreal.log_error("ASTRA_EDITOR_BRIDGE_CLOSE_ERROR: " + str(exc))

    def process_requests(self):
        # Process a bounded batch; never execute Python/console text from requests.
        for path in sorted((self.folder / "requests").glob("*.json"))[:8]:
            request_id = path.stem
            if not request_id.replace("-", "").isalnum():
                continue
            try:
                if path.stat().st_size > 8192:
                    raise ValueError("Request is larger than 8 KiB")
                request = json.loads(path.read_text(encoding="utf-8-sig"))
                if request.get("session_id") != self.session_id:
                    raise ValueError("Request targets a different editor session; run the checker again")
                action = request.get("action", "status")
                if action == "status":
                    self.publish()
                    self.respond(request_id, "complete", action=action, status_path=str(self.folder / "status.json"))
                elif action == "close_editor":
                    dirty = self.check_close_preconditions()
                    if dirty:
                        self.respond(request_id, "error", action=action, closing=False,
                                     error="Editor close refused because packages have unsaved changes", dirty_packages=dirty)
                    else:
                        self.pending_close = request_id
                        try:
                            self.respond(request_id, "complete", action=action, closing=True, dirty_packages=[],
                                         message="Closing accepted; normal editor shutdown will be requested on the next Slate tick")
                            self.publish()
                        except Exception:
                            self.pending_close = None
                            raise
                        # Do not run another queued action after accepting close.
                        return
                elif action == "rebuild_small_destruction":
                    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
                    if levels.is_in_play_in_editor():
                        raise ValueError("Stop PIE before rebuilding the small-destruction assets")
                    if self.pending_screenshot or self.busy_action:
                        raise ValueError("Wait for the current capture or rebuild to finish")
                    # This exact local script is the sole mutable action. Request
                    # fields never select a script, path, Python or console text.
                    build_script = self.project / "Scripts" / "build_small_destruction.py"
                    if not build_script.is_file():
                        raise ValueError("Project small-destruction build script is missing")
                    self.busy_action = action
                    self.respond(request_id, "pending", action=action, script=str(build_script))
                    self.publish()
                    try:
                        runpy.run_path(str(build_script))
                    except Exception:
                        unreal.log_error("ASTRA_EDITOR_BRIDGE_REBUILD_ERROR:\n" + traceback.format_exc())
                        raise
                    finally:
                        self.busy_action = None
                    self.respond(request_id, "complete", action=action, script=str(build_script),
                                 report_path=str(self.project / "Saved" / "SmallDestruction" / "build_report.json"))
                elif action == "screenshot":
                    if self.pending_screenshot:
                        raise ValueError("Another screenshot is still pending")
                    if "-nullrhi" in unreal.SystemLibrary.get_command_line().lower():
                        raise ValueError("Screenshot requires a rendered editor; -NullRHI is active")
                    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
                    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
                    if not levels.get_viewport_config_keys() or not editor.get_level_viewport_camera_info():
                        raise ValueError("No level editor viewport is available")
                    width = max(64, min(3840, int(request.get("width", 1280))))
                    height = max(64, min(2160, int(request.get("height", 720))))
                    screenshot = self.folder / "screenshots" / (request_id + ".png")
                    restore = []
                    try:
                        self.prepare_background_rendering()
                        restore, age = self.prepare_niagara(request)
                        task = unreal.AutomationLibrary.take_high_res_screenshot(width, height, str(screenshot), delay=0.75 if age is not None else 0.2)
                        if not task or not task.is_valid_task():
                            raise RuntimeError("Unreal rejected the viewport screenshot request")
                        components = [object_path(state[0]) for state in restore]
                        self.pending_screenshot = {"id": request_id, "task": task, "path": screenshot, "started": time.monotonic(),
                                                   "restore": restore, "age": age, "components": components}
                        self.respond(request_id, "pending", action=action, path=str(screenshot), niagara_age_seconds=age, niagara_components=components)
                    except Exception:
                        self.pending_screenshot = None
                        self.restore_niagara(restore)
                        for error in self.restore_background_rendering():
                            unreal.log_error("ASTRA_EDITOR_BRIDGE_RESTORE_ERROR: " + error)
                        raise
                else:
                    raise ValueError("Supported actions are status, screenshot, rebuild_small_destruction and close_editor")
            except Exception as exc:
                self.respond(request_id, "error", error=str(exc))
                unreal.log_warning("ASTRA_EDITOR_BRIDGE_REQUEST_ERROR: {}".format(exc))
            finally:
                path.unlink(missing_ok=True)

    def tick(self, delta_seconds):
        now = time.monotonic()
        if self.in_tick:
            return
        if self.pending_close is not None:
            self.in_tick = True
            try:
                self.finish_close()
            finally:
                self.in_tick = False
            return
        if now < self.next_tick:
            return
        self.in_tick = True
        self.next_tick = now + self.INTERVAL
        try:
            if not self.pending_screenshot:
                for error in self.restore_background_rendering():
                    unreal.log_error("ASTRA_EDITOR_BRIDGE_RESTORE_ERROR: " + error)
            self.poll_screenshot()
            self.process_requests()
            self.publish()
            self.last_tick_error = None
        except Exception as exc:
            # Keep the callback alive so transient map loads can recover.
            message = str(exc)
            if message != self.last_tick_error:
                unreal.log_error("ASTRA_EDITOR_BRIDGE_TICK_ERROR: " + message)
                self.last_tick_error = message
        finally:
            self.in_tick = False


previous = getattr(unreal, "_astra_editor_status_bridge", None)
if previous is not None:
    previous.stop()
bridge = EditorStatusBridge()
unreal._astra_editor_status_bridge = bridge
bridge.start()
