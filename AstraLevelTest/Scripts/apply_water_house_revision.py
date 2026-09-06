"""Apply the verified terrain and water refinements in one editor session."""
import runpy
from pathlib import Path
scripts=Path(__file__).resolve().parent
runpy.run_path(str(scripts/'refresh_house_terrain.py'),run_name='__main__')
runpy.run_path(str(scripts/'refine_unreal_water.py'),run_name='__main__')
