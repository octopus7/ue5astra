"""Place a terrain-fitted shoreline review beside the saved pink cottage.

Run Blender 4.5 in background.  Reads the existing woodland scene/heightmap;
writes only the separate review scene, site FBX files, site manifest and PNG.
The baseline woodland, house placement and Landscape remain unchanged.
"""
import bpy
import bmesh
import hashlib
import importlib.util
import json
import math
import random
import struct
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
SOURCE = ART / 'Blender' / 'AstraWoodland.blend'
KIT_SOURCE = ART / 'Blender' / 'AstraShorelineKit.blend'
SITE_BLEND = ART / 'Blender' / 'AstraLakeshoreReview.blend'
SITE_JSON = ART / 'Layout' / 'shoreline_site.json'
SITE_MESHES = ART / 'Meshes' / 'ShorelineSite'
SITE_PNG = ART / 'Previews' / 'Blender_ShorelineSite.png'
HEIGHT = ART / 'Layout' / 'landscape_height.r16'
LAYOUT = ART / 'Layout' / 'woodland_layout.json'
WATER = 0.10
ORIGIN = Vector((18.0, -34.0, WATER))
PROTECTED = (SOURCE, HEIGHT, LAYOUT)
SOURCE_HASHES = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in PROTECTED}
META = json.loads(LAYOUT.read_text(encoding='utf-8'))
KIT_META = json.loads((ART / 'Layout' / 'shoreline_assets.json').read_text(encoding='utf-8'))
HEIGHTS = struct.unpack('<16129H', HEIGHT.read_bytes())
RNG = random.Random(907580)


def saturate(value):
    return max(0.0, min(1.0, value))


def smooth(a, b, value):
    t = saturate((value-a)/(b-a))
    return t*t*(3.0-2.0*t)


def terrain(x, y):
    """Bilinear samples from the actual unsigned16 UE heightmap; UE XY metres."""
    fx, fy = saturate((x+50.4)/100.8)*126, saturate((y+50.4)/100.8)*126
    i, j = min(125, int(fx)), min(125, int(fy))
    tx, ty = fx-i, fy-j
    return sum((HEIGHTS[(j+dj)*127+i+di]-32768)/128.0
               * (tx if di else 1-tx) * (ty if dj else 1-ty)
               for di in (0, 1) for dj in (0, 1))


def shore_y(x):
    lo, hi = 28.0, 37.0
    for _ in range(36):
        mid = (lo+hi)*0.5
        if terrain(x, mid) > WATER:
            hi = mid
        else:
            lo = mid
    return (lo+hi)*0.5


def shore_shift(x):
    """Two broad spits project slightly lakeward; the middle stays recessed.

    Raising an overlay on the water side adds shoreline rhythm without cutting
    the immutable Landscape or taking any space from the cottage path.
    """
    ends = smooth(11.4,13.0,x)*(1-smooth(22.9,24.7,x))
    spits = (.47*math.exp(-((x-14.1)/1.65)**2)
             + .64*math.exp(-((x-21.4)/1.9)**2))
    return -ends*spits


def site_shore_y(x):
    return shore_y(x)+shore_shift(x)


def wet_width(x):
    """Shallow visibility varies over whole coves, not fine edge noise."""
    return (3.05 + 1.20*math.exp(-((x-14.0)/1.9)**2)
            + 1.42*math.exp(-((x-21.5)/1.8)**2)
            - .63*math.exp(-((x-17.9)/1.5)**2))


def far_width(x):
    return wet_width(x)+1.45+.16*math.sin(x*.91+.7)


def profile(distance, width):
    # An analytic C1 profile avoids a hard kink between the flat shallows and
    # the deeper skirt. The actual terrain blend handles the final immersion.
    t = max(0.0, distance)/width
    return WATER-.026-.155*t-.79*t*t


