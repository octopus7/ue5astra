"""Append independent life-prop kits to the authored scene without re-scattering.

Only plants/rocks intersecting new footprints are preserved hidden. Native
foliage survivors retain their exact original transforms and their order.
"""
import bpy,json,math,runpy,shutil,struct,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource'
backup=ART/'Backups/BeforeLifeProps';backup.mkdir(parents=True,exist_ok=True)
for rel in ['Blender/AstraWoodland.blend','Layout/woodland_layout.json','Layout/landscape_height.r16','Layout/foliage_placement.json','Previews/UE_FoliageValidation.json']:
    target=backup/Path(rel).name
    if not target.exists():shutil.copy2(ART/rel,target)
bpy.ops.wm.open_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
scene=bpy.context.scene;layout=bpy.data.collections['02_WoodlandLayout'];library=bpy.data.collections['01_MeshLibrary']
data=json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'))
oldrecords={o['name']:o for o in data['objects']}
raw=(ART/'Layout/landscape_height.r16').read_bytes();heights=struct.unpack('<16129H',raw)
def height(x,y):
    fx=max(0,min(125.999,(x+50.4)/.8));fy=max(0,min(125.999,(y+50.4)/.8));ix=int(fx);iy=int(fy);u=fx-ix;v=fy-iy
    return (heights[iy*127+ix]*(1-u)*(1-v)+heights[iy*127+ix+1]*u*(1-v)+heights[(iy+1)*127+ix]*(1-u)*v+heights[(iy+1)*127+ix+1]*u*v-32768)/128
specs={}
for kit in ['fishing_dock','fishing_props','home_life_props','woodland_life_props']:
    meta=json.loads((ART/f'Layout/{kit}.json').read_text(encoding='utf-8'))
    data['palette_srgb_hex'].update(meta['palette_srgb_hex']);data.setdefault('material_properties',{}).update(meta['material_properties'])
    for spec in meta['assets']:
        name=spec['asset_id'];specs[name]=spec
        if name not in bpy.data.objects:
            with bpy.data.libraries.load(str(ROOT/meta['source']),link=False) as (src,dst):dst.objects=[name]
            library.objects.link(dst.objects[0])
        obj=bpy.data.objects[name];obj.hide_render=True;obj.hide_set(True);obj['asset_id']=name;obj['collision']=spec['collision']
        for slot in obj.material_slots:
            canonical=slot.material.name.split('.')[0];existing=bpy.data.materials.get(canonical)
            if existing:slot.material=existing
            else:slot.material.name=canonical
        data['assets'][name]={'file':spec['file'].removeprefix('ArtSource/'),'collision':spec['collision'],'materials':spec['material_slots'],'dimensions_m':spec['dimensions_m'],'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS'}
new_names=[];footprints=[];grounding=[]
def place(label,asset,x,y,z=None,yaw=0,scale=1,group='Home',align=False):
    name='LifeProps_'+label;obj=bpy.data.objects.get(name)
    if obj is None:obj=bpy.data.objects.new(name,bpy.data.objects[asset].data);layout.objects.link(obj)
    obj.location=(x,-y,height(x,y) if z is None else z);obj.rotation_euler=(0,0,-math.radians(yaw));obj.scale=(scale,)*3
    if align:
        # Match the local terrain tangent for ground sheets and low props.
        dx=(height(x+.35,y)-height(x-.35,y))/.7;dy=(height(x,y+.35)-height(x,y-.35))/.7
        normal=Vector((-dx,dy,1)).normalized();q=Vector((0,0,1)).rotation_difference(normal)
        obj.rotation_euler=(q@obj.rotation_euler.to_quaternion()).to_euler()
    obj['asset_id']=asset;obj['collision']=specs[asset]['collision'];obj['group']='LifeProps/'+group
    obj.hide_render=False;obj.hide_set(False);new_names.append(name)
    if z is None:
        bpy.context.view_layer.update()
        # A small burial is preferable to feet visibly floating over the grass.
        feet=[obj.matrix_world@v.co for v in obj.data.vertices if v.co.z<.025]
        residuals=[p.z-height(p.x,-p.y) for p in feet]
        if residuals:obj.location.z-=max(residuals)-.012
        grounding.append({'name':name,'height_m':obj.location.z,'terrain_center_m':height(x,y)})
    if asset!='SM_FishingDock':
        lo=specs[asset]['bounds_min_m'];hi=specs[asset]['bounds_max_m']
        footprints.append({'label':name,'center':[x,y],'yaw_deg':yaw,'local_bounds':[lo[0]*scale,hi[0]*scale,-hi[1]*scale,-lo[1]*scale],'margin':.28})
    return obj
