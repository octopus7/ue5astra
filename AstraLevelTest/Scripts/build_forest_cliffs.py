"""Three closed forest cliff modules, hand-painted UV texture and a standalone showcase.

Run Blender --background --factory-startup --python this_file.py.
Metres, front -X, width along Y. Bury the lower continuous four metres as needed.
Only the independent ForestCliffs assets are written; no main scene or UE map edits.
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
for folder in ('Blender', 'Meshes', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_ForestCliffMeshLibrary')
presentation = bpy.data.collections.new('02_CliffPresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)
texture = bpy.data.images.load(str(ART/'Textures'/'T_ForestCliffPaint.png'))
texture.name = 'T_ForestCliffPaint'
texture.colorspace_settings.name = 'sRGB'
texture.pack()

MATERIALS = {
    'M_ForestCliffStone': {'tint_linear': [1.12, 1.15, 1.19], 'roughness': .88, 'metallic': 0., 'palette_srgb_hex': 'ADB8BF'},
    'M_ForestCliffCool': {'tint_linear': [.97, 1.10, 1.37], 'roughness': .88, 'metallic': 0., 'palette_srgb_hex': '94AAD0'},
    'M_ForestCliffWarm': {'tint_linear': [1.28, 1.21, 1.05], 'roughness': .88, 'metallic': 0., 'palette_srgb_hex': 'C5C5AC'},
    'M_ForestCliffMoss': {'tint_linear': [.97, 1.12, .53], 'roughness': .93, 'metallic': 0., 'palette_srgb_hex': 'A3B477'},
}
materials = {}
for name, properties in MATERIALS.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = properties['roughness']
    shader.inputs['Metallic'].default_value = 0
    shader.inputs['Specular IOR Level'].default_value = .25
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = texture
    tex.extension = 'REPEAT'
    tex.interpolation = 'Linear'
    tex.location = (-520, 50)
    uv = mat.node_tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'UVMap'
    uv.location = (-740, 50)
    tint = mat.node_tree.nodes.new('ShaderNodeMixRGB')
    tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1
    tint.inputs[2].default_value = (*properties['tint_linear'], 1)
    tint.location = (-240, 50)
    mat.node_tree.links.new(uv.outputs['UV'], tex.inputs['Vector'])
    mat.node_tree.links.new(tex.outputs['Color'], tint.inputs[1])
    mat.node_tree.links.new(tint.outputs[0], shader.inputs['Base Color'])
    mat.diffuse_color = (*[v*.42 for v in properties['tint_linear']], 1)
    materials[name] = mat


def outline(variant):
    # Ordered CCW cross-section. Long front consists of several chunky stone planes.
    if variant == 'C':
        return [(1.16,-2.46),(.35,-2.60),(-.65,-2.55),(-1.18,-2.22),
                (-1.48,-1.66),(-1.68,-.75),(-1.49,.12),(-1.07,.67),
                (-.88,1.58),(-.68,2.25),(-.22,2.56),(.65,2.57),
                (1.17,2.21),(1.31,1.26),(1.24,.05),(1.30,-1.32)]
    return [(1.14,-2.20),(.50,-2.54),(-.45,-2.58),(-1.10,-2.28),
            (-1.31,-1.52),(-1.40,-.74),(-1.33,.16),(-1.45,.94),
            (-1.30,1.75),(-.88,2.39),(-.12,2.60),(.70,2.51),
            (1.19,2.12),(1.25,1.20),(1.20,.10),(1.28,-1.10)]


def create_cliff(variant):
    rng = random.Random(907 + ord(variant))
    cross = outline(variant)
    n = len(cross)
    # Inward 8 cm seams never split the solid. Extra lip rings give broad chamfers.
    levels = [(0,1.03),(.13,1.045)]
    bands = ([1.10,2.90,3.55,5.90,6.50,7.80] if variant == 'B'
             else [1.20,2.58,3.89,5.27,6.57,7.80])
    for index, top in enumerate(bands):
        levels += [(top-.17,1.035 if index%2 == 0 else 1.005),
                   (top-.055,.985), (top,.957), (top+.06,.97)]
        if index < len(bands)-1:
            levels += [(top+.17,1.035)]
    levels += [(7.98,.934)]
    if variant == 'C':
        # A single broad projecting shoulder instead of A's repeated thin strata.
        levels = [(0,1.03),(.13,1.045),(2.30,1.02),(2.50,.975),
                  (2.65,1.04),(4.15,1.02),(4.32,1.025),(4.48,1.025),
                  (6.15,1.025),(6.42,.99),(6.58,.965),(7.80,.975),(7.98,.934)]
    vertices=[]
    for level_index,(z, scale) in enumerate(levels):
        for point_index,(x,y) in enumerate(cross):
            height_ratio=z/8
            irregular = math.sin(point_index*2.21+level_index*.72)*.021
            # Diagonal formations: strata incline consistently along the front.
            z_slant = (.26*y*min(1,z/1.2)*min(1,(8-z)/1.2) if variant == 'B' and z else 0)
            silhouette = .045*math.sin(point_index*1.7) * height_ratio**9
            sx = (x*scale + irregular + (.17*math.sin(z*.94) if variant=='B' else 0))
            sy = y*scale + (.07*math.sin(z*.85) if variant=='C' else 0)
            if variant == 'B':
                # The upper half visibly leans 0.5 m towards local +Y.
                sy += .5*max(0,min(1,(z-3.4)/4.6))
            elif variant == 'C':
                # Continuous lower shaft, then one massive corner shoulder and ledge.
                shoulder = max(0,min(1,(z-4.15)/.33))*max(0,min(1,(6.58-z)/.43))
                front_weight = max(0,min(1,(-x-.05)/1.5))
                corner_weight = max(.15,min(1,(1.5-y)/2.0))
                sx -= .60*shoulder*front_weight*corner_weight
            vertices.append((sx,sy,z+z_slant+silhouette))
    faces=[]
    ring_face_count=(len(levels)-1)*n
    for ring in range(len(levels)-1):
        for index in range(n):
            following=(index+1)%n
            faces.append((ring*n+index,ring*n+following,(ring+1)*n+following,(ring+1)*n+index))
    faces.append(tuple(range(n-1,-1,-1)))
    top_index=len(vertices)
    # The cap is filled, not hollow; the lowered inner ring prevents a spiky fan.
    for x,y in cross:
        vertices.append((x*.49,y*.49+(.5 if variant=='B' else 0),7.99+.035*math.sin(y*1.4)))
    outer_start=(len(levels)-1)*n
    for index in range(n):
        following=(index+1)%n
        faces.append((outer_start+index,outer_start+following,top_index+following,top_index+index))
    center=len(vertices)
    vertices.append((0,.5 if variant=='B' else 0,8.035))
    for index in range(n):
        faces.append((top_index+index,top_index+(index+1)%n,center))
    data=bpy.data.meshes.new('SM_ForestCliff_'+variant)
    data.from_pydata(vertices,[],faces)
    data.update()
    bm=bmesh.new(); bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(data); bm.free()
    data.update()
    obj=bpy.data.objects.new('SM_ForestCliff_'+variant,data)
    library.objects.link(obj)
    for mat in materials.values():
        data.materials.append(mat)
    color_layer=data.color_attributes.new(name='CliffFacetTint', type='FLOAT_COLOR', domain='CORNER')
    uv_layer=data.uv_layers.new(name='UVMap')
    # New custom-data layers can invalidate earlier RNA handles; reacquire both.
    color_layer=data.color_attributes['CliffFacetTint']
    uv_layer=data.uv_layers['UVMap']
    for face in data.polygons:
        if face.index > ring_face_count:
            # One connected moss crown, with stone only on a few outer lip facets.
            slot=2 if face.index-ring_face_count in (3,4,12) else 3
        elif face.normal.z > .52:
            slot=3 if face.center.z > 4.8 and rng.random()<.38 else 2
        elif face.normal.y < -.3 or face.normal.z < -.25:
            slot=1
        else:
            slot=1 if rng.random()<.14 else (2 if rng.random()<.20 else 0)
        face.material_index=slot
        face.use_smooth=False
        # Box-projected UV, two metres per repeat. Bake axis selection into UV0.
        dominant=max(range(3),key=lambda index:abs(face.normal[index]))
        for loop_index in face.loop_indices:
            co=data.vertices[data.loops[loop_index].vertex_index].co
            if dominant==0:
                uv=(co.y/2,co.z/2)
            elif dominant==1:
                uv=(co.x/2,co.z/2)
            else:
                uv=(co.x/2,co.y/2)
            uv_layer.data[loop_index].uv=uv
            color_layer.data[loop_index].color=(1,1,1,1)
    obj['asset_id']=obj.name
    obj['collision']='complex'
    obj['front_axis']='-X'
    obj['bury_depth_range_m']='0 to 4.5'
    return obj


def metadata_asset(obj):
    bounds=[Vector(corner) for corner in obj.bound_box]
    bm=bmesh.new(); bm.from_mesh(obj.data)
    non_manifold=sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    finite=all(math.isfinite(value) for vertex in obj.data.vertices for value in vertex.co)
    degenerate=sum(face.area<1e-9 for face in obj.data.polygons)
    assert finite and non_manifold==0 and degenerate==0
    assert abs(min(v.z for v in bounds))<1e-6
    return {'asset_id':obj.name,'file':f'ArtSource/Meshes/{obj.name}.fbx',
            'collision':'complex','front_axis_blender':'-X','origin':'ground at (0, 0, 0)',
            'dimensions_m':[round(v,6) for v in obj.dimensions],
            'bounds_min_m':[round(min(v[i] for v in bounds),6) for i in range(3)],
            'bounds_max_m':[round(max(v[i] for v in bounds),6) for i in range(3)],
            'vertices':len(obj.data.vertices),'triangles':sum(len(p.vertices)-2 for p in obj.data.polygons),
            'material_slots':[s.material.name for s in obj.material_slots],
            'recommended_overlap_m':.55,'continuous_buryable_lower_height_m':4.5,
            'silhouette':{'A':'Broad regular horizontal strata',
                          'B':'Upper half leans 0.5 m toward local +Y; alternating wide and narrow strata',
                          'C':'Large front -X corner shoulder and wide ledge at 6.2 m; fewer broader strata'}[obj.name[-1]],
            'uv':{'channel':0,'name':'UVMap','metres_per_tile':2.,
                  'projection':'Dominant local normal: X faces YZ, Y faces XZ, Z faces XY. Baked UV0; no UE axis conversion required.'},
            'validation':{'finite_vertices':finite,'non_manifold_edges':non_manifold,'degenerate_faces':degenerate,'closed_bottom':True,'closed_top':True}}


assets=[create_cliff(v) for v in ('A','B','C')]
bpy.context.view_layer.update()
asset_info=[metadata_asset(obj) for obj in assets]
for obj in assets:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.fbx(filepath=str(ART/'Meshes'/f'{obj.name}.fbx'),
        use_selection=True,object_types={'MESH'},apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True,
        path_mode='STRIP',colors_type='LINEAR')
    obj.hide_render=True
    obj.hide_set(True)

# Reload every FBX into a temporary collection and validate exported shape + baked UV.
roundtrip=[]
for obj, expected in zip(assets,asset_info):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ART/'Meshes'/f'{obj.name}.fbx'))
    imported=[x for x in set(bpy.data.objects)-before if x.type=='MESH']
    assert len(imported)==1
    actual=imported[0]
    bpy.context.view_layer.update()
    error=max(abs(float(actual.dimensions[i])-expected['dimensions_m'][i]) for i in range(3))
    uv=actual.data.uv_layers.active
    assert error < .0001 and uv is not None and len(uv.data)>0
    assert all(math.isfinite(v) for item in uv.data for v in item.uv)
    uv_bounds=[min(item.uv[i] for item in uv.data) for i in range(2)]+[max(item.uv[i] for item in uv.data) for i in range(2)]
    assert uv_bounds[3] > 3.9 and uv_bounds[0] < -1.0, 'UVs must retain baked two-metre projection, not per-face 0-1 defaults'
    assert len(actual.data.materials)==len(obj.data.materials)
    bm=bmesh.new(); bm.from_mesh(actual.data)
    # FBX contains split normal/UV seams, so weld coordinates before manifold audit.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    open_edges=sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert open_edges==0
    roundtrip.append({'asset_id':obj.name,'dimensions_error_m':error,'uv_loops':len(uv.data),'uv_bounds_min_u_min_v_max_u_max_v':uv_bounds,'finite_uv':True,'welded_non_manifold_edges':open_edges,'material_slots':len(actual.data.materials)})
    for item in list(set(bpy.data.objects)-before):
        bpy.data.objects.remove(item,do_unlink=True)

metadata={'source':'ArtSource/Blender/ForestCliffs.blend','script':'Scripts/build_forest_cliffs.py',
          'reference':'ArtSource/Reference/Ref_ForestCliffs.png','units':'metres',
          'unreal_conversion':'(Blender X, -Blender Y, Blender Z) * 100; yaw negated',
          'palette_srgb_hex':{name:p['palette_srgb_hex'] for name,p in MATERIALS.items()},
          'material_properties':{name:{**p,'base_color_texture':'ArtSource/Textures/T_ForestCliffPaint.png',
                    'base_color_formula':'sRGB-decoded TextureSample(UV0).rgb * tint_linear',
                    'texture_srgb':True,'sampler_address':'wrap','uv_channel':0,
                    'normal_texture':None,'emissive':0,'specular':.25} for name,p in MATERIALS.items()},
          'assets':asset_info,'fbx_roundtrip_validation':roundtrip,
          'placement_notes':'Stand vertically, assemble along local Y with 0.55 m overlap. Front -X. Bury origin 0–4.5 m below visible ground to expose 3.5–8 m. All sides and bottom remain closed. Match upper terrain to the cap or bury cap slightly into hillside. C is a projecting corner; yaw +/-15–45 degrees to wrap a hill. The lower half is fully continuous solid stone, with no detached shelves or floating details.'}
(ART/'Layout'/'forest_cliffs.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')

def instance(original,name,location,rotation=0):
    obj=bpy.data.objects.new(name,original.data)
    presentation.objects.link(obj)
    obj.location=location
    obj.rotation_euler.z=math.radians(rotation)
    return obj

# Three originals in back; foreground assembly deliberately has their lower halves buried.
for index,obj in enumerate(assets):
    instance(obj,'Preview_'+obj.name,(3,(index-1)*6.55,0))
for index,obj in enumerate(assets):
    instance(obj,'HalfBuried_'+obj.name,(-6,(index-1)*4.75,-4.1),(-5,4,14)[index])
ground=bpy.data.materials.new('Preview_CliffGround')
ground.use_nodes=True
ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.35,.41,.22,1)
ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.92
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.015))
bpy.context.object.data.materials.append(ground)
bpy.context.object.name='PreviewGround'
scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.58,.69,.92,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.5
bpy.ops.object.light_add(type='SUN',location=(-9,-8,15))
sun=bpy.context.object
sun.name='SoftSun_50deg'
sun.rotation_euler=(math.radians(23),math.radians(-31),math.radians(-35))
sun.data.energy=2.4
sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-25,-14,20))
cam=bpy.context.object
cam.rotation_euler=(Vector((-1.4,0,3.6))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO'; cam.data.ortho_scale=26.3
scene.camera=cam
scene.render.engine='CYCLES'
scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.render.resolution_x=1800
scene.render.resolution_y=1300
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ART/'Previews'/'Blender_ForestCliffs.png')
scene.view_settings.view_transform='AgX'
scene.view_settings.look='AgX - Medium High Contrast'
scene.render.film_transparent=False
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'ForestCliffs.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA FOREST CLIFFS COMPLETE '+json.dumps(asset_info))