def mesh_attributes(mesh):
    """Projected metre UVs and local water/depth hints for every triangle."""
    mesh.update()
    uv = mesh.uv_layers.get('UVMap') or mesh.uv_layers.new(name='UVMap')
    for face in mesh.polygons:
        axis = max(range(3), key=lambda a: abs(face.normal[a]))
        axes = ((1, 2), (0, 2), (0, 1))[axis]
        for index in face.loop_indices:
            co = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (co[axes[0]], co[axes[1]])
    attr = mesh.color_attributes.get('ShoreData')
    if attr is None:
        attr = mesh.color_attributes.new(name='ShoreData', type='FLOAT_COLOR', domain='POINT')
    for v, colour in zip(mesh.vertices, attr.data):
        wx, wy, wz = ORIGIN+v.co
        distance = site_shore_y(wx)+wy
        colour.color = (saturate((WATER-wz)/1.5), saturate(distance/4.0), 0, 1)


def validate(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bad_edges = sum(not e.is_manifold for e in bm.edges)
    bad_faces = sum(f.calc_area()<1e-10 for f in bm.faces)
    volume = bm.calc_volume(signed=True)
    bm.free()
    uv = mesh.uv_layers.active.data
    bad_uv = 0
    for tri in mesh.loop_triangles:
        a, b, c = (uv[li].uv for li in tri.loops)
        bad_uv += abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)) < 1e-10
    assert bad_edges == bad_faces == bad_uv == 0, (obj.name, bad_edges, bad_faces, bad_uv)
    assert volume > 0, (obj.name, volume)
    return {'triangles': len(mesh.loop_triangles), 'vertices': len(mesh.vertices),
            'non_manifold_edges': bad_edges, 'degenerate_uv_triangles': bad_uv,
            'signed_volume_m3': volume,
            'smooth_shaded_polygons':sum(face.use_smooth for face in mesh.polygons)}


def create_mesh(name, vertices, faces, mats, indices):
    mesh = bpy.data.meshes.new(name+'_Mesh')
    mesh.from_pydata(vertices, [], faces)
    for mat in mats:
        mesh.materials.append(mat)
    for face, index in zip(mesh.polygons, indices):
        face.material_index = index
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh_attributes(mesh)
    obj = bpy.data.objects.new(name, mesh)
    library.objects.link(obj)
    obj['asset_id'] = name
    obj['collision'] = 'none'
    obj['shore_kind'] = 'terrain_fitted_site'
    return obj


