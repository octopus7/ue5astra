"""Update only water meshes in the saved Blender scene, preserving manual layout."""
import bpy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts'))
from water_geometry import water_geometry,add_edge_mask
ART=ROOT/'ArtSource'
bpy.ops.wm.open_mainfile(filepath=str(ART/'Blender'/'AstraWoodland.blend'))
metadata=json.loads((ART/'Layout'/'woodland_layout.json').read_text(encoding='utf-8'))
for asset in ['SM_LakeSurface','SM_StreamSurface','SM_Puddle']:
    obj=bpy.data.objects.get(asset)
    old_mesh=obj.data
    verts,faces,weights=water_geometry(asset)
    mesh=bpy.data.meshes.new(asset+'_SoftEdge')
    mesh.from_pydata(verts,[],faces);mesh.update()
    for mat in old_mesh.materials:mesh.materials.append(mat)
    add_edge_mask(mesh,weights)
    for linked in list(bpy.data.objects):
        if linked.type=='MESH' and linked.data==old_mesh:linked.data=mesh
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{asset}.fbx'),use_selection=True,
        object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,
        mesh_smooth_type='FACE',use_mesh_modifiers=True)
    metadata['assets'][asset]['dimensions_m']=list(obj.dimensions)
    obj.select_set(False);obj.hide_set(True)
    print(f'{asset}: {len(verts)} vertices; edge mask {min(weights)} to {max(weights)}')
(ART/'Layout'/'woodland_layout.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
for record in metadata['objects']:
    if record['asset']=='SM_StreamSurface':
        record['group']='PreviewOnly'
        o=bpy.data.objects.get(record['name'])
        if o:o['group']='PreviewOnly';o.hide_render=True;o.hide_set(True)
(ART/'Layout'/'woodland_layout.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'AstraWoodland.blend'))
