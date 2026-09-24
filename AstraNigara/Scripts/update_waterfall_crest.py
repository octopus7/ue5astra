"""Reimport only the two joined water surfaces and refresh their shared shader."""
import hashlib,json,runpy
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
dest='/Game/VFX/Waterfall'
protected=[root/'Content/Maps/L_AnimeWaterfall.umap',root/'Content/VFX/Waterfall/NS_AnimeWaterfall.uasset']
protected+=list((root/'Content/VFX/Waterfall/Foliage').glob('*.uasset'))
protected+=list((root/'Content/VFX/Waterfall/Blueprints').glob('*.uasset'))
protected+=[root/'Content/VFX/Waterfall/Meshes/SM_WF_ImpactApron.uasset']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
tasks=[]
for name in ('SM_WF_UpperStream','SM_WF_WaterCurtain'):
    task=unreal.AssetImportTask()
    task.filename=str(root/'ArtSource/Waterfall/FBX'/(name+'.fbx'))
    task.destination_path=dest+'/Meshes';task.destination_name=name
    task.automated=True;task.save=False;task.replace_existing=True;task.factory=unreal.FbxFactory()
    opt=unreal.FbxImportUI();opt.import_mesh=True;opt.import_as_skeletal=False
    opt.import_materials=False;opt.import_textures=False;opt.import_animations=False
    opt.automated_import_should_detect_type=False;opt.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    data=opt.static_mesh_import_data;data.combine_meshes=True;data.build_nanite=False
    data.generate_lightmap_u_vs=False;data.auto_generate_collision=False
    data.convert_scene=True;data.convert_scene_unit=True;data.import_uniform_scale=1.
    data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
    task.options=opt;tasks.append(task)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
material=unreal.load_asset(dest+'/Materials/M_WF_Waterfall_UV')
for task in tasks:
    mesh=unreal.load_asset(dest+'/Meshes/'+task.destination_name)
    mesh.set_material(0,material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(mesh)
codes=[e for e in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if e.get_outer()==material]
flow=next(e for e in codes if 'float v=(1-UV.y)-T*Speed;' in e.get_editor_property('code'))
code=flow.get_editor_property('code')
if 'float crest=' not in code:
    code=code.replace('return lerp(blue', 'float crest=exp(-pow(((1-UV.y)-.18)/.013,2))*.10*smoothstep(-.3,.6,sin(u*37+v*5));\nreturn lerp(blue')
    code=code.replace('saturate(white+churn)', 'saturate(white+churn+crest)')
    flow.set_editor_property('code',code)
    unreal.MaterialEditingLibrary.recompile_material(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
runpy.run_path(str(root/'Scripts/validate_waterfall.py'))
report={'passed':True,'unchanged_protected_assets':len(hashes),'shared_seam_vertices':13,
        'source_geometry':json.loads((root/'ArtSource/Waterfall/waterfall_manifest.json').read_text())['continuous_crest']}
(root/'Saved/waterfall_crest_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('WATERFALL_CREST_UPDATED_OK')
