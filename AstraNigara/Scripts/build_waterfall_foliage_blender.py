"""Create three original folded, curved grass clumps in Blender 4.5 (cm).

Blender --background --factory-startup --python this_file
VertexColor R is the root-to-tip wind weight, G/B carry per-blade variation.
"""
import bpy
import json
import math
import random
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource' / 'WaterfallFoliage'
FBX = ART / 'FBX'
FBX.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = .01
scene.unit_settings.length_unit = 'CENTIMETERS'

material = bpy.data.materials.new('WF_MeadowGrass')
material.diffuse_color = (.31, .49, .16, 1)
material.use_nodes = True
nodes = material.node_tree.nodes
bsdf = nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = .9
vc = nodes.new('ShaderNodeVertexColor')
vc.layer_name = 'WindWeight'
separate = nodes.new('ShaderNodeSeparateColor')
material.node_tree.links.new(vc.outputs['Color'], separate.inputs['Color'])
ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (.045, .145, .085, 1)
ramp.color_ramp.elements[1].color = (.49, .64, .22, 1)
material.node_tree.links.new(separate.outputs['Red'], ramp.inputs['Fac'])
material.node_tree.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])


def make_clump(name, blades, height, width, lean, seed):
    rng = random.Random(seed)
    vertices, faces, uvs, colors = [], [], [], []
    for index in range(blades):
        # Most blades lean together, with a few crossing the tuft silhouette.
        angle = rng.uniform(-.7, .7) + (math.pi if index % 5 == 0 else 0)
        direction = Vector((math.cos(angle), math.sin(angle), 0))
        across = Vector((-direction.y, direction.x, 0))
        root_angle = rng.random() * math.tau
        root_radius = rng.uniform(1, 7)
        root = Vector((math.cos(root_angle)*root_radius,
                       math.sin(root_angle)*root_radius, 0))
        h = height * rng.uniform(.64, 1.12)
        w = width * rng.uniform(.7, 1.13)
        bend = lean * rng.uniform(.7, 1.18)
        blade_variation, phase = rng.random(), rng.random()
        start = len(vertices)
        for t in (0, .4, .76):
            center = root + direction * bend * (t ** 1.85)
            center.z = h * (t - .12*t*t)
            half_width = w * (1 - .78*t)
            for side in (-1, 0, 1):
                p = center + across * side * half_width
                # Raised middle rib gives each blade two readable broad facets.
                p.z += (1-abs(side)) * half_width * .34
                vertices.append(tuple(p))
                uvs.append(((side+1)/2, t))
                colors.append((t, blade_variation, phase, 1))
        tip = root + direction*bend
        tip.z = h*.84
        vertices.append(tuple(tip))
        uvs.append((.5, 1))
        colors.append((1, blade_variation, phase, 1))
        for row in range(2):
            for side in range(2):
                a = start + row*3 + side
                faces.append((a, a+1, a+4, a+3))
        faces.extend(((start+6, start+7, start+9),
                      (start+7, start+8, start+9)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name='UVMap')
    color = mesh.color_attributes.new(name='WindWeight', type='FLOAT_COLOR', domain='CORNER')
    for loop in mesh.loops:
        uv.data[loop.index].uv = uvs[loop.vertex_index]
        color.data[loop.index].color = colors[loop.vertex_index]
    mesh.color_attributes.active_color = color
    mesh.calc_loop_triangles()
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = FBX / (name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True,
        object_types={'MESH'}, global_scale=1, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
        bake_space_transform=False, mesh_smooth_type='FACE',
        use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False,
        colors_type='LINEAR')
    dimensions = [max(v[i] for v in vertices)-min(v[i] for v in vertices) for i in range(3)]
    assert min(c[0] for c in colors) == 0 and max(c[0] for c in colors) == 1
    return obj, {'name':name, 'fbx':'FBX/'+path.name,
                 'triangles':len(mesh.loop_triangles), 'blades':blades,
                 'dimensions_cm':dimensions, 'vertex_color':'WindWeight',
                 'wind_weight_min':0, 'wind_weight_max':1, 'uv_channels':1}


report = {'units':'cm', 'wind_channel':'VertexColor.R', 'assets':[]}
specs = [('SM_WF_GrassTuft',8,32,3.4,17,271),
         ('SM_WF_GrassFan',10,25,3.6,20,272),
         ('SM_WF_GrassSedge',6,44,2.7,15,273)]
for index, spec in enumerate(specs):
    obj, info = make_clump(*spec)
    report['assets'].append(info)
    # Presentation positions are applied only after FBX export; roots in FBX remain 0.
    obj.location.x = (index-1)*60

(ART/'foliage_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
scene.world.color = (.25, .3, .25)
bpy.ops.object.light_add(type='AREA', location=(-60,-90,160))
light=bpy.context.object
light.data.energy=24000
light.data.shape='DISK'
light.data.size=150
bpy.ops.object.light_add(type='SUN', location=(-100,-100,200))
sun=bpy.context.object
sun.data.energy=2.4
sun.rotation_euler=(math.radians(20),math.radians(-25),math.radians(-35))
bpy.ops.object.camera_add(location=(75,-170,105))
camera=bpy.context.object
camera.rotation_euler=(Vector((0,0,18))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=200
camera.data.clip_end=10000
scene.camera=camera
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.cycles.use_denoising=True
scene.render.resolution_x=1400
scene.render.resolution_y=800
scene.render.resolution_percentage=100
scene.render.film_transparent=True
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ART/'GrassClumps.png')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'WaterfallFoliage.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA_WATERFALL_FOLIAGE_BLENDER_OK '+json.dumps(report))
