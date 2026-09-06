"""Convert small plants to native Unreal Foliage and add restrained habitat clusters."""
import unreal,json,math,random,struct,shutil
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();ART=ROOT/'ArtSource'
DATA=json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'))
backup=ART/'Backups/BeforeFoliage';backup.mkdir(parents=True,exist_ok=True)
if not (backup/'L_AstraWoodland.umap').exists():shutil.copy2(ROOT/'Content/Astra/Maps/L_AstraWoodland.umap',backup/'L_AstraWoodland.umap')
unreal.EditorLevelLibrary.load_level('/Game/Astra/Maps/L_AstraWoodland')
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
es=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=es.get_all_level_actors();index={a.get_actor_label():a for a in actors}
species=['SM_Grass','SM_Fern','SM_Flowers','SM_Mushrooms','SM_Reeds']
species=[s for s in species if s in DATA['assets']]
transforms={s:[] for s in species};records=[];preserved=[];rng=random.Random(73951)
for entry in DATA['objects']:
    name=entry['name'];kind=entry['asset'];a=index.get(name)
    if kind not in transforms or entry['group']=='PreviewOnly' or not isinstance(a,unreal.StaticMeshActor):continue
    owned=str(a.get_folder_path())=='PreservedBeforeFoliage'
    if a.get_editor_property('hidden') and not owned:continue
    transforms[kind].append(a.get_actor_transform());preserved.append(a)
    records.append({'source_actor':name,'asset':kind,'ue_location_cm':entry['ue_location_cm'],'ue_rotation_deg':entry['ue_rotation_deg'],'scale':entry['scale'],'kind':'converted'})
heights=struct.unpack('<16129H',(ART/'Layout/landscape_height.r16').read_bytes())
def height(x,y):
    fx=max(0,min(125.999,(x+50.4)/.8));fy=max(0,min(125.999,(y+50.4)/.8));ix=int(fx);iy=int(fy);u=fx-ix;v=fy-iy
    h=heights[iy*127+ix]*(1-u)*(1-v)+heights[iy*127+ix+1]*u*(1-v)+heights[(iy+1)*127+ix]*(1-u)*v+heights[(iy+1)*127+ix+1]*u*v
    return (h-32768)/128
def segdist(x,y,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-a[0]-dx*t,y-a[1]-dy*t)
def path_distance(x,y):
    return min(segdist(x,y,a,b)-w for pts,w in DATA['paths'] for a,b in zip(pts,pts[1:]))
trees=[(o['ue_location_cm'][0]/100,o['ue_location_cm'][1]/100) for o in DATA['objects'] if o['asset'].startswith(('SM_Oak','SM_Fir')) and o['group']!='PreviewOnly']
extra_count=0;habitats={'woodland':0,'forest_edge':0,'open_ground':0}
for gx in range(61):
    for gy in range(61):
        x=-48+gx*1.6+rng.uniform(-.65,.65);y=-48+gy*1.6+rng.uniform(-.65,.65)
        z=height(x,y);pd=path_distance(x,y)
        if z<.30 or pd<.7:continue
        if math.hypot((x+5)*.9,y+10)<7.8:continue
        if 12.5<x<23.8 and 35.3<y<45.3:continue
        if ((x-36)/8)**2+((y+3)/8.7)**2<1:continue
        if 26.5<x<32.8 and -12.5<y<7:continue
        if any(((x-px)/(rx+.5))**2+((y-py)/(ry+.5))**2<1 for px,py,rx,ry in DATA['puddles']):continue
        slope=math.hypot(height(x+.4,y)-height(x-.4,y),height(x,y+.4)-height(x,y-.4))/.8
        if slope>.65:continue
        tree_distance=min(math.hypot(x-tx,y-ty) for tx,ty in trees)
        if tree_distance<.65:continue
        habitat='woodland' if tree_distance<5.5 else 'forest_edge' if tree_distance<9 else 'open_ground'
        chance={'woodland':.47,'forest_edge':.25,'open_ground':.055}[habitat]
        patch=.35+.65*(.5+.5*math.sin(x*.51+math.cos(y*.28))*math.cos(y*.42))
        if rng.random()>chance*patch:continue
        pick=rng.random();kind='SM_Grass' if pick<.79 else 'SM_Fern' if pick<.96 else 'SM_Flowers'
        scale=rng.uniform(.5,.88) if kind=='SM_Grass' else rng.uniform(.38,.64) if kind=='SM_Fern' else rng.uniform(.55,.85)
        yaw=rng.uniform(-180,180);p=[x*100,y*100,z*100-1.5]
        rotation=unreal.Rotator(yaw=yaw);t=unreal.Transform(location=unreal.Vector(*p),rotation=rotation,scale=unreal.Vector(scale,scale,scale))
        transforms[kind].append(t);extra_count+=1;habitats[habitat]+=1
        records.append({'asset':kind,'ue_location_cm':p,'ue_rotation_deg':{'pitch':0,'yaw':yaw,'roll':0},'scale':[scale]*3,'kind':'additional','habitat':habitat})
