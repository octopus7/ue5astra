"""Build the independent Star Pond ruin kit from its generated detail reference.

Blender 4.5, metres, Z up, gate and menhir fronts face -Y. The source library
remains at the floor origin; only presentation duplicates are repositioned.
"""
import bpy
import bmesh
import json
import math
import random
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
REFERENCE = ART / 'Reference/StarPond/Ref_StarPondRuins.png'
assert REFERENCE.is_file(), 'Generate and inspect the ruin detail reference first.'
for folder in ('Blender', 'Meshes/StarPond', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
library = bpy.data.collections.new('StarPondRuins_Library')
scene.collection.children.link(library)
display = bpy.data.collections.new('StarPondRuins_Presentation')
scene.collection.children.link(display)

MATERIALS = {
    'M_SP_Ruins_PaintedStone': {'base_color': 'CAD5CD', 'roughness': .84, 'metallic': 0,
                              'base_color_texture': 'ArtSource/Textures/T_AnimeForestRockPaint.png'},
    'M_SP_Ruins_PaleStone': {'base_color': 'C6CCC1', 'roughness': .85, 'metallic': 0},
    'M_SP_Ruins_ShadowStone': {'base_color': '919F99', 'roughness': .9, 'metallic': 0},
    'M_SP_Ruins_Moss': {'base_color': '70834E', 'roughness': .96, 'metallic': 0},
    'M_SP_Ruins_MossLight': {'base_color': '91A067', 'roughness': .95, 'metallic': 0},
    'M_SP_Ruins_Brass': {'base_color': 'B9A365', 'roughness': .39, 'metallic': .72},
    'M_SP_Ruins_BrassLight': {'base_color': 'E5CC87', 'roughness': .32, 'metallic': .66},
    'M_SP_Ruins_StarInset': {'base_color': '327D89', 'roughness': .37, 'metallic': .15,
                             'emissive_color': '58CFDB', 'emissive_strength': .7},
    'M_SP_Ruins_StarCore': {'base_color': 'A0E2DC', 'roughness': .31, 'metallic': .12,
                            'emissive_color': '89EAE9', 'emissive_strength': 1.3},
}

def rgba(s):
    values = [int(s[i:i+2], 16)/255 for i in (0, 2, 4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values)+(1,)

materials = {}
for name, props in MATERIALS.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba(props['base_color'])
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = props['roughness']
    shader.inputs['Metallic'].default_value = props['metallic']
    if 'base_color_texture' in props:
        image = bpy.data.images.load(str(ROOT/props['base_color_texture']))
        image.pack()
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = image
        mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
    if 'emissive_color' in props:
        shader.inputs['Emission Color'].default_value = rgba(props['emissive_color'])
        shader.inputs['Emission Strength'].default_value = props['emissive_strength']
    materials[name] = mat

STONE = 'M_SP_Ruins_PaintedStone'
PALE = 'M_SP_Ruins_PaleStone'
SHADOW = 'M_SP_Ruins_ShadowStone'
MOSS = 'M_SP_Ruins_Moss'
BRASS = 'M_SP_Ruins_Brass'
BRIGHT = 'M_SP_Ruins_BrassLight'
CYAN = 'M_SP_Ruins_StarInset'

def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def mesh_object(name, vertices, faces, material):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces); mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh); library.objects.link(obj)
    mesh.materials.append(materials[material])
    for poly in mesh.polygons: poly.use_smooth = True
    return obj

def bevel(obj, width=.025, segments=3):
    activate(obj)
    mod = obj.modifiers.new('SoftFractureEdges', 'BEVEL')
    mod.width = width; mod.segments = segments; mod.limit_method = 'ANGLE'; mod.angle_limit = .32
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = obj.modifiers.new('BroadFractureNormals', 'WEIGHTED_NORMAL')
    mod.keep_sharp = True; mod.weight = 60
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj

