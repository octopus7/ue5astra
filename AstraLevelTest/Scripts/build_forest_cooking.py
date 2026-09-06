"""Independent Blender campfire, cooking tripod, supplies and lantern asset kit."""
import bpy,bmesh,ast,json,math,random
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'ArtSource';R=random.Random(907)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
library=bpy.data.collections.new('01_ForestCookingLibrary');scene.collection.children.link(library)
presentation=bpy.data.collections.new('02_CookingPresentation');scene.collection.children.link(presentation)
PALETTE={'M_CampWood':'A77C45','M_CampWoodLight':'C99B60','M_CampCharcoal':'403F43',
 'M_CampStoneBlue':'65758A','M_CampStoneLight':'8B979F','M_CampIron':'354A57',
 'M_CampEnamel':'397E84','M_CampEnamelLight':'76A4A3','M_CampOchre':'C78040',
 'M_CampRope':'CEB589','M_CampFlame':'FFAE21','M_CampFlameCore':'FFE486',
 'M_CampLanternGlow':'FFC765','M_CampSoup':'945D31'}
# Reuse only proven geometry helpers, without running the cottage builder.
source=(ROOT/'Scripts/build_pink_house_assets.py').read_text(encoding='utf-8')
names={'linear','finish','cube','mesh','bar','cylinder','asset','asset_metadata'}
tree=ast.parse(source)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(ROOT/'Scripts/build_pink_house_assets.py'),'exec'))
materials={}
for name,h in PALETTE.items():
    m=bpy.data.materials.new(name);m.use_nodes=True
    c=tuple(linear(int(h[i:i+2],16)/255) for i in (0,2,4));m.diffuse_color=(*c,1)
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*c,1)
    bs.inputs['Roughness'].default_value=.42 if ('Iron' in name or 'Enamel' in name) else .88
    bs.inputs['Metallic'].default_value=.30 if ('Iron' in name or 'Enamel' in name) else 0
    if 'Flame' in name or 'Glow' in name:
        bs.inputs['Emission Color'].default_value=(*c,1);bs.inputs['Emission Strength'].default_value=1.4
    materials[name]=m

def stone(name,p,s,mat):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=p)
    o=bpy.context.object;o.name=name;o.scale=s
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,mat)

def bowl(name,p,r,height,mat,n=12):
    rings=[(.62,0),(.94,.16),(1,1),(.86,1),(.73,.22)]
    vs=[(p[0]+r*rad*math.cos(i*math.tau/n),p[1]+r*rad*math.sin(i*math.tau/n),p[2]+height*z) for rad,z in rings for i in range(n)]
    fs=[tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))]
    for j in range(len(rings)-1):
        for i in range(n):a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
    return mesh(name,vs,fs,mat)

def arch_handle(name,p,r,z,mat,thickness=.025):
    parts=[]
    for i in range(10):
        a=i*math.pi/10;b=(i+1)*math.pi/10
        parts.append(cylinder(name,(p[0]+r*math.cos(a),p[1],z+r*math.sin(a)),(p[0]+r*math.cos(b),p[1],z+r*math.sin(b)),thickness,mat,6))
    return parts

# Campfire is a reusable ring; tripod remains a separate object.
p=[cylinder('AshBed',(0,0,.01),(0,0,.07),.64,'M_CampCharcoal',16)]
for i in range(11):
    a=i*math.tau/11
    p.append(stone('BlueFireStone',(.73*math.cos(a),.73*math.sin(a),.19),(.25,.21,.19),'M_CampStoneLight' if i%3==0 else 'M_CampStoneBlue'))
for i,a in enumerate((0,.8,2.1)):
    d=Vector((math.cos(a),math.sin(a),0));center=Vector((0,0,.14+i*.07))
    p.append(cylinder('CharredLog',center-d*.58,center+d*.58,.11,'M_CampCharcoal',9))
    p.append(cylinder('LogEnd',center+d*.579,center+d*.593,.095,'M_CampWoodLight',9))
