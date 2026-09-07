"""Apply cave lighting and internal island collision after real-engine review."""
import unreal,json
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
DATA=json.loads((ROOT/'ArtSource/Layout/CrystalCave/cave_layout.json').read_text(encoding='utf-8'))
assert unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraCrystalCave')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
lights={a.get_actor_label():a for a in actors if isinstance(a,unreal.PointLight)}
for l in DATA['lights']:
    a=lights[l['name']];a.light_component.set_intensity(l['intensity']*.32)
for a in actors:
    if a.get_actor_label()=='CC_DimSoftFill':
        a.light_component.set_intensity(1.25);a.light_component.set_cast_shadows(False)
es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
by_name={a.get_actor_label():a for a in actors}
for obj in DATA['objects']:
    if obj['asset']=='SM_CC_CrystalHeart':by_name[obj['name']].set_actor_rotation(unreal.Rotator(yaw=90),False)
for box in DATA.get('collision_boxes',[]):
    a=by_name.get(box['name']) or es.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*box['ue_location_cm']))
    a.set_actor_label(box['name']);a.set_folder_path('CrystalCave/Collision');a.tags=[unreal.Name(box['tag'])]
    a.set_actor_rotation(unreal.Rotator(yaw=box.get('ue_yaw',0)),False)
    c=a.static_mesh_component;c.set_static_mesh(unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube'))
    a.set_actor_scale3d(unreal.Vector(*[v/100 for v in box['dimensions_cm']]))
    a.set_actor_hidden_in_game(True);c.set_visibility(False);c.set_collision_profile_name('BlockAll')
assert unreal.EditorLevelLibrary.save_current_level()
unreal.log('CAVE RELIGHT SAVED: 18 point lights x0.32; dim diffuse fill1.25, no fill shadow')
import sys
sys.path.insert(0,str(ROOT/'Scripts'))
from validate_cave_unreal import verify
verify()
