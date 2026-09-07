"""Rebuild the independent Crystal Cave crystal kit in Blender 4.5.

Run: blender --factory-startup --background --python AstraLevelTest/Scripts/build_cave_crystals.py
Reference: ArtSource/Reference/CrystalCave/Ref_CC_Crystals.png.
All four exports are single combined mesh objects, metres, ground-centred.
The presentation scene is an actual Blender render, not the generated reference.
"""
import bpy
import bmesh
import json
import math
import random
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
for directory in ('Blender', 'Meshes/CrystalCave', 'Layout/CrystalCave', 'Previews/CrystalCave'):
    (ART / directory).mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('CrystalCave_CrystalLibrary')
scene.collection.children.link(library)
preview = bpy.data.collections.new('CrystalCave_CrystalReview')
scene.collection.children.link(preview)

MATERIALS = {
    'M_CC_Rock': dict(base_color='283343', roughness=.87, metallic=0,
                      emissive_strength=0, base_color_texture='ArtSource/Textures/CrystalCave/T_CC_Rock.png'),
    'M_CC_CyanDeep': dict(base_color='08657E', emissive_color='0A6881', emissive_strength=.32, roughness=.25, metallic=.12),
    'M_CC_CyanBlue': dict(base_color='08779D', emissive_color='0797BC', emissive_strength=.38, roughness=.24, metallic=.10),
    'M_CC_CyanBody': dict(base_color='14A9C8', emissive_color='18CDE2', emissive_strength=.55, roughness=.22, metallic=.08),
    'M_CC_CyanLight': dict(base_color='37C4DB', emissive_color='3BDEEB', emissive_strength=.85, roughness=.20, metallic=.06),
    'M_CC_CyanTip': dict(base_color='75EAF0', emissive_color='76FFF2', emissive_strength=1.35, roughness=.18, metallic=.02),
    'M_CC_CyanEdge': dict(base_color='D5FFFF', emissive_color='B4FFF9', emissive_strength=2.20, roughness=.18, metallic=.02),
    'M_CC_VioletDeep': dict(base_color='392169', emissive_color='552D93', emissive_strength=.35, roughness=.26, metallic=.12),
    'M_CC_VioletBlue': dict(base_color='522491', emissive_color='7135C6', emissive_strength=.40, roughness=.23, metallic=.10),
    'M_CC_VioletBody': dict(base_color='8540D0', emissive_color='A65FE8', emissive_strength=.60, roughness=.22, metallic=.08),
    'M_CC_VioletLight': dict(base_color='AF62E1', emissive_color='C478FC', emissive_strength=.85, roughness=.20, metallic=.06),
    'M_CC_VioletTip': dict(base_color='D393F7', emissive_color='E7A1FF', emissive_strength=1.35, roughness=.18, metallic=.02),
    'M_CC_VioletEdge': dict(base_color='F6E1FF', emissive_color='F9D8FF', emissive_strength=2.10, roughness=.18, metallic=.02),
}


def rgba(hex_color):
    rgb = [int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb) + (1,)


materials = {}
for name, spec in MATERIALS.items():
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba(spec['base_color'])
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = rgba(spec['base_color'])
    bsdf.inputs['Roughness'].default_value = spec['roughness']
    bsdf.inputs['Metallic'].default_value = spec['metallic']
    bsdf.inputs['Emission Color'].default_value = rgba(spec.get('emissive_color', spec['base_color']))
    bsdf.inputs['Emission Strength'].default_value = spec['emissive_strength']
    if name == 'M_CC_Rock':
        texture_path = ROOT / spec['base_color_texture']
        if texture_path.exists():
            texture = material.node_tree.nodes.new('ShaderNodeTexImage')
            texture.image = bpy.data.images.load(str(texture_path))
            texture.image.pack()
            coords = material.node_tree.nodes.new('ShaderNodeTexCoord')
            material.node_tree.links.new(coords.outputs['Generated'], texture.inputs['Vector'])
            texture.projection = 'BOX'
            texture.projection_blend = .2
            material.node_tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
    materials[name] = material


