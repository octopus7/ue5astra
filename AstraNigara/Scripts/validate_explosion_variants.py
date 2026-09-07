"""Run in Unreal Python to check authored explosions and the loaded showcase."""
import json
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
report = {'systems': [], 'passed': False}
expected = {
    'Medium': {'counts': [52,26,32,3], 'loop': 4, 'smoke_life': 2.2, 'smoke_delay': .18},
    'Large': {'counts': [104,48,64,4], 'loop': 6, 'smoke_life': 4.2, 'smoke_delay': .32},
}
for name, spec in expected.items():
    for suffix, behavior in [('', 'Once'), ('_Showcase','Infinite')]:
        path = f'/Game/VFX/Explosions/NS_{name}Explosion{suffix}'
        system = unreal.load_asset(path)
        assert isinstance(system, unreal.NiagaraSystem), path
        data = json.loads(unreal.AstraNiagaraLibrary.describe_system(system))
        assert data['valid'] and data['ready_to_run'] and data['fixed_bounds_enabled'], path
        assert [e['name'] for e in data['emitters']] == ['Debris','Flame','Smoke','Distortion']
        for i,e in enumerate(data['emitters']):
            assert e['enabled'] and e['mode'] == 'Stateless'
            assert e['loop_behavior'] == behavior and e['loop_duration_seconds'] == spec['loop']
            assert len(e['spawns']) == 1
            spawn = e['spawns'][0]
            assert spawn['enabled'] and spawn['type'] == 'Burst'
            assert spawn['count_min'] == spawn['count_max'] == spec['counts'][i]
            r = e['renderers'][0]
            assert r['enabled'] and unreal.load_asset(r['material'])
        debris,flame,smoke,heat = data['emitters']
        assert abs(smoke['spawns'][0]['time']-spec['smoke_delay']) < 1e-5
        modules = {m['class']:m['properties'] for m in smoke['modules']}
        assert abs(modules['NiagaraStatelessModule_InitializeParticle']['lifetimeDistribution']['max']-spec['smoke_life']) < 1e-5
        meshes = debris['renderers'][0]['meshes']
        assert len(meshes) == 6
        assert debris['mesh_index_distribution']['max'] == 5
        for mesh in meshes:
            assert unreal.load_asset(mesh['asset'])
            assert mesh['lod_count'] == 3 and mesh['lod_mode'] == 'ComponentOrigin'
            a,b,c = mesh['lod_triangles']
            assert a > b > c > 0
        report['systems'].append(data)

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_name() == 'L_ExplosionScaleShowcase', 'Open L_ExplosionScaleShowcase before validation'
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for name in ['Small','Medium','Large']:
    matches = [a for a in actors if a.get_actor_label() == f'EX_{name}_Looping']
    assert len(matches) == 1
    c = matches[0].get_component_by_class(unreal.NiagaraComponent)
    assert c.get_editor_property('auto_activate') and c.get_asset()
    if name != 'Small': assert c.get_asset().get_name() == f'NS_{name}Explosion_Showcase'
    assert matches[0].get_actor_scale3d() == unreal.Vector(1,1,1)
report['map'] = world.get_path_name()
report['passed'] = True
(root/'Saved'/'explosion_variants_validation.json').write_text(json.dumps(report,indent=2), encoding='utf-8')
unreal.log('EXPLOSION_VARIANTS_VALIDATION_OK')
