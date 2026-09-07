"""Validate saved waterfall resources in the open UE editor, after Niagara Compile."""
import json,runpy
from pathlib import Path
import unreal
root=Path(unreal.Paths.project_dir()).resolve()
builder=runpy.run_path(str(root/'Scripts'/'build_waterfall.py'))
dest=builder['DEST']
report={'passed':False,'meshes':[],'emitters':[]}
(root/'Saved'/'waterfall_validation.json').write_text(json.dumps(report),encoding='utf-8')
manifest=json.loads((root/'ArtSource'/'Waterfall'/'waterfall_manifest.json').read_text())
sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
for entry in manifest['assets']:
    mesh=unreal.load_asset(dest+'/Meshes/'+entry['name'])
    assert isinstance(mesh,unreal.StaticMesh)
    assert sub.get_num_uv_channels(mesh,0)==1
    bounds=mesh.get_bounding_box()
    size=sorted(getattr(bounds.max,a)-getattr(bounds.min,a) for a in 'xyz')
    assert all(abs(a-b)<.2 for a,b in zip(size,sorted(entry['dimensions_cm'])))
    for index in range(len(mesh.get_editor_property('static_materials'))):
        assert mesh.get_material(index).get_path_name().startswith(dest+'/Materials/')
    report['meshes'].append({'name':entry['name'],'uv_channels':1,'source_triangles':entry['triangles']})
system=unreal.load_asset(dest+'/NS_AnimeWaterfall')
data=json.loads(unreal.AstraNiagaraLibrary.describe_system(system))
assert data['ready_to_run'] and data['valid'] and data['fixed_bounds_enabled']
assert {e['name'] for e in data['emitters']} in ({'Ripples','Splash','Mist','Foam'},{'Ripples','Splash','Upwash','Foam'})
for name,rate in [('Debris',3.2),('Flame',180),('Smoke',96),('Distortion',30)]:
    emitter=builder['emitter_objects'](system)[name]
    spawn=emitter.get_editor_property('SpawnInfos')[0]
    assert 'Type=Rate' in spawn.export_text()
    actual=spawn.get_editor_property('Rate')
    assert abs(actual.get_editor_property('Min')-rate)<.001 and abs(actual.get_editor_property('Max')-rate)<.001
    assert 'LoopBehavior=Infinite' in emitter.get_editor_property('EmitterState').export_text()
    report['emitters'].append({'name':name,'spawn_per_second':rate})
    modules={m.get_class().get_name().removeprefix('NiagaraStatelessModule_'):m for m in emitter.get_editor_property('Modules')}
    init=modules['InitializeParticle']
    positions=init.get_editor_property('InitialPositionDistribution').get_editor_property('Values')
    if name in ('Flame','Smoke'):
        assert len(positions)==2 and all(p.get_editor_property('x')==0 for p in positions),'Ring center must not be scattered twice'
        shape=modules['ShapeLocation']
        assert shape.get_editor_property('bModuleEnabled')
        assert shape.get_editor_property('RingRadius').get_editor_property('Min')==60
        assert abs(shape.get_editor_property('DiscCoverage').get_editor_property('Min')-.12)<.001
        assert shape.get_editor_property('RingUDistribution').get_editor_property('Min')==0
        assert abs(shape.get_editor_property('ShapeScale').get_editor_property('Min').get_editor_property('y')-.17)<.001
        velocity=modules['AddVelocity'].get_editor_property('LinearVelocityDistribution')
        assert abs(velocity.get_editor_property('Min').get_editor_property('x'))<=8
        assert velocity.get_editor_property('Min').get_editor_property('z')>=135
        assert modules['GravityForce'].get_editor_property('bModuleEnabled')
    else:
        assert len(positions)==2 and positions[1].get_editor_property('x')-positions[0].get_editor_property('x')>=80
    assert 'NonUniformRange' in init.get_editor_property('ColorDistribution').export_text()
    if name=='Debris':
        assert modules['InitialMeshOrientation'].get_editor_property('bModuleEnabled')
        orientation=modules['InitialMeshOrientation']
        rotation=orientation.get_editor_property('Rotation')
        assert rotation.get_editor_property('Min').get_editor_property('x')==rotation.get_editor_property('Max').get_editor_property('x')==0
        assert rotation.get_editor_property('Min').get_editor_property('y')==rotation.get_editor_property('Max').get_editor_property('y')==0
        assert rotation.get_editor_property('Max').get_editor_property('z')==360
        scale=init.get_editor_property('MeshScaleDistribution')
        assert scale.get_editor_property('Min').get_editor_property('x')!=scale.get_editor_property('Min').get_editor_property('y')
        life=init.get_editor_property('LifetimeDistribution')
        assert life.get_editor_property('Max')-life.get_editor_property('Min')>.9
        assert not modules['GravityForce'].get_editor_property('bModuleEnabled')
        assert modules['ScaleMeshSize'].get_editor_property('bModuleEnabled')
        curve=modules['ScaleMeshSize'].get_editor_property('ScaleDistribution')
        assert 'Time=1.000000,Value=4.650000' in curve.export_text()
    if name=='Distortion':
        assert modules['SpriteFacingAndAlignment'].get_editor_property('bModuleEnabled')
    if name=='Flame': assert modules['GravityForce'].get_editor_property('bModuleEnabled')
m=unreal.load_asset(dest+'/Materials/M_WF_Waterfall_UV')
codes=[e.get_editor_property('code') for e in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if e.get_outer()==m]
assert any('float v=(1-UV.y)-T*Speed;' in c for c in codes),'Downstream UV conversion must match UE FBX V flip'
ripple=unreal.load_asset(dest+'/Materials/M_WF_Ripple')
codes=[e.get_editor_property('code') for e in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if e.get_outer()==ripple]
assert any('float arcs=' in c and 'C.r*6.2831853' in c for c in codes),'Ripples need broken per-particle arcs'
curtain=unreal.load_asset(dest+'/Meshes/SM_WF_WaterCurtain')
pool=unreal.load_asset(dest+'/Meshes/SM_WF_Pool')
assert curtain.get_bounding_box().min.z<pool.get_bounding_box().min.z-3,'Curtain must penetrate the water surface'
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_name()=='L_AnimeWaterfall'
actors={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
c=actors['WF_Impact_Niagara'].get_component_by_class(unreal.NiagaraComponent)
assert c.get_asset()==system and c.get_editor_property('auto_activate') and c.is_active()
assert abs(actors['WF_Impact_Niagara'].get_actor_location().z-9)<.01
assert actors['WF_ShowcaseCamera'].camera_component.field_of_view==50
assert actors['WF_ImpactApron'].static_mesh_component.static_mesh==unreal.load_asset(dest+'/Meshes/SM_WF_ImpactApron')
report.update(passed=True,map=world.get_path_name(),niagara=data,downstream_uv=True,organic_impact=True,localized_ring_cm=[120,20.4])
(root/'Saved'/'waterfall_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('ANIME_WATERFALL_VALIDATION_OK')