EAL=unreal.EditorAssetLibrary;AT=unreal.AssetToolsHelpers.get_asset_tools()
plant_materials={}
for kind in species:
    mesh=EAL.load_asset('/Game/Astra/Meshes/'+kind)
    for slot in mesh.get_editor_property('static_materials'):
        material=slot.material_interface
        if isinstance(material,unreal.Material):plant_materials[material.get_path_name()]=material
for material in plant_materials.values():
    unreal.MaterialEditingLibrary.set_material_usage(material,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not EAL.save_loaded_asset(material,only_if_is_dirty=False):raise RuntimeError('Foliage material usage save failed '+material.get_name())
counts={};type_paths=[]
for kind,items in transforms.items():
    name='FT_Astra_'+kind.removeprefix('SM_');path='/Game/Astra/Foliage/'+name
    ft=EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(name,'/Game/Astra/Foliage',unreal.FoliageType_InstancedStaticMesh,unreal.FoliageType_InstancedStaticMeshFactory())
    ft.set_editor_property('mesh',EAL.load_asset('/Game/Astra/Meshes/'+kind))
    ft.set_editor_property('density',40.0);ft.set_editor_property('enable_density_scaling',True)
    body=ft.get_editor_property('body_instance');body.set_editor_property('collision_profile_name','NoCollision');body.set_editor_property('collision_enabled',unreal.CollisionEnabled.NO_COLLISION);ft.set_editor_property('body_instance',body)
    if not EAL.save_loaded_asset(ft):raise RuntimeError('Foliage type save failed '+name)
    unreal.InstancedFoliageActor.remove_all_instances(world,ft)
    unreal.InstancedFoliageActor.add_instances(world,ft,items)
    counts[kind]=len(items);type_paths.append(path)
for a in preserved:
    a.set_actor_hidden_in_game(True);a.set_actor_enable_collision(False);a.set_folder_path('PreservedBeforeFoliage')
    a.set_is_temporarily_hidden_in_editor(True);c=a.static_mesh_component;c.set_visibility(False);c.set_hidden_in_game(True);c.set_collision_profile_name('NoCollision')
foliage_actors=[a for a in es.get_all_level_actors() if isinstance(a,unreal.InstancedFoliageActor)]
actual={s:0 for s in species}
for a in foliage_actors:
    for c in a.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
        if c.static_mesh and c.static_mesh.get_name() in actual:
            actual[c.static_mesh.get_name()]+=c.get_instance_count()
            c.set_collision_profile_name('NoCollision')
if counts!=actual:raise RuntimeError('Foliage instance count differs '+json.dumps({'expected':counts,'actual':actual}))
camera=index.get('Camera_Foliage')
look=[-1500,-900,80];arm=2700;p=math.radians(58)
if camera is None:
    camera=es.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(look[0]-arm*math.cos(p),look[1],look[2]+arm*math.sin(p)),unreal.Rotator(pitch=-58))
    camera.set_actor_label('Camera_Foliage');camera.set_folder_path('ReviewCameras')
cc=camera.camera_component;cc.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC);cc.set_editor_property('ortho_width',1900);cc.set_editor_property('constrain_aspect_ratio',False)
if not unreal.EditorLevelLibrary.save_current_level():raise RuntimeError('Foliage map save failed')
report={'status':'success','seed':73951,'native_foliage_actor_count':len(foliage_actors),'foliage_types':type_paths,
        'converted_original_actors':len(preserved),'additional_instances':extra_count,'additional_habitats':habitats,
        'counts':actual,'actor_count':len(es.get_all_level_actors()),'path_exclusion_margin_m':.7,'plant_collision':'NoCollision',
        'source_actors_preserved_hidden':True,'placement_layer':'ArtSource/Layout/foliage_placement.json'}
(ART/'Layout/foliage_placement.json').write_text(json.dumps({'settings':report,'instances':records},indent=2),encoding='utf-8')
(ART/'Previews/UE_FoliageValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('ASTRA NATIVE FOLIAGE SAVED '+json.dumps(report))