place('FishingDock','SM_FishingDock',4,28,-1.50,group='Fishing')
# Keep the centre line free for WASD access and the two fishing positions.
place('RodStand','SM_FishingRodStand',9.4,29.0,.854,group='Fishing',scale=.86)
place('Chair','SM_FishingChair',8.25,29.0,.854,group='Fishing')
place('Bucket','SM_FishBucket',9.25,26.85,.854,group='Fishing')
place('TackleBox','SM_FishingTackleBox',7.55,26.85,.854,group='Fishing',yaw=-12)
place('Clothesline','SM_HomeClothesline',10.5,45.15,yaw=0)
place('VegetablePatch','SM_VegetablePatch',14.0,44.55,yaw=0,align=True)
place('WateringTools','SM_WateringTools',12.2,44.65,yaw=0,align=True)
place('BootsAndBroom','SM_BootsAndBroom',15.6,42.7,yaw=0,scale=.82)
place('HerbDryingRack','SM_HerbDryingRack',16.0,37.0,yaw=0)
place('Handcart','SM_WoodHandcart',9.2,41.0,yaw=15,scale=.90,align=True)
place('ChoppingStump','SM_ChoppingStump',39.2,3.45,yaw=-18,scale=.90,group='Camp')
place('Picnic','SM_PicnicSet',-8.0,-16.5,yaw=-12,group='Clearing',align=True)
place('ForagingBasket','SM_ForagingBasket',-6.1,-17.0,yaw=20,group='Clearing',align=True)
place('BridgeRepair','SM_BridgeRepairSupplies',-26.8,-13.2,yaw=15,group='BridgeRepair',align=True)
# Two rectangles describe the pier rather than clearing its entire bounding box.
footprints.extend([
 {'label':'DockApproach','center':[4,28],'yaw_deg':0,'local_bounds':[-2.65,3.05,-1.15,1.15],'margin':.3},
 {'label':'DockPlatform','center':[4,28],'yaw_deg':0,'local_bounds':[2.90,6.45,-2.25,2.25],'margin':.3}])
def overlaps(x,y,radius=0):
    for f in footprints:
        a=math.radians(f['yaw_deg']);dx=x-f['center'][0];dy=y-f['center'][1];u=dx*math.cos(a)+dy*math.sin(a);v=-dx*math.sin(a)+dy*math.cos(a)
        x0,x1,y0,y1=f['local_bounds'];m=f['margin']+radius
        if x0-m<u<x1+m and y0-m<v<y1+m:return True
    return False
prior_path=ART/'Layout/life_props_placement.json'
prior=json.loads(prior_path.read_text(encoding='utf-8')) if prior_path.exists() else {}
hidden={e['name']:e for e in prior.get('hidden_original_instances',[])}
for obj in list(layout.objects):
    if obj.name.startswith('LifeProps_') or 'asset_id' not in obj or obj.get('group')=='PreviewOnly':continue
    kind=obj['asset_id'];natural=kind.startswith(('SM_Grass','SM_Fern','SM_Flower','SM_Mushroom','SM_Reeds','SM_Lotus','SM_Lily','SM_Shrub','SM_MossRock'))
    radius=.6 if kind.startswith('SM_MossRock') else .3 if kind=='SM_Shrub' else .15
    if natural and overlaps(obj.location.x,-obj.location.y,radius):
        hidden.setdefault(obj.name,oldrecords[obj.name]);obj['group']='PreviewOnly';obj.hide_render=True;obj.hide_set(True)
# Filtering the backed-up placement layer makes reruns deterministic and reversible.
foliage=json.loads((backup/'foliage_placement.json').read_text(encoding='utf-8'))
survivors=[];removed=[]
for entry in foliage['instances']:
    x,y,_=entry['ue_location_cm'];(removed if overlaps(x/100,y/100,.20) else survivors).append(entry)
foliage['instances']=survivors;foliage['settings']['life_props_footprint_removed']=len(removed)
foliage['settings'].pop('actor_count',None)  # Actual saved actor count belongs to the UE validation report.
foliage['settings']['counts']={asset:sum(o['asset']==asset for o in survivors) for asset in foliage['settings']['counts']}
foliage['settings']['converted_original_actors']=sum(o.get('kind')=='converted' for o in survivors)
foliage['settings']['additional_instances']=sum(o.get('kind')=='additional' for o in survivors)
foliage['settings']['additional_habitats']={h:sum(o.get('kind')=='additional' and o.get('habitat')==h for o in survivors) for h in ['woodland','forest_edge','open_ground']}
(ART/'Layout/foliage_placement.json').write_text(json.dumps(foliage,indent=2),encoding='utf-8')
(ART/'Layout/woodland_layout.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
runpy.run_path(str(ROOT/'Scripts/export_blender_layout.py'),run_name='__main__')
assert (ART/'Layout/landscape_height.r16').read_bytes()==raw,'Existing Landscape changed'
records=json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'))['objects'];index={o['name']:o for o in records}
guards=[{'name':'FishingDock_ShoulderGuard_'+label,'ue_location_cm':[695,y,145],'scale':[.18,1.30,1.8],'ue_rotation_deg':{'pitch':0,'yaw':0,'roll':0}} for label,y in [('LowY',2655),('HighY',2945)]]
report={'version':1,'asset_ids':list(specs),'new_instances':[index[n] for n in new_names],'hidden_original_instances':list(hidden.values()),'foliage_removed_instances':removed,'footprints':footprints,'grounding':grounding,'native_landscape_unchanged':True,'landscape_sha256':hashlib.sha256(raw).hexdigest(),'foliage_survivors':len(survivors),'deck':{'origin_ue_cm':[400,2800,-150],'surface_world_z_cm':85,'approach_world_ue_cm':[160,2800,64],'forward_axis':'+X','clear_walk_lane_y_cm':2800,'guards':guards}}
prior_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
print('LIFE PROPS PLACED '+json.dumps({'new_assets':len(specs),'new_instances':len(new_names),'hidden_originals':len(hidden),'foliage_removed':len(removed),'foliage_remaining':len(survivors),'landscape_unchanged':True}))
