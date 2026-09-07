"""Apply review-camera refinements without regenerating geometry or foliage."""
import json,math,sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import import_rootbelltower_level as rb
path=ROOT/'ArtSource/Layout/rootbelltower_layout.json'
data=json.loads(path.read_text())
for item in data['review_cameras']:
    if item['name']=='RBArch':item['arm']=3000
    if item['name']=='RBCloister':item.update(look_cm=[-1300,1200,330],width=1800,pitch=-43,yaw=-90,arm=3000)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(rb.MAP)
before=rb.protected_content()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for item in data['review_cameras']:
    if item['name'] not in ('RBArch','RBCloister'):continue
    actor=next(a for a in actors if a.get_actor_label()=='Camera_'+item['name'])
    p,y=map(math.radians,(item['pitch'],item['yaw']));look=item['look_cm'];arm=item['arm']
    actor.set_actor_location(unreal.Vector(look[0]-arm*math.cos(p)*math.cos(y),look[1]-arm*math.cos(p)*math.sin(y),look[2]-arm*math.sin(p)),False,False)
    actor.set_actor_rotation(unreal.Rotator(pitch=item['pitch'],yaw=item['yaw'],roll=0),False)
    actor.camera_component.set_editor_property('ortho_width',item['width'])
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
assert all(rb.check_protected(before).values())
path.write_text(json.dumps(data,indent=2)+'\n')
report_path=ROOT/'ArtSource/Previews/UE_RootBelltowerImportValidation.json'
report=json.loads(report_path.read_text());report['layout_sha256']=rb.digest(path)
assert all(rb.check_protected(report['protected_asset_sha256']).values())
report['review_camera_refinement']=['RBArch','RBCloister']
report_path.write_text(json.dumps(report,indent=2)+'\n')
unreal.log('ROOT_BELLTOWER_REVIEW_CAMERAS_REFINED')
