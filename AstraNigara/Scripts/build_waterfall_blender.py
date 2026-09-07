"""Blender 4.5: original low-poly anime waterfall kit, UVs, FBX and preview.
Run with --background --factory-startup --python this_file.
All model coordinates are centimetres; export objects share a scene origin.
"""
import bpy, math, random, json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'ArtSource'/'Waterfall'
FBX = ART/'FBX'
FBX.mkdir(parents=True, exist_ok=True)
(ROOT/'Docs'/'Previews').mkdir(parents=True, exist_ok=True)
random.seed(782)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = .01
scene.unit_settings.length_unit = 'CENTIMETERS'
groups = {}


def mat(name, rgb, emission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb,1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*rgb,1)
    p.inputs['Roughness'].default_value = .8
    if emission:
        p.inputs['Emission Color'].default_value = (*rgb,1)
        p.inputs['Emission Strength'].default_value = emission
    return m


rock = mat('WF_Rock', (.24,.31,.33))
moss = mat('WF_Moss', (.24,.43,.20))
earth = mat('WF_Earth', (.15,.23,.19))
leaf = mat('WF_Leaf', (.13,.35,.22))
leaflight = mat('WF_LeafLight', (.39,.59,.24))
bark = mat('WF_Bark', (.19,.23,.19))
flower = mat('WF_Flower', (.76,.82,.57), .2)
water = mat('WF_Water', (.045,.53,.62), .15)
poolmat = mat('WF_Pool', (.025,.31,.34), .12)
foam = mat('WF_Foam', (.70,.94,.91), .4)
impactfoam = mat('WF_ImpactFoam', (.55,.85,.80), .25)


def add_group(obj, group):
    groups.setdefault(group, []).append(obj)
    return obj