def build_bed():
    # The outer ring lies below the actual terrain.  It is curved in plan and
    # tapers down at both ends; no rectangular cliff/skirt can emerge in water.
    xs = [11.0+i*(14.3/40) for i in range(41)]
    # Positive rows are inland metres. Negative rows are fractions of the
    # varying full underwater extent; resolution supports smooth bends only.
    offsets = (0.95,0.60,0.25,0.0,-.055,-.12,-.20,-.29,-.39,
               -.49,-.59,-.69,-.78,-.86,-.925,-.97,-1.0)
    vertices, faces, indices = [], [], []
    cols, rows = len(xs), len(offsets)
    top_world = []
    boundary_blend = []
    for row, base_d in enumerate(offsets):
        for col, base_x in enumerate(xs):
            x = base_x
            if 0 < row < rows-1 and 0 < col < cols-1:
                x += RNG.uniform(-0.068,0.068)
            width = wet_width(x)
            extent = far_width(x)
            d = base_d if base_d >= 0 else base_d*extent
            if 3 < row < rows-1 and 0 < col < cols-1:
                d += RNG.uniform(-.021,.021)
            y = site_shore_y(x)+d
            ground = terrain(x, y)
            goal = profile(-d,width)
            goal += .011*math.sin(x*.64+d*.52)*smooth(.15,1.0,-d)
            if d > 0:
                # Support the small raised bank lobes, then disappear inland.
                goal = max(goal+.24*smooth(0,.7,d),ground-.035)
            end_weight = smooth(11.0,13.0,x)*(1-smooth(22.8,25.3,x))
            land_weight = 1-smooth(0.10,0.95,d)
            # A 2 m-scale irregular immersion band replaces the previous lip.
            blend_start = width*.63+.11*math.sin(x*.73)
            far_weight = 1-smooth(blend_start,extent,-d)
            weight = end_weight*land_weight*far_weight
            z = (ground-0.10)*(1-weight)+goal*weight
            if row in (0, rows-1) or col in (0, cols-1):
                z = ground-0.10
                weight = 0.0
            top_world.append((x, y, z))
            boundary_blend.append(saturate(1.0-weight))
            vertices.append(tuple(Vector((x, -y, z))-ORIGIN))
    for row in range(rows-1):
        for col in range(cols-1):
            a=row*cols+col
            b, c, d = a+1, a+cols, a+cols+1
            pairs = ((a,b,c),(b,d,c)) if RNG.random()<0.5 else ((a,b,d),(a,d,c))
            for face in pairs:
                faces.append(face)
                x = sum(top_world[i][0] for i in face)/3
                y = sum(top_world[i][1] for i in face)/3
                depth = site_shore_y(x)-y
                tone = 0.5+0.18*math.sin(x*0.64-depth*0.4)+0.16*math.cos(depth*0.8+x*0.3)
                indices.append(1 if tone>0.67 else 2 if tone<0.31 else 0)
    top_triangles = len(faces)
    boundary = list(range(cols))
    boundary += [r*cols+cols-1 for r in range(1,rows)]
    boundary += [(rows-1)*cols+c for c in range(cols-2,-1,-1)]
    boundary += [r*cols for r in range(rows-2,0,-1)]
    bottom_start = len(vertices)
    for index in boundary:
        x, y, _ = vertices[index]
        vertices.append((x, y, -2.10))
        boundary_blend.append(1.0)
    bottom_centre = len(vertices)
    vertices.append((0, 2, -2.10))
    boundary_blend.append(1.0)
    for ring, a in enumerate(boundary):
        nxt=(ring+1)%len(boundary)
        b=boundary[nxt]
        ba, bb=bottom_start+ring,bottom_start+nxt
        faces.extend(((a,ba,bb),(a,bb,b),(bottom_centre,bb,ba)))
        indices.extend((2,2,2))
    obj = create_mesh('SM_ShorelineSite_CurvedBed', vertices, faces,
                      [mats[n] for n in ('M_ShoreSand','M_ShoreSandLight','M_ShoreSandDark')], indices)
    for polygon in obj.data.polygons:
        polygon.use_smooth = polygon.index < top_triangles
    # B was reserved in the generic kit. This site bed now supplies the exact
    # continuous blend back to the pre-existing lake floor: 0=sand, 1=floor.
    # R/G/A and all authored geometry/UV/normals remain unchanged.
    shore_data = obj.data.color_attributes['ShoreData']
    for colour, blend in zip(shore_data.data,boundary_blend):
        rgba = list(colour.color)
        rgba[2] = blend
        colour.color = rgba
    obj['top_triangle_count'] = top_triangles
    obj['source_kit'] = 'SM_ShallowShelf_01 / SM_ShallowShelf_Cove_01 profile'
    obj['description_ko'] = '두 개의 넓은 돌출부와 중앙의 좁은 만으로 폭이 달라지는 부드러운 수중 선반. 외곽과 양끝은 기존 지형 아래로 완만하게 매립.'
    obj['wet_width_range_m'] = [min(wet_width(x) for x in xs),max(wet_width(x) for x in xs)]
    obj['shore_projection_range_m'] = [min(shore_shift(x) for x in xs),max(shore_shift(x) for x in xs)]
    obj['shoredata_blue_meaning'] = '1 - end_weight * land_weight * far_weight; 0=sand interior, 1=baseline floor/closure boundary.'
    obj['shoredata_blue_intermediate_vertices'] = sum(0.0<b<1.0 for b in boundary_blend)
    # Confirm the complete closure boundary is below unchanged terrain.
    gaps = [top_world[i][2]-terrain(top_world[i][0],top_world[i][1]) for i in boundary]
    assert max(gaps)<-0.09
    obj['maximum_boundary_above_terrain_m'] = max(gaps)
    return obj


