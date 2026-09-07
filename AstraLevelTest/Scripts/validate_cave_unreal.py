"""Read the saved cave and verify imported source transforms, terrain and real lights."""
import unreal,json,math
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
def verify():
    data=json.loads((ROOT/'ArtSource/Layout/CrystalCave/cave_layout.json').read_text(encoding='utf-8'))
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    names={a.get_actor_label():a for a in actors};checks=[]
    def check(name,ok,detail):checks.append(dict(name=name,passed=bool(ok),detail=detail))
    mismatches=[]
    for o in data['objects']:
        a=names.get(o['name'])
        if not a:mismatches.append(o['name']+' missing');continue
        p=a.get_actor_location();s=a.get_actor_scale3d();r=a.get_actor_rotation()
        if max(abs(x-y) for x,y in zip([p.x,p.y,p.z],o['ue_location_cm']))>.1:mismatches.append(o['name']+' position')
        if max(abs(x-y) for x,y in zip([s.x,s.y,s.z],o['scale']))>.0001:mismatches.append(o['name']+' scale')
        if abs((r.yaw-o['ue_rotation_deg']['yaw']+180)%360-180)>.01:mismatches.append(o['name']+' yaw')
        if a.static_mesh_component.static_mesh.get_name()!=o['asset']:mismatches.append(o['name']+' mesh')
    check('source_mesh_transforms',not mismatches,dict(count=len(data['objects']),mismatches=mismatches))
    landscapes=[a for a in actors if isinstance(a,unreal.Landscape)]
    check('real_landscape',len(landscapes)==1,len(landscapes))
    if landscapes:
        land=landscapes[0];components=land.get_components_by_class(unreal.LandscapeComponent)
        check('landscape_two_components',len(components)==2,len(components))
        p=land.get_actor_location();s=land.get_actor_scale3d()
        check('landscape_extent_50x30m',abs(p.x+1500)<.1 and abs(p.y+2500)<.1 and abs(s.x*126-3000)<.1 and abs(s.y*63-5000)<.1,dict(origin=[p.x,p.y,p.z],size_cm=[s.x*126,s.y*63]))
    lights=[]
    for source in data['lights']:
        a=names.get(source['name']);ok=isinstance(a,unreal.PointLight)
        if ok:
            c=a.light_component;actual=c.get_editor_property('intensity')
            ok=abs(actual-source['intensity']*.32)<.1 and c.get_editor_property('attenuation_radius')==source['radius_cm']
            lights.append(dict(name=source['name'],lumens=actual,radius_cm=c.get_editor_property('attenuation_radius'),cast_shadows=c.get_editor_property('cast_shadows')))
        check(source['name'],ok,lights[-1] if ok else 'Missing or incorrect point light')
    for box in data.get('collision_boxes',[]):
        a=names.get(box['name']);check(box['name'],a is not None and a.get_actor_enable_collision(),box)
    check('two_fork_islands',sum(1 for o in data['objects'] if o['group']=='Architecture/ForkIslands')==2,'First cyan island and second violet island')
    check('cutaway_foreground',all(o['asset']=='SM_CC_RockWallLow' for o in data['objects'] if o['group']=='Architecture/Perimeter' and o['ue_location_cm'][0]<0),'Near camera perimeter uses low walls; no ceiling over corridors')
    result=dict(passed=all(c['passed'] for c in checks),checks=checks,actor_count=len(actors),mesh_instances=len(data['objects']),point_lights=lights,map='/Game/Astra/Maps/L_AstraCrystalCave')
    (ROOT/'ArtSource/Previews/CrystalCave/UE_CaveSavedValidation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert result['passed'],[c for c in checks if not c['passed']]
    unreal.log('CAVE SAVED VALIDATION PASS')
    return result
if __name__=='__main__':
    unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraCrystalCave');verify()