def mesh_object(name, vertices, faces, palette, indices=None):
    mesh = bpy.data.meshes.new(name + '_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    library.objects.link(obj)
    for material in palette:
        mesh.materials.append(materials[material])
    if indices:
        for polygon, index in zip(mesh.polygons, indices):
            polygon.material_index = index
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    return obj


def bevel(obj, width, edge_material=-1):
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new('Narrow polished edge facets', 'BEVEL')
    modifier.width = width
    modifier.segments = 1
    modifier.affect = 'EDGES'
    modifier.limit_method = 'ANGLE'
    modifier.angle_limit = math.radians(12)
    modifier.material = edge_material
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def crystal(name, position, radius, height, tilt, palette='Cyan', seed=0):
    """Six irregular broad faces, staggered shoulders and a skewed clipped tip."""
    rng = random.Random(seed)
    colors = ['M_CC_' + palette + suffix for suffix in ('Deep', 'Blue', 'Body', 'Light', 'Tip', 'Edge')]
    phase = rng.uniform(0, math.tau)
    radii = [radius * rng.uniform(.85, 1.12) for _ in range(6)]
    angles = [phase + i * math.tau / 6 + rng.uniform(-.075, .075) for i in range(6)]
    shoulders = [.76 + rng.uniform(-.07, .04) for _ in range(6)]
    tip_xy = (radius * rng.uniform(-.24, .24), radius * rng.uniform(-.2, .2))
    vertices = []
    for tier in range(5):
        for i, angle in enumerate(angles):
            if tier == 0:
                r, z = radii[i] * .72, 0
            elif tier == 1:
                r, z = radii[i], height * .19
            elif tier == 2:
                z = height * (.39 + .09 * math.sin(angle*2+seed))
                r = radii[i] * (1 - .06 * ((z/height-.19)/(shoulders[i]-.19)))
            elif tier == 3:
                r, z = radii[i] * .94, height * shoulders[i]
            else:
                r, z = radius * .018, height
            shift = (z / height) ** 1.2
            vertices.append((math.cos(angle) * r + tip_xy[0] * shift,
                             math.sin(angle) * r + tip_xy[1] * shift, z))
    faces, indices = [tuple(reversed(range(6)))], [0]
    for tier in range(4):
        for i in range(6):
            j = (i + 1) % 6
            faces.append((tier*6+i, tier*6+j, (tier+1)*6+j, (tier+1)*6+i))
            if tier == 0:
                indices.append((i + seed) % 2)
            elif tier == 1:
                indices.append((0, 1, 2, 1, 0, 1)[(i + seed) % 6])
            elif tier == 2:
                indices.append((1, 2, 3, 2, 1, 2)[(i + seed) % 6])
            else:
                indices.append((3, 4, 3, 2, 3, 4)[(i + seed) % 6])
    faces.append(tuple(range(24, 30)))
    indices.append(4)
    obj = mesh_object(name, vertices, faces, colors, indices)
    bevel(obj, radius * .017, 5)
    obj.rotation_euler = tuple(math.radians(v) for v in tilt)
    obj.location = position
    return obj


def clip_polygon(points, normal, bound):
    result = []
    for p, q in zip(points, points[1:] + points[:1]):
        dp = p[0]*normal[0] + p[1]*normal[1] - bound
        dq = q[0]*normal[0] + q[1]*normal[1] - bound
        if dp <= 0:
            result.append(p)
        if (dp <= 0) != (dq <= 0):
            t = dp / (dp-dq)
            result.append((p[0] + t*(q[0]-p[0]), p[1] + t*(q[1]-p[1])))
    return result


def rock_slab(name, polygon, z, thickness, rng):
    n = len(polygon)
    center = tuple(sum(p[i] for p in polygon)/n for i in (0, 1))
    vertices = []
    for scale, elevation in ((.91, z), (1, z+thickness*.28), (.98, z+thickness*.9), (.9, z+thickness)):
        for x, y in polygon:
            vertices.append((center[0]+(x-center[0])*scale, center[1]+(y-center[1])*scale,
                             elevation + rng.uniform(-.015, .015)*thickness))
    faces = [tuple(reversed(range(n))), tuple(range(3*n,4*n))]
    for tier in range(3):
        for i in range(n):
            j = (i+1) % n
            faces.append((tier*n+i, tier*n+j, (tier+1)*n+j, (tier+1)*n+i))
    return mesh_object(name, vertices, faces, ['M_CC_Rock'])


def socket(name, radius, height, seed):
    """Two irregular fractured strata, split by recessed Voronoi joints."""
    rng = random.Random(seed)
    parts = []
    for tier in range(2):
        phase = .2 + tier*.31
        boundary = [(math.cos(i*math.tau/13+phase)*radius*rng.uniform(.88,1.02),
                     math.sin(i*math.tau/13+phase)*radius*rng.uniform(.79,.98)) for i in range(13)]
        seeds = [(0, 0)] + [(math.cos(i*math.tau/7+.2)*radius*.64,
                             math.sin(i*math.tau/7+.2)*radius*.64) for i in range(7)]
        for i, p in enumerate(seeds):
            polygon = boundary[:]
            for j, q in enumerate(seeds):
                if i == j:
                    continue
                normal = (q[0]-p[0], q[1]-p[1])
                bound = (q[0]**2+q[1]**2-p[0]**2-p[1]**2)/2
                polygon = clip_polygon(polygon, normal, bound)
            centroid = tuple(sum(point[k] for point in polygon)/len(polygon) for k in (0,1))
            polygon = [(centroid[0]+(x-centroid[0])*.953, centroid[1]+(y-centroid[1])*.953) for x,y in polygon]
            parts.append(rock_slab(name+'_Stratum', polygon, tier*height*.42,
                                   height*.59*rng.uniform(.85,1.05), rng))
    for i in range(13):
        angle = rng.uniform(0,math.tau)
        distance = radius*rng.uniform(.79,1.06)
        size = radius*rng.uniform(.025,.075)
        center = (math.cos(angle)*distance,math.sin(angle)*distance)
        polygon = [(center[0]+math.cos(j*math.tau/5)*size*rng.uniform(.6,1.2),
                    center[1]+math.sin(j*math.tau/5)*size*rng.uniform(.6,1.2)) for j in range(5)]
        parts.append(rock_slab(name+'_Debris', polygon, .01, height*rng.uniform(.12,.35),rng))
    return parts


def faceted_heart():
    """A readable heart gemstone, with deep pavilion and a broad raised crown."""
    contour = [(0,.06),(.5,.54),(.95,1.14),(1.04,1.69),(.81,2.01),(.43,2.10),
               (0,1.80),(-.40,2.12),(-.85,1.95),(-1.07,1.60),(-.91,1.12),(-.49,.55)]
    vertices = []
    for y, scale in ((.02,1),(-.36,.91),(-.58,.62)):
        for x,z in contour:
            vertices.append((x*scale,y,(z-1.1)*scale+1.1))
    vertices += [(0,-.69,1.08),(0,.57,1.16)]
    n = len(contour)
    faces, indices = [], []
    for i in range(n):
        j=(i+1)%n
        faces.extend([(i,j,n+j,n+i),(n+i,n+j,2*n+j,2*n+i),(2*n+i,2*n+j,36),(j,i,37)])
        indices.extend([(2,3,4,3,4,3,4,3,2,3,2,1)[i], (1,2,3,4,4,3,4,3,2,1,2,1)[i],
                        (2,2,3,3,4,3,4,3,2,2,2,1)[i],1+(i%2)])
    palette = ['M_CC_Cyan'+suffix for suffix in ('Deep','Blue','Body','Light','Tip','Edge')]
    obj=mesh_object('Heart_Crown',vertices,faces,palette,indices)
    bevel(obj,.007,5)
    obj.location=(0,-.16,.37)
    return obj


def combine(name, parts, target_width, target_height):
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bounds=[Vector(corner) for corner in obj.bound_box]
    minimum=Vector(tuple(min(v[i] for v in bounds) for i in range(3)))
    maximum=Vector(tuple(max(v[i] for v in bounds) for i in range(3)))
    width=max(maximum.x-minimum.x,maximum.y-minimum.y)
    height=maximum.z-minimum.z
    center=(minimum+maximum)/2
    for vertex in obj.data.vertices:
        vertex.co.x=(vertex.co.x-center.x)*target_width/width
        vertex.co.y=(vertex.co.y-center.y)*target_width/width
        vertex.co.z=(vertex.co.z-minimum.z)*target_height/height
    obj.data.update()
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(65),island_margin=.018)
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj


