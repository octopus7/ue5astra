"""Refresh only submerged-rock smooth normals, preserving authored geometry.

Blender background: --python this_file.py. Then run a fresh process with
--python this_file.py -- --verify-only for exact FBX normal/UV/colour checks.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import bpy

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
NAMES=('SM_SubmergedRock_Round_01','SM_SubmergedRock_Flat_01',
       'SM_SubmergedRock_Small_01','SM_SubmergedPebbles_01')
KIT=ART/'Blender'/'AstraShorelineKit.blend'
SITE=ART/'Blender'/'AstraLakeshoreReview.blend'
MANIFEST=ART/'Layout'/'shoreline_assets.json'
REPORT=ART/'Previews'/'ShorelineRockNormals_FBXValidation.json'


def digest(obj,include_smooth=False):
    mesh=obj.data
    payload={'verts':[list(v.co) for v in mesh.vertices],
             'faces':[(list(p.vertices),p.material_index) for p in mesh.polygons],
             'uv':{layer.name:[list(d.uv) for d in layer.data] for layer in mesh.uv_layers},
             'colours':{attr.name:[list(d.color) for d in attr.data] for attr in mesh.color_attributes},
             'materials':[mat.name for mat in mesh.materials],
             'location':list(obj.location),'rotation':list(obj.rotation_euler),'scale':list(obj.scale)}
    if include_smooth:payload['smooth']=[p.use_smooth for p in mesh.polygons]
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def scene_digest():
    return {obj.name:digest(obj,include_smooth=obj.get('asset_id') not in NAMES and obj.name not in NAMES)
            for obj in bpy.data.objects if obj.type=='MESH'}


def smooth_loaded_rocks():
    meshes={}
    for obj in bpy.data.objects:
        if obj.type=='MESH' and (obj.get('asset_id') in NAMES or obj.name in NAMES):
            meshes[obj.data.name]=obj.data
    assert meshes,'No rock meshes in loaded scene'
    for mesh in meshes.values():
        for face in mesh.polygons:face.use_smooth=True
        mesh.update()
    return len(meshes)


def refresh():
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    protected={ART/spec['file']:hashlib.sha256((ART/spec['file']).read_bytes()).hexdigest()
               for name,spec in manifest['assets'].items() if name not in NAMES}
    protected.update({ART/'Meshes'/'ShorelineSite'/name:hashlib.sha256((ART/'Meshes'/'ShorelineSite'/name).read_bytes()).hexdigest()
                      for name in ('SM_ShorelineSite_CurvedBed.fbx','SM_ShorelineSite_BankWest.fbx',
                                   'SM_ShorelineSite_BankLow.fbx','SM_ShorelineSite_BankEast.fbx')})
    bpy.ops.wm.open_mainfile(filepath=str(KIT))
    before=scene_digest()
    mesh_count=smooth_loaded_rocks()
    assert scene_digest()==before,'Kit geometry, UV, colour, slots or transforms changed'
    for name in NAMES:
        obj=bpy.data.objects[name]
        hidden=obj.hide_get()
        collection_visibility=[(collection,collection.hide_viewport) for collection in obj.users_collection]
        for collection,_ in collection_visibility:collection.hide_viewport=False
        obj.hide_set(False)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        assert obj in bpy.context.selected_objects,'Rock library still hidden from export selection'
        target=ART/manifest['assets'][name]['file']
        bpy.ops.export_scene.fbx(filepath=str(target),use_selection=True,object_types={'MESH'},
            apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
            bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True,
            use_custom_props=True,colors_type='LINEAR',prioritize_active_color=True)
        obj.hide_set(hidden)
        for collection,was_hidden in collection_visibility:collection.hide_viewport=was_hidden
        obj['normal_shading']='smooth; geometry/UV/material slots unchanged'
        manifest['assets'][name]['metadata']['normal_shading']=obj['normal_shading']
        manifest['assets'][name]['sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(KIT))
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    native_report_path=ART/'Previews'/'Shoreline_MeshValidation.json'
    native_report=json.loads(native_report_path.read_text(encoding='utf-8'))
    for name in NAMES:
        native_report['assets'][name]['smooth_shaded_polygons']=len(bpy.data.objects[name].data.polygons)
        native_report['assets'][name]['geometry_uv_colour_slots_preserved']=True
    native_report_path.write_text(json.dumps(native_report,indent=2)+'\n',encoding='utf-8')
    bpy.ops.wm.open_mainfile(filepath=str(SITE))
    before_site=scene_digest()
    site_mesh_count=smooth_loaded_rocks()
    assert scene_digest()==before_site,'Site geometry, UV, colour, slots or transforms changed'
    bpy.ops.wm.save_as_mainfile(filepath=str(SITE))
    site_manifest_path=ART/'Layout'/'shoreline_site.json'
    site_manifest=json.loads(site_manifest_path.read_text(encoding='utf-8'))
    for name in NAMES:site_manifest['assets'][name]=manifest['assets'][name]
    site_manifest_path.write_text(json.dumps(site_manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert all(hashlib.sha256(path.read_bytes()).hexdigest()==sha for path,sha in protected.items())
    scene=bpy.context.scene
    scene.render.filepath=str(ART/'Previews'/'Blender_ShorelineSite.png')
    if '--skip-render' not in sys.argv:bpy.ops.render.render(write_still=True)
    print('SUBMERGED_ROCK_SMOOTH_REFRESH '+json.dumps({'kit_rock_meshes':mesh_count,
        'site_rock_meshes':site_mesh_count,'geometry_uv_colour_slots_transforms_preserved':True,
        'protected_shelf_bank_and_site_fbx_unchanged':True}))


def verify():
    module_spec=importlib.util.spec_from_file_location('site_fbx_audit',ROOT/'Scripts'/'validate_shoreline_site_fbx.py')
    audit=importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(audit)
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    native=json.loads((ART/'Previews'/'Shoreline_MeshValidation.json').read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(KIT),link=False) as (src,dst):dst.objects=list(NAMES)
    sources={obj.name:audit.snapshot(obj) for obj in dst.objects}
    results={}
    for name in NAMES:
        spec=dict(manifest['assets'][name])
        spec['validation']={'triangles':spec['triangles'],'signed_volume_m3':native['assets'][name]['signed_volume_m3']}
        assert sources[name]['smooth_face_count']==spec['triangles']
        results[name]=audit.verify_asset(name,spec,sources[name])
        assert results[name]['imported_smooth_face_count']==spec['triangles']
    report={'passed':True,'blender':bpy.app.version_string,
            'scope':'Fresh Blender process: four submerged rock FBX smooth normals; unchanged shape, triangles, pivots, UV, colour, material slots. No new textures/materials.',
            'assets':results}
    REPORT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    common=ART/'Previews'/'Shoreline_FBXValidation.json'
    common_report=json.loads(common.read_text(encoding='utf-8'))
    for name,result in results.items():common_report['assets'][name]=result
    common.write_text(json.dumps(common_report,indent=2)+'\n',encoding='utf-8')
    print('SUBMERGED_ROCK_NORMALS_FBX_PASS '+json.dumps({name:{'smooth_faces':result['imported_smooth_face_count'],
           'max_normal_error_deg':result['max_loop_normal_angle_error_deg']} for name,result in results.items()}))


if __name__=='__main__':
    verify() if '--verify-only' in sys.argv else refresh()
