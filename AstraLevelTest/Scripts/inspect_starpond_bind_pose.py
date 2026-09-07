"""Read actual mesh reference and animation transforms to diagnose skin binding."""
import json,math
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
DEST='/Game/Astra/Characters/StarPond/Guardian'
mesh=unreal.EditorAssetLibrary.load_asset(DEST+'/SK_SP_UnicornElephant')
anim=unreal.EditorAssetLibrary.load_asset(DEST+'/A_SP_UnicornElephant_Idle')
options=unreal.AnimPoseEvaluationOptions();options.optional_skeletal_mesh=mesh
pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,0.,options)
def row(t):
    return {'t':[t.translation.x,t.translation.y,t.translation.z],
        'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],
        's':[t.scale3d.x,t.scale3d.y,t.scale3d.z]}
data={}
for name in unreal.AnimPoseExtensions.get_bone_names(pose):
    a=row(unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.LOCAL))
    r=row(unreal.AnimPoseExtensions.get_ref_bone_pose(pose,name,unreal.AnimPoseSpaces.LOCAL))
    q=sum(x*y for x,y in zip(a['q'],r['q']))
    data[str(name)]={'animation_zero':a,'mesh_reference':r,'rotation_error_degrees':math.degrees(2*math.acos(min(1,abs(q))))}
(ROOT/'ArtSource/Previews/StarPondBindPose_Inspection.json').write_text(json.dumps(data,indent=2))
unreal.log('STAR_POND_BIND_POSES '+json.dumps({n:r['rotation_error_degrees'] for n,r in data.items()}))
