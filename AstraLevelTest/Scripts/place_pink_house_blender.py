"""Integrate the independent cottage/well into the saved woodland scene.

This is also called after a full build_blender_scene.py rebuild when the house assets
exist. On repeated runs it keeps existing instance transforms and applies the same
terrain pad from a stored pre-pad height attribute; manual layout exports should use
export_blender_layout.py without re-running this placement operation.
"""
import bpy
import hashlib
import json
import math
import runpy
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'ArtSource'
BLEND = ART/'Blender'/'AstraWoodland.blend'
LAYOUT = ART/'Layout'/'woodland_layout.json'
PATCH = ART/'Layout'/'pink_house_placement.json'
HOUSE_SOURCE = ART/'Blender'/'PinkHouseAssets.blend'
PATH_POINTS = [[8,35], [10,38.2], [12.1,39.0], [14.1,39.0], [15.1,40.5]]
PATH_HALF_WIDTH = 1.15
VERSION = 1

if bpy.data.objects.get('Landscape_Source_100m') is None:
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
scene = bpy.context.scene
ground = bpy.data.objects['Landscape_Source_100m']
library = bpy.data.collections['01_MeshLibrary']
layout = bpy.data.collections['02_WoodlandLayout']
metadata = json.loads(LAYOUT.read_text(encoding='utf-8'))
house_meta = json.loads((ART/'Layout'/'pink_house_assets.json').read_text(encoding='utf-8'))
previous = json.loads(PATCH.read_text(encoding='utf-8')) if PATCH.exists() else {}
previous_objects = {entry['name']:entry for entry in metadata['objects']}
height_file = ART/'Layout'/'landscape_height.r16'
before_hash = hashlib.sha256(height_file.read_bytes()).hexdigest()


def smooth(lo, hi, value):
    t = max(0, min(1, (value-lo)/(hi-lo)))
    return t*t*(3-2*t)


