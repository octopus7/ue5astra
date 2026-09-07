"""Reload persisted assets and verify the showcase wiring in Unreal Editor."""
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level('/Game/Maps/L_Showcase')
system = unreal.load_asset('/Game/VFX/NS_SimpleFountain')
assert isinstance(system, unreal.NiagaraSystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
effects = [actor for actor in actors if isinstance(actor, unreal.NiagaraActor)]
assert len(effects) == 1, 'Expected exactly one fountain'
component = effects[0].get_component_by_class(unreal.NiagaraComponent)
assert component.get_asset() == system
assert component.get_editor_property('auto_activate')
assert any(isinstance(actor, unreal.CameraActor) for actor in actors)
assert len([actor for actor in actors if isinstance(actor, unreal.StaticMeshActor)]) == 2
unreal.log('ASTRA_NIAGARA_VALIDATE_OK: saved map, one Niagara actor, auto activation, camera, two stage meshes')
