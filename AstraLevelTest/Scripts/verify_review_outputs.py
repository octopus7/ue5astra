"""Record actual GPU render outputs, shader diagnostics and movement results."""
import json,hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
views=['Sky','SkySeam','SkyZenith','Camp','Cliffs','Sign','Foliage','Rocks','Puddle','PuddleSkyTop','PuddleSkyLow','Shoreline','Overview','Gameplay','Bridge','House','Lake','Fishing','HomeLife','Picnic','Repair','CampLife']
results=[]
for view in views:
    path=ROOT/'ArtSource/Previews'/('UE_'+view+'.png')
    log=(ROOT/'Saved'/('Review_'+view+'.log')).read_text(encoding='utf-8',errors='replace')
    errors=[line for line in log.splitlines() if any(token in line for token in ['Failed to compile Material','LogShaderCompilers: Error','LogMaterial: Error','missing bUsedWith'])]
    raw=path.read_bytes();size=struct.unpack('>II',raw[16:24])
    results.append({'view':view,'size_px':size,'sha256':hashlib.sha256(raw).hexdigest(),'shader_errors':errors,'engine_exited':'LogExit: Exiting.' in log})
checks={name:json.loads((ROOT/'ArtSource/Previews'/name).read_text(encoding='utf-8-sig'))['passed'] for name in ['UE_MovementValidation.json','UE_BridgeValidation.json','UE_CampMovementValidation.json','UE_DockMovementValidation.json','UE_ForestReloadValidation.json','UE_LifePropsReloadValidation.json','Blender_ExportValidation.json','UE_ShorelinePolishMainValidation.json','FishingDock_FBXValidation.json']}
report={'passed':all(checks.values()) and all(not r['shader_errors'] and r['engine_exited'] and min(r['size_px'])>800 for r in results),'checks':checks,'renders':results}
(ROOT/'ArtSource/Previews/UE_FinalReviewValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'views':len(results),'checks':checks},indent=2))
if not report['passed']:raise SystemExit(1)
