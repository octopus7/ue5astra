"""Check that opening and exporting the saved layout preserves all authored data."""
import bpy,json,runpy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource'
bpy.ops.wm.open_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
paths=[ART/'Layout/woodland_layout.json',ART/'Layout/landscape_height.r16']
before={p.name:p.read_bytes() for p in paths}
runpy.run_path(str(ROOT/'Scripts/export_blender_layout.py'),run_name='__main__')
same={p.name:before[p.name]==p.read_bytes() for p in paths}
data=json.loads(paths[0].read_text(encoding='utf-8'))
result={'passed':all(same.values()),'byte_identical':same,'object_count':len(data['objects']),
        'asset_count':len(data['assets']),'height_samples':len(paths[1].read_bytes())//2,
        'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
(ART/'Previews/Blender_ExportValidation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if not result['passed']:raise RuntimeError('Saved Blender layout export differs: '+str(same))
print('BLENDER EXPORT VALIDATED '+json.dumps(result))
