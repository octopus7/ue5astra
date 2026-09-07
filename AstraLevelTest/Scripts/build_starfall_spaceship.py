"""Grounded, tilted retro spacecraft kit for the Starfall forest level.

Run Blender 4.5 --factory-startup -b --python this_file.py.
All coordinates are metres; the access hatch faces local -X. The hull leans
towards +Y by sixteen degrees while all three independent feet stay horizontal.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'ArtSource'
REF = ART / 'Reference/Starfall/Ref_StarfallSpaceship.png'
TEX = ART / 'Textures/Starfall/T_SF_ShipPaint.png'
for folder in ('Blender', 'Meshes/Starfall', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
assert REF.exists(), 'Inspect and preserve the new spacecraft reference before final generation.'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_StarfallSpaceshipLibrary')
presentation = bpy.data.collections.new('02_StarfallSpaceshipPresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)

MAT = {
    'M_SF_Ship_Hull': {'base_color':'DCE4E1', 'roughness':.44, 'metallic':.30},
    'M_SF_Ship_Silver': {'base_color':'C0CFD0', 'roughness':.32, 'metallic':.65},
    'M_SF_Ship_Nose': {'base_color':'6A7B83', 'roughness':.39, 'metallic':.62},
    'M_SF_Ship_Teal': {'base_color':'438F98', 'roughness':.34, 'metallic':.28},
    'M_SF_Ship_Glass': {'base_color':'80D3D5', 'roughness':.19, 'metallic':.45},
    'M_SF_Ship_Seam': {'base_color':'43555D', 'roughness':.59, 'metallic':.32},
    'M_SF_Ship_Engine': {'base_color':'35444D', 'roughness':.51, 'metallic':.58},
    'M_SF_Ship_Brass': {'base_color':'C2A36C', 'roughness':.46, 'metallic':.50},
}


def linear(c):
    return c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4


def color(h):
    return tuple(linear(int(h[i:i+2],16)/255) for i in (0,2,4))


materials = {}
texture = bpy.data.images.load(str(TEX), check_existing=True) if TEX.exists() else None
if texture:
    texture.pack()
    MAT['M_SF_Ship_Hull']['base_color_texture'] = TEX.relative_to(ROOT).as_posix()
for name, definition in MAT.items():
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color(definition['base_color']),1)
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = definition['roughness']
    shader.inputs['Metallic'].default_value = definition['metallic']
    if definition.get('emissive_color'):
        shader.inputs['Emission Color'].default_value = (*color(definition['emissive_color']),1)
        shader.inputs['Emission Strength'].default_value = definition['emissive_strength']
    if name == 'M_SF_Ship_Hull' and texture:
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = texture
        node.interpolation = 'Linear'
        mat.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
    materials[name] = mat

LEAN = Matrix.Rotation(math.radians(-16),4,'X')
ORIGIN = Vector((0,0,.95))


def H(v):
    return LEAN @ Vector(v) + ORIGIN


def ground_part(obj, apply_hull=False):
    if apply_hull:
        obj.matrix_world = Matrix.Translation(ORIGIN) @ LEAN @ obj.matrix_world
    return obj


def assign(obj, mat):
    obj.data.materials.append(materials[mat])
    return obj


def finish_edges(obj, bevel=.04, smooth=True):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if bevel:
        mod = obj.modifiers.new('SoftMachinedEdges','BEVEL')
        mod.width = bevel
        mod.segments = 3
        mod.affect = 'EDGES'
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in obj.data.polygons:
        p.use_smooth = smooth
    if smooth and bevel:
        mod = obj.modifiers.new('AuthoredBroadFaceNormals','WEIGHTED_NORMAL')
        mod.keep_sharp = True
        mod.weight = 45
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.select_set(False)
    return obj


def mesh(name, verts, faces, mat, bevel=0, hull=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts,[],faces)
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(me); bm.free()
    obj = bpy.data.objects.new(name,me)
    scene.collection.objects.link(obj)
    assign(obj,mat)
    finish_edges(obj,bevel)
    ground_part(obj,hull)
    return obj


def cube(name, center, size, mat, bevel=.04, hull=True):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center)
    obj = bpy.context.object; obj.name=name; obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    assign(obj,mat); finish_edges(obj,min(bevel,min(size)*.43))
    ground_part(obj,hull)
    return obj


def cylinder(name,a,b,r,mat,sides=20,hull=True):
    a,b=Vector(a),Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides,radius=r,depth=(b-a).length,location=(a+b)/2)
    obj=bpy.context.object;obj.name=name
    obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    assign(obj,mat)
    for p in obj.data.polygons: p.use_smooth=len(p.vertices)==4
    ground_part(obj,hull)
    return obj


def tube(name,points,r,mat,hull=True,sides=8):
    curve=bpy.data.curves.new(name,'CURVE')
    curve.dimensions='3D';curve.resolution_u=1
    curve.bevel_depth=r;curve.bevel_resolution=2;curve.use_fill_caps=True
    spline=curve.splines.new('POLY');spline.points.add(len(points)-1)
    for point,co in zip(spline.points,points):point.co=(*co,1)
    obj=bpy.data.objects.new(name,curve);scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target='MESH');obj=bpy.context.object
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free()
    assign(obj,mat)
    for face in obj.data.polygons:face.use_smooth=len(face.vertices)==4
    ground_part(obj,hull)
    return [obj]


def lathe(name,profile,mat,sides=72,hull=True,closed=False):
    verts=[(r*math.cos(i*math.tau/sides),r*math.sin(i*math.tau/sides),z)
           for r,z in profile for i in range(sides)]
    faces=[]
    limit=len(profile) if closed else len(profile)-1
    for row in range(limit):
        nxt=(row+1)%len(profile)
        for i in range(sides):
            j=(i+1)%sides
            faces.append((row*sides+i,row*sides+j,nxt*sides+j,nxt*sides+i))
    if not closed:
        faces.extend((tuple(range(sides-1,-1,-1)),tuple(range((len(profile)-1)*sides,len(profile)*sides))))
    obj=mesh(name,verts,faces,mat,hull=hull)
    # Analytic cylindrical UVs keep paint texture scale consistent across seams.
    uv=obj.data.uv_layers.new(name='UVMap')
    for poly in obj.data.polygons:
        ids=[obj.data.loops[k].vertex_index for k in poly.loop_indices]
        indices=[idx%sides for idx in ids]
        seam=0 in indices and (sides-1) in indices
        for loop in poly.loop_indices:
            idx=obj.data.loops[loop].vertex_index
            side=idx%sides;row=idx//sides
            u=1 if seam and side==0 else side/sides
            uv.data[loop].uv=(u*2.4,profile[row][1]/4.0)
        if len(poly.vertices)>4: poly.use_smooth=False
    return obj


PROFILE=[(1.28,0),(1.40,.15),(1.64,.6),(1.86,1.5),(1.97,2.8),
         (2.0,5.2),(1.965,7.4),(1.83,9.3),(1.66,10.45),(1.43,11.2),
         (1.13,11.92),(.79,12.57),(.39,13.12),(.12,13.4),(.045,13.43)]


def radius(z):
    for (ra,za),(rb,zb) in zip(PROFILE,PROFILE[1:]):
        if za<=z<=zb:return ra+(rb-ra)*(z-za)/(zb-za)
    return PROFILE[-1][0] if z>PROFILE[-1][1] else PROFILE[0][0]


def section(name,low,high,mat,offset=0):
    profile=[(radius(low)+offset,low)]
    profile += [(r+offset,z) for r,z in PROFILE if low<z<high]
    profile.append((radius(high)+offset,high))
    return lathe(name,profile,mat)


def torus(name,z,r,mat,minor=.021):
    bpy.ops.mesh.primitive_torus_add(major_segments=72,minor_segments=8,
        location=(0,0,z),major_radius=r,minor_radius=minor)
    o=bpy.context.object;o.name=name
    assign(o,mat)
    for p in o.data.polygons:p.use_smooth=True
    ground_part(o,True)
    return o


def radial_point(angle,r,z):
    return (r*math.cos(angle),r*math.sin(angle),z)


parts=[]
# A tapered long hull with a restrained dark nose and teal cockpit ribbon.
parts.append(section('IvoryMainPressureHull',0,10.06,'M_SF_Ship_Hull'))
parts.append(section('ContinuousTealCockpitWindowBand',10.06,10.82,'M_SF_Ship_Glass',.012))
parts.append(section('RoundedTitaniumNose',10.82,13.43,'M_SF_Ship_Nose'))
for low,high in ((1.22,1.58),(2.02,2.18)):
    parts.append(section('TurquoiseLowerHullStripe',low,high,'M_SF_Ship_Teal',.012))
for z in (.36,1.19,1.60,2.00,2.2,3.55,6.65,8.7,10.04,10.84,11.82,12.72):
    parts.append(torus('InsetPanelGasket',z,radius(z)+.005,'M_SF_Ship_Seam',.018))
for z in (10.07,10.82):
    parts.append(torus('CockpitSilverBeading',z,radius(z)+.024,'M_SF_Ship_Silver',.036))
for i in range(7):
    a=i*math.tau/7+.10
    for low,high in ((2.23,3.50),(3.60,6.60),(6.7,8.65),(8.75,10.00),(10.87,13.34)):
        # Break joints align as large intentional pressure-shell panels.
        zs=sorted({low+(high-low)*j/12 for j in range(13)} | {z for _,z in PROFILE if low<z<high})
        points=[radial_point(a,radius(z)+.012,z) for z in zs]
        parts += tube('LongitudinalPanelJoint',points,.009,'M_SF_Ship_Seam',sides=6)
    points=[radial_point(a,radius(z)+.036,z) for z in (10.08,10.25,10.45,10.5,10.79)]
    parts += tube('CockpitWindowMullion',points,.042,'M_SF_Ship_Teal',sides=10)


def rounded_rect_patch(name,zmid,w,h,depth,mat,radius_corner=.24):
    boundary=[]
    for cy,cz,start in ((w/2-radius_corner,h/2-radius_corner,0),
                        (-w/2+radius_corner,h/2-radius_corner,90),
                        (-w/2+radius_corner,-h/2+radius_corner,180),
                        (w/2-radius_corner,-h/2+radius_corner,270)):
        for i in range(7):
            a=math.radians(start+i*90/6)
            boundary.append((cy+radius_corner*math.cos(a),zmid+cz+radius_corner*math.sin(a)))
    def surface(y,z,d):
        rr=radius(z)
        return (-math.sqrt(max(.01,rr*rr-y*y))-d,y,z)
    vs=[surface(y,z,d) for d in (depth-.055,depth) for y,z in boundary]
    n=len(boundary)
    vs += [surface(0,zmid,depth-.055),surface(0,zmid,depth)]
    fs=[]
    for i in range(n):
        j=(i+1)%n
        fs += [(2*n,j,i),(2*n+1,n+i,n+j),(i,j,n+j,n+i)]
    return mesh(name,vs,fs,mat)


# A broad, readable hatch, with a small portal and one handle rather than tiny clutter.
parts.append(rounded_rect_patch('HatchDarkRubberPerimeter',4.77,1.38,2.33,.047,'M_SF_Ship_Seam',.26))
parts.append(rounded_rect_patch('HatchSilverRim',4.77,1.29,2.24,.074,'M_SF_Ship_Silver',.23))
parts.append(rounded_rect_patch('HatchIvoryPressureDoor',4.77,1.15,2.10,.094,'M_SF_Ship_Hull',.20))
parts.append(rounded_rect_patch('HatchLittleWindowBezel',5.29,.69,.63,.115,'M_SF_Ship_Teal',.19))
parts.append(rounded_rect_patch('HatchLittleBlueWindow',5.29,.56,.50,.126,'M_SF_Ship_Glass',.15))
parts.append(cube('RecessedHatchHandlePlate',(-2.114,-.33,4.45),(.047,.17,.38),'M_SF_Ship_Seam',.032))
parts.append(cylinder('HatchLeverGrip',(-2.17,-.33,4.36),(-2.17,-.33,4.57),.041,'M_SF_Ship_Silver',12))
for z in (4.02,5.55):
    parts.append(cube('VisibleHatchHinge',(-2.03,.63,z),(.11,.12,.24),'M_SF_Ship_Silver',.035))
parts.append(rounded_rect_patch('SmallStarfallMissionBadge',7.58,.44,.59,.055,'M_SF_Ship_Teal',.13))
# A simple raised four-point star emblem, no text or logos.
star=[(-.08,7.59),(-.022,7.65),(0,7.78),(.022,7.65),(.08,7.59),(.022,7.55),(0,7.40),(-.022,7.55)]
vs=[(-radius(z)-depth,y,z) for depth in (.072,.089) for y,z in star]
n=len(star);fs=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
parts.append(mesh('FourPointMissionStar',vs,fs,'M_SF_Ship_Silver',.006))

# Open bell engine: a closed thick radial cross-section with a visible dark recess.
parts.append(lathe('LargeRecessedEngineBell',[(.41,.49),(.58,.36),(.91,-.19),(1.13,-.41),
    (1.13,-.53),(1.04,-.55),(.89,-.24),(.51,.31),(.37,.36)],'M_SF_Ship_Engine',64,closed=True))
parts.append(lathe('EngineLipSilverEdge',[(1.045,-.56),(1.145,-.56),(1.145,-.42),(1.09,-.40)],'M_SF_Ship_Silver',64,closed=True))
parts.append(lathe('EngineDarkRecess',[(.36,.33),(.36,.38)],'M_SF_Ship_Seam',48))


def fin(angle):
    # Rounded swept nacelle: broad aerodynamic side faces and narrow edge bevels.
    profile=[(1.55,.23),(2.07,.16),(2.66,.38),(3.00,.81),(3.04,1.26),
             (2.82,2.30),(2.39,3.12),(1.96,3.46),(1.88,2.28)]
    vs=[]
    for tangential in (-.25,.25):
        for r,z in profile:
            vs.append((r*math.cos(angle)-tangential*math.sin(angle),
                       r*math.sin(angle)+tangential*math.cos(angle),z))
    n=len(profile)
    fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=mesh('SweptLandingFin',vs,fs,'M_SF_Ship_Hull',.14)
    # Nacelle outer seam follows the swept leading edge on both visible sides.
    for side in (-.257,.257):
        path=[]
        for r,z in [(2.43,.52),(2.74,.82),(2.77,1.27),(2.57,2.23),(2.18,2.97)]:
            path.append((r*math.cos(angle)-side*math.sin(angle),r*math.sin(angle)+side*math.cos(angle),z))
        parts.extend(tube('LandingFinPanelGasket',path,.014,'M_SF_Ship_Seam',sides=6))
    return o


feet=[]
for index,a in enumerate((math.pi/2,7*math.pi/6,11*math.pi/6)):
    parts.append(fin(a))
    top=H(radial_point(a,2.75,.83))
    foot=H(radial_point(a,3.15,-.65));foot.z=.24
    feet.append([round(v,6) for v in foot])
    # Unequal piston lengths are real geometry, which absorbs the sixteen-degree lean.
    lower=foot+Vector((0,0,.13))
    middle=lower+(top-lower)*.56
    parts.append(cylinder('GroundedLandingPiston',lower,top,.13,'M_SF_Ship_Silver',24,False))
    parts.append(cylinder('DarkShockAbsorberSleeve',middle,top,.195,'M_SF_Ship_Engine',24,False))
    parts.append(cylinder('BrassShockCollar',middle-Vector((0,0,.05)),middle+Vector((0,0,.07)),.217,'M_SF_Ship_Brass',24,False))
    pad=cube('HorizontalOvalLandingPad',tuple(foot-Vector((0,0,.10))),(1.55,1.17,.28),'M_SF_Ship_Silver',.16,False)
    pad.rotation_euler.z=a
    parts.append(pad)
    tread=cube('DarkLandingPadCushion',tuple(foot-Vector((0,0,.205))),(1.45,1.07,.07),'M_SF_Ship_Engine',.033,False)
    tread.rotation_euler.z=a
    parts.append(tread)
    parts.append(cylinder('FootSwivelJoint',foot-Vector((0,.21,0)),foot+Vector((0,.21,0)),.23,'M_SF_Ship_Teal',20,False))

# Three broad ladder treads immediately below the closed hatch, readable from top-down.
for z in (2.64,3.03,3.42):
    parts.append(cube('ExteriorAccessLadderTread',(-2.00,0,z),(.35,.88,.095),'M_SF_Ship_Silver',.035))
for yy in (-.46,.46):
    parts.append(cylinder('LadderSideRail',(-1.98,yy,2.54),(-2.04,yy,3.64),.045,'M_SF_Ship_Silver',12))
for angle in (math.pi*.30,math.pi*.7,math.pi*1.25,math.pi*1.75):
    for z in (.81,.99):
        pp=radial_point(angle,radius(z)+.08,z)
        end=radial_point(angle,radius(z)+.16,z)
        parts.append(cylinder('LowerUtilityRecess',pp,end,.075,'M_SF_Ship_Engine',12))

# Join only this independent asset, retaining meaningful stable material slots.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0]
bpy.ops.object.join()
ship=bpy.context.object;ship.name='SM_SF_LandedSpaceship'
scene.cursor.location=(0,0,0)
bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
ship['asset_id']=ship.name;ship['collision']='complex';ship['front_axis']='-X'
ship['hull_lean_degrees']=16.0
# Retain analytic hull UVs. Smart projection fills only parts without their own UVs
# during join, then gives every mesh face a finite non-zero paint footprint.
bpy.context.view_layer.objects.active=ship
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='DESELECT')
bm=bmesh.from_edit_mesh(ship.data)
uv_layer=bm.loops.layers.uv.verify()
for face in bm.faces:
    points=[loop[uv_layer].uv.copy() for loop in face.loops]
    area=abs(sum(a.x*b.y-b.x*a.y for a,b in zip(points,points[1:]+points[:1])))/2
    face.select_set(area<1e-10)
bmesh.update_edit_mesh(ship.data)
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.018,area_weight=.12)
bpy.ops.object.mode_set(mode='OBJECT')
mod=ship.modifiers.new('StableAuthoredTriangulation','TRIANGULATE')
mod.keep_custom_normals=True
bpy.ops.object.modifier_apply(modifier=mod.name)
for col in list(ship.users_collection):col.objects.unlink(ship)
library.objects.link(ship)
bpy.context.view_layer.update()
file=ART/'Meshes/Starfall/SM_SF_LandedSpaceship.fbx'
bpy.ops.export_scene.fbx(filepath=str(file),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True)
ship.data.calc_loop_triangles()
item={'asset_id':ship.name,'file':file.relative_to(ROOT).as_posix(),
      'materials':[slot.material.name for slot in ship.material_slots],
      'collision':'complex','dimensions_m':[round(float(v),6) for v in ship.dimensions],
      'triangles':len(ship.data.loop_triangles),'normal_import_method':'import_normals_and_tangents',
      'front_axis':'-X','hull_lean_degrees':16,'landing_pad_centres_m':feet}
metadata={'source':'ArtSource/Blender/StarfallSpaceship.blend','script':'Scripts/build_starfall_spaceship.py',
          'reference':REF.relative_to(ROOT).as_posix(),'units':'metres',
          'coordinate_conversion':'(Blender X, -Blender Y, Blender Z) * 100',
          'materials':MAT,'assets':[item],
          'placement_notes':'Ground origin z=0. Hull lean toward Blender +Y baked into geometry. Hatch faces -X. Three landing pads are horizontal; do not add a second tilt when placing.'}
before=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(file),use_anim=False)
created=set(bpy.data.objects)-before
imported=[o for o in created if o.type=='MESH']
assert len(imported)==1
back=imported[0];bpy.context.view_layer.update()
delta=max(abs(ship.dimensions[i]-back.dimensions[i]) for i in range(3))
slots=[s.material.name.split('.')[0] for s in back.material_slots]
bm=bmesh.new();bm.from_mesh(back.data)
nonmanifold=sum(not e.is_manifold for e in bm.edges)
degenerate=sum(f.calc_area()<1e-12 for f in bm.faces)
if degenerate:
    bad=[{'material':slots[f.material_index],'center':list(f.calc_center_median()),
          'verts':[list(v.co) for v in f.verts]} for f in bm.faces if f.calc_area()<1e-12]
    print('DEGENERATE DIAGNOSTIC '+json.dumps(bad[:8]),flush=True)
bm.free()
finite=all(math.isfinite(c) for v in back.data.vertices for c in v.co)
uv_finite=bool(back.data.uv_layers) and all(math.isfinite(c) for v in back.data.uv_layers.active.data for c in v.uv)
ground_z=min(v.co.z for v in back.data.vertices)
contacts=[sum(abs(v.co.z)<1e-5 and math.hypot(v.co.x-x,v.co.y-y)<1.0
              for v in back.data.vertices) for x,y,_ in feet]
back.data.calc_loop_triangles()
assert delta<2e-5 and back.location.length<1e-6 and finite and uv_finite
assert abs(ground_z)<1e-5 and all(count>=4 for count in contacts),(ground_z,contacts)
assert slots==item['materials'] and len(back.data.loop_triangles)==item['triangles']
assert nonmanifold==0 and degenerate==0,(nonmanifold,degenerate)
validation={'passed':True,'asset_id':ship.name,'fbx_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
    'triangles':item['triangles'],'dimensions_m':item['dimensions_m'],'bounds_roundtrip_error_m':delta,
    'ground_origin_zero':True,'hull_lean_degrees':16,'three_horizontal_landing_pads':True,
    'minimum_z_m':ground_z,'ground_contact_vertices_per_pad':contacts,
    'material_slots_match':True,'finite_vertices':finite,'uv_finite':uv_finite,
    'non_manifold_edges':nonmanifold,'degenerate_faces':degenerate,'authored_normals':bool(back.data.has_custom_normals)}
for o in created:bpy.data.objects.remove(o,do_unlink=True)
(ART/'Layout/starfall_spaceship.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
(ART/'Previews/StarfallSpaceship_FBXValidation.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')

ship.hide_render=True;ship.hide_set(True)
copy=bpy.data.objects.new('Preview_LandedSpaceship',ship.data);presentation.objects.link(copy)
bpy.ops.mesh.primitive_plane_add(size=180,location=(0,0,-.012))
ground=bpy.context.object;ground.name='PresentationOnly_MeadowGround'
gm=bpy.data.materials.new('PresentationOnly_SageGround');gm.use_nodes=True
gm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*color('8F9E6C'),1)
gm.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.92
ground.data.materials.append(gm)
bpy.ops.object.light_add(type='SUN',location=(-9,-7,18));sun=bpy.context.object
sun.rotation_euler=(.45,-.4,-.65);sun.data.energy=2.0;sun.data.angle=math.radians(50)
bpy.ops.object.light_add(type='AREA',location=(-5,4,14));fill=bpy.context.object
fill.rotation_euler=(Vector((0,0,7))-fill.location).to_track_quat('-Z','Y').to_euler()
fill.data.energy=1500;fill.data.shape='DISK';fill.data.size=12
scene.world=bpy.data.worlds.new('PresentationOnly_CoolSky');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.48,.65,.88,1);bg.inputs['Strength'].default_value=.70
bpy.ops.object.camera_add(location=(-23,-25,22));cam=bpy.context.object
cam.rotation_euler=(Vector((0,1.4,7))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=20.0;scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1500;scene.render.resolution_y=1700
scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
scene.render.filepath=str(ART/'Previews/Blender_StarfallSpaceship.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/StarfallSpaceship.blend'))
bpy.ops.render.render(write_still=True)
print('STARFALL SPACESHIP COMPLETE '+json.dumps(metadata['assets']))
