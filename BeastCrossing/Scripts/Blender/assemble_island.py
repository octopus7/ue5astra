"""Assemble authored modules, export FBX assemblies and render actual geometry."""
from pathlib import Path
import bpy
import json
import math
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Art' / 'Blender'
EXPORT = ROOT / 'Art' / 'Exports'
PREVIEW = ROOT / 'Art' / 'Previews'
EXPORT.mkdir(parents=True, exist_ok=True)
PREVIEW.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
manifest = {'units': 'meters', 'assets': [], 'materials': {}}

for module, name in [('terrain', 'SM_IslandTerrain'), ('village', 'SM_IslandVillage'), ('nature', 'SM_IslandNature')]:
    with bpy.data.libraries.load(str(SOURCE / (module + '.blend')), link=False) as (src, dst):
        dst.objects = src.objects
    meshes = []
    for obj in dst.objects:
        if obj and obj.type == 'MESH':
            scene.collection.objects.link(obj)
            meshes.append(obj)
    assert meshes, module
    # Convert evaluated modifiers and parent transforms before joining for export.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.join()
    combined = bpy.context.object
    combined.name = name
    scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    combined.data.validate(verbose=False, clean_customdata=False)
    combined.data.update()
    # Non-degenerate face-projected UVs support tangent generation for solid colors.
    # These are geometry coordinates, not image-generated texture content.
    uv = combined.data.uv_layers.active or combined.data.uv_layers.new(name='UVMap')
    for face in combined.data.polygons:
        dominant = max(range(3), key=lambda axis: abs(face.normal[axis]))
        axes = [axis for axis in range(3) if axis != dominant]
        for loop_index in face.loop_indices:
            point = combined.data.vertices[combined.data.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = (point[axes[0]], point[axes[1]])
    # Preserve the original scene for revision; this file contains export assemblies.
    bpy.ops.export_scene.fbx(filepath=str(EXPORT / (name + '.fbx')), use_selection=True,
        object_types={'MESH'}, axis_forward='-Y', axis_up='Z', apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_NONE', use_mesh_modifiers=True,
        mesh_smooth_type='FACE', bake_anim=False, add_leaf_bones=False)
    bounds = [combined.matrix_world @ Vector(c) for c in combined.bound_box]
    manifest['assets'].append({'name': name, 'module': module,
        'vertices': len(combined.data.vertices), 'polygons': len(combined.data.polygons),
        'bounds_min': [min(p[i] for p in bounds) for i in range(3)],
        'bounds_max': [max(p[i] for p in bounds) for i in range(3)],
        'materials': [m.name for m in combined.data.materials if m]})
    for mat in combined.data.materials:
        if not mat:
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if mat.use_nodes else None
        color = list(bsdf.inputs['Base Color'].default_value) if bsdf else list(mat.diffuse_color)
        roughness = bsdf.inputs['Roughness'].default_value if bsdf else mat.roughness
        manifest['materials'][mat.name] = {'color': color, 'roughness': roughness}

ocean = bpy.data.materials.new('M_OceanPreview')
ocean.diffuse_color = (0.028, 0.42, 0.49, 1)
ocean.use_nodes = True
bsdf = ocean.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value = ocean.diffuse_color
bsdf.inputs['Roughness'].default_value = 0.3
# Procedural preview water; no generated raster imagery is used.
noise = ocean.node_tree.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 1.6
noise.inputs['Detail'].default_value = 2
tex = ocean.node_tree.nodes.new('ShaderNodeTexCoord')
ocean.node_tree.links.new(tex.outputs['Object'], noise.inputs['Vector'])
bump = ocean.node_tree.nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.16
bump.inputs['Distance'].default_value = 0.18
ocean.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
ocean.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
bpy.ops.mesh.primitive_plane_add(size=1000, location=(0, 0, 0))
bpy.context.object.name = 'Ocean_Preview'
bpy.context.object.data.materials.append(ocean)

world = bpy.data.worlds.new('Island_Daylight')
scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.64, 0.79, 0.9, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.65
bpy.ops.object.light_add(type='SUN', location=(-35, -45, 70))
sun = bpy.context.object
sun.name = 'Preview_Sun'
sun.rotation_euler = (math.radians(25), math.radians(-25), math.radians(-30))
sun.data.energy = 2.6
sun.data.angle = math.radians(10)
bpy.ops.object.light_add(type='AREA', location=(-25, -35, 55))
fill = bpy.context.object
fill.data.energy = 14000
fill.data.shape = 'DISK'
fill.data.size = 45
fill.rotation_euler = (Vector((0, 0, 0)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(location=(78, -128, 104))
camera = bpy.context.object
camera.name = 'Camera_IslandOverview'
camera.rotation_euler = (Vector((0, -3, 1.5)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 119
camera.data.clip_end = 2000
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(PREVIEW / 'island_blender_overview.png')
(EXPORT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / 'BeastCrossing_Island.blend'))
bpy.ops.render.render(write_still=True)
print('BEAST_ASSEMBLY_OK', json.dumps(manifest['assets']))
