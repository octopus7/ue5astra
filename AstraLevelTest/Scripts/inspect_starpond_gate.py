"""Read the authored gate and measure microscopic bevel slivers; do not save it."""
import bpy,json,math,struct
from pathlib import Path
root=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(root/'ArtSource/Blender/StarPondRuins.blend'))
o=bpy.data.objects['SM_SP_CrescentGate']
rows=[]
f32=lambda x:struct.unpack('f',struct.pack('f',x))[0]
for p in o.data.polygons:
    v=[[f32(float(c)*100) for c in o.data.vertices[i].co] for i in p.vertices]
    a=[v[1][i]-v[0][i] for i in range(3)];b=[v[2][i]-v[0][i] for i in range(3)]
    cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    area=math.sqrt(sum(x*x for x in cross))/2
    rows.append(dict(index=p.index,area_cm2=area,source_area_m2=p.area,vertices_cm=v))
rows.sort(key=lambda r:r['area_cm2'])
r=dict(triangles=len(rows),microscopic_area_limit_m2=2e-8,microscopic_triangle_count=sum(r['source_area_m2']<2e-8 for r in rows),smallest_triangles=rows[:8])
(root/'ArtSource/Previews/StarPondGate_TopologyInspection.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r))
