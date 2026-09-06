"""Replace all original rock datablocks while preserving every placement transform."""
import bpy,json,runpy,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource'
backup=ART/'Backups/BeforeSmoothRocks';backup.mkdir(parents=True,exist_ok=True)
for rel in ['Blender/AstraWoodland.blend','Layout/woodland_layout.json']:
    target=backup/Path(rel).name
    if not target.exists():shutil.copy2(ART/rel,target)
bpy.ops.wm.open_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
meta=json.loads((ART/'Layout/forest_smooth_rocks.json').read_text(encoding='utf-8'))
data=json.loads((ART/'Layout/woodland_layout.json').read_text(encoding='utf-8'))
before={o.name:(tuple(o.location),tuple(o.rotation_euler),tuple(o.scale)) for o in bpy.data.collections['02_WoodlandLayout'].objects}
count=0
for item in meta['assets']:
    old=item['original_asset_id'];new=item['asset_id']
    with bpy.data.libraries.load(str(ROOT/meta['source']),link=False) as (src,dst):dst.objects=[new]
    obj=dst.objects[0]
    for target in list(bpy.data.objects):
        if target.get('asset_id')==old or target.name==old:target.data=obj.data;count+=1
    bpy.data.objects.remove(obj,do_unlink=True)
    data['assets'][old].update({'file':item['file'].removeprefix('ArtSource/'),'materials':['M_ForestRockPaint'],
                              'collision':'complex','dimensions_m':item['dimensions_m'],
                              'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS'})
data['palette_srgb_hex']['M_ForestRockPaint']='FFFFFF'
data.setdefault('material_properties',{}).update(meta['material_properties'])
(ART/'Layout/woodland_layout.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
runpy.run_path(str(ROOT/'Scripts/export_blender_layout.py'),run_name='__main__')
after={o.name:(tuple(o.location),tuple(o.rotation_euler),tuple(o.scale)) for o in bpy.data.collections['02_WoodlandLayout'].objects}
assert before==after,'Rock replacement moved existing instances'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/AstraWoodland.blend'))
(ART/'Previews/Blender_SmoothRockPlacementValidation.json').write_text(json.dumps({'passed':True,'replaced_datablocks':count,'all_layout_transforms_unchanged':True},indent=2),encoding='utf-8')
print('SMOOTH ROCKS APPLIED '+str(count))
