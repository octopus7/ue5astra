"""Place the independently modeled forest kit and sculpt a walkable camp hill."""
import bpy,json,math,runpy,shutil
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource'
backup=ART/'Backups/BeforeForestExpansion';backup.mkdir(parents=True,exist_ok=True)
for rel in ['Blender/AstraWoodland.blend','Layout/woodland_layout.json','Layout/landscape_height.r16']:
    target=backup/Path(rel).name
    if not target.exists():shutil.copy2(ART/rel,target)
bpy.ops.wm.open_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
scene=bpy.context.scene;layout=bpy.data.collections['02_WoodlandLayout'];library=bpy.data.collections['01_MeshLibrary']
data=json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'))
metas=[json.loads((ART/f'Layout/forest_{name}.json').read_text(encoding='utf-8')) for name in ['cliffs','tent','signs','cooking']]
asset_specs={}
for meta in metas:
    data['palette_srgb_hex'].update(meta['palette_srgb_hex'])
    data.setdefault('material_properties',{}).update(meta['material_properties'])
    for spec in meta['assets']:
        name=spec['asset_id'];asset_specs[name]=spec
        if name not in bpy.data.objects:
            with bpy.data.libraries.load(str(ROOT/meta['source']),link=False) as (src,dst):dst.objects=[name]
            obj=dst.objects[0];library.objects.link(obj)
            for slot in obj.material_slots:
                canonical=slot.material.name.split('.')[0]
                existing=bpy.data.materials.get(canonical)
                if existing:slot.material=existing
                else:slot.material.name=canonical
        obj=bpy.data.objects[name];obj.hide_render=True;obj.hide_set(True)
        obj['asset_id']=name;obj['collision']=spec['collision']
        data['assets'][name]={'file':spec['file'].removeprefix('ArtSource/'),'collision':spec['collision'],
                             'materials':spec['material_slots'],'dimensions_m':spec['dimensions_m']}
ground=bpy.data.objects['Landscape_Source_100m']
base=ground.data.attributes.get('ForestPreHillHeight')
if base is None:
    base=ground.data.attributes.new('ForestPreHillHeight','FLOAT','POINT')
    for v,a in zip(ground.data.vertices,base.data):a.value=v.co.z
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
source={};old={};new={}
for v,a in zip(ground.data.vertices,base.data):
    key=(round((v.co.x+50.4)/.8),round((-v.co.y+50.4)/.8));source[key]=a.value;old[key]=v.co.z
def sample(values,x,y):
    fx=max(0,min(125.999,(x+50.4)/.8));fy=max(0,min(125.999,(y+50.4)/.8));ix=int(fx);iy=int(fy);u=fx-ix;v=fy-iy
    return values[ix,iy]*(1-u)*(1-v)+values[ix+1,iy]*u*(1-v)+values[ix,iy+1]*(1-u)*v+values[ix+1,iy+1]*u*v
for v,a in zip(ground.data.vertices,base.data):
    x,y=v.co.x,-v.co.y;key=(round((x+50.4)/.8),round((y+50.4)/.8))
    weight=smooth(27.9,30.8,x)*(1-smooth(42.5,48,x))*(1-smooth(8,12,abs(y+3)))
    z=a.value*(1-weight)+5.2*weight
    ramp=(1-smooth(1.8,3.1,abs(x-33)))*(1-smooth(-10,-8,y))*smooth(-21,-20,y)
    rampz=a.value+(5.2-a.value)*smooth(-20,-10,y)
    z=z*(1-ramp)+rampz*ramp
    v.co.z=round(z*128)/128;new[key]=v.co.z
ground.data.update()
prior_path=ART/'Layout/forest_expansion.json'
prior=json.loads(prior_path.read_text(encoding='utf-8')) if prior_path.exists() else {}
hidden={o['name']:o for o in prior.get('hidden_original_instances',[])};changed={o['name']:None for o in prior.get('modified_existing_instances',[])}
original_records={o['name']:o for o in data['objects']}
for obj in list(layout.objects):
    if obj.name.startswith('ForestExpansion_') or 'asset_id' not in obj:continue
    if obj.get('group')=='PreviewOnly':continue
    x,y=obj.location.x,-obj.location.y;kind=obj.get('asset_id','')
    tree=kind.startswith(('SM_Oak','SM_Fir'))
    clear_camp=((x-36)/8.8)**2+((y+3)/10.5)**2<1
    clear_front=tree and 23<x<32 and -12<y<7
    clear_ramp=abs(x-33)<2.5 and -20<y<-9
    natural=kind.startswith(('SM_Oak','SM_Fir','SM_Grass','SM_Fern','SM_Flower','SM_Mushroom','SM_MossRock','SM_FallenLog'))
    if natural and (clear_camp or clear_front or clear_ramp):
        hidden.setdefault(obj.name,original_records[obj.name]);obj['group']='PreviewOnly';obj.hide_render=True;obj.hide_set(True)
    elif natural:
        dz=sample(new,x,y)-sample(old,x,y)
        if abs(dz)>.002:obj.location.z+=dz;changed[obj.name]=obj
