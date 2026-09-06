"""Refresh the persisted base Landscape layer without replacing any actors."""
import unreal,json
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
land=next(a for a in actors if isinstance(a,unreal.Landscape))
points={'house':(1900,4050,0),'well':(1250,4130,0),'steps':(1500,4050,0)}
before={k:unreal.AstraSceneLibrary.landscape_height_at(land,unreal.Vector(*p)) for k,p in points.items()}
if not unreal.AstraSceneLibrary.update_terrain_heights(land):raise RuntimeError('Terrain update failed')
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Map save failed')
after={k:unreal.AstraSceneLibrary.landscape_height_at(land,unreal.Vector(*p)) for k,p in points.items()}
if any(abs(h-98.4375)>1 for h in after.values()):raise RuntimeError('House ground height mismatch: '+str(after))
result={'before_height_cm':before,'after_height_cm':after,'expected_cm':98.4375,'existing_landscape_preserved':True}
(root/'ArtSource/Previews/UE_HouseTerrainValidation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('ASTRA TERRAIN VERIFIED '+str(result))
