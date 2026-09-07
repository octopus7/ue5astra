"""Read-only Crystal Cave source validation against exported layout and routes.

Run Blender --background --factory-startup --python Scripts/validate_cave_blender.py.
Report: ArtSource/Previews/CrystalCave/Blender_LayoutValidation.json.
The generated scene and layout are never modified by this audit.
"""
import bpy, json, math, struct, sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts'))
import cave_layout as D
layout=json.loads((ROOT/'ArtSource/Layout/CrystalCave/cave_layout.json').read_text())
routes=json.loads((ROOT/'ArtSource/Layout/CrystalCave/cave_routes.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'ArtSource/Blender/AstraCrystalCave.blend'))
bpy.context.view_layer.update()
result={'source':'Read-only independent Blender geometry audit','objects':len(layout['objects']),
        'lights':len(layout['lights']),'transform_mismatches':[],'actionable_issues':[]}

def tree_for(obs):
    vertices=[];faces=[]
    for ob in obs:
        start=len(vertices)
        vertices.extend(ob.matrix_world@v.co for v in ob.data.vertices)
        faces.extend(tuple(i+start for i in p.vertices) for p in ob.data.polygons)
    return BVHTree.FromPolygons(vertices,faces,all_triangles=False)

for item in layout['objects']:
    ob=bpy.data.objects.get(item['name'])
    if ob is None:
        result['transform_mismatches'].append([item['name'],'missing'])
        continue
    expected=Vector((item['ue_location_cm'][0]/100,-item['ue_location_cm'][1]/100,item['ue_location_cm'][2]/100))
    err=(ob.location-expected).length
    angle=abs(math.degrees(ob.rotation_euler.z)+item['ue_rotation_deg']['yaw'])
    scale=max(abs(a-b) for a,b in zip(ob.scale,item['scale']))
    if err>1e-5 or angle>1e-4 or scale>1e-6:
        result['transform_mismatches'].append([item['name'],err,angle,scale])
for item in layout['lights']:
    ob=bpy.data.objects.get(item['name'])
    expected=Vector((item['ue_location_cm'][0]/100,-item['ue_location_cm'][1]/100,item['ue_location_cm'][2]/100))
    if ob is None or (ob.location-expected).length>1e-5:
        result['transform_mismatches'].append([item['name'],'light'])

land=bpy.data.objects['Landscape_Source_50x30m']
ls=layout['landscape']; raw=(ROOT/ls['file']).read_bytes()
values=struct.unpack('<'+'H'*(len(raw)//2),raw)
height_error=max(abs((value-32768)/128-land.data.vertices[i].co.z) for i,value in enumerate(values))
result['landscape']={'samples':ls['samples'],'vertices':len(land.data.vertices),'faces':len(land.data.polygons),
   'dimensions_m':list(land.dimensions),'raw_bytes':len(raw),'height_quantization_error_m':height_error,
   'origin_and_scale_dimensions_m':[(ls['samples'][i]-1)*ls['scale'][i]/100 for i in range(2)]}
assert len(values)==127*64 and height_error<=1/256+.00001

blockers=[];perimeter=[];trees=[]
for item in layout['objects']:
    if item['collision']=='none':continue
    ob=bpy.data.objects[item['name']]
    blockers.append(ob)
    if 'CaveBoundary' in item.get('tags',[]):perimeter.append(ob)
    trees.append((item,tree_for([ob])))
all_tree=tree_for(blockers)
perimeter_tree=tree_for(perimeter)

def uevec(x,y,z):return Vector((x,-y,z))
def nearest(x,y):
    # Cat capsule radius 0.30, half-height 0.88. Sphere-centre samples over the
    # central axis assess existing mesh surfaces; UE sweep remains authoritative.
    floor=D.height(x,y)
    best=(1e9,None)
    for z in [.30,.59,.88,1.17,1.46]:
        hit=all_tree.find_nearest(uevec(x,y,floor+z))
        if hit and hit[0] is not None and hit[3]<best[0]:best=(hit[3],z)
    return best

result['walking_routes']=[]
for route in routes['routes']:
    if route['kind']!='walk':continue
    closest=(1e9,None);near=[];count=0
    pts=[[v/100 for v in p] for p in route['waypoints']]
    for a,b in zip(pts,pts[1:]):
        count_segments=math.ceil(math.dist(a,b)/.10)
        for i in range(count_segments+1):
            t=i/count_segments;x=a[0]+t*(b[0]-a[0]);y=a[1]+t*(b[1]-a[1])
            distance,z=nearest(x,y);count+=1
            if distance<closest[0]:closest=(distance,[x,y,z])
            if distance<.30:near.append([round(x,3),round(y,3),round(distance,3)])
    result['walking_routes'].append({'name':route['name'],'sample_count':count,
        'minimum_capsule_surface_margin_m':round(closest[0]-.30,4),'closest_point_m':closest[1],
        'surface_contact_samples':near[:20]})

result['islands']=[]
for item in layout['objects']:
    if 'CaveIsland' not in item.get('tags',[]):continue
    ob=bpy.data.objects[item['name']];coords=[ob.matrix_world@v.co for v in ob.data.vertices]
    lo=[min(v[i] for v in coords) for i in range(3)];hi=[max(v[i] for v in coords) for i in range(3)]
    result['islands'].append({'name':item['name'],'ue_xy_bounds_m':[lo[0],hi[0],-hi[1],-lo[1]],
        'footprint_m':[hi[0]-lo[0],hi[1]-lo[1]],'side_centerline_minimum_bbox_clearance_m':5.5-max(abs(lo[0]),abs(hi[0]))})

result['collision_probes']=[]
for route in routes['routes']:
    if route['kind']!='collision':continue
    a,b=[[v/100 for v in p] for p in route['waypoints']]
    direction=uevec(b[0]-a[0],b[1]-a[1],0);dist=direction.length;direction.normalize()
    hits=[]
    for offset in [.45,.88,1.3]:
        origin=uevec(a[0],a[1],D.height(*a)+offset)
        for item,tree in trees:
            hit=tree.ray_cast(origin,direction,dist)
            if hit[0] is not None:hits.append((hit[3],item['name'],item.get('tags',[]),offset))
    hits.sort()
    result['collision_probes'].append({'name':route['name'],'first_hit':hits[0] if hits else None,
      'expected_tag_hit':any(route['expected_blocker_tag'] in h[2] for h in hits)})

def ranges(samples,step=.1):
    chunks=[]
    for v in samples:
        if not chunks or v-chunks[-1][-1]>step*1.5:chunks.append([v])
        else:chunks[-1].append(v)
    return [[round(c[0],3),round(c[-1],3),round(c[-1]-c[0]+step,3)] for c in chunks]

# Probe the entire sides/endcaps against boundary meshes only. A no-hit interval
# wider than capsule diameter is a potential escape route, pending UE stepping.
result['perimeter_ray_gaps']={}
for side in [-1,1]:
    gaps=[]
    for i in range(475):
        y=-23.7+i*.1; blocked=False
        for z in [.45,.75]:
            hit=perimeter_tree.ray_cast(uevec(0,y,D.height(0,y)+z),Vector((side,0,0)),16)
            if hit[0] is not None:blocked=True
        if not blocked:gaps.append(y)
    result['perimeter_ray_gaps']['left' if side<0 else 'right']=ranges(gaps)
for end in [-1,1]:
    gaps=[]
    for i in range(201):
        x=-10+i*.1;blocked=False
        for z in [.45,.75]:
            hit=perimeter_tree.ray_cast(uevec(x,0,D.height(x,end*23)+z),Vector((0,-end,0)),26)
            if hit[0] is not None:blocked=True
        if not blocked:gaps.append(x)
    result['perimeter_ray_gaps']['entrance' if end<0 else 'far_end']=ranges(gaps)
result['limitations']='Geometric sampled audit; no UE movement, stepping, pawn sweep or runtime collision-channel simulation. Endcap probes from centre can intersect side boundary at distant x.'
for side,chunks in result['perimeter_ray_gaps'].items():
    for a,b,width in chunks:
        if width>.60:result['actionable_issues'].append({'type':'potential_perimeter_escape','edge':side,'interval_m':[a,b],'width_m':width})
for route in result['walking_routes']:
    if route['surface_contact_samples']:result['actionable_issues'].append({'type':'route_mesh_contact','route':route['name']})
path=ROOT/'ArtSource/Previews/CrystalCave/Blender_LayoutValidation.json'
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