path=[[[26,-20],[33,-19],[33,-12],[33,-7]],1.35]
if path not in data['paths']:data['paths'].append(path)
data['clearings']=[{'center':[36,-3],'radii':[6.7,7.3]}]
new_names=[]
def place(name,asset,x,y,z=None,yaw=0,scale=1):
    name='ForestExpansion_'+name;obj=bpy.data.objects.get(name)
    if obj is None:obj=bpy.data.objects.new(name,bpy.data.objects[asset].data);layout.objects.link(obj)
    scale=(scale,scale,scale) if isinstance(scale,(int,float)) else scale
    spec=asset_specs[asset]
    obj.location=(x,-y,(sample(new,x,y)-spec['bounds_min_m'][2]*scale[2]) if z is None else z)
    obj.rotation_euler=(0,0,-math.radians(yaw));obj.scale=scale
    obj['asset_id']=asset;obj['collision']='none' if asset in ['SM_CampBedroll','SM_CampSatchel','SM_CampLantern'] else 'complex'
    obj['group']='ForestExpansion/Cliffs' if 'Cliff' in asset else 'ForestExpansion/Camp'
    obj.hide_render=False;obj.hide_set(False);new_names.append(name)
for label,asset,x,y,top,yaw,scale in [
 ('CliffA','SM_ForestCliff_A',29.3,-8,5.24,-3,1),
 ('CliffB','SM_ForestCliff_B',29.45,-3.1,5.43,2,1),
 ('CliffC','SM_ForestCliff_C',29.35,1.85,5.18,-4,1),
 ('CliffSide','SM_ForestCliff_A',30.2,4.7,4.98,68,.78)]:
    place(label,asset,x,y,top-asset_specs[asset]['bounds_max_m'][2]*scale,yaw,scale)
place('Tent','SM_ForestTent',38,-4,yaw=0)
place('Bedroll','SM_CampBedroll',36.8,-3.2,scale=.78)
place('Satchel','SM_CampSatchel',36.8,-5.8,scale=.75)
place('Fire','SM_Campfire',33,.6,scale=.85)
place('CookFire','SM_Campfire',36,3.1,scale=.44)
place('Tripod','SM_CampCookingTripod',36,3.1)
place('Kitchen','SM_CampCookingStation',37.5,1.25,yaw=-12)
place('LanternTent','SM_CampLantern',35.8,-5.4)
place('Woodpile','SM_CampWoodpile',39,1.2,yaw=12)
for i,(x,y,a) in enumerate([(31.3,.2,-15),(33,2.35,10),(34.3,-.8,90)]):place('Stool'+str(i),'SM_CampLogStool',x,y,yaw=a)
place('SignCamp','SM_ForestSignpost',29.3,-17,yaw=-12)
place('SignClearing','SM_ForestSignpost',-2.1,-13,yaw=0)
(ART/'Layout/woodland_layout.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
runpy.run_path(str(ROOT/'Scripts/export_blender_layout.py'),run_name='__main__')
data=json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'));records={o['name']:o for o in data['objects']}
data['terrain']['camp_hill']={'plateau_height_m':5.2,'entry_route_ue_m':[[33,-20],[33,-10]],'cliff_burial':'actor Z = desired rim Z - local mesh max Z * scale Z'}
(ART/'Layout/woodland_layout.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
report={'version':1,'source':'Scripts/place_forest_expansion.py','asset_ids':list(asset_specs),
 'new_instances':[records[n] for n in new_names],'hidden_original_instances':list(hidden.values()),
 'modified_existing_instances':[records[n] for n in changed],
 'height_samples_changed':sum(abs(new[k]-source[k])>.001 for k in new),
 'camp_height_m':5.2,'camp_route':[[33,-20],[33,-10]],'native_landscape_preserved':True}
prior_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
# Match the main ground preview to the camp clearing and access trail.
colors=ground.data.color_attributes.get('TerrainTint')
if colors:
    for v,c in zip(ground.data.vertices,colors.data):
        x,y=v.co.x,-v.co.y;d=math.hypot((x-36)/6.7,(y+3)/7.3)
        if d<1.05:c.color=(.43,.33,.15,1) if d<.95 else (.26,.33,.13,1)
cam=bpy.data.objects.get('ForestExpansionPreviewCamera')
if cam is None:bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='ForestExpansionPreviewCamera'
cam.location=(20,3,24);cam.rotation_euler=(Vector((35,3,3.3))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=26;scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1600;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.filepath=str(ART/'Previews/Blender_ForestCampSite.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
bpy.ops.render.render(write_still=True)
print('FOREST EXPANSION PLACED '+json.dumps({k:v for k,v in report.items() if k not in ['new_instances','hidden_original_instances','modified_existing_instances']}))