def mesh(name, vertices, faces, material, group, uvs=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    data.materials.append(material)
    uv = data.uv_layers.new(name='UVMap')
    for p in data.polygons:
        for li in p.loop_indices:
            vi = data.loops[li].vertex_index
            uv.data[li].uv = uvs[vi] if uvs else (vertices[vi][0]/400+.5, vertices[vi][1]/400+.5)
    return add_group(obj, group)


def stone(name, pos, scale, material=rock, group='SM_WF_Rockwork', subdivisions=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions,radius=1, location=pos)
    obj=bpy.context.object
    obj.name=name
    for v in obj.data.vertices:
        v.co *= random.uniform(.86,1.13)
    obj.scale=scale
    obj.rotation_euler=(random.uniform(-.2,.2),random.uniform(-.2,.2),random.uniform(-.5,.5))
    obj.data.materials.append(material)
    return add_group(obj, group)


def ellipsoid_disc(name, rx, ry, center, material, group, segments=64, rings=5, irregular=.025):
    verts=[center]
    uv=[(.5,.5)]
    for j in range(1,rings+1):
        radius=j/rings
        for i in range(segments):
            a=2*math.pi*i/segments
            uneven=1+irregular*math.sin(a*5+.8)+irregular*.5*math.sin(a*9)
            x,y=rx*radius*math.cos(a)*uneven,ry*radius*math.sin(a)*uneven
            verts.append((center[0]+x,center[1]+y,center[2]))
            uv.append((x/rx/2+.5,y/ry/2+.5))
    faces=[]
    for i in range(segments): faces.append((0,1+i,1+(i+1)%segments))
    for j in range(rings-1):
        a=1+j*segments
        b=a+segments
        for i in range(segments):
            ni=(i+1)%segments
            faces.append((a+i,b+i,b+ni,a+ni))
    return mesh(name,verts,faces,material,group,uv)


# An intentionally bent, ribbon-shaped waterfall, including the top lip.
# U is cross-stream; V monotonically increases downstream from 0 to 1.
rows,cols=30,12
vertices=[];uvs=[]
path=[]
for j in range(rows+1):
    t=j/rows
    if t < .18:
        u=t/.18
        y,z=130-55*u,224-12*u*u
    else:
        u=(t-.18)/.82
        # Continue below the pond instead of leaving a visible cut edge above it.
        y,z=75-42*u+7*math.sin(u*math.pi),212-214*u
    path.append((y,z))
    width=47 + 9*t + 12*t**7
    for i in range(cols+1):
        u=i/cols
        x=(u*2-1)*width
        vertices.append((x, y+2.3*math.sin(u*math.pi*5+t*10), z+1.1*math.cos(u*math.pi*4)))
        uvs.append((u,t))
faces=[]
for j in range(rows):
    for i in range(cols):
        a=j*(cols+1)+i
        faces.append((a,a+1,a+cols+2,a+cols+1))
curtain=mesh('Waterfall curtain / V downward',vertices,faces,water,'SM_WF_WaterCurtain',uvs)
for p in curtain.data.polygons: p.use_smooth=True
ellipsoid_disc('Quiet emerald pool',180,145,(0,-50,5),poolmat,'SM_WF_Pool',rings=5)

# Curved impact sheet: a low lifted collar joins the curtain to an outgoing
# surface fan. UE erodes the silhouette and animates foam through these UVs.
verts=[];uv=[];faces=[]
for j in range(11):
    t=j/10
    for i in range(33):
        u=i/32;s=u*2-1
        width=77+22*t+4*math.sin(t*7+s*3)
        y=47-90*t+3*math.sin(s*7+t*5)
        lift=19*math.exp(-((t-.19)/.19)**2)
        z=6.4+lift*(.76+.24*math.cos(s*4))
        z+=1.9*math.sin(s*13+t*9)*math.sin(t*math.pi)
        verts.append((s*width,y,z));uv.append((u,t))
for j in range(10):
    for i in range(32):
        a=j*33+i;faces.append((a,a+1,a+34,a+33))
apron=mesh('Breaking impact foam fan',verts,faces,impactfoam,'SM_WF_ImpactApron',uv)
for p in apron.data.polygons:p.use_smooth=True

# Small upper stream, visible between the banks on the crest.
mesh('Upper stream', [(-47,78,223),(47,78,223),(42,180,229),(-42,180,229)],[(0,1,2,3)],water,'SM_WF_UpperStream',[(0,1),(1,1),(1,0),(0,0)])

# Rock escarpment: interlocked faceted boulders around the falling water.
for side in [-1,1]:
    for j in range(3):
        for k in range(2):
            x=side*(70+k*57+random.uniform(-8,8))
            y=109+random.uniform(-8,13)+k*9
            z=38+j*73+random.uniform(-5,5)
            sx,sy,sz=49+random.random()*13,53+random.random()*15,53+random.random()*9
            stone('Cliff layered stone',(x,y,z),(sx,sy,sz),subdivisions=2)
            if j==2 or (j==1 and k==1):
                stone('Velvet moss cap',(x-4,y-3,z+sz*.72),(sx*.91,sy*.85,12),moss,'SM_WF_Moss',2)
stone('Back wall',(0,150,105),(105,38,112),rock,subdivisions=2)
stone('Crest left',(-72,148,232),(46,76,23),moss,'SM_WF_Moss',2)
stone('Crest right',(78,150,230),(45,71,20),moss,'SM_WF_Moss',2)

# Pond bank follows the irregular ellipse; leave the back centre open at impact.
for i in range(22):
    a=2*math.pi*i/22
    if abs(a-math.pi/2)<.34: continue
    x=199*math.cos(a);y=-50+161*math.sin(a)
    s=random.uniform(18,31)
    stone('River-worn bank stone',(x,y,3),(s*1.3,s,random.uniform(18,30)),rock,subdivisions=2)
    if i%3==0: stone('Moss at water edge',(x-3,y,22),(s*.95,s*.7,6),moss,'SM_WF_Moss')

# A cropped forest floor forms a compact diorama rather than a test grid.
island=ellipsoid_disc('Forest glade top',340,285,(0,-10,-13),moss,'SM_WF_Ground',segments=64,rings=3,irregular=.075)
verts=[];faces=[]
for i in range(64):
    a=2*math.pi*i/64
    r=1+.075*math.sin(a*5+.8)+.0375*math.sin(a*9)
    for z,f in [(-13,1),(-48,.95)]: verts.append((340*math.cos(a)*r*f,-10+285*math.sin(a)*r*f,z))
for i in range(64):
    ni=(i+1)%64
    faces.append((i*2,ni*2,ni*2+1,i*2+1))
mesh('Glade earthen cut edge',verts,faces,earth,'SM_WF_Ground')


def blade(pos, height, angle, width=4, material=leaflight):
    x,y,z=pos
    dx,dy=math.cos(angle),math.sin(angle)
    wx,wy=-dy*width,dx*width
    verts=[(x-wx,y-wy,z),(x+wx,y+wy,z),
           (x+dx*height*.23+wx*.6,y+dy*height*.23+wy*.6,z+height*.58),
           (x+dx*height*.23-wx*.6,y+dy*height*.23-wy*.6,z+height*.58),
           (x+dx*height*.65,y+dy*height*.65,z+height)]
    mesh('Curved grass blade',verts,[(0,1,2,3),(3,2,4)],material,'SM_WF_Foliage')


for i in range(100):
    a=random.uniform(0,2*math.pi)
    radius=random.uniform(1.12,1.52)
    pos=(195*math.cos(a)*radius,-50+153*math.sin(a)*radius,-10)
    if pos[1]>105 and abs(pos[0])<155: continue
    for k in range(random.randint(3,6)):
        blade((pos[0]+random.uniform(-5,5),pos[1]+random.uniform(-5,5),pos[2]),random.uniform(15,34),a+random.uniform(-2,2),random.uniform(2,4))
    if i%8==0:
        stone('Tiny ivory wildflower',(pos[0],pos[1],19),(3,3,3),flower,'SM_WF_Foliage')

# Fern fronds with alternating lance-shaped leaflets.
for px,py in [(-205,-70),(220,-135),(-140,-213),(238,15),(-210,116),(140,191)]:
    for arm in range(6):
        a=arm*math.tau/6+.3
        for j in range(1,7):
            t=j/7; length=52*t; z=12+30*math.sin(t*2.2)
            cx,cy=px+math.cos(a)*length,py+math.sin(a)*length
            for side in [-1,1]:
                al=a+side*1.03
                reach=18*(1-t*.55)
                tip=(cx+math.cos(al)*reach,cy+math.sin(al)*reach,z+3)
                perpendicular=Vector((-math.sin(al)*3,math.cos(al)*3,0))
                mid=(Vector((cx,cy,z))+Vector(tip))*.5
                mesh('Fern leaflet',[(cx,cy,z),tuple(mid+perpendicular),tip,tuple(mid-perpendicular)],[(0,1,2,3)],leaf if arm%2 else leaflight,'SM_WF_Foliage')

# Background shrubs softly frame the crest without hiding the water.
for pos,scale in [((-227,135,48),(70,64,64)),((220,165,63),(65,71,70)),((-155,222,100),(72,60,55)),((132,237,93),(62,56,59))]:
    stone('Woodland shrub',pos,scale,leaf,'SM_WF_Foliage',2)
    stone('Sunlit shrub crown',(pos[0]-10,pos[1]-7,pos[2]+scale[2]*.4),(scale[0]*.84,scale[1]*.85,scale[2]*.63),leaflight,'SM_WF_Foliage',2)

# Uneven thin band, with a duplicated UV seam. Niagara varies ellipse/heading;
# the shader removes broad angular segments independently for each particle.
verts=[];uv=[];faces=[]
for i in range(65):
    a=math.tau*i/64
    center=10*(1+.075*math.sin(a*3+.4)+.045*math.sin(a*5+1.2))
    halfwidth=.65*(1+.30*math.sin(a*4+.8))
    for r,v in [(center-halfwidth,0),(center+halfwidth,1)]:
        verts.append((math.cos(a)*r,math.sin(a)*r,0))
        uv.append((i/64,v))
for i in range(64):
    n=i+1
    faces.append((i*2,n*2,n*2+1,i*2+1))
ring=mesh('Expanding ripple annulus',verts,faces,foam,'SM_WF_RippleRing',uv)
ring.hide_render=True

# Bounds-only locator assets establish FBX basis conversion without guessing.
for name,pos in [('Impact',(0,33,9)),('View',(580,-820,430)),('LookAt',(0,30,90))]:
    bpy.ops.mesh.primitive_cube_add(size=.1,location=pos)
    obj=bpy.context.object
    obj.name='Locator '+name
    obj.data.materials.append(foam)
    obj.hide_render=True
    add_group(obj,'SM_WF_Locator'+name)


def select_only(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]


report={'units':'cm','waterfall_height_cm':220,'pool_width_cm':360,'assets':[]}
for name,objects in groups.items():
    select_only(objects)
    bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=name
    scene.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    if not obj.data.uv_layers:
        uv=obj.data.uv_layers.new(name='UVMap')
        for l in obj.data.loops:
            p=obj.data.vertices[l.vertex_index].co
            uv.data[l.index].uv=(p.x/400+.5,p.y/400+.5)
    obj.data.calc_loop_triangles()
    path=FBX/(name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},
        global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y',axis_up='Z',bake_space_transform=False,
        mesh_smooth_type='FACE',use_mesh_modifiers=True,add_leaf_bones=False,bake_anim=False)
    report['assets'].append({'name':name,'fbx':'FBX/'+path.name,
        'triangles':len(obj.data.loop_triangles),'uv_channels':len(obj.data.uv_layers),
        'materials':[m.name for m in obj.data.materials],
        'dimensions_cm':list(obj.dimensions)})

(ART/'waterfall_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
world=scene.world or bpy.data.worlds.new('Pale sky')
scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.45,.65,.72,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.6
bpy.ops.object.light_add(type='SUN',location=(-300,-400,700))
sun=bpy.context.object;sun.name='Gentle afternoon sun';sun.data.energy=2.4;sun.data.angle=.2
sun.rotation_euler=(math.radians(24),math.radians(-30),math.radians(-30))
bpy.ops.object.camera_add(location=(580,-820,430))
camera=bpy.context.object
camera.rotation_euler=(Vector((0,30,90))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=805;camera.data.clip_end=10000;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1500;scene.render.resolution_y=1150;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ROOT/'Docs'/'Previews'/'Waterfall_Blender.png')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'AnimeWaterfall.blend'))
bpy.ops.render.render(write_still=True)
print('ASTRA_WATERFALL_BLENDER_OK '+json.dumps(report))
