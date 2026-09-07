"""Validate saved Niagara assets and showcase wiring inside UE 5.7."""
import json
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
library = unreal.AstraNiagaraLibrary
report = {'systems': []}
for suffix, behavior in [('', 'Once'), ('_Showcase', 'Infinite')]:
    system = unreal.load_asset('/Game/VFX/SmallDestruction/NS_SmallDestruction' + suffix)
    assert isinstance(system, unreal.NiagaraSystem)
    description = json.loads(library.describe_system(system))
    assert description['valid'] and description['ready_to_run'], 'Niagara system not ready to run'
    emitters = description['emitters']
    assert [entry['name'] for entry in emitters] == ['Debris', 'Flame', 'Smoke', 'Distortion']
    for entry in emitters:
        assert entry['enabled'] and entry['loop_behavior'] == behavior
        assert len(entry['spawns']) == 1 and entry['spawns'][0]['enabled']
        assert entry['spawns'][0]['type'] == 'Burst' and entry['spawns'][0]['count_min'] > 0
        renderer = entry['renderers'][0]
        assert renderer['enabled'] and unreal.load_asset(renderer['material'])
    assert 'NiagaraMeshRenderer' in emitters[0]['renderers'][0]['class']
    assert unreal.load_asset(emitters[0]['renderers'][0]['mesh'])
    report['systems'].append(description)

heat = unreal.load_asset('/Game/VFX/SmallDestruction/Materials/M_HeatDistortion')
assert heat.get_editor_property('refraction_method') == unreal.RefractionMode.RM_2D_OFFSET
smoke = unreal.load_asset('/Game/VFX/SmallDestruction/Materials/M_Smoke')
assert smoke.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_TRANSLUCENT

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/L_SmallDestructionShowcase')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
effects = [actor for actor in actors if isinstance(actor, unreal.NiagaraActor)]
assert len(effects) == 1
component = effects[0].get_component_by_class(unreal.NiagaraComponent)
assert component.get_asset().get_name() == 'NS_SmallDestruction_Showcase'
assert component.get_editor_property('auto_activate')
assert any(actor.get_actor_label() == 'SD_100cm_Diameter' for actor in actors)
report['map'] = '/Game/Maps/L_SmallDestructionShowcase'
report['passed'] = True
output = root / 'Saved' / 'SmallDestruction' / 'validation.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('ASTRA_SMALL_DESTRUCTION_VALIDATION_OK')
