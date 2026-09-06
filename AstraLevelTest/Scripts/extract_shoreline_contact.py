"""Reproduce the actual composite waterline used by the site's foam shader.

Blender background: --python this_file.py, optionally -- --dry-run.
Only the site JSON's foam contour and diagnostic metadata are written; no mesh,
FBX, material or .blend is saved. The site builder calls update_manifest() after
saving its freshly generated review scene, so regeneration retains this field.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
OBJECT_NAMES=('Landscape_Source_100m','AST_Shoreline_CurvedBed',
              'AST_Shoreline_BankWest','AST_Shoreline_BankLow','AST_Shoreline_BankEast')


def update_manifest(manifest_path=None, blend_path=None, *, load_scene=False, dry_run=False):
    """Extract 0.25 m samples from Landscape+bed+banks, excluding all props.

    The planned contour only defines a search neighbourhood. Each output point
    comes from the first waterward-to-landward top-surface crossing of Z=water.
    Existing planned contour values and all unrelated manifest fields remain.
    """
    manifest_path=Path(manifest_path or ART/'Layout'/'shoreline_site.json')
    blend_path=Path(blend_path or ART/'Blender'/'AstraLakeshoreReview.blend')
    data=json.loads(manifest_path.read_text(encoding='utf-8'))
    if load_scene:
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    bpy.context.view_layer.update()
    missing=[name for name in OBJECT_NAMES if name not in bpy.data.objects]
    if missing:
        raise RuntimeError('Open the shoreline review scene before extracting: '+', '.join(missing))
    objects=[bpy.data.objects[name] for name in OBJECT_NAMES]
    inverses={obj.name:obj.matrix_world.inverted() for obj in objects}
    water=float(data['water_level_cm'])/100
    planned_points=data['shoreline_contour_ue_m']

    def planned(x):
        for a,b in zip(planned_points,planned_points[1:]):
            if x<=b[0]:
                return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0])
        return planned_points[-1][1]

    def ray(obj,point,direction):
        inverse=inverses[obj.name]
        hit,position,_,_=obj.ray_cast(inverse@point,(inverse.to_3x3()@direction).normalized())
        return obj.matrix_world@position if hit else None

    def top(x,y):
        hits=[hit.z for obj in objects
              if (hit:=ray(obj,Vector((x,-y,5)),Vector((0,0,-1)))) is not None]
        if not hits:
            raise RuntimeError(f'No composite ground below ({x}, {y})')
        return max(hits)

    spacing=.25
    start,end=float(planned_points[0][0]),float(planned_points[-1][0])
    count=round((end-start)/spacing)+1
    contour=[]
    errors=[]
    outer_distances=[]
    for index in range(count):
        x=start+index*spacing
        base=planned(x)
        samples=[base-2+step*.035 for step in range(101)]
        previous=samples[0]
        if top(x,previous)>=water:
            raise RuntimeError(f'Waterward search bound is dry at X={x}')
        bracket=None
        for y in samples[1:]:
            if top(x,y)>=water:
                bracket=(previous,y)
                break
            previous=y
        if bracket is None:
            raise RuntimeError(f'No composite waterline crossing at X={x}')
        lo,hi=bracket
        for _ in range(34):
            mid=(lo+hi)*.5
            if top(x,mid)>=water:
                hi=mid
            else:
                lo=mid
        y=(lo+hi)*.5
        contour.append([round(x,6),round(y,9),water])
        errors.append(abs(top(x,y)-water))
        outer_distances.append((base-y)*100)

    # Mirror the material's monotone-cubic sample slopes and fixed camera ray
    # when reporting the first two wave-band depths, without changing shading.
    secants=[(b[1]-a[1])/spacing for a,b in zip(contour,contour[1:])]
    slopes=[secants[0]]
    for left,right in zip(secants,secants[1:]):
        slopes.append(0 if left*right<=0 else 2*left*right/(left+right))
    slopes.append(secants[-1])
    pitch=math.radians(58)
    direction=Vector((math.cos(pitch),0,-math.sin(pitch)))

    def view_depth(x,y):
        point=Vector((x,-y,water))
        distances=[(hit-point).length for obj in objects
                   if (hit:=ray(obj,point+direction*.00001,direction)) is not None]
        if not distances:
            raise RuntimeError(f'No composite view-depth hit at ({x}, {y})')
        return min(distances)*math.sin(pitch)*100

    probes=[]
    for index,point in enumerate(contour):
        if abs(point[0]-round(point[0]))>1e-5:
            continue
        factor=math.sqrt(1+slopes[index]**2)
        entry={'x_m':point[0],'actual_y_m':point[1],
               'planned_to_actual_waterward_cm':round(outer_distances[index],2)}
        for distance in (.45,1.38):
            y=point[1]-distance*factor
            entry[f'wave_{int(distance*100)}cm']={
                'vertical_depth_cm':round((water-top(point[0],y))*100,2),
                'view_depth_proxy_cm':round(view_depth(point[0],y),2)}
        probes.append(entry)

    existing_matches=data.get('foam_shoreline_contour_ue_m')==contour
    data['foam_shoreline_contour_ue_m']=contour
    data['foam_shoreline_contour_source']={
        'method':'First waterward-to-landward crossing of actual composite mesh top at world Z=0.10 m, vertical raycasts plus bisection.',
        'spacing_m':spacing,'sample_count':len(contour),
        'included_objects':list(OBJECT_NAMES),
        'excluded':'Isolated rocks, plants, lilies and water surface; only Landscape + bed + banks.',
        'water_level_m':water,'max_intersection_height_error_m':max(errors),
        'source_blend_sha256':hashlib.sha256(blend_path.read_bytes()).hexdigest(),
        'planned_contour_preserved':True,'wave_depth_diagnostic_ue_m':probes}
    if not dry_run:
        manifest_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'samples':len(contour),'spacing_m':spacing,
             'max_intersection_height_error_m':max(errors),
             'matches_existing_contour':existing_matches,'manifest_written':not dry_run}
    print('ACTUAL_SHORELINE_CONTACT '+json.dumps(summary))
    return summary


if __name__=='__main__':
    update_manifest(load_scene=True,dry_run='--dry-run' in sys.argv)