objects=[]
parts=socket('CyanSocket',.76,.25,601)
specs=[((-.06,.08,.17),.235,1.94,(3,-8,0)),((.34,.09,.17),.17,1.14,(-5,23,15)),
       ((-.34,-.11,.16),.16,.9,(8,-25,40)),((.12,-.37,.17),.14,.65,(18,10,0)),
       ((.45,-.16,.13),.1,.61,(5,31,35)),((-.5,.15,.14),.11,.58,(-17,-29,0))]
for i,(p,r,h,t) in enumerate(specs):
    parts.append(crystal('Cyan_Prism',p,r,h,t,seed=210+i))
for i in range(14):
    angle=i*math.tau/14
    parts.append(crystal('Cyan_Seed',(.53*math.cos(angle),.40*math.sin(angle),.18),.035+(i%3)*.015,
                         .10+(i%5)*.034,(math.sin(angle)*16,math.cos(angle)*18,angle*180/math.pi),seed=301+i))
objects.append(combine('SM_CC_CrystalCyan',parts,1.6,2.0))

parts=socket('VioletSocket',.7,.19,710)
specs=[((-.11,.12,.13),.245,1.13,(-5,-11,15)),((.29,.07,.13),.205,.84,(-1,29,60)),
       ((-.36,-.17,.13),.205,.58,(14,-29,10)),((.04,-.35,.13),.19,.51,(19,9,0)),
       ((.4,.32,.13),.075,.4,(-10,27,22))]
