"""Repair only the owned idle clip; the full importer repeats this correction."""
import sys
from pathlib import Path
import unreal
root=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(root/'Scripts'))
import import_starpond_elephant as elephant
mesh=elephant.EAL.load_asset(elephant.DEST+'/'+elephant.MESH_NAME)
animation=elephant.EAL.load_asset(elephant.DEST+'/'+elephant.ANIM_NAME)
elephant.align_stationary_root(mesh,animation)
elephant.validate_animation(animation)
assert elephant.EAL.save_loaded_asset(animation)
unreal.log('STARPOND_ROOT_REPAIR_PASSED')
