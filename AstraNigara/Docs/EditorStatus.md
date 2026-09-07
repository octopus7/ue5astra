# Editor status and viewport captures

The project-local Python bridge writes `Saved/EditorBridge/status.json` every two seconds while the editor's Slate tick runs. It reports the editor PID/session, loaded editor and game maps, PIE state, actor counts, selected actors, viewport camera, and Niagara components with asset paths, activation and visibility. A fresh heartbeat confirms the editor is processing callbacks; it does not prove that every Niagara particle rendered correctly. The screenshot provides visual evidence.

During PIE, Unreal's editor-only map, actor and selection queries are skipped to avoid native log errors. `editor_queries_skipped_during_pie` is `true`, `editor_map` and `editor_actor_count` are `null`, and `selected_actors` is empty. Inspect `game_map`, `game_actor_count` and Niagara entries with `world: "game"` for the running simulation. The game data uses UE 5.7's `UnrealEditorSubsystem.get_game_world()` and `GameplayStatics.get_all_actors_of_class()`.

## Start the bridge

The project requires the PythonScriptPlugin and EditorScriptingUtilities plugins, already enabled in its `.uproject`. At the end of an editor build/bootstrap Python script, run:

```python
import pathlib
import runpy
import unreal
runpy.run_path(str(pathlib.Path(unreal.Paths.project_dir()).resolve() / "Scripts" / "editor_status.py"))
```

The included `Content/Python/init_unreal.py` already starts the bridge automatically with the project. Re-running the bridge unregisters the old callback before registering the replacement. The bridge itself does not install startup settings or a background service.

For an explicitly requested visible interactive editor launch:

```powershell
& 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' `
  'D:\github\ue5astra\AstraNigara\AstraNigara.uproject' `
  '-AstraKeepEditorOpen' `
  '-ExecutePythonScript=D:\github\ue5astra\AstraNigara\Scripts\editor_status.py'
