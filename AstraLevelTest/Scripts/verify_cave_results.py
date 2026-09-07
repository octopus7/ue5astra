"""Aggregate saved UE evidence and quantify localized light on real rendered surfaces."""
import json,hashlib,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'ArtSource/Previews/CrystalCave'
def read(n):return json.loads((OUT/n).read_text(encoding='utf-8-sig'))
movement=read('UE_CaveMovementValidation.json');saved=read('UE_CaveSavedValidation.json');blender=read('Blender_LayoutValidation.json')
images={}
for view in ['CaveOverview','CaveFork1','CaveFork2','CaveHeart','CaveGameplay','CaveFork1_LightsOff']:
    p=OUT/f'UE_{view}.png';im=Image.open(p).convert('RGB')
    images[view]=dict(size=list(im.size),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    assert im.size==(1600,1000),(view,im.size)
on=np.asarray(Image.open(OUT/'UE_CaveFork1.png').convert('RGB'),dtype=float)/255
off=np.asarray(Image.open(OUT/'UE_CaveFork1_LightsOff.png').convert('RGB'),dtype=float)/255
assert on.shape==off.shape
# Same orthographic UE camera: width2600cm, pitch58, look(0,-900,100).
# Surface ROIs exclude emissive crystals: clear foreground path and front rock face.
regions={'floor_front_path':(690,720,760,775),'floor_rear_path':(650,275,720,330),'island_front_rock':(750,565,805,610)}
lighting={}
for name,(x1,y1,x2,y2) in regions.items():
    a=on[y1:y2,x1:x2];b=off[y1:y2,x1:x2]
    lum=lambda c:float((c@np.array([.2126,.7152,.0722])).mean())
    lighting[name]=dict(pixel_region=[x1,y1,x2,y2],lights_on_luma=lum(a),lights_off_luma=lum(b),mean_rgb_gain=list((a-b).mean(axis=(0,1))),luma_gain=lum(a)-lum(b))
lighting_pass=lighting['floor_front_path']['luma_gain']>.015 and lighting['island_front_rock']['luma_gain']>.015
# Every pre-existing Content/Config/Source file is preserved; cave files are additions.
diff=subprocess.check_output(['git','diff','--name-status','86d3894','--','AstraLevelTest/Content','AstraLevelTest/Config','AstraLevelTest/Source'],cwd=ROOT.parent,text=True)
modified_existing=[line for line in diff.splitlines() if not line.startswith('A\t')]
report=dict(passed=bool(movement['passed'] and saved['passed'] and not blender['actionable_issues'] and lighting_pass and not modified_existing),
    map='/Game/Astra/Maps/L_AstraCrystalCave',movement=dict(passed=movement['passed'],routes=movement['routes_completed'],failed_checks=movement['failed_checks'],elapsed_game_seconds=movement['elapsed_game_seconds'],full_traversal_m=movement['routes'][0]['travel_cm']/100),
    saved_map_passed=saved['passed'],blender_actionable_issues=blender['actionable_issues'],lighting_passed=lighting_pass,lighting_comparison=lighting,images=images,modified_preexisting_content_config_source=modified_existing,
    cave_native_render_profile='1600x1000 native; NGX disabled only in review launcher; shared DLSS configuration preserved')
(OUT/'UE_CaveFinalValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='images'},indent=2));assert report['passed']
