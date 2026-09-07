"""Start the local status bridge whenever this project opens in the editor."""
import runpy
from pathlib import Path
import unreal

bridge = Path(unreal.Paths.project_dir()).resolve() / 'Scripts' / 'editor_status.py'
if bridge.is_file():
    try:
        runpy.run_path(str(bridge), run_name='astra_editor_status')
    except Exception as error:
        unreal.log_warning('Astra editor status bridge: ' + str(error))