```

The bridge enables `EditorPythonScripting.set_keep_python_script_alive(True)` only when a `-ExecutePythonScript` launch also explicitly includes `-AstraKeepEditorOpen`. `open_showcase.ps1 -RebuildAssets` supplies this flag so its interactive editor remains open after the build. Normal project startup and batch build/validation scripts do not change Python keep-alive behavior. Use a rendered editor for screenshots; `-NullRHI` cannot capture them. The bridge requires an interactive editor tick, so it is not a persistent monitor when run as a commandlet. To stop the callback from Unreal Python without closing the editor:

```python
unreal._astra_editor_status_bridge.stop()
```

## Check or capture

Run from the repository root:

```powershell
.\AstraNigara\Scripts\check_editor.ps1
.\AstraNigara\Scripts\check_editor.ps1 -Refresh -AsJson -LogTail 0
.\AstraNigara\Scripts\check_editor.ps1 -Screenshot -WaitSeconds 50
.\AstraNigara\Scripts\check_editor.ps1 -Screenshot -NiagaraAgeSeconds 0.15 -WaitSeconds 50
.\AstraNigara\Scripts\check_editor.ps1 -RebuildAssets -WaitSeconds 60
.\AstraNigara\Scripts\check_editor.ps1 -CloseEditor -WaitSeconds 10
```

`-Screenshot` asks Unreal's own renderer for a 1280×720 PNG of the active level viewport and returns its absolute path. It does not use Windows desktop capture APIs. `-Width` and `-Height` change resolution, capped at 3840×2160. Capture temporarily uses Game View and UE restores it on completion. The viewport must be available and rendering; compiling shaders, loading maps, modal dialogs or a minimized/throttled editor can delay completion. Captures contain the viewport, not editor panels. Live effect motion requires PIE/Simulate or the effect's editor preview to be active.

While a screenshot is pending, the bridge temporarily disables `EditorPerformanceSettings.bThrottleCPUWhenNotForeground` in memory so UE can render its viewport in the background. It loads the native default object at `/Script/UnrealEd.Default__EditorPerformanceSettings`, which also works when the class is not exported as a Python module attribute. It uses `PropertyAccessChangeNotifyMode.NEVER`, never saves preferences/config, and restores the previous value after completion, failure, timeout or bridge stop. `background_throttle_temporarily_disabled` reports this temporary override. Viewport realtime defaults are not changed by this capture operation. An editor whose windows are all hidden or minimized can still be throttled separately by Unreal.

For a short burst, `-NiagaraAgeSeconds 0.15` resets the current editor world's Niagara components, enables solo simulation, switches them to Desired Age, and manually advances them to 0.15 seconds before capture. The accepted range is 0–3 seconds. Add `-NiagaraActorLabel 'Exact actor label'` to select one actor. This option requires PIE to be stopped and viewport realtime enabled. The response records the requested simulation age and affected components; it does not claim a measured GPU particle age. After capture or timeout, the bridge restores the components' previous age mode, desired age, solo setting and activation state. If an originally active one-shot completed during capture, it is reactivated from the beginning. Their simulation has been restarted, so this is intended for the showcase preview, not preserving a live simulation timeline. Without this option the bridge captures the current viewport state without changing Niagara components.

The checker reports:

| State | Meaning |
| --- | --- |
| `LIVE` | A matching Unreal process exists and heartbeat age is at most 15 seconds. |
| `STALE` | The process exists but the bridge has not updated recently; check the log and editor. |
| `EDITOR_EXITED` | The heartbeat's writer PID is no longer an Unreal editor process. |
| `NO_HEARTBEAT` | The bridge has not written a status file for this checkout. |
| `INVALID_STATUS` | The status file cannot be parsed. |
| `CLOCK_MISMATCH` | The saved timestamp is more than five seconds in the future. |

The output includes Unreal process window titles, project command-line matches, recent log lines and recent errors. The bridge records its own `-abslog` path (or the project's default `Saved/Logs/AstraNigara.log`), and the checker prefers that path over unrelated editor logs. Launch with `-abslog=D:/github/ue5astra/AstraNigara/Saved/Logs/AstraNigara_Bridge.log` to distinguish this editor's log explicitly. Process `responding` is only an OS observation; heartbeat freshness is the stronger editor-specific signal. Exit code `0` means a live heartbeat and completed request (if any), `2` means unavailable/stale status, and `3` means the request failed or timed out. A checker timeout leaves the response path available for late completion.

`-RebuildAssets` explicitly reruns the fixed project script `Scripts/build_small_destruction.py` inside the running editor. It updates the generated small-destruction materials, Niagara systems and showcase map according to that script, so save unrelated edits before invoking it. PIE must be stopped and no screenshot may be pending. The bridge reports `busy_action` while rebuilding and writes full Python failures to the editor log. Since the build runs on the editor thread, heartbeat updates pause during the build; a checker timeout does not cancel it. Only one request switch (`-Screenshot`, `-Refresh`, `-RebuildAssets` or `-CloseEditor`) can be supplied per checker invocation.

`-CloseEditor` requests normal Unreal editor shutdown for this project's live bridge. It refuses to close during PIE, capture, rebuild or pending temporary-settings restoration. It queries both dirty map and content packages, including edited plugin/engine packages loaded in this editor. Any unsaved changes produce an error response with `dirty_packages`; nothing is automatically saved or discarded. With no dirty packages, the bridge persists a `complete` response with `action: "close_editor"` and `closing: true`, then calls `unreal.SystemLibrary.quit_editor()` on the next Slate tick. It rechecks the preconditions immediately before shutdown and can replace the response with an error if new changes appeared. No process-kill API is used.

For `-CloseEditor`, exit code `0` means the shutdown request was accepted, regardless of whether the process is still finishing shutdown or the heartbeat has ended. It does not claim the process has already exited. The checker waits only for the bounded response; the saved response file can report a subsequent refusal if state changed between ticks.

## Local request protocol

Requests live in `Saved/EditorBridge/requests/<unique-id>.json`. Write a `.tmp` file first and rename it to `.json` so the editor never reads partial content. Include the current `session_id` from `status.json` to avoid sending old requests to a restarted editor:

```json
{"action":"screenshot","session_id":"copy-from-status","width":1280,"height":720}
```

Optional screenshot fields are `niagara_age_seconds` and `niagara_actor_label` as described above. Omit `-AstraKeepEditorOpen` for batch scripts launched with `-ExecutePythonScript` so Unreal can exit normally when the script finishes.

Only `status`, `screenshot`, `rebuild_small_destruction` and `close_editor` actions are supported. The rebuild action accepts no script path or code: it executes only the fixed project build script. Responses are written atomically to `responses/<unique-id>.json`, with `pending`, `complete` or `error` state. PNG files live in `screenshots/`. Requests never execute arbitrary code or console commands, and screenshot names cannot select an output path outside this project folder. The bridge opens no network port. Generated state, requests, responses and screenshots belong under ignored `Saved/`, not source control.

Implementation is based on the installed UE 5.7 headers/source: `UnrealEditorSubsystem.h/.cpp`, `LevelEditorSubsystem.h`, `EditorActorSubsystem.h/.cpp`, `EditorScriptingHelpers.cpp`, `GameplayStatics.cpp`, `EditorPerformanceSettings.h/.cpp`, `EditorEngine.cpp`, `PropertyAccessUtil.h`, `FileHelpers.h/.cpp`, `KismetSystemLibrary.h/.cpp`, PythonScriptPlugin's `PySlate.cpp`, `PyWrapperObject.cpp` and `EditorPythonExecuter.cpp`, and FunctionalTesting's `AutomationBlueprintFunctionLibrary.h/.cpp`.