def prism_xz(name, outline, front, back, material):
    n = len(outline)
    vertices = [(x, y, z) for y in (front, back) for x, z in outline]
    faces = [tuple(range(n-1, -1, -1)), tuple(n+i for i in range(n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    return mesh_object(name, vertices, faces, material)

def cube(name, loc, dims, material, rounding=.025):
    x, y, z = loc; dx, dy, dz = [v/2 for v in dims]
    obj = prism_xz(name, [(x-dx, z-dz), (x+dx, z-dz), (x+dx, z+dz), (x-dx, z+dz)], y-dy, y+dy, material)
    return bevel(obj, rounding)

def oval(name, center, scale, material, seed=0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=center)
    obj = bpy.context.object; obj.name = name
    for col in list(obj.users_collection): col.objects.unlink(obj)
    library.objects.link(obj)
    for v in obj.data.vertices:
        a = math.atan2(v.co.y, v.co.x)
        fac = 1+.12*math.cos(3*a+seed)+.08*math.sin(5*a-seed)
        v.co.x *= fac; v.co.y *= fac
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(materials[material])
    for poly in obj.data.polygons: poly.use_smooth = True
    return obj

def star_outline(center, radius, points=8, inner=.24, compass=False):
    result=[]
    for i in range(2*points):
        angle=math.pi/2+math.tau*i/(2*points)
        r=radius if i%2 == 0 else radius*inner
        if compass and i%4 == 2: r *= .64
        result.append((center[0]+r*math.cos(angle), center[1]+r*math.sin(angle)))
    return result

def relief_star(name, x, z, radius, front=-.53, points=8):
    outline = star_outline((x,z), radius, points, .25, points==8)
    obj = prism_xz(name, outline, front-.028, front+.005, BRASS)
    obj.data.materials.append(materials[BRIGHT])
    # Triangular facets on the front read as old beaten brass at top-down range.
    n=len(outline)
    face_verts=[(x,front-.05,z)]+[(px,front-.029,pz) for px,pz in outline]
    fan = mesh_object(name+'Facets', face_verts, [(0,i+1,(i+1)%n+1) for i in range(n)], BRASS)
    fan.data.materials.append(materials[BRIGHT])
    for i,p in enumerate(fan.data.polygons): p.material_index=i%2
    return [obj, fan]

def ring_sector(name, inner, outer, start, end, low, high, material, segments=4, gap=.0):
    angles=[start+(end-start)*i/segments for i in range(segments+1)]
    vertices=[]
    if inner <= 0:
        outline=[(0,0)]+[(outer*math.cos(a),outer*math.sin(a)) for a in angles]
    else:
        outline=[(inner*math.cos(a),inner*math.sin(a)) for a in reversed(angles)]
        outline += [(outer*math.cos(a),outer*math.sin(a)) for a in angles]
    n=len(outline)
    vertices=[(x,y,z) for z in (low,high) for x,y in outline]
    faces=[tuple(range(n-1,-1,-1)),tuple(n+i for i in range(n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh_object(name,vertices,faces,material)

def gate():
    parts=[]
    # Broad 15 cm steps on both sides, plus a third central passage tread.
    for row,(width,depth,low,high) in enumerate(((5.65,2.25,0,.15),(5.25,1.60,.15,.30))):
        n=7
        for i in range(n):
            x=(i-(n-1)/2)*width/n
            parts.append(cube('GateAccessibleStep', (x,0,(low+high)/2), (width/n-.009,depth,high-low), STONE, .016))
    for i in range(3):
        parts.append(cube('GateCentralPassageTread',(.65+(i-1)*.7,0,.375),(.694,1.02,.15),STONE,.012))
    # The inner circle reaches below the passage tread, leaving a real opening
    # to walk through instead of the half-metre barrier a complete crescent has.
    ro, ri, offset, cz = 3.0, 2.75, .8, 3.0
    start=math.acos((ro*ro+offset*offset-ri*ri)/(2*ro*offset))+.009
    end=math.tau-start
    rng=random.Random(1881)
    for row,count in ((0,27),(1,31)):
        for i in range(count):
            a=start+(end-start)*i/count+.0023
            b=start+(end-start)*(i+1)/count-.0023
            angles=[a+(b-a)*j/3 for j in range(4)]
            edge=[]
            for u, aa in ((row*.5+.005,angles),((row+1)*.5-.005,reversed(angles))):
                for t in aa:
                    inner=offset*math.cos(t)+math.sqrt(ri*ri-offset*offset*math.sin(t)**2)
                    r=inner+(ro-inner)*u
                    edge.append((r*math.cos(t)+.28,cz+r*math.sin(t)))
            y=-.465+rng.uniform(-.018,.018)
            mat=STONE if rng.random()<.85 else PALE
            parts.append(bevel(prism_xz('CrescentFractureBlock',edge,y,.465+rng.uniform(-.03,.03),mat),.018))
    for x,z,r in ((-1.93,4.42,.36),(-2.10,3.22,.23),(-1.35,1.36,.22),(-.45,5.57,.20),(-2.12,2.21,.16),(.40,5.87,.10)):
        parts += relief_star('AncientBrassGateStar',x,z,r)
    for i in range(15):
        a=math.radians(72+i*16)
        inner=offset*math.cos(a)+math.sqrt(ri*ri-offset*offset*math.sin(a)**2)
        r=inner+(ro-inner)*(.44 if i%2 else .88)
        x,z=r*math.cos(a)+.28,cz+r*math.sin(a)
        parts.append(oval('CrescentSeamMoss',(x,-.479,z),(.11,.023,.052),MOSS,i))
    for x,y,s in ((-2.42,-.72,.25),(-2.58,.72,.2),(2.33,.55,.2),(-1.7,.66,.16),(1.81,-.82,.17)):
        parts.append(oval('GateFootMoss',(x,y,.15),(s,s*.7,.028),MOSS,int(x*30)))
    return finish('SM_SP_CrescentGate',parts)

def dais():
    parts=[]
    # Overall diameter 3.6 m. Full circumference has 30 cm tread and 15 cm rise.
    for row,(radius,low,high,count) in enumerate(((1.8,0,.15,20),(1.5,.15,.3,18))):
        for i in range(count):
            a=math.tau*i/count+.0015; b=math.tau*(i+1)/count-.0015
            obj=ring_sector('DaisRadialCutStone',0,radius,a,b,low,high,STONE,4)
            parts.append(bevel(obj,.009))
    # Flush inlays stand only 2 mm proud, below character step tolerance.
    parts.append(ring_sector('FlushBrassObservationRing',1.275,1.292,0,math.tau,.300,.302,BRASS,128))
    outline=star_outline((0,0),1.03,8,.225,True)
    n=len(outline)
    verts=[(0,0,.3025)]+[(x,y,.302) for x,y in outline]
    star=mesh_object('FlushBrassCompassStar',verts,[(0,i+1,(i+1)%n+1) for i in range(n)],BRASS)
    star.data.materials.append(materials[BRIGHT])
    for i,p in enumerate(star.data.polygons): p.material_index=i%2
    parts.append(star)
    for i in range(8):
        a=math.tau*i/8
        parts.append(oval('BrassRingRivet',(1.284*math.cos(a),1.284*math.sin(a),.301),(.035,.035,.003),BRIGHT,i))
    for i in (0,3,7,11,14,18):
        a=math.tau*i/20
        parts.append(oval('SmallStepMoss',(1.66*math.cos(a),1.66*math.sin(a),.148),(.10,.08,.017),MOSS,i))
    return finish('SM_SP_ViewingDais',parts)

def menhir(index):
    sx=1.04 if index==1 else .78
    sy=.74 if index==1 else .63
    # The wide front is a deliberate planar fracture, not a rounded pebble.
    outline=[(-.32,-.5),(.32,-.5),(.5,-.28),(.48,.32),(.28,.5),(-.30,.47),(-.5,.22),(-.49,-.27)]
    rings=[(0,.80,0),(.17,1,0),(.72,1.03,.012),(1.22,.88,-.022),(1.57,.45,.065 if index==1 else -.08),(1.70,.15,.09 if index==1 else -.12)]
    vertices=[((x*s+dx)*sx,y*sy*s,z) for z,s,dx in rings for x,y in outline]
    n=len(outline); faces=[tuple(range(n-1,-1,-1))]
    for j in range(len(rings)-1):
        for i in range(n): faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    faces.append(tuple((len(rings)-1)*n+i for i in range(n)))
    stone=mesh_object('BroadFracturedMenhir',vertices,faces,STONE)
    radius=.295 if index==1 else .225; z=.91 if index==1 else .86
    star=star_outline((0,z),radius,5,.43)
    cutter=prism_xz('TemporaryStarRecess',star,-.8,-sy*.30,SHADOW)
    activate(stone)
    mod=stone.modifiers.new('ActualCarvedStarRecess','BOOLEAN'); mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    bevel(stone,.019)
    parts=[stone]
    inset=prism_xz('RecessedTurquoiseStar',star_outline((0,z),radius*.925,5,.43),-sy*.305,-sy*.292,CYAN)
    parts.append(bevel(inset,.008,2))
    # Small luminous center is kept inside the cavity behind the face.
    core=prism_xz('RecessedStarHeart',star_outline((0,z),radius*.39,5,.43),-sy*.31,-sy*.302,'M_SP_Ruins_StarCore')
    parts.append(core)
    for i,(x,y,w,h) in enumerate(((-.34,-.12,.16,.13),(.31,.08,.20,.18),(-.2,.25,.15,.10),(.21,-.23,.11,.09))):
        parts.append(cube('MenhirBrokenFootstone',(x*sx,y*sy,h/2),(w,.19,h),STONE,.025))
        parts.append(oval('MenhirFootMoss',(x*sx,y*sy,h*.85),(w*.58,.105,.025),MOSS,i))
    # Fine brass datum beneath the star gives the monolith a readable front.
    parts += relief_star('MenhirSmallBrassMark',0,.39,.055,-sy*.52,4)
    return finish(f'SM_SP_StarMenhir_{index:02}',parts)

def finish(name,parts):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts: obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join(); obj=bpy.context.object; obj.name=name
    scene.cursor.location=(0,0,0); bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    tri=obj.modifiers.new('FBXTriangles','TRIANGULATE')
    if hasattr(tri,'keep_custom_normals'): tri.keep_custom_normals=True
    bpy.ops.object.modifier_apply(modifier=tri.name)
    # Bevel intersections at the tapering crescent tips can produce collapsed
    # slivers. Remove only effectively zero-area faces before UV/FBX creation.
    bm=bmesh.new(); bm.from_mesh(obj.data)
    tiny=[face for face in bm.faces if face.calc_area()<1e-8]
    if tiny: bmesh.ops.delete(bm,geom=tiny,context='FACES_ONLY')
    bm.to_mesh(obj.data); bm.free()
    if not obj.data.uv_layers: obj.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.011)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Reuse generated painted rock over large islands instead of per-triangle colors.
    obj.data.update()
    if not obj.data.has_custom_normals:
        obj.data.normals_split_custom_set([tuple(n.vector) for n in obj.data.corner_normals])
    obj['asset_id']=name; obj['collision']='complex'; obj['front_axis']='-Y'
    return obj

def bounds(obj):
    return [[min(v.co[a] for v in obj.data.vertices) for a in range(3)],
            [max(v.co[a] for v in obj.data.vertices) for a in range(3)]]

assets=[gate(),dais(),menhir(1),menhir(2)]
# Verify the actual triangulated passage, including all decorative geometry.
gate_mesh=assets[0].data
gate_bvh=BVHTree.FromPolygons([v.co for v in gate_mesh.vertices],
                            [tuple(p.vertices) for p in gate_mesh.polygons],all_triangles=True)
clearance_rays=0
for x in (.15,.40,.65,.90,1.15):
    for z in (.52,.75,1.05,1.45,1.85,2.25,2.65):
        hit=gate_bvh.ray_cast(Vector((x,-1.5,z)),Vector((0,1,0)),3)
        assert hit[0] is None, ('gate passage obstruction',x,z,hit[0])
        clearance_rays+=1
floor_heights=[]
for i in range(97):
    y=-1.2+i*.025
    hit=gate_bvh.ray_cast(Vector((.65,y,2.4)),Vector((0,0,-1)),3)
    floor_heights.append(float(hit[0].z) if hit[0] else 0)
max_step=max(abs(a-b) for a,b in zip(floor_heights,floor_heights[1:]))
assert max_step <= .151, ('gate step too high',max_step)
infos=[]
for obj in assets:
    activate(obj); bb=bounds(obj)
    assert abs(bb[0][2])<1e-5, (obj.name,bb)
    assert all(len(p.vertices)==3 and p.area>1e-12 for p in obj.data.polygons), obj.name
    assert all(p.use_smooth for p in obj.data.polygons)
    assert obj.data.has_custom_normals and obj.data.uv_layers.active
    info={'asset_id':obj.name,'file':f'ArtSource/Meshes/StarPond/{obj.name}.fbx',
          'materials':[m.name for m in obj.data.materials], 'collision':'complex',
          'dimensions_m':[bb[1][i]-bb[0][i] for i in range(3)],
          'bounds_min_m':bb[0],'bounds_max_m':bb[1],
          'triangles':len(obj.data.polygons),'vertices':len(obj.data.vertices),
          'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS','pivot':'floor origin at Z=0',
          'uv_channel':0,'front_axis':'-Y'}
    export_path=ROOT/info['file']
    if export_path.exists(): export_path.unlink()
    bpy.ops.export_scene.fbx(filepath=str(export_path),use_selection=True,object_types={'MESH'},
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True,
        path_mode='STRIP',use_tspace=True)
    obj.hide_render=True; obj.hide_set(True); infos.append(info)

roundtrip=[]
for expected in infos:
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(ROOT/expected['file']),use_custom_normals=True)
    added=set(bpy.data.objects)-before; meshes=[o for o in added if o.type=='MESH']
    assert len(meshes)==1
    obj=meshes[0]; actual=bounds(obj)
    error=max(abs(actual[j][i]-[expected['bounds_min_m'],expected['bounds_max_m']][j][i]) for j in range(2) for i in range(3))
    assert error<2e-5,(expected['asset_id'],error)
    assert len(obj.data.polygons)==expected['triangles']
    assert obj.data.has_custom_normals and all(p.use_smooth for p in obj.data.polygons)
    assert len(obj.data.materials)==len(expected['materials'])
    actual_mats=[m.name.rsplit('.',1)[0] if m.name.rsplit('.',1)[-1].isdigit() else m.name for m in obj.data.materials]
    assert actual_mats==expected['materials'],actual_mats
    assert obj.data.uv_layers.active
    finite=all(math.isfinite(v) for loop in obj.data.uv_layers.active.data for v in loop.uv)
    assert finite
    roundtrip.append({'asset_id':expected['asset_id'],'passed':True,'bounds_error_m':error,
                     'triangle_count_preserved':True,'ordered_material_slots_preserved':True,
                     'authored_normals_preserved':True,'all_faces_smooth':True,'finite_uv':True,
                     'ground_pivot_preserved':True})
    for obj in added: bpy.data.objects.remove(obj,do_unlink=True)

metadata={'source':'ArtSource/Blender/StarPondRuins.blend','script':'Scripts/build_starpond_ruins.py',
          'reference':'ArtSource/Reference/StarPond/Ref_StarPondRuins.png','units':'metres',
          'materials':MATERIALS,'assets':infos,
          'placement_notes':'Gate faces -Y with an open passage centered near local X=0.65 m and three 15 cm steps (landing Z=0.45 m). '
                            'Dais is 3.6 m diameter overall, with a 3.0 m upper observation platform; '
                            'both rises are 15 cm. Brass inlay is at most 5 mm above the stone. '
                            'Menhirs are 1.7 m high, with actual recessed cyan stars facing -Y.',
          'fbx_roundtrip_validation':roundtrip}
(ART/'Layout/starpond_ruins.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
validation={'passed':True,'asset_count':4,'assets':infos,'fbx_roundtrip_validation':roundtrip,
            'accessibility':{'step_rise_m':.15,'dais_outer_diameter_m':3.6,'dais_top_height_m':.3,
                             'dais_max_inlay_relief_m':.005,'gate_passage_floor_height_m':.45,
                             'gate_passage_center_x_m':.65,'gate_clearance_rays_passed':clearance_rays,
                             'gate_walkable_floor_samples':len(floor_heights),'gate_max_measured_step_m':max_step}}
(ART/'Previews/StarPondRuins_Validation.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')

positions=[(-2.55,1.55,0),(2.9,-1.55,0),(3.35,2.00,0),(4.75,2.05,0)]
for original,position in zip(assets,positions):
    duplicate=bpy.data.objects.new('Preview_'+original.name,original.data)
    display.objects.link(duplicate); duplicate.location=position
ground=bpy.data.materials.new('PreviewOnlySageGround'); ground.use_nodes=True
ground.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.17,.205,.175,1)
ground.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.94
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.018))
bpy.context.object.name='PreviewOnlyGround'; bpy.context.object.data.materials.append(ground)
scene.world=bpy.data.worlds.new('PreviewOnlySoftSky'); scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.64,.77,.91,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.7
bpy.ops.object.light_add(type='SUN',location=(-5,-8,12)); sun=bpy.context.object
sun.rotation_euler=(.4,-.5,-.55); sun.data.energy=2.4; sun.data.angle=math.radians(50)
bpy.ops.object.light_add(type='AREA',location=(-5,-7,9)); light=bpy.context.object
light.data.energy=850; light.data.shape='DISK'; light.data.size=6
light.rotation_euler=(Vector((0,0,2))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(10,-20,14)); camera=bpy.context.object
camera.rotation_euler=(Vector((.0,.4,2.25))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'; camera.data.ortho_scale=13.8; scene.camera=camera
scene.render.engine='CYCLES'; scene.cycles.samples=48; scene.cycles.use_denoising=True
scene.render.resolution_x=1800; scene.render.resolution_y=1350; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(ART/'Previews/Blender_StarPondRuins.png')
scene.view_settings.view_transform='AgX'; scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/StarPondRuins.blend'))
bpy.ops.render.render(write_still=True)
print('STAR_POND_RUINS_COMPLETE '+json.dumps(infos))
