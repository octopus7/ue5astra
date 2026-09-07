"""Five standalone cottage-life prop sets; local -X front, metre units.

Run Blender --background --factory-startup --python this_file.py.
Only this kit's .blend, FBXs, metadata and preview/validation are written.
"""
import bpy, bmesh, ast, json, math, random, hashlib
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'ArtSource'
R = random.Random(918)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
library = bpy.data.collections.new('01_HomeLifeLibrary')
presentation = bpy.data.collections.new('02_HomeLifePresentation')
scene.collection.children.link(library)
scene.collection.children.link(presentation)
PALETTE = {
 'M_HomeLife_Wood':'A87947', 'M_HomeLife_WoodLight':'CBA16B',
 'M_HomeLife_WoodDark':'796049', 'M_HomeLife_Cream':'EBDEB8',
 'M_HomeLife_Sage':'98AB82', 'M_HomeLife_SageShade':'738C79',
 'M_HomeLife_Rope':'CBB58A', 'M_HomeLife_Soil':'79624E',
 'M_HomeLife_SoilLight':'8A7360', 'M_HomeLife_Carrot':'E69B48',
 'M_HomeLife_Pumpkin':'DFA049', 'M_HomeLife_PumpkinLight':'EABA64',
 'M_HomeLife_Leaf':'668C58', 'M_HomeLife_LeafLight':'8BA66C',
 'M_HomeLife_Iron':'6C8087', 'M_HomeLife_IronDark':'455860',
 'M_HomeLife_Ochre':'C89851', 'M_HomeLife_Straw':'CBB270',
 'M_HomeLife_StrawShade':'AD975D', 'M_HomeLife_Mushroom':'CAB185',
}
source = (ROOT/'Scripts/build_forest_signs.py').read_text(encoding='utf-8')
names = {'linear','finish','mesh','cube','cylinder','slab','ring','polyline','asset','metadata_for'}
tree = ast.parse(source)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],
                       type_ignores=[]), str(ROOT/'Scripts/build_forest_signs.py'), 'exec'))
materials = {}
for name, value in PALETTE.items():
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    c = tuple(linear(int(value[i:i+2],16)/255) for i in (0,2,4))
    m.diffuse_color = (*c,1)
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*c,1)
    bs.inputs['Roughness'].default_value = .45 if 'Iron' in name else .86
    bs.inputs['Metallic'].default_value = .18 if 'Iron' in name else 0
    materials[name] = m


def smooth_sides(obj):
    for f in obj.data.polygons:
        if len(f.vertices) == 4:
            f.use_smooth = True
    return obj


def pole(name, a, b, radius, mat, sides=12):
    return smooth_sides(cylinder(name,a,b,radius,mat,sides))


def ellipsoid(name, center, size, mat, segments=12, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,radius=1,location=center)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for f in o.data.polygons:
        f.use_smooth = True
    return finish(o,mat)


def lathe(name, center, profile, mat, sides=16, xy=(1,1)):
    # Profile is a closed radial cross-section: open vessels remain closed solid shells.
    cx,cy,cz = center
    verts = [(cx+r*xy[0]*math.cos(i*math.tau/sides),cy+r*xy[1]*math.sin(i*math.tau/sides),cz+z)
             for r,z in profile for i in range(sides)]
    faces = []
    for j in range(len(profile)):
        nj=(j+1)%len(profile)
        for i in range(sides):
            ni=(i+1)%sides
            faces.append((j*sides+i,j*sides+ni,nj*sides+ni,nj*sides+i))
    return smooth_sides(mesh(name,verts,faces,mat))


def leaf(name, start, end, width, mat):
    a,b = Vector(start),Vector(end)
    axis = b-a
    side = axis.cross(Vector((1,0,.15)))
    if side.length < .001:
        side = axis.cross(Vector((0,1,0)))
    side.normalize()
    normal = axis.normalized().cross(side).normalized()
    center = a*.40+b*.60
    vs = [a,b,center+side*width/2,center-side*width/2,center+normal*.024,center-normal*.012]
    fs = [(0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)]
    obj = mesh(name,vs,fs,mat)
    for f in obj.data.polygons:
        f.use_smooth=True
    return obj


