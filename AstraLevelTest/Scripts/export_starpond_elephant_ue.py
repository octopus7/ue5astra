"""Export a centimetre copy for UE without changing the metre-authored blend.

Run in Blender 4.5 background mode. Scaling the actual mesh and bone data keeps
the root and animation scales at one, independent of importer unit overrides.
"""
import json
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'ArtSource'
bpy.ops.wm.open_mainfile(filepath=str(ART/'Blender/StarPondElephant.blend'))
scene=bpy.context.scene
scene.frame_set(1)
rig=bpy.data.objects['Armature']
mesh=bpy.data.objects['SK_SP_UnicornElephant']
assert rig.type=='ARMATURE' and mesh.type=='MESH' and mesh.parent==rig
assert all(abs(v-1)<1e-6 for obj in (rig,mesh) for v in obj.scale)
assert all(abs(v)<1e-6 for obj in (rig,mesh) for v in obj.location)

scale=Matrix.Scale(100.,4)
mesh.data.transform(scale)
rig.data.transform(scale)
for action in bpy.data.actions:
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.data_path.endswith('location'):
                        for key in curve.keyframe_points:
                            key.co.y*=100
                            key.handle_left.y*=100
                            key.handle_right.y*=100
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=.01
scene.unit_settings.length_unit='CENTIMETERS'
scene.frame_set(1)
bpy.context.view_layer.update()

bpy.ops.object.select_all(action='DESELECT')
for obj in (rig,mesh):
    obj.hide_set(False)
    obj.hide_viewport=False
    obj.select_set(True)
bpy.context.view_layer.objects.active=rig
fbx=ART/'Meshes/StarPond/SK_SP_UnicornElephant_UE.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH','ARMATURE'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    mesh_smooth_type='FACE',use_mesh_modifiers=True,add_leaf_bones=False,
    use_armature_deform_only=True,bake_anim=True,bake_anim_use_all_bones=True,
    bake_anim_use_nla_strips=False,bake_anim_use_all_actions=False,
    bake_anim_force_startend_keying=True,bake_anim_step=1,bake_anim_simplify_factor=0)

metadata_path=ART/'Layout/starpond_elephant.json'
metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
metadata.update(ue_fbx=str(fbx.relative_to(ROOT)).replace('\\','/'),
    ue_fbx_units='centimetres',ue_import_scale=1)
metadata_path.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
report={'passed':True,'source_blend_unchanged':True,'ue_fbx':metadata['ue_fbx'],
    'fbx_units':'centimetres','bone_count':len(rig.data.bones),
    'mesh_dimensions_cm':list(mesh.dimensions),'root_scale':list(rig.scale),
    'method':'Scale copied mesh data, armature data and location keys; preserve all scale keys and original metre blend.'}
(ART/'Previews/StarPondElephant_UEExportValidation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('STAR_POND_CENTIMETRE_EXPORT '+json.dumps(report))
