"""Export manual edits from the currently open AstraWoodland.blend without re-scattering."""
import bpy,json,math,struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
data=json.loads((ART/'Layout'/'woodland_layout.json').read_text(encoding='utf-8'))
layout=bpy.data.collections.get('02_WoodlandLayout')
ground=bpy.data.objects.get('Landscape_Source_100m')
if layout is None or ground is None:
    raise RuntimeError('Open ArtSource/Blender/AstraWoodland.blend before exporting.')
records=[]
for o in layout.objects:
    if 'asset_id' not in o:continue
    if o.parent is None and o.rotation_mode=='XYZ':
        loc,e,scale=o.location,o.rotation_euler,o.scale
    else:
        loc,quat,scale=o.matrix_world.decompose();e=quat.to_euler('XYZ')
    records.append({'name':o.name,'asset':o['asset_id'],'group':o.get('group','Forest'),'collision':o.get('collision','none'),
      'blender_location_m':list(loc),'blender_rotation_euler_rad':list(e),'scale':list(scale),
      'ue_location_cm':[loc.x*100,-loc.y*100,loc.z*100],
      'ue_rotation_deg':{'pitch':-math.degrees(e.y),'yaw':-math.degrees(e.z),'roll':math.degrees(e.x)}})
heights=[None]*(127*127)
for vertex in ground.data.vertices:
    v=ground.matrix_world@vertex.co
    i=round((v.x+50.4)/.8);j=round((-v.y+50.4)/.8)
    if not (0<=i<127 and 0<=j<127) or abs(v.x-(-50.4+i*.8))>.02 or abs(-v.y-(-50.4+j*.8))>.02:
        raise RuntimeError('Landscape export requires the 80cm XY grid; sculpt height (Z) without moving XY vertices.')
    heights[j*127+i]=max(0,min(65535,round(32768+v.z*128)))
if None in heights:raise RuntimeError('The Landscape sample grid is incomplete.')
data['objects']=records
(ART/'Layout'/'woodland_layout.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
with open(ART/'Layout'/'landscape_height.r16','wb') as f:f.write(struct.pack('<16129H',*heights))
print(f'Exported {len(records)} scene objects and {len(heights)} Landscape height samples from the current Blender scene.')
