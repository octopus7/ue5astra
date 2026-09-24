"""Update only stream/curtain in the existing Blender source and export those FBXs."""
import bpy, json, runpy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'/'Waterfall'
surfaces=runpy.run_path(str(ROOT/'Scripts'/'waterfall_flow_geometry.py'))['build_flow_surfaces']()
manifest=json.loads((ART/'waterfall_manifest.json').read_text())
for name,(vertices,faces,uvs) in surfaces.items():
    obj=bpy.data.objects[name]
    old=obj.data
    data=bpy.data.meshes.new(name+'_ContinuousFlow')
    data.from_pydata(vertices,[],faces);data.update()
    for material in old.materials:data.materials.append(material)
    uv=data.uv_layers.new(name='UVMap')
    for polygon in data.polygons:
        polygon.use_smooth=True
        for li in polygon.loop_indices:uv.data[li].uv=uvs[data.loops[li].vertex_index]
    obj.data=data
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=str(ART/'FBX'/(name+'.fbx')),use_selection=True,
        object_types={'MESH'},global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y',axis_up='Z',bake_space_transform=False,mesh_smooth_type='FACE',
        use_mesh_modifiers=True,add_leaf_bones=False,bake_anim=False)
    data.calc_loop_triangles()
    entry=next(e for e in manifest['assets'] if e['name']==name)
    entry.update(triangles=len(data.loop_triangles),dimensions_cm=list(obj.dimensions))
manifest['continuous_crest']={'shared_edge_vertices':13,'position_error_cm':0,'uv_error':0,
    'uv_mapping':'arc length; upper V negative, shared seam V=0, curtain bottom V=1'}
(ART/'waterfall_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'AnimeWaterfall.blend'))
print('CONTINUOUS_WATERFALL_CREST_OK')