for i,(x,y,h,r) in enumerate(((0,0,.82,.22),(-.28,-.08,.55,.15),(.27,.12,.59,.15),(.08,-.26,.46,.13))):
    n=6;vs=[]
    for z,rad,dx in ((.24,r,0),(.24+h*.35,r*.70,.04),(.24+h*.72,r*.31,-.04)):
        vs.extend((x+dx+rad*math.cos(k*math.tau/n),y+rad*math.sin(k*math.tau/n),z) for k in range(n))
    vs.append((x+.09,y-.02,.24+h));fs=[tuple(range(n-1,-1,-1))]
    for j in range(2):
        for k in range(n):fs.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
    fs.extend((12+k,12+(k+1)%n,18) for k in range(n))
    p.append(mesh('FlameTongue',vs,fs,'M_CampFlameCore' if i==3 else 'M_CampFlame'))
fire=asset('SM_Campfire',p)

p=[]
for a in (math.pi*.5,math.pi*7/6,math.pi*11/6):
    p.append(cylinder('TripodPole',(math.cos(a)*.87,math.sin(a)*.87,.03),(0,0,1.74),.055,'M_CampWood',8))
p.append(cylinder('TripodBinding',(0,0,1.61),(0,0,1.72),.105,'M_CampRope',10))
p.append(cylinder('PotChain',(0,0,1.09),(0,0,1.63),.019,'M_CampIron',6))
p.append(bowl('EnamelPot',(0,0,.68),.31,.30,'M_CampIron'))
p.append(cylinder('PotLid',(0,0,.982),(0,0,1.003),.31,'M_CampEnamel',12))
p.append(cylinder('LidKnob',(0,0,1.002),(0,0,1.055),.052,'M_CampIron',8))
p.extend(arch_handle('PotHandle',(0,0,0),.28,1.0,'M_CampIron',.018))
tripod=asset('SM_CampCookingTripod',p)

p=[]
for x in (-.64,.64):
    for y in (-.33,.33):p.append(cube('CrateLeg',(x,y,.39),(.12,.12,.78),'M_CampWood'))
for i in range(5):
    p.append(cube('CookingTopPlank',(0,-.30+i*.15,.78),(1.43,.139,.085),'M_CampWoodLight' if i%2==0 else 'M_CampWood'))
    p.append(cube('LowerShelf',(0,-.30+i*.15,.17),(1.36,.139,.06),'M_CampWood'))
for y in (-.38,.38):
    for z in (.28,.47):p.append(cube('CrateSideRail',(0,y,z),(1.40,.055,.12),'M_CampWood'))
for x in (-.64,.64):
    for y in (-.39,.39):p.append(cube('IronCorner',(x,y,.76),(.16,.03,.18),'M_CampIron'))
# Kettle, bowl, orange mug, pan and spoon all share the portable cooking station.
kp=(-.38,-.02,.825)
p.append(stone('KettleBody',(-.38,-.02,1.045),(.19,.18,.22),'M_CampEnamel'))
p.append(cylinder('KettleLid',(-.38,-.02,1.23),(-.38,-.02,1.26),.14,'M_CampEnamelLight',12))
p.append(cylinder('KettleKnob',(-.38,-.02,1.26),(-.38,-.02,1.31),.04,'M_CampIron',8))
p.append(cylinder('KettleSpout',(-.38,.08,1.03),(-.38,.30,1.20),.055,'M_CampEnamel',8))
p.extend(arch_handle('KettleHandle',(-.38,-.02,0),.22,1.12,'M_CampIron',.021))
p.append(bowl('WoodenBowl',(.04,.15,.825),.18,.13,'M_CampWoodLight'))
p.append(bowl('Mug',(.42,.18,.825),.09,.19,'M_CampOchre',10))
p.append(bar('MugHandle',(.49,.18,.89),(.57,.18,.89),.035,.035,'M_CampOchre'))
p.append(bar('MugHandle',(.57,.18,.89),(.57,.18,.98),.035,.035,'M_CampOchre'))
p.append(bar('MugHandle',(.57,.18,.98),(.49,.18,.98),.035,.035,'M_CampOchre'))
p.append(bowl('FryingPan',(.22,-.20,.825),.18,.055,'M_CampIron'))
p.append(bar('PanHandle',(.38,-.20,.86),(.67,-.20,.89),.06,.035,'M_CampIron'))
p.append(bar('WoodenSpoon',(-.10,-.23,.84),(-.24,-.31,.84),.028,.016,'M_CampWoodLight'))
p.append(stone('SpoonHead',(-.26,-.32,.84),(.05,.028,.015),'M_CampWoodLight'))
p.append(cube('FoldedCloth',(-.28,-.08,.245),(.46,.38,.10),'M_CampEnamelLight'))
station=asset('SM_CampCookingStation',p)