def cloth(name, center_y, top, width, height, mat, stripe):
    cols,rows = 10,6
    front=[]
    for row in range(rows+1):
        v=row/rows
        for col in range(cols+1):
            u=col/cols
            yy=center_y+(u-.5)*width
            zz=top-v*height+.025*math.cos(u*math.tau)*v
            xx=-.008+.05*math.sin(u*math.pi*5)*(.18+.82*v)+.018*math.sin(v*math.pi)
            front.append((xx,yy,zz))
    n=len(front)
    vs=front+[(x+.027,y,z) for x,y,z in front]
    fs=[]
    for row in range(rows):
        for col in range(cols):
            i=row*(cols+1)+col
            fs.extend(((i,i+1,i+cols+2,i+cols+1),(n+i+cols+1,n+i+cols+2,n+i+1,n+i)))
    border=list(range(cols+1))+[r*(cols+1)+cols for r in range(1,rows+1)]
    border += [rows*(cols+1)+c for c in range(cols-1,-1,-1)]
    border += [r*(cols+1) for r in range(rows-1,0,-1)]
    fs += [(a,b,n+b,n+a) for a,b in zip(border,border[1:]+border[:1])]
    o=mesh(name,vs,fs,mat)
    o.data.materials.append(materials[stripe])
    for f in o.data.polygons:
        f.use_smooth=True
        if f.center.z < top-height*.79 and f.center.z > top-height*.95:
            f.material_index=1
    return o


# Clothesline: overall span ~3 m, soft thick cloth surfaces and chunky pegs.
p=[]
for yy in (-1.48,1.48):
    p.append(pole('LaundryPost',(0,yy,0),(.026,yy+(.025 if yy>0 else -.025),1.8),.070,'M_HomeLife_Wood'))
    p.append(pole('PostCutCap',(.026,yy,1.785),(.026,yy,1.805),.071,'M_HomeLife_WoodLight'))
    for z in (1.61,1.65):
        p.append(ring('LaundryRopeWrap',(.020,yy,z),.076,.014,'Z','M_HomeLife_Rope',16))
line=[(.013,-1.48+i*2.96/12,1.655-.13*math.sin(i*math.pi/12)) for i in range(13)]
p += polyline('SaggingClothesline',line,.013,'M_HomeLife_Rope',6)
p.append(cloth('CreamTowel',-.94,1.573,.68,.88,'M_HomeLife_Cream','M_HomeLife_Sage'))
p.append(cloth('SageBlanket',.93,1.573,.73,.91,'M_HomeLife_Sage','M_HomeLife_Cream'))
shirt=[(-.27,1.49),(-.39,1.33),(-.26,1.22),(-.20,1.29),(-.20,.99),
       (.20,.99),(.20,1.29),(.26,1.22),(.39,1.33),(.27,1.49),(.12,1.52),
       (.075,1.435),(-.075,1.435),(-.12,1.52)]
p.append(slab('LittleCreamShirt',shirt,-.055,.045,'M_HomeLife_Cream',.015))
p.append(cube('ShirtButtonPlacket',(-.083,0,1.28),(.014,.022,.28),'M_HomeLife_Rope',.004))
for z in (1.18,1.29,1.39):
    p.append(pole('WoodShirtButton',(-.101,0,z),(-.089,0,z),.017,'M_HomeLife_WoodLight',8))
for yy in (-1.2,-.68,-.20,.20,.65,1.22):
    z=1.655-.13*math.sin((yy+1.48)/2.96*math.pi)
    p.append(cube('WoodClothPeg',(-.022,yy,z+.005),(.044,.031,.14),'M_HomeLife_WoodLight',.004))
clothesline=asset('SM_HomeClothesline',p,'complex')


# The entire crop patch is decorative and can be placed beside the house's path.
p=[cube('RaisedDarkEarth',(0,0,.057),(1.91,1.91,.114),'M_HomeLife_Soil',.035)]
for xx in (-.975,.975):
    p.append(cube('BedSideTimber',(xx,0,.06),(.09,2.04,.12),'M_HomeLife_Wood',.014))
for yy in (-.975,.975):
    p.append(cube('BedEndTimber',(0,yy,.06),(1.96,.09,.12),'M_HomeLife_WoodLight',.012))
for xx in (-.96,.96):
    for yy in (-.96,.96):
        p.append(pole('BedCornerPeg',(xx,yy,0),(xx,yy,.17),.07,'M_HomeLife_WoodLight',10))
for row in (-.60,0,.60):
    p.append(cube('SoftRaisedSoilRow',(0,row,.116),(1.7,.28,.07),'M_HomeLife_SoilLight',.033))