def build_bank(source_id, centre, label):
    source = kit[source_id]
    mesh = source.data.copy()
    obj = bpy.data.objects.new(label, mesh)
    library.objects.link(obj)
    for vertex in mesh.vertices:
        sx, sy, sz = vertex.co
        x = centre-sx
        # Both small bank spits and the smooth bed share the same contour.
        y = site_shore_y(x)+sy-0.055
        ground = terrain(x,y)
        z = WATER+sz
        # Ends of the full stretch submerge into the existing Landscape.
        fade = (smooth(11.5,12.5,x)*(1-smooth(22.6,23.7,x))
                * smooth(0.0,0.60,2.0-abs(sx)))
        z = min(z,ground-0.09)*(1-fade)+z*fade
        vertex.co = Vector((x,-y,z))-ORIGIN
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    mesh_attributes(mesh)
    obj['asset_id']=label
    obj['source_kit']=source_id
    obj['collision']='none'
    obj['description_ko']='공유 해안 키트를 실제 호수 곡률에 맞춰 변형한 현장용 낮은 흙턱.'
    return obj


def record(obj):
    loc, e, scale = obj.location, obj.rotation_euler, obj.scale
    return {'name':obj.name,'asset':obj['asset_id'],'group':'Shoreline/Site',
            'collision':'none','blender_location_m':list(loc),
            'blender_rotation_euler_rad':list(e),'scale':list(scale),
            'ue_location_cm':[loc.x*100,-loc.y*100,loc.z*100],
            'ue_rotation_deg':{'pitch':-math.degrees(e.y),'yaw':-math.degrees(e.z),'roll':math.degrees(e.x)}}


def instance(source, name, location, yaw=0, scale=1):
    obj=bpy.data.objects.new(name,source.data)
    site.objects.link(obj)
    obj.location=location
    obj.rotation_euler.z=math.radians(yaw)
    obj.scale=(scale,scale,scale)
    obj['asset_id']=source['asset_id']
    obj['collision']='none'
    obj['group']='Shoreline/Site'
    return obj


def export_asset(obj):
    obj.hide_set(False)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    destination=SITE_MESHES/(obj.name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(destination),use_selection=True,
        object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,
        mesh_smooth_type='FACE',use_mesh_modifiers=True,use_custom_props=True,
        colors_type='LINEAR',prioritize_active_color=True)
    dimensions=[max(v.co[a] for v in obj.data.vertices)-min(v.co[a] for v in obj.data.vertices)
                for a in range(3)]
    return {'file':destination.relative_to(ART).as_posix(),'materials':[m.name for m in obj.data.materials],
            'collision':'none','dimensions_m':dimensions,'validation':validate(obj)}


bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1.0
SITE_MESHES.mkdir(parents=True,exist_ok=True)
library=bpy.data.collections.new('04_ShorelineSiteAssets')
site=bpy.data.collections.new('05_ShorelineSitePlacement')
scene.collection.children.link(library)
scene.collection.children.link(site)
library.hide_render=True
with bpy.data.libraries.load(str(KIT_SOURCE),link=False) as (src,dst):
    dst.objects=[name for name in KIT_META['assets'] if name in src.objects]
kit={}
for obj in dst.objects:
    library.objects.link(obj)
    obj['asset_id']=obj.name
    obj.hide_render=True
    obj.hide_set(True)
    for slot in obj.material_slots:
        canonical=slot.material.name.split('.')[0]
        existing=bpy.data.materials.get(canonical)
        if existing:slot.material=existing
        else:slot.material.name=canonical
    kit[obj.name]=obj