p=[cylinder('LanternBase',(0,0,.015),(0,0,.105),.21,'M_CampIron',10),
   cylinder('AmberChamber',(0,0,.10),(0,0,.49),.155,'M_CampLanternGlow',8),
   cylinder('LanternTop',(0,0,.48),(0,0,.56),.20,'M_CampIron',10)]
for x,y in ((-.14,-.14),(-.14,.14),(.14,-.14),(.14,.14)):
    p.append(bar('LanternFrame',(x,y,.09),(x*.77,y*.77,.52),.025,.025,'M_CampIron'))
for x in (-.15,.15):p.append(bar('LanternHandle',(x,0,.54),(x,0,.77),.027,.027,'M_CampIron'))
p.append(cylinder('WoodGrip',(-.15,0,.77),(.15,0,.77),.03,'M_CampWoodLight',8))
lantern=asset('SM_CampLantern',p)
assets=[fire,tripod,station,lantern]
props={name:{'roughness':.42 if 'Iron' in name or 'Enamel' in name else .88,
             'metallic':.30 if 'Iron' in name or 'Enamel' in name else 0,
             'emissive_strength':1.4 if 'Flame' in name or 'Glow' in name else 0} for name in PALETTE}
metadata={'source':'ArtSource/Blender/ForestCooking.blend','script':'Scripts/build_forest_cooking.py',
 'reference':'ArtSource/Reference/Ref_ForestCooking.png','units':'metres','unreal_conversion':'(X,-Y,Z)*100',
 'palette_srgb_hex':PALETTE,'material_properties':props,'assets':[asset_metadata(a) for a in assets]}
(ART/'Layout/forest_cooking.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
for a,pos in zip(assets,[(-1.55,-1.0,0),(.80,1.0,0),(-1.15,1.65,0),(1.85,-1.0,0)]):
    o=bpy.data.objects.new('Preview_'+a.name,a.data);presentation.objects.link(o);o.location=pos
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.03));ground=bpy.context.object
groundmat=bpy.data.materials.new('CookingPreviewGround');groundmat.diffuse_color=(.35,.31,.22,1);ground.data.materials.append(groundmat)
bpy.ops.object.light_add(type='SUN',location=(-5,-8,12));sun=bpy.context.object
sun.rotation_euler=(.5,-.4,-.6);sun.data.energy=2.5;sun.data.angle=math.radians(50)
scene.world=bpy.data.worlds.new('CookingSky');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.48,.62,.78,1);bg.inputs['Strength'].default_value=.65
bpy.ops.object.camera_add(location=(-8,-6,10));cam=bpy.context.object
cam.rotation_euler=(Vector((0,.2,.6))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=7.4;scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(ART/'Previews/Blender_ForestCooking.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender/ForestCooking.blend'))
bpy.ops.render.render(write_still=True)
print('FOREST COOKING COMPLETE '+json.dumps(metadata['assets']))