def pumpkin(center,radius=.19):
    cx,cy,cz=center
    n,rings=24,7
    vs=[]
    for j in range(1,rings+1):
        phi=math.pi*j/(rings+1)
        for i in range(n):
            angle=math.tau*i/n
            rad=radius*math.sin(phi)*(1+.095*math.cos(6*angle))
            vs.append((cx+rad*math.cos(angle),cy+rad*math.sin(angle),cz+radius*.82*math.cos(phi)))
    vs.extend(((cx,cy,cz+radius*.82),(cx,cy,cz-radius*.82)))
    fs=[]
    for j in range(rings-1):
        for i in range(n):
            fs.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    fs += [(n*rings,i,(i+1)%n) for i in range(n)]
    fs += [(n*rings+1,(rings-1)*n+(i+1)%n,(rings-1)*n+i) for i in range(n)]
    o=mesh('RibbedPumpkin',vs,fs,'M_HomeLife_Pumpkin')
    o.data.materials.append(materials['M_HomeLife_PumpkinLight'])
    for f in o.data.polygons:
        f.use_smooth=True
        if f.index%24 in (3,4,11,12,19,20):f.material_index=1
    return o


for yy in (-.59,.59):
    for xx in (-.59,0,.59):
        p.append(pumpkin((xx,yy,.29),.175))
        p.append(pole('PumpkinBentStem',(xx,yy,.39),(xx+.028,yy,.49),.025,'M_HomeLife_WoodDark',8))
        for i in range(4):
            angle=i*math.pi/2+.3
            end=(xx+.27*math.cos(angle),yy+.23*math.sin(angle),.27)
            p.append(leaf('BroadPumpkinLeaf',(xx,yy,.25),end,.22,'M_HomeLife_Leaf' if i%2 else 'M_HomeLife_LeafLight'))
for xx in (-.66,-.22,.22,.66):
    p.append(lathe('CarrotShoulder',(xx,0,.14),[(.012,0),(.045,.025),(.065,.10),(.052,.145),(.018,.16)],'M_HomeLife_Carrot',10))
    for i in range(5):
        angle=i*math.tau/5
        end=(xx+.125*math.cos(angle),.14*math.sin(angle),.57+(.05 if i%2 else 0))
        p.append(leaf('TallCarrotGreens',(xx,0,.27),end,.066,'M_HomeLife_LeafLight' if i%2 else 'M_HomeLife_Leaf'))
vegetables=asset('SM_VegetablePatch',p,'none')


# Watering can: actual open rim with a dark inside, big handle and long spout.
p=[]
can=(0,-.24,0)
p.append(lathe('WateringCanBody',can,[(.012,.025),(.17,.025),(.185,.10),(.18,.39),
    (.165,.405),(.15,.405),(.152,.08),(.012,.065)],'M_HomeLife_Sage',20))
for z in (.07,.34):
    p.append(ring('CanRaisedBand',(0,-.24,z),.18,.012,'Z','M_HomeLife_SageShade',20))
p.append(pole('LongWateringSpout',(0,-.36,.10),(0,-.81,.46),.045,'M_HomeLife_Sage',12))
p.append(pole('SprinklerRose',(0,-.81,.46),(0,-.86,.50),.086,'M_HomeLife_Iron',12))
for dx,dz in ((0,0),(-.035,.025),(.035,.025),(-.035,-.025),(.035,-.025)):
    p.append(ellipsoid('SprinklerHole',(dx,-.866,.50+dz),(.009,.008,.009),'M_HomeLife_IronDark',8,4))
handle=[]
for i in range(11):
    angle=i*math.pi/10
    handle.append((.23*math.cos(angle),-.24,.37+.23*math.sin(angle)))
p += polyline('CanArchedHandle',handle,.027,'M_HomeLife_SageShade',8)
p += polyline('CanRearGrip',[(0,-.07,.12),(0,.05,.17),(0,.075,.31),(0,-.08,.37)],.025,'M_HomeLife_SageShade',8)
# Spade front -X: a broad slightly beveled blade and D handle.
p.append(slab('SpadeBlade',[(.24,.30),(.22,.10),(.39,0),(.56,.10),(.54,.30)],-.046,.07,'M_HomeLife_Iron',.014))
p.append(pole('SpadeTimberShaft',(0,.39,.25),(0,.39,1.04),.032,'M_HomeLife_WoodLight'))
p.append(pole('SpadeMetalSocket',(0,.39,.26),(0,.39,.43),.041,'M_HomeLife_Iron',10))
p += polyline('SpadeDGrip',[(0,.39,1.00),(0,.28,1.10),(0,.28,1.23),(0,.50,1.23),(0,.50,1.10),(0,.39,1.00)],.026,'M_HomeLife_Iron',8)
p.append(pole('SpadeWoodGrip',(0,.28,1.23),(0,.50,1.23),.036,'M_HomeLife_WoodLight'))
tools=asset('SM_WateringTools',p,'complex')