mats={name:bpy.data.materials[name] for name in KIT_META['palette_srgb_hex'] if name in bpy.data.materials}

assets=[build_bed(),
        build_bank('SM_ShoreBank_Curve_01',13.7,'SM_ShorelineSite_BankWest'),
        build_bank('SM_ShoreBank_Low_01',17.55,'SM_ShorelineSite_BankLow'),
        build_bank('SM_ShoreBank_Straight_01',21.4,'SM_ShorelineSite_BankEast')]
asset_manifest={obj.name:export_asset(obj) for obj in assets}
instances=[instance(obj,'AST_Shoreline_'+obj.name.removeprefix('SM_ShorelineSite_'),ORIGIN) for obj in assets]
bpy.context.view_layer.update()
bed=instances[0]

stone_specs=[
 ('SM_SubmergedRock_Flat_01',12.8,-1.28,25,.75),
 ('SM_SubmergedRock_Round_01',13.3,-.42,12,.57),
 ('SM_SubmergedPebbles_01',14.6,-2.30,47,.80),
 ('SM_SubmergedRock_Small_01',15.4,-.70,-25,.70),
 ('SM_SubmergedRock_Flat_01',16.4,-1.48,-18,.90),
 ('SM_SubmergedPebbles_01',17.15,-3.05,31,.78),
 ('SM_SubmergedRock_Small_01',18.10,-1.22,64,.75),
 ('SM_SubmergedRock_Round_01',19.25,-.50,-28,.61),
 ('SM_SubmergedRock_Flat_01',20.10,-1.65,29,.80),
 ('SM_SubmergedPebbles_01',21.65,-2.55,-15,.70),
 ('SM_SubmergedRock_Small_01',22.1,-.93,80,.67),
 ('SM_SubmergedRock_Round_01',22.8,-1.65,18,.45)]
for index,(asset,x,offset,yaw,scale) in enumerate(stone_specs):
    # Keep the existing twelve names and visual groups inside the newly
    # varying shallow footprint rather than leaving a cluster on its deep lip.
    offset *= min(1.15,wet_width(x)/3.55)
    y=site_shore_y(x)+offset
    inverse=bed.matrix_world.inverted()
    hit, point, _, _=bed.ray_cast(inverse@Vector((x,-y,4)),Vector((0,0,-1)))
    assert hit, ('No bed beneath stone',index,x,y)
    z=(bed.matrix_world@point).z-.035
    source=kit[asset]
    instances.append(instance(source,f'AST_Shoreline_Stone_{index+1:02}',(x,-y,z),yaw,scale))
    asset_manifest[asset]=KIT_META['assets'][asset]

hidden=[]
for obj in bpy.data.collections['02_WoodlandLayout'].objects:
    if obj.get('group')!='Rocks/LakeShore':continue
    x,y=obj.location.x,-obj.location.y
    if 11.8<x<24.1 and abs(y-shore_y(x))<1.8:
        obj.hide_render=True
        obj.hide_set(True)
        hidden.append(obj.name)

# The base Blender water is opaque.  Dry geometry inspection hides it only in
# this separate review scene; runtime hide records contain shore boulders only.
review_hidden_water=[]
for obj in bpy.data.collections['02_WoodlandLayout'].objects:
    if obj.get('asset_id')=='SM_LakeSurface':
        obj.hide_render=True
        obj.hide_set(True)
        review_hidden_water.append(obj.name)

for obj in assets:
    obj.hide_render=True
    obj.hide_set(True)