for i,(p,r,h,t) in enumerate(specs):
    parts.append(crystal('Violet_Prism',p,r,h,t,'Violet',230+i))
for i in range(12):
    angle=i*math.tau/12+.4
    parts.append(crystal('Violet_Seed',(.5*math.cos(angle),.4*math.sin(angle),.14),.045+(i%3)*.018,
                         .11+(i%4)*.04,(math.sin(angle)*20,math.cos(angle)*20,0),'Violet',320+i))
objects.append(combine('SM_CC_CrystalViolet',parts,1.4,1.3))

parts=socket('HeartSocket',1.41,.33,820)
parts.append(faceted_heart())
specs=[((0,.55,.25),.29,3.26,(-3,4,0)),((-.67,.40,.24),.24,2.08,(-5,-13,10)),
       ((.68,.46,.24),.25,2.37,(-4,14,55)),((1.0,.2,.23),.18,1.28,(8,27,40)),
       ((-1.0,.08,.23),.19,1.16,(6,-27,15)),((.61,-.57,.24),.15,.65,(20,25,45)),
       ((-.66,-.61,.24),.17,.74,(21,-23,15)),((.18,-.83,.24),.13,.46,(18,8,0))]
for i,(p,r,h,t) in enumerate(specs):
    parts.append(crystal('Heart_Prism',p,r,h,t,seed=401+i))
for i in range(27):
    angle=i*math.tau/27
    parts.append(crystal('Heart_Seed',(1.1*math.cos(angle),.86*math.sin(angle),.23),.04+(i%4)*.018,
                         .12+(i%5)*.04,(math.sin(angle)*22,math.cos(angle)*22,0),seed=440+i))
objects.append(combine('SM_CC_CrystalHeart',parts,3.0,3.5))

parts=socket('ShardsSocket',.30,.07,901)
specs=[((-.015,.03,.04),.073,.43,(0,-12,15)),((.10,.07,.035),.056,.25,(-5,28,0)),
       ((-.12,-.05,.04),.055,.24,(17,-29,35)),((.04,-.11,.04),.058,.16,(22,10,0)),
       ((.18,-.045,.035),.042,.13,(9,41,60)),((-.19,.055,.035),.036,.1,(-18,-33,0))]
for i,(p,r,h,t) in enumerate(specs):
    parts.append(crystal('Tiny_Shard',p,r,h,t,seed=510+i))
objects.append(combine('SM_CC_CrystalShards',parts,.6,.45))

assets={}
for obj in objects:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    file='ArtSource/Meshes/CrystalCave/'+obj.name+'.fbx'
    bpy.ops.export_scene.fbx(filepath=str(ROOT/file),use_selection=True,object_types={'MESH'},
                            global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
                            axis_forward='-Y',axis_up='Z',bake_space_transform=False,
                            use_mesh_modifiers=True,mesh_smooth_type='FACE',use_triangles=True,
                            add_leaf_bones=False,bake_anim=False)
    assets[obj.name]=dict(file=file,materials=[slot.name for slot in obj.data.materials],collision='complex',
                         dimensions_m=[round(v,5) for v in obj.dimensions],origin='ground centre',
                         vertex_count=len(obj.data.vertices),polygon_count=len(obj.data.polygons),
                         uv_channels=1,rotation_degrees=[0,0,0],scale=[1,1,1],
                         recommended_light=dict(color='53DAEF' if 'Violet' not in obj.name else 'BB85EF',
                                                intensity_lumens=1200 if 'Heart' in obj.name else 450,
                                                attenuation_radius_m=6 if 'Heart' in obj.name else 3.6))
    obj.hide_render=True
    obj.hide_set(True)

