"""Replace only the five rock datablocks; preserve every authored placement."""
import bpy,json,runpy,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource'
backup=ART/'Backups/BeforeFracturedRocks';backup.mkdir(parents=True,exist_ok=True)
for rel in ['Blender/AstraWoodland.blend','Layout/woodland_layout.json','Previews/UE_SmoothRocksValidation.json']:
    target=backup/Path(rel).name
    if not target.exists():shutil.copy2(ART/rel,target)
bpy.ops.wm.open_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
meta=json.loads((ART/'Layout/forest_fractured_rocks.json').read_text(encoding='utf-8'))
data_path=ART/'Layout/woodland_layout.json';data=json.loads(data_path.read_text(encoding='utf-8'))
before_records=data['objects'];height_before=(ART/'Layout/landscape_height.r16').read_bytes()
collection=bpy.data.collections['02_WoodlandLayout']
before={o.name:(tuple(o.location),tuple(o.rotation_euler),tuple(o.scale)) for o in collection.objects}
count=0;replacements=[]
for item in meta['assets']:
    old=item['original_asset_id'];new=item['asset_id']
    old_object=bpy.data.objects[old];material=old_object.data.materials[0]
    with bpy.data.libraries.load(str(ROOT/meta['source']),link=False) as (src,dst):dst.objects=[new]
    obj=dst.objects[0]
    temporary_materials=list(obj.data.materials)
    temporary_images={n.image for m in temporary_materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}
    obj.data.materials.clear();obj.data.materials.append(material)
    for target in list(bpy.data.objects):
        if target.get('asset_id')==old or target.name==old:
            target.data=obj.data;count+=1;replacements.append(target.name)
    bpy.data.objects.remove(obj,do_unlink=True)
    for m in temporary_materials:
        if m and m.users==0:bpy.data.materials.remove(m)
    for img in temporary_images:
        if img.users==0:bpy.data.images.remove(img)
    data['assets'][old].update({'file':item['file'].removeprefix('ArtSource/'),'materials':['M_ForestRockPaint'],
       'collision':'complex','dimensions_m':item['dimensions_m'],'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS'})
data['rock_model_revision']={'style':'fractured broad faces with softened edges','metadata':'Layout/forest_fractured_rocks.json'}
data_path.write_text(json.dumps(data,indent=2),encoding='utf-8')
runpy.run_path(str(ROOT/'Scripts/export_blender_layout.py'),run_name='__main__')
after={o.name:(tuple(o.location),tuple(o.rotation_euler),tuple(o.scale)) for o in collection.objects}
after_records=json.loads(data_path.read_text(encoding='utf-8'))['objects']
assert before==after and before_records==after_records,'Rock shape replacement changed placement data'
assert (ART/'Layout/landscape_height.r16').read_bytes()==height_before,'Landscape was changed'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
report={'passed':True,'replaced_datablocks':count,'all_layout_transforms_unchanged':True,'all_layout_records_unchanged':True,
        'landscape_unchanged':True,'placement_record_count':len(after_records),'replaced_objects':replacements,
        'landscape_sha256':hashlib.sha256(height_before).hexdigest()}
(ART/'Previews/Blender_FracturedRockPlacementValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FRACTURED ROCKS APPLIED '+json.dumps({k:v for k,v in report.items() if k!='replaced_objects'}))