camera_data=bpy.data.cameras.new('LakeshoreSiteReviewCamera')
camera_data.type='ORTHO'
camera_data.ortho_scale=23.5
camera_data.clip_end=250
camera=bpy.data.objects.new('LakeshoreSiteReviewCamera',camera_data)
site.objects.link(camera)
look=Vector((17.3,-36.1,.25))
camera.location=look+Vector((-math.cos(math.radians(58))*35,0,math.sin(math.radians(58))*35))
camera.rotation_euler=(look-camera.location).to_track_quat('-Z','Y').to_euler()
scene.camera=camera
scene.render.engine='BLENDER_EEVEE_NEXT'
scene.render.resolution_x=1600
scene.render.resolution_y=1200
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(SITE_PNG)
scene['shoreline_review_note']='Dry geometry QA: lake hidden only in review blend; runtime water untouched.'
scene['shoreline_source_heightmap_sha256']=SOURCE_HASHES[str(HEIGHT)]
bpy.context.preferences.filepaths.save_version=0

manifest={
 'version':1,'source':'Scripts/place_shoreline_blender.py',
 'description':'집 앞 약12m의 높이맵을 보존하면서 두 돌출부와 중앙 만으로 폭이 변하는 부드러운 모래 선반, 낮은 흙턱과 수중돌 배치. 기존 큰 돌벽은 해당 구간에서만 숨김.',
 'units':'metres','axis_mapping':'UE=(Blender.X,-Blender.Y,Blender.Z)',
 'palette_srgb_hex':KIT_META['palette_srgb_hex'],
 'assets':asset_manifest,'objects':[record(o) for o in instances],
 'hide_existing_actor_names':sorted(hidden),
 'review_camera':{'look_ue_cm':[look.x*100,-look.y*100,look.z*100],
                  'width_cm':2350,'pitch_deg':-58,'yaw_deg':0},
 'water_level_cm':10,
 'shoredata':{'attribute':'ShoreData','type':'FLOAT_COLOR','source_domain':'POINT',
              'R':'clamp((water_level_z - world_z) / 1.5, 0, 1)',
              'G':'clamp(distance_to_site_shore_m / 4.0, 0, 1)',
              'B':'SM_ShorelineSite_CurvedBed only: 1 - end_weight * land_weight * far_weight. Continuous baseline-floor colour blend: interior 0, fully terrain-following outer ring/skirts/bottom 1. Banks and shared rocks keep B=0.',
              'A':'1',
              'bed_blue_intermediate_vertices':assets[0]['shoredata_blue_intermediate_vertices']},
 'shoreline_contour_ue_m':[[x,site_shore_y(x),WATER] for x in range(11,26)],
 'baseline_shoreline_contour_ue_m':[[x,shore_y(x),WATER] for x in range(11,26)],
 'shallow_width_samples_m':[[x,wet_width(x)] for x in range(11,26)],
 'validation':{'source_sha256':SOURCE_HASHES,'boundary_buried_m':0.1,
               'source_terrain_unchanged':True,'instances':len(instances),
               'house_retained':bpy.data.objects.get('PinkRoofHouse_Lakeside') is not None,
               'review_only_hidden_water':review_hidden_water,
               'review_png_is_dry_geometry':True}}
SITE_JSON.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(SITE_BLEND))
# Foam follows the actual composite water intersection, not the design datum.
# Re-extract after every geometry build so the manifest never loses this field.
contact_spec=importlib.util.spec_from_file_location('extract_shoreline_contact',
    ROOT/'Scripts'/'extract_shoreline_contact.py')
contact_module=importlib.util.module_from_spec(contact_spec)
contact_spec.loader.exec_module(contact_module)
contact_module.update_manifest(SITE_JSON,SITE_BLEND)
bpy.ops.render.render(write_still=True)
for path in PROTECTED:
    assert hashlib.sha256(path.read_bytes()).hexdigest()==SOURCE_HASHES[str(path)], str(path)
print('SHORELINE_SITE_COMPLETE '+json.dumps({'objects':len(instances),'assets':len(asset_manifest),
    'hidden_existing':hidden,'blend':str(SITE_BLEND),'preview':str(SITE_PNG)},ensure_ascii=False))