metadata=dict(source='ArtSource/Blender/CrystalCaveCrystals.blend',script='Scripts/build_cave_crystals.py',
              reference='ArtSource/Reference/CrystalCave/Ref_CC_Crystals.png',units='metres',
              fbx_axes=dict(forward='-Y',up='Z',apply_scale_options='FBX_SCALE_UNITS'),
              assets=assets,materials=MATERIALS,
              notes=['Each asset is one mesh, with disconnected closed crystal and fractured socket components.',
                     'Narrow bevel polygons carry a brighter edge material; large faces keep distinct emission levels.',
                     'Opaque polished gemstones retain facets. Add local UE lights to illuminate surrounding rocks.',
                     'Preview point lights are presentation-only and are not exported.',
                     'Hero heart faces local -Y; rotate toward the fixed camera when placing it.'])
(ART/'Layout/CrystalCave/crystals_kit.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')

def move_to_review(obj):
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    preview.objects.link(obj)


for obj,location in zip(objects,[(-3.5,0,0),(-1.35,-.25,0),(1.65,.28,0),(4.1,-.55,0)]):
    duplicate=obj.copy()
    duplicate.data=obj.data
    duplicate.name='REVIEW_'+obj.name
    preview.objects.link(duplicate)
    duplicate.hide_render=False
    duplicate.hide_set(False)
    duplicate.location=location
    lamp=bpy.data.lights.new('Local reflected gemstone glow','POINT')
    lamp.energy=60 if 'Heart' in obj.name else 20
    lamp.color=(.08,.73,1) if 'Violet' not in obj.name else (.55,.18,1)
    lamp.shadow_soft_size=1.0
    light=bpy.data.objects.new('Local reflected gemstone glow',lamp)
    preview.objects.link(light)
    light.location=(location[0],location[1]-.48,.50)

floor_material=bpy.data.materials.new('REVIEW_Backdrop')
floor_material.use_nodes=True
floor_bsdf=floor_material.node_tree.nodes.get('Principled BSDF')
floor_bsdf.inputs['Base Color'].default_value=rgba('121A27')
floor_bsdf.inputs['Roughness'].default_value=.8
bpy.ops.mesh.primitive_plane_add(size=200)
floor=bpy.context.object
floor.name='REVIEW_Ground'
floor.location.z=-.014
floor.data.materials.append(floor_material)
move_to_review(floor)
world=bpy.data.worlds.new('Crystal Cave dark studio')
world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.035,.052,.09,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.25
scene.world=world
for name,location,power,color,size in [('Softbox',(-3,-5,8),450,(.65,.82,1),7),
                                      ('Rim',(4,3,7),600,(.3,.55,1),6)]:
    lamp=bpy.data.lights.new(name,'AREA')
    lamp.energy=power
    lamp.color=color
    lamp.shape='DISK'
    lamp.size=size
    obj=bpy.data.objects.new(name,lamp)
    preview.objects.link(obj)
    obj.location=location
    obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
camera_data=bpy.data.cameras.new('Crystal kit actual Blender review')
camera=bpy.data.objects.new('Crystal kit actual Blender review',camera_data)
preview.objects.link(camera)
camera.location=(5.0,-13,8.2)
camera.rotation_euler=(Vector((.05,0,1.40))-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type='ORTHO'
camera_data.ortho_scale=11.3
scene.camera=camera
scene.render.engine='CYCLES'
scene.cycles.samples=40
scene.cycles.use_denoising=True
scene.render.resolution_x=1600
scene.render.resolution_y=1000
scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ART/'Previews/CrystalCave/Blender_Crystals.png')
scene.use_nodes=True
nodes=scene.node_tree.nodes
nodes.clear()
render=nodes.new('CompositorNodeRLayers')
glare=nodes.new('CompositorNodeGlare')
glare.glare_type='FOG_GLOW'
glare.threshold=2.2
glare.quality='HIGH'
glare.mix=-.91
glare.size=7
output=nodes.new('CompositorNodeComposite')
scene.node_tree.links.new(render.outputs['Image'],glare.inputs['Image'])
scene.node_tree.links.new(glare.outputs['Image'],output.inputs['Image'])
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/CrystalCaveCrystals.blend'))
bpy.ops.render.render(write_still=True)
print('CRYSTAL_KIT_COMPLETE '+json.dumps({k:v['dimensions_m'] for k,v in assets.items()}))