# Four boots, a small rest and the leaning straw broom form one collision-free set.
p=[]
for i,yy in enumerate((-.44,-.19,.10,.35)):
    mat='M_HomeLife_Ochre' if i<2 else 'M_HomeLife_SageShade'
    p.append(ellipsoid('RoundedBootFoot',(-.075,yy,.10),(.185,.095,.092),mat,14,8))
    p.append(cube('BootSole',(-.075,yy,.025),(.35,.18,.05),'M_HomeLife_WoodDark',.02))
    p.append(lathe('OpenBootShaft',(.018,yy,.06),[(.018,0),(.09,0),(.098,.33),(.084,.345),
        (.071,.345),(.069,.09),(.018,.075)],mat,16,xy=(1.10,1)))
    p.append(ring('BootRolledRim',(.018,yy,.404),.085,.012,'Z',mat,16))
for yy in (-.59,.55):
    p.append(cube('LittleBootRestPost',(.16,yy,.30),(.08,.08,.60),'M_HomeLife_Wood',.013))
for z in (.31,.50):
    p.append(cube('LittleBootRestRail',(.19,-.02,z),(.066,1.16,.13),'M_HomeLife_WoodLight',.01))
p.append(slab('StrawBroomBody',[(.53,.01),(.91,.01),(.87,.21),(.75,.45),(.66,.45),(.57,.21)],-.095,.13,'M_HomeLife_Straw',.014))
for i in range(8):
    yy=.55+i*.047
    p.append(pole('BroomCoarseStrand',(-.111,yy,.025),(-.098,.70+(yy-.72)*.27,.40),.009,'M_HomeLife_StrawShade',6))
p.append(pole('LeaningBroomHandle',(-.03,.705,.34),(.15,.45,1.33),.029,'M_HomeLife_WoodLight'))
p.append(cube('BroomBinding',(-.105,.708,.32),(.033,.18,.075),'M_HomeLife_Rope',.01))
boots=asset('SM_BootsAndBroom',p,'none')


# Herb drying rack with green tied sprigs and one mushroom string.
p=[]
for yy in (-.65,.65):
    p.append(pole('DryingRackUpright',(0,yy,.02),(.014,yy,1.30),.055,'M_HomeLife_Wood'))
    p.append(pole('DryingRackGroundFoot',(-.24,yy,.049),(.24,yy,.049),.049,'M_HomeLife_WoodLight'))
p.append(pole('DryingRackCrossbar',(.013,-.76,1.17),(.013,.76,1.17),.06,'M_HomeLife_WoodLight'))
for yy in (-.65,.65):
    for z in (1.12,1.16,1.20):p.append(ring('RackBinding',(.012,yy,z),.065,.012,'Z','M_HomeLife_Rope',12))
for k,yy in enumerate((-.46,-.13,.47)):
    p.append(pole('HerbHangingCord',(-.027,yy,1.17),(-.027,yy,.97),.012,'M_HomeLife_Rope',6))
    for stem in range(5):
        side=(stem-2)*.019
        bottom=.32+.04*abs(stem-2)
        p.append(pole('DryingHerbStem',(-.03,yy+side,1.00),(-.028,yy+side*2,bottom),.008,'M_HomeLife_Leaf',5))
        for j in range(3):
            zz=.46+j*.14
            direction=-1 if (stem+j)%2 else 1
            p.append(leaf('HangingHerbLeaf',(-.03,yy+side,zz+.13),
                (-.065,yy+side+direction*.12,zz-.08),.075 if k!=1 else .11,
                'M_HomeLife_LeafLight' if (stem+j)%3==0 else 'M_HomeLife_Leaf'))
    p.append(ring('HerbBundleTie',(-.028,yy,.94),.047,.011,'Z','M_HomeLife_Rope',12))
yy=.19
p.append(pole('MushroomString',(-.015,yy,1.17),(-.015,yy,.31),.009,'M_HomeLife_Rope',5))
for j in range(5):
    y=yy+(.065 if j%2 else -.045)
    z=.40+j*.14
    p.append(pole('DryMushroomStem',(-.016,y,z-.045),(-.016,y,z+.025),.019,'M_HomeLife_Cream',8))
    p.append(ellipsoid('DryMushroomCap',(-.016,y,z+.024),(.066,.070,.037),'M_HomeLife_Mushroom',10,6))
rack=asset('SM_HerbDryingRack',p,'complex')