def segment_distance(x, y, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    t = max(0, min(1, ((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-a[0]-t*dx, y-a[1]-t*dy)


def new_path_distance(x, y):
    return min(segment_distance(x,y,a,b) for a,b in zip(PATH_POINTS,PATH_POINTS[1:]))


def rectangle_distance(x, y, bounds):
    xmin,xmax,ymin,ymax = bounds
    return math.hypot(max(xmin-x,0,x-xmax), max(ymin-y,0,y-ymax))


def sample(values, x, y):
    fx = max(0,min(126,(x+50.4)/.8))
    fy = max(0,min(126,(y+50.4)/.8))
    ix,iy = min(125,int(fx)),min(125,int(fy))
    tx,ty = fx-ix,fy-iy
    return (values[(ix,iy)]*(1-tx)*(1-ty)+values[(ix+1,iy)]*tx*(1-ty)
            +values[(ix,iy+1)]*(1-tx)*ty+values[(ix+1,iy+1)]*tx*ty)


# Preserve source heights independently of scene serialization/order and only move Z.
attribute = ground.data.attributes.get('PinkHousePrePadHeight')
if attribute is None:
    attribute = ground.data.attributes.new('PinkHousePrePadHeight','FLOAT','POINT')
    for index,vertex in enumerate(ground.data.vertices):
        attribute.data[index].value = vertex.co.z
source, old_heights = {}, {}
for index,vertex in enumerate(ground.data.vertices):
    v = ground.matrix_world@vertex.co
    key = (round((v.x+50.4)/.8),round((-v.y+50.4)/.8))
    source[key] = attribute.data[index].value
    old_heights[key] = v.z
pad_height = round(sample(source,19,40.5)*128)/128
pad_bounds = [14.3,22.2,36.8,44.2]
modified_samples = []
new_heights = {}
for index,vertex in enumerate(ground.data.vertices):
    x,y = vertex.co.x,-vertex.co.y
    key = (round((x+50.4)/.8),round((y+50.4)/.8))
    pad = 1-smooth(0,2.4,rectangle_distance(x,y,pad_bounds))
    well = 1-smooth(1.8,3.2,math.hypot(x-12.5,y-41.3))
    approach = (1-smooth(1.0,2.3,new_path_distance(x,y)))*smooth(9.1,12.0,x)
    blend = max(pad,well,approach)
    z = round((source[key]*(1-blend)+pad_height*blend)*128)/128
    vertex.co.z = z
    new_heights[key] = z
    if abs(z-source[key])>.00001:
        modified_samples.append({'grid_ij':list(key),'ue_xy_cm':[round(x*100,3),round(y*100,3)],
                                 'before_z_cm':round(source[key]*100,6),'after_z_cm':round(z*100,6)})
ground.data.update()
assert len(new_heights)==16129

# Add assets with canonical material names so the UE palette can reuse existing slots.
for entry in house_meta['assets']:
    asset_id = entry['asset_id']
    obj = bpy.data.objects.get(asset_id)
    if obj is None:
        with bpy.data.libraries.load(str(HOUSE_SOURCE),link=False) as (source_lib,destination_lib):
            destination_lib.objects = [asset_id]
        obj = destination_lib.objects[0]
        library.objects.link(obj)
        for slot in obj.material_slots:
            canonical = slot.material.name.split('.')[0]
            existing = bpy.data.materials.get(canonical)
            if existing is not None:
                slot.material = existing
            else:
                slot.material.name = canonical
    obj['asset_id'] = asset_id
    obj['collision'] = 'complex'
    obj.hide_render = True
    obj.hide_set(True)
    metadata['assets'][asset_id] = {
        'file':f'Meshes/{asset_id}.fbx','collision':'complex',
        'materials':entry['material_slots'],'dimensions_m':entry['dimensions_m']}
metadata['palette_srgb_hex'].update(house_meta['palette_srgb_hex'])
metadata.setdefault('material_properties',{}).update(house_meta['material_properties'])
if not any(points==PATH_POINTS for points,width in metadata['paths']):
    metadata['paths'].append([PATH_POINTS,PATH_HALF_WIDTH])

# Clear the footprint, camera-facing approach and new path; retain the surrounding frame.
removed = []
changed_existing = []
for obj in list(layout.objects):
    asset_id = obj.get('asset_id','')
    if asset_id in ('SM_PinkRoofHouse','SM_FrontWell') or asset_id.startswith('SM_Lake') or obj.get('group','').startswith('Water'):
        continue
    x,y = obj.location.x,-obj.location.y
    if not (5.5<x<26.5 and 32.0<y<48.0):
        continue
    tree = asset_id.startswith(('SM_Oak','SM_Fir'))
    rock = asset_id.startswith('SM_MossRock') or asset_id=='SM_FallenLog'
    footprint = rectangle_distance(x,y,[14.6,21.65,37.3,43.7])
    well_distance = math.hypot(x-12.5,y-41.3)
    path_distance = new_path_distance(x,y)
    remove = ((tree and rectangle_distance(x,y,[9,22.5,36.5,44.7])<2.1)
        or (rock and (footprint<1.35 or well_distance<2.15 or path_distance<2.0))
        or (not tree and not rock and (footprint<.4 or well_distance<1.4 or path_distance<1.3)))
    if remove:
        removed.append(previous_objects.get(obj.name,{'name':obj.name,'asset':asset_id}))
        bpy.data.objects.remove(obj,do_unlink=True)
    else:
        delta = sample(new_heights,x,y)-sample(old_heights,x,y)
        if abs(delta)>.00001:
            obj.location.z += delta
            changed_existing.append(obj.name)

new_names = []
for name,asset_id,x,y,group in (
        ('PinkRoofHouse_Lakeside','SM_PinkRoofHouse',19,40.5,'Structures/PinkHouse'),
        ('FrontWell_Lakeside','SM_FrontWell',12.5,41.3,'Structures/FrontWell')):
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name,bpy.data.objects[asset_id].data)
        layout.objects.link(obj)
        obj.location=(x,-y,sample(new_heights,x,y))
        obj.rotation_euler=(0,0,0)
    obj['asset_id']=asset_id
    obj['collision']='complex'
    obj['group']=group
    new_names.append(name)

# Match Blender's colored Landscape preview to the new path from the actual export data.
colors = ground.data.color_attributes.get('TerrainTint')
green = bpy.data.materials['M_Ground'].diffuse_color
path_hex = metadata['palette_srgb_hex']['M_Path']
path_srgb = [int(path_hex[i:i+2],16)/255 for i in (0,2,4)]
ochre = [value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in path_srgb]
for index,vertex in enumerate(ground.data.vertices):
    x,y=vertex.co.x,-vertex.co.y
    d=min(segment_distance(x,y,a,b)-width for points,width in metadata['paths'] for a,b in zip(points,points[1:]))
    d=min(d,math.hypot((x+5)*.9,y+10)-7.2)
    alpha=1-smooth(-.5,1.2,d)
    shore=1-smooth(.0,.50,abs(vertex.co.z-.1))
    alpha=max(alpha,shore*.6)
    colors.data[index].color=tuple(green[c]*(1-alpha)+ochre[c]*alpha for c in range(3))+(1,)
metadata['terrain']['pink_house_pad']={'height_m':pad_height,'flat_bounds_ue_m':pad_bounds,'blend_width_m':2.4}
LAYOUT.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
runpy.run_path(str(ROOT/'Scripts'/'export_blender_layout.py'),run_name='__main__')
metadata=json.loads(LAYOUT.read_text(encoding='utf-8'))
records={record['name']:record for record in metadata['objects']}
prior_removed=previous.get('removed_existing_instances',[])
all_removed={record['name']:record for record in prior_removed+removed}
all_changed=set(previous.get('modified_existing_actor_names',[]))|set(changed_existing)
patch={
    'version':VERSION,'source':'Scripts/place_pink_house_blender.py',
    'removed_existing_actor_names':sorted(all_removed),
    'removed_existing_instances':list(all_removed.values()),
    'new_instances':[records[name] for name in new_names],
    'modified_existing_actor_names':sorted(name for name in all_changed if name in records),
    'modified_existing_instances':[records[name] for name in sorted(all_changed) if name in records],
    'added_path':[PATH_POINTS,PATH_HALF_WIDTH],
    'terrain':{'source':'landscape_height.r16','grid_samples':127,'spacing_cm':80,
        'pad_height_cm':pad_height*100,'flat_bounds_ue_m':pad_bounds,'blend_width_m':2.4,
        'modified_sample_count':len(modified_samples),'modified_samples':modified_samples,
        'before_sha256':before_hash,'after_sha256':hashlib.sha256(height_file.read_bytes()).hexdigest()},
    'validation':{'source_grid_vertices':len(ground.data.vertices),'new_instances':2,
        'door_front_ue_axis':'-X','step_approach_center_cm':[1500,4050],
        'well_path_center_clearance_m':round(new_path_distance(12.5,41.3),3),
        'house_ground_cm':records[new_names[0]]['ue_location_cm'][2],
        'well_ground_cm':records[new_names[1]]['ue_location_cm'][2]},
}
PATCH.write_text(json.dumps(patch,indent=2)+'\n',encoding='utf-8')

# Overview is saved as the source scene camera; local review camera remains available.
overview = bpy.data.objects['OverviewCamera']
site_camera = bpy.data.objects.get('PinkHouseSiteCamera')
if site_camera is None:
    bpy.ops.object.camera_add(location=(-3.0,-38.2,30.5))
    site_camera=bpy.context.object
    site_camera.name='PinkHouseSiteCamera'
    site_camera.rotation_euler=(Vector((16.5,-38.2,1.8))-site_camera.location).to_track_quat('-Z','Y').to_euler()
    site_camera.data.type='ORTHO'
    site_camera.data.ortho_scale=25
scene.camera=overview
scene.render.filepath=str(ART/'Previews'/'Blender_LayoutOverview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
bpy.ops.render.render(write_still=True)
scene.camera=site_camera
scene.render.filepath=str(ART/'Previews'/'Blender_PinkHouseSite.png')
bpy.ops.render.render(write_still=True)
scene.camera=overview
scene.render.filepath=str(ART/'Previews'/'Blender_LayoutOverview.png')
print('ASTRA PINK HOUSE PLACED '+json.dumps({
    'removed':len(all_removed),'repositioned':len(all_changed),'instances':patch['new_instances'],
    'height_samples_changed':len(modified_samples),'pad_height_m':pad_height,
    'well_path_clearance_m':patch['validation']['well_path_center_clearance_m']}))
