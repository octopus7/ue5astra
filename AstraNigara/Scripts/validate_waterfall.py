"""Validate saved waterfall resources in the open UE editor, after Niagara Compile."""
import json,runpy
from pathlib import Path
import unreal
root=Path(unreal.Paths.project_dir()).resolve()
builder=runpy.run_path(str(root/'Scripts'/'build_waterfall.py'))
dest=builder['DEST']
report={'passed':False,'soft_impact':False,'meshes':[],'emitters':[]}
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
assert {e['name'] for e in data['emitters']}=={'Ripples','Splash','Mist','Foam'}
footprints={
    'Debris':((-40,8,-1.7),(40,24,-1.2)),
    'Flame':((-65,-3,-1),(65,13,4)),
    'Smoke':((-61,2,1),(61,20,6)),
    'Distortion':((-69,5,-1.4),(69,26,-.8)),
}


def close(actual,expected):
    assert abs(actual-expected)<.001,(actual,expected)


def vector_matches(actual,expected):
    for axis,value in zip('xyz',expected):
        close(actual.get_editor_property(axis),value)


def range_matches(obj,prop,low,high):
    value=obj.get_editor_property(prop)
    for side,expected in [('Min',low),('Max',high)]:
        actual=value.get_editor_property(side)
        if isinstance(expected,tuple):
            vector_matches(actual,expected)
        else:
            close(actual,expected)


for name,rate in [('Debris',3.2),('Flame',92),('Smoke',16),('Distortion',30)]:
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
    assert not modules['ShapeLocation'].get_editor_property('bModuleEnabled'),'Strong ring emission must be disabled'
    assert len(positions)==2
    for position,expected in zip(positions,footprints[name]):
        vector_matches(position,expected)
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
    if name=='Flame':
        range_matches(init,'LifetimeDistribution',.32,.62)
        range_matches(init,'SpriteSizeDistribution',(2.2,5),(5.2,11))
        range_matches(modules['AddVelocity'],'LinearVelocityDistribution',(-25,6,48),(25,40,100))
        assert modules['GravityForce'].get_editor_property('bModuleEnabled')
        range_matches(modules['GravityForce'],'GravityDistribution',(0,0,-240),(0,0,-240))
        assert emitter.get_editor_property('RendererProperties')[0].get_editor_property('Material')==unreal.load_asset(dest+'/Materials/M_WF_Splash')
    if name=='Smoke':
        range_matches(init,'LifetimeDistribution',.75,1.35)
        range_matches(init,'SpriteSizeDistribution',(20,20),(36,36))
        range_matches(modules['AddVelocity'],'LinearVelocityDistribution',(-10,8,12),(10,20,28))
        assert not modules['GravityForce'].get_editor_property('bModuleEnabled')
        assert modules['Drag'].get_editor_property('bModuleEnabled')
        range_matches(modules['Drag'],'DragDistribution',.8,.8)
        assert emitter.get_editor_property('RendererProperties')[0].get_editor_property('Material')==unreal.load_asset(dest+'/Materials/M_WF_Mist')
m=unreal.load_asset(dest+'/Materials/M_WF_Waterfall_UV')
codes=[e.get_editor_property('code') for e in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if e.get_outer()==m]
assert any('float v=(1-UV.y)-T*Speed;' in c for c in codes),'Downstream UV conversion must match UE FBX V flip'
ripple=unreal.load_asset(dest+'/Materials/M_WF_Ripple')
codes=[e.get_editor_property('code') for e in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if e.get_outer()==ripple]
assert any('float arcs=' in c and 'C.r*6.2831853' in c for c in codes),'Ripples need broken per-particle arcs'
for name,signature in [('Splash','p.x*=1.15+.35*p.y;'),('Mist','pow(saturate(1-length(p)),2)*A*.12')]:
    material=unreal.load_asset(dest+'/Materials/M_WF_'+name)
    codes=[e.get_editor_property('code') for e in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if e.get_outer()==material]
    assert any(signature in code for code in codes),'Soft '+name+' material must be restored'
curtain=unreal.load_asset(dest+'/Meshes/SM_WF_WaterCurtain')
pool=unreal.load_asset(dest+'/Meshes/SM_WF_Pool')
assert curtain.get_bounding_box().min.z<pool.get_bounding_box().min.z-3,'Curtain must penetrate the water surface'
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_name()=='L_AnimeWaterfall'
actors={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
packaged=actors.get('WF_AnimeWaterfall')
if packaged:
    assert not any(label in actors for label in ('WF_UpperStream','WF_WaterCurtain','WF_ImpactApron','WF_Impact_Niagara'))
    kit=runpy.run_path(str(root/'Scripts'/'build_waterfall_blueprint.py'))
    kit_components=kit['check_instance'](packaged)
    report['blueprint']=kit['BP_PATH']
    report['migration_dependencies']=kit['dependencies']()
    c=kit_components['ImpactNiagara']
    apron=kit_components['ImpactApron']
else:
    c=actors['WF_Impact_Niagara'].get_component_by_class(unreal.NiagaraComponent)
    apron=actors['WF_ImpactApron'].static_mesh_component
assert c.get_asset()==system and c.get_editor_property('auto_activate') and c.is_active()
assert abs(c.get_world_transform().translation.z-9)<.01
assert actors['WF_ShowcaseCamera'].camera_component.field_of_view==50
assert apron.static_mesh==unreal.load_asset(dest+'/Meshes/SM_WF_ImpactApron')
expected_foliage={'SM_WF_GrassTuft':441,'SM_WF_GrassFan':316,'SM_WF_GrassSedge':98}
foliage_counts={name:0 for name in expected_foliage}
for actor in actors.values():
    if isinstance(actor,unreal.InstancedFoliageActor):
        for component in actor.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
            mesh=component.get_editor_property('static_mesh')
            if mesh and mesh.get_name() in foliage_counts:
                foliage_counts[mesh.get_name()]+=component.get_instance_count()
assert foliage_counts==expected_foliage,(foliage_counts,expected_foliage)
report.update(passed=True,map=world.get_path_name(),niagara=data,downstream_uv=True,
              organic_impact=True,soft_impact=True,foliage_instances=sum(foliage_counts.values()),
              foliage_counts=foliage_counts,foliage_preserved=True)
(root/'Saved'/'waterfall_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('ANIME_WATERFALL_VALIDATION_OK')