assets=[clothesline,vegetables,tools,boots,rack]
metadata={
 'source':'ArtSource/Blender/HomeLifeProps.blend',
 'script':'Scripts/build_home_life_props.py',
 'reference':'ArtSource/Reference/Ref_HomeLifeProps.png',
 'units':'metres','unreal_conversion':'(Blender X, -Blender Y, Blender Z) * 100; yaw negated',
 'palette_srgb_hex':PALETTE,
 'material_properties':{name:{'roughness':.45 if 'Iron' in name else .86,
     'metallic':.18 if 'Iron' in name else 0.0} for name in PALETTE},
 'assets':[metadata_for(o) for o in assets],
 'placement_notes': 'Front is -X for every set. Clothesline and drying rack span local Y, with cloth/herbs facing the camera at Unreal yaw 0. Vegetable patch and boots are decorative with no collision. Set the origin on the ground; use independent actors so the house approach remains open.',
 'collision_notes': {'SM_HomeClothesline':'complex; poles and hanging cloth, place clear of walking paths',
   'SM_VegetablePatch':'none; decorative low frame, soil and plants',
   'SM_WateringTools':'complex; upright spade and watering can',
   'SM_BootsAndBroom':'none; small decorative shoes and broom',
   'SM_HerbDryingRack':'complex; rack, feet and hanging decorative herbs'}
}
validation={'source':metadata['source'],'method':'FBX reimport into Blender; bounds, slot order, finite vertices and closed-solid geometry','assets':[]}
for original,item in zip(assets,metadata['assets']):
    before=set(bpy.data.objects)
    path=ART/'Meshes'/f'{original.name}.fbx'
    bpy.ops.import_scene.fbx(filepath=str(path),use_anim=False)
    created=set(bpy.data.objects)-before
    imported=[o for o in created if o.type=='MESH']
    assert len(imported)==1
    obj=imported[0]
    bpy.context.view_layer.update()
    delta=max(abs(obj.dimensions[i]-original.dimensions[i]) for i in range(3))
    coords=[obj.matrix_world@v.co for v in obj.data.vertices]
    finite=all(math.isfinite(c) for v in coords for c in v)
    bm=bmesh.new();bm.from_mesh(obj.data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    degenerate=sum(f.calc_area()<=1e-12 for f in bm.faces)
    bm.free()
    slots=[s.material.name.split('.')[0] for s in obj.material_slots]
    assert delta<1e-5 and obj.location.length<1e-6 and finite and nonmanifold==0 and degenerate==0
    assert slots==item['material_slots']
    v={'asset_id':original.name,'fbx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'dimensions_max_error_m':round(delta,9),'origin_zero':True,'material_slots_match':True,
       'finite_vertices':finite,'non_manifold_edges':nonmanifold,'degenerate_faces':degenerate,'passed':True}
    item['validation']['fbx_roundtrip']=v
    validation['assets'].append(v)
    for o in created:bpy.data.objects.remove(o,do_unlink=True)
validation['passed']=True
(ART/'Layout/home_life_props.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
(ART/'Previews/HomeLifeProps_FBXValidation.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')

# Separated preview instances retain the exported library's independent ground-zero origins.
placements=[(.9,1.70,0),(1.55,-1.57,0),(-1.25,-1.69,0),(-1.50,.07,0),(-1.35,2.34,0)]
for original,position in zip(assets,placements):
    o=bpy.data.objects.new('Preview_'+original.name,original.data)
    presentation.objects.link(o)
    o.location=position
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.018))
ground=bpy.context.object
ground.name='HomeLifePreviewGround'
gm=bpy.data.materials.new('HomeLifePreviewGround')
gm.diffuse_color=(.31,.34,.27,1)
ground.data.materials.append(gm)
bpy.ops.object.light_add(type='SUN',location=(-6,-8,12))
sun=bpy.context.object
sun.rotation_euler=(.45,-.35,-.60)
sun.data.energy=2.5
sun.data.angle=math.radians(50)
scene.world=bpy.data.worlds.new('HomeLifeSoftSky')
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get('Background')
bg.inputs['Color'].default_value=(.48,.62,.82,1)
bg.inputs['Strength'].default_value=.65
bpy.ops.object.camera_add(location=(-10.3,-7.5,9.3))
cam=bpy.context.object
cam.rotation_euler=(Vector((.08,.38,.62))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=8.0;scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT'
scene.render.resolution_x=1800;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ART/'Previews/Blender_HomeLifeProps.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/HomeLifeProps.blend'))
bpy.ops.render.render(write_still=True)
print('HOME LIFE PROPS COMPLETE '+json.dumps(metadata['assets']))
