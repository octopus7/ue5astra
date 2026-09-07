"""Starfall snapped wood, aged log and layered pink canopy kit, in metres.

Run Blender 4.5 --factory-startup -b --python this_file.py.
Every asset has its lowest geometry at local Z=0 and XY-centred footprint.
Fallen trunks run along local +X. Leaves are closed, curved lens meshes.
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
OUT = ART / 'Meshes' / 'Starfall'
OUT.mkdir(parents=True, exist_ok=True)
for folder in ('Blender', 'Layout', 'Previews'):
    (ART / folder).mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
SCENE = bpy.context.scene
SCENE.unit_settings.system = 'METRIC'
SCENE.unit_settings.scale_length = 1.0
LIBRARY = bpy.data.collections.new('01_StarfallTreesMeshLibrary')
PREVIEW = bpy.data.collections.new('02_StarfallTreesPresentation')
SCENE.collection.children.link(LIBRARY)
SCENE.collection.children.link(PREVIEW)
PALETTE = {
    'M_SF_Tree_Bark': '8F654D',
    'M_SF_Tree_BarkWarm': 'AC7D5B',
    'M_SF_Tree_BarkShadow': '68585B',
    'M_SF_Tree_BarkGroove': '594B49',
    'M_SF_Tree_FreshWood': 'F5D79B',
    'M_SF_Tree_FreshWoodRing': 'CB9C64',
    'M_SF_Tree_OldWood': '8B8474',
    'M_SF_Tree_OldWoodLight': 'ACA18A',
    'M_SF_Tree_RottenInterior': '514F49',
    'M_SF_Tree_Moss': '738B4B',
    'M_SF_Tree_MossLight': 'A8BA66',
    'M_SF_Tree_Fungus': 'C79675',
    'M_SF_Tree_FungusEdge': 'EDCFAD',
    'M_SF_Tree_LeafGreen': '62945B',
    'M_SF_Tree_LeafGreenLight': '90B766',
    'M_SF_Tree_LeafGreenDark': '416C58',
    'M_SF_Tree_LeafPink': 'F0A0AE',
    'M_SF_Tree_LeafPinkLight': 'F7B7C0',
    'M_SF_Tree_LeafPinkRose': 'DE86A2',
    'M_SF_Tree_LeafPinkShade': 'B96891',
}


def linear(x):
    return x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4


MATS = {}
for name, color_hex in PALETTE.items():
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    color = tuple(linear(int(color_hex[i:i+2], 16) / 255) for i in (0, 2, 4))
    material.diffuse_color = (*color, 1)
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .84
    MATS[name] = material


def mesh(name, vertices, faces, mat, per_face=None, additional=()):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    SCENE.collection.objects.link(obj)
    for key in (mat, *additional):
        data.materials.append(MATS[key])
    for index, face in enumerate(data.polygons):
        face.use_smooth = True
        if per_face:
            face.material_index = per_face[index]
    return obj


def ball(name, center, scale, mat, segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(MATS[mat])
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def tube(name, points, radii, mat, sides=12):
    points = [Vector(p) for p in points]
    vertices = []
    for index, point in enumerate(points):
        if index == 0:
            tangent = (points[1] - point).normalized()
        elif index == len(points)-1:
            tangent = (point - points[-2]).normalized()
        else:
            tangent = (points[index+1] - points[index-1]).normalized()
        base = Vector((0, 1, 0)) if abs(tangent.z) > .95 else Vector((0, 0, 1))
        axis_u = tangent.cross(base).normalized()
        axis_v = tangent.cross(axis_u).normalized()
        for j in range(sides):
            a = math.tau * j / sides
            r = radii[index] * (1 + .032 * math.sin(j * 2.8))
            vertices.append(point + r * (math.cos(a) * axis_u + math.sin(a) * axis_v))
    faces = [tuple(range(sides-1, -1, -1))]
    for row in range(len(points)-1):
        for j in range(sides):
            faces.append((row*sides+j, row*sides+(j+1)%sides,
                          (row+1)*sides+(j+1)%sides, (row+1)*sides+j))
    faces.append(tuple(range((len(points)-1)*sides, len(points)*sides)))
    return mesh(name, vertices, faces, mat)


def leaf_shell(name, center, radii, pink=True, seed=0, rows=9):
    """Staggered leaves follow the ellipsoid, overlapping like broad canopy scales."""
    rng = random.Random(seed)
    center, radii = Vector(center), Vector(radii)
    vertices, faces, indices = [], [], []
    count = 0
    # The outline has pointed tips, broad shoulders and a raised curved midrib.
    outline = [(0, -.64), (.19, -.42), (.25, -.14), (.22, .18), (.11, .44),
               (0, .73), (-.11, .44), (-.22, .18), (-.25, -.14), (-.19, -.42)]
    outline_count = len(outline)
    average_radius = sum(radii) / 3
    step = math.pi / (rows + 1)
    for row in range(rows):
        theta = step * (row + 1)
        around = max(7, round(2 * math.pi * math.sin(theta) / step))
        for col in range(around):
            phi = math.tau * (col + .5 * (row % 2)) / around + .05 * math.sin(row * 1.73)
            normal = Vector((math.sin(theta)*math.cos(phi), math.sin(theta)*math.sin(phi), math.cos(theta)))
            u = Vector((-math.sin(phi), math.cos(phi), 0))
            down = Vector((math.cos(theta)*math.cos(phi), math.cos(theta)*math.sin(phi), -math.sin(theta)))
            twist = rng.uniform(-.11, .11)
            u, down = u*math.cos(twist)+down*math.sin(twist), down*math.cos(twist)-u*math.sin(twist)
            width = step * 2.40 * (1 + rng.uniform(-.05, .05))
            length = step * 1.38
            base = len(vertices)
            for xx, yy in outline:
                d = (normal + u*xx*width + down*yy*length).normalized()
                # Lower tip floats above the row beneath, producing a readable leaf lip.
                lift = .036 + max(0, yy)*.16
                vertices.append(center + Vector((d.x*radii.x, d.y*radii.y, d.z*radii.z)) + d*lift)
            vertices.append(center + Vector((normal.x*radii.x, normal.y*radii.y, normal.z*radii.z)) + normal*.064)
            vertices.append(center + Vector((normal.x*radii.x, normal.y*radii.y, normal.z*radii.z)) + normal*.027)
            # Material varies by whole leaf and broad height band, never by triangle.
            if pink:
                tone = 1 if normal.z > .45 and (col+row)%3 != 0 else (3 if normal.z < -.38 else (2 if (col+row)%5 == 0 else 0))
            else:
                tone = 1 if normal.z > .15 and (col+row)%3 != 0 else (2 if normal.z < -.38 else 0)
            for j in range(outline_count):
                faces.append((base+j, base+(j+1)%outline_count, base+outline_count)); indices.append(tone)
                faces.append((base+(j+1)%outline_count, base+j, base+outline_count+1)); indices.append(tone)
            count += 1
    palette = ('M_SF_Tree_LeafPink', 'M_SF_Tree_LeafPinkLight', 'M_SF_Tree_LeafPinkRose', 'M_SF_Tree_LeafPinkShade') if pink else ('M_SF_Tree_LeafGreen', 'M_SF_Tree_LeafGreenLight', 'M_SF_Tree_LeafGreenDark')
    obj = mesh(name, vertices, faces, palette[0], indices, palette[1:])
    # Leaf front and back meet at a crisp thin rim. Splitting only this boundary
    # avoids the inflated pillow shading produced by averaging opposite sides.
    stride = outline_count + 2
    for edge in obj.data.edges:
        a, b = edge.vertices
        if a//stride == b//stride and a%stride < outline_count and b%stride < outline_count:
            edge.use_edge_sharp = True
    core = ball(name+'_RoundedCore', center, radii, palette[-1], 20, 12)
    obj['actual_leaf_count'] = count
    return [core, obj], count


def roots_and_trunk(height=3.8, radius=.26, seed=0):
    rng = random.Random(seed)
    parts = [tube('SoftlyCurvedLivingTrunk', [(0,0,.07), (.03,-.02,.55), (-.10,.05,1.65),
             (.10,.08,2.8), (.05,0,height)], [radius*1.55, radius, radius*.84, radius*.62, radius*.15], 'M_SF_Tree_Bark', 16)]
    for i in range(6):
        a = math.tau*i/6 + .13
        reach = .7 + .15*rng.random()
        parts.append(tube('CurvedRoot', [(0,0,.38), (.33*math.cos(a),.33*math.sin(a),.18),
             (reach*math.cos(a),reach*math.sin(a),.055)], [radius*.65,.13,.015], 'M_SF_Tree_Bark', 10))
    for i in range(4):
        a = math.tau*i/4+.6
        parts.append(tube('CanopyBranch', [(0,.02,2.15), (.36*math.cos(a),.36*math.sin(a),2.95),
             (.93*math.cos(a),.93*math.sin(a),3.65)], [.145,.095,.015], 'M_SF_Tree_BarkWarm', 10))
    for i in range(7):
        a=math.tau*i/7+.29
        parts.append(tube('LivingBarkFlow',[(radius*.99*math.cos(a)+.03,radius*.99*math.sin(a)-.02,.58),
                    (radius*.90*math.cos(a)-.09,radius*.90*math.sin(a)+.05,1.55),
                    (radius*.67*math.cos(a)+.07,radius*.67*math.sin(a)+.07,2.60)],
                    [.016,.022,.008], 'M_SF_Tree_BarkWarm' if i%3 else 'M_SF_Tree_BarkShadow',8))
    return parts


def jagged_stump():
    n = 22
    vertices, faces, face_mats = [], [], []
    heights = [2.04 + .26*math.sin(j*1.91) + (.48 if j%7 == 1 else 0) for j in range(n)]
    for row in range(5):
        for j in range(n):
            a = math.tau*j/n
            r = (.70,.54,.48,.46,.385)[row] * (1+.065*math.sin(j*2.6))
            z = (0,.32,1.70,heights[j],heights[j]-.115)[row]
            vertices.append((r*math.cos(a)+.025*z,r*math.sin(a),z))
    faces.append(tuple(range(n-1,-1,-1))); face_mats.append(0)
    for row in range(4):
        for j in range(n):
            faces.append((row*n+j,row*n+(j+1)%n,(row+1)*n+(j+1)%n,(row+1)*n+j))
            face_mats.append(1 if row == 3 else (2 if j%6 == 2 else 0))
    vertices.append((.045,0,1.96))
    for j in range(n):
        faces.append((4*n+j,4*n+(j+1)%n,5*n)); face_mats.append(1)
    parts = [mesh('FreshStumpOuterBarkAndSplinteredHeart',vertices,faces,'M_SF_Tree_Bark',face_mats,
                  ('M_SF_Tree_FreshWood','M_SF_Tree_BarkShadow'))]
    for i, a in enumerate((.3,1.3,2.7,3.9,5.1)):
        x,y=.30*math.cos(a),.30*math.sin(a)
        h=(.78,.52,.96,.64,.43)[i]
        v=[(x-.055,y-.055,1.87),(x+.075,y-.045,1.91),(x+.05,y+.07,1.93),(x-.04,y+.055,1.86),
           (x+.075*math.cos(a),y+.075*math.sin(a),1.97+h)]
        f=[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]
        parts.append(mesh('PaleLongSharpFreshSplinter',v,f,'M_SF_Tree_FreshWood'))
    for i in range(7):
        a=math.tau*i/7
        parts.append(tube('StumpRoot',[(.1,0,.55),(.53*math.cos(a),.53*math.sin(a),.22),
                          (1.1*math.cos(a),1.1*math.sin(a),.035)],[.20,.18,.025],'M_SF_Tree_Bark',10))
    for i in range(10):
        a=math.tau*(i+.18)/10
        parts.append(tube('VerticalBarkCrevice',[(.522*math.cos(a)+.008,.522*math.sin(a),.43),
                           (.49*math.cos(a)+.025,.49*math.sin(a),1.06),
                           (.473*math.cos(a)+.043,.473*math.sin(a),1.60)],
                           [.012,.018,.009],'M_SF_Tree_BarkGroove',6))
    return parts


def fresh_fallen():
    parts=[tube('FreshFallenTrunk',[(-3.3,0,.65),(-1.6,.02,.64),(.1,-.05,.85),(1.8,.05,1.09),(2.6,.08,1.16)],
                [.43,.37,.28,.16,.04],'M_SF_Tree_Bark',18)]
    for i in range(11):
        a=math.tau*(i+.18)/11
        parts.append(tube('FreshFallenBarkCrease',[(-3.20,.43*math.cos(a),.65+.43*math.sin(a)),
                   (-1.6,.02+.377*math.cos(a),.64+.377*math.sin(a)),
                   (.1,-.05+.286*math.cos(a),.85+.286*math.sin(a)),
                   (1.6,.04+.18*math.cos(a),1.06+.18*math.sin(a))],
                   [.014,.021,.018,.008],'M_SF_Tree_BarkShadow' if i%3 else 'M_SF_Tree_BarkWarm',8))
    # Pale broken end is a solid crown of jagged wedges, rather than a flat saw cut.
    n=18; vertices=[]; faces=[]
    for ring in range(2):
        for j in range(n):
            a=math.tau*j/n
            x=-3.31-(.11+.15*(.5+.5*math.sin(j*2.8)) if ring else -.045)
            r=.38 if ring else .39
            vertices.append((x,r*math.cos(a),.65+r*math.sin(a)))
    faces.append(tuple(range(n-1,-1,-1)))
    for j in range(n): faces.append((j,(j+1)%n,n+(j+1)%n,n+j))
    vertices.append((-3.40,0,.65))
    for j in range(n): faces.append((n+j,n+(j+1)%n,2*n))
    parts.append(mesh('FreshFallenPaleJaggedBreak',vertices,faces,'M_SF_Tree_FreshWood'))
    for j in (1,4,8,12,15):
        a=math.tau*j/n
        yy,zz=.27*math.cos(a),.65+.27*math.sin(a)
        v=[(-3.29,yy-.045,zz-.04),(-3.29,yy+.05,zz-.04),(-3.29,yy+.05,zz+.06),
           (-3.29,yy-.045,zz+.06),(-3.77+(j%3)*.07,yy,zz+.025)]
        parts.append(mesh('BrokenFallenWoodFibre',v,[(0,1,2,3),(0,4,1),(1,4,2),(2,4,3),(3,4,0)],'M_SF_Tree_FreshWood'))
    for a,b in [((-.3,0,.80),(.8,-1.0,1.0)),((.6,0,.92),(1.9,1.12,1.4)),((1.1,0,1.0),(2.3,-.6,1.7))]:
        parts.append(tube('FreshCrownBranch',[a,Vector(a).lerp(Vector(b),.55),b],[.15,.11,.025],'M_SF_Tree_BarkWarm',10))
    leaf_count=0
    for j,(center,radii) in enumerate([((1.50,.05,1.55),(1.55,1.35,1.25)),((.80,-.91,1.20),(1.12,.90,.88)),((2.15,.80,1.55),(1.15,.92,1.03))]):
        objects,count=leaf_shell('FreshGreenLayeredCrown',center,radii,False,92+j,7)
        parts.extend(objects); leaf_count+=count
    return parts,leaf_count


def old_log():
    n=24; rows=6; vertices=[];faces=[];indices=[]
    # Thick closed shell with a real hollow passage and uneven eroded annular rims.
    for inner in (False,True):
        for row in range(rows):
            t=row/(rows-1)
            for j in range(n):
                a=math.tau*j/n
                radius=(.57 if not inner else .365)*(1+.075*math.sin(j*2.3+.6*row))
                x=-2.5+5*t
                if row in (0,rows-1): x+=.10*math.sin(j*2.1)+.06*math.cos(j*4.5)
                z=.60+radius*math.sin(a)+.04*math.sin(t*math.pi)
                vertices.append((x,radius*math.cos(a),z))
    for inner in (False,True):
        offset=rows*n if inner else 0
        for row in range(rows-1):
            for j in range(n):
                f=(offset+row*n+j,offset+row*n+(j+1)%n,offset+(row+1)*n+(j+1)%n,offset+(row+1)*n+j)
                faces.append(tuple(reversed(f)) if inner else f);indices.append(1 if inner else (2 if j%6==0 else 0))
    for row in (0,rows-1):
        for j in range(n):
            f=(row*n+j,row*n+(j+1)%n,rows*n+row*n+(j+1)%n,rows*n+row*n+j)
            faces.append(tuple(reversed(f)) if row==0 else f);indices.append(2)
    parts=[mesh('HollowWeatheredLog',vertices,faces,'M_SF_Tree_OldWood',indices,
                ('M_SF_Tree_RottenInterior','M_SF_Tree_OldWoodLight'))]
    # Detached-looking bark plates remain closed solids, with worn broken ends.
    # Their broad strips reveal age at game scale without texture-sized geometry.
    for i in range(15):
        a = math.tau*(i+.27)/15
        x0 = -2.38 + .11*math.sin(i*1.7)
        x1 = 2.37 + .13*math.cos(i*2.1)
        if i%3==0: x0 += .50
        vv=[];ff=[]
        for radial in (0,1):
            for row in range(5):
                t=row/4
                for j in range(3):
                    angle=a+(j-1)*.11+.017*math.sin(row*2+i)
                    radius=.565+radial*(.038+.012*math.sin(row*1.4+i))
                    x=x0+(x1-x0)*t
                    if row in (0,4): x += (j-1)*.075+.06*math.sin(i+j*2)
                    vv.append((x,radius*math.cos(angle),.60+radius*math.sin(angle)+.028*math.sin(t*math.pi)))
        for radial in (0,1):
            start=radial*15
            for row in range(4):
                for j in range(2):
                    f=(start+row*3+j,start+row*3+j+1,start+(row+1)*3+j+1,start+(row+1)*3+j)
                    ff.append(tuple(reversed(f)) if radial==0 else f)
        border=[0,1,2,5,8,11,14,13,12,9,6,3]
        for j in range(len(border)):
            a0,b0=border[j],border[(j+1)%len(border)]
            ff.append((a0,b0,b0+15,a0+15))
        parts.append(mesh('RaisedWeatheredBarkPlate',vv,ff,'M_SF_Tree_OldWoodLight' if i%4==0 else 'M_SF_Tree_OldWood'))
    for i in range(12):
        a=math.tau*(i+.12)/12
        pts=[]
        for j in range(5):
            x=-2.20+j*1.06
            pts.append((x,(.582+.015*math.sin(j*2+i))*math.cos(a),.60+.586*math.sin(a)+.05*math.sin(j)))
        parts.append(tube('DeepAgedBarkFissure',pts,[.014,.022,.02,.018,.010],'M_SF_Tree_RottenInterior',6))
    for i,(x,y,s) in enumerate([(-1.6,-.12,.61),(-.85,.07,.57),(-.04,-.11,.64),(.65,.15,.55),(1.50,.06,.61),(2.04,-.07,.36)]):
        parts.append(ball('SoftMossPillow',(x,y,1.125),(s,.36,.115),'M_SF_Tree_Moss' if i%2 else 'M_SF_Tree_MossLight',16,8))
    for i,(x,y,z) in enumerate([(-1.8,-.49,.67),(-1.59,-.52,.88),(.65,-.49,.61),(.82,-.45,.89),(1.70,.50,.76)]):
        size=.24 if i%2 else .30
        parts.append(ball('ShelfFungusCreamEdge',(x,y,z),(size,.20,.055),'M_SF_Tree_FungusEdge',16,8))
        parts.append(ball('ShelfFungusWarmCap',(x,y,z+.034),(size*.89,.172,.047),'M_SF_Tree_Fungus',16,8))
    parts.append(tube('AgedSnappedBranch',[(1.09,.24,.80),(1.17,.58,1.13),(1.04,.69,1.36)],[.17,.12,.09],'M_SF_Tree_OldWood',12))
    return parts


ASSETS=[]; INFOS=[]


def finish_asset(name, parts, collision, description, leaves=0, height=None):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts: obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    obj=bpy.context.object;obj.name=name
    SCENE.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    mins=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    maxs=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    scale_z=height/(maxs[2]-mins[2]) if height else 1
    for v in obj.data.vertices:
        v.co.x-=(mins[0]+maxs[0])*.5;v.co.y-=(mins[1]+maxs[1])*.5
        v.co.z=(v.co.z-mins[2])*scale_z
    obj.data.update()
    # A real UV0 is present even for the deliberately solid painted palette.
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.002)
    bpy.ops.object.mode_set(mode='OBJECT')
    tri=obj.modifiers.new('ExportTriangles','TRIANGULATE');tri.keep_custom_normals=True
    bpy.ops.object.modifier_apply(modifier=tri.name)
    for face in obj.data.polygons:face.use_smooth=True
    for collection in list(obj.users_collection):collection.objects.unlink(obj)
    LIBRARY.objects.link(obj)
    obj['asset_id']=name;obj['collision']=collision;obj['description']=description
    obj['actual_leaf_count']=leaves
    bpy.context.view_layer.update()
    bm=bmesh.new();bm.from_mesh(obj.data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    degenerate=sum(f.calc_area()<1e-10 for f in bm.faces)
    bm.free()
    assert nonmanifold==0 and degenerate==0,(name,nonmanifold,degenerate)
    assert all(math.isfinite(c) for v in obj.data.vertices for c in v.co)
    assert all(math.isfinite(c) for d in obj.data.uv_layers.active.data for c in d.uv)
    uv_min_area=1
    for face in obj.data.polygons:
        a,b,c=[obj.data.uv_layers.active.data[i].uv for i in face.loop_indices]
        uv_min_area=min(uv_min_area,abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5)
    assert uv_min_area>1e-14,(name,uv_min_area)
    used=set(p.material_index for p in obj.data.polygons)
    # Joining can duplicate material slots; canonicalize them before interchange.
    slot_names=[s.material.name for s in obj.material_slots]
    canonical=[]
    for idx in sorted(used):
        if slot_names[idx] not in canonical:canonical.append(slot_names[idx])
    old_indices=[canonical.index(slot_names[p.material_index]) for p in obj.data.polygons]
    obj.data.materials.clear()
    for key in canonical:obj.data.materials.append(MATS[key])
    for face,idx in zip(obj.data.polygons,old_indices):face.material_index=idx
    bounds=[[min(v.co[i] for v in obj.data.vertices) for i in range(3)],
            [max(v.co[i] for v in obj.data.vertices) for i in range(3)]]
    item={'asset_id':name,'file':f'ArtSource/Meshes/Starfall/{name}.fbx',
          'materials':canonical,'material_slots':canonical,'collision':collision,
          'dimensions_m':[round(float(v),6) for v in obj.dimensions],
          'bounds_min_m':[round(v,6) for v in bounds[0]],'bounds_max_m':[round(v,6) for v in bounds[1]],
          'triangles':len(obj.data.polygons),'vertices':len(obj.data.vertices),
          'normal_import_method':'IMPORT_NORMALS_AND_TANGENTS','origin':'XY footprint centre, ground Z=0',
          'front_axis_blender':'+X','description':description,'actual_leaf_count':leaves,
          'validation':{'non_manifold_edges':nonmanifold,'degenerate_triangles':degenerate,
                        'finite_vertices':True,'finite_uv':True,'minimum_uv_triangle_area':uv_min_area,
                        'all_faces_smooth':True,'ground_z_zero':abs(bounds[0][2])<1e-6}}
    if collision=='trunk':item['trunk_collision']={'radius_m':.33,'height_m':2.8,
                        'centre_xy_m':[round(-(mins[i]+maxs[i])*.5,6) for i in range(2)],
                        'roots_no_collision':True,'canopy_no_collision':True}
    bpy.ops.export_scene.fbx(filepath=str(OUT/f'{name}.fbx'),use_selection=True,object_types={'MESH'},
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
        bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_mesh_modifiers=True,
        path_mode='STRIP',use_tspace=True)
    obj.hide_render=True;obj.hide_set(True)
    ASSETS.append(obj);INFOS.append(item)
    return obj


finish_asset('SM_SF_FreshBrokenStump',jagged_stump(),'complex',
             'Newly broken standing trunk; pale ragged heartwood, long sharp wood fibres, radiating roots.',height=3.0)
parts,leaves=fresh_fallen()
finish_asset('SM_SF_FreshFallenTree',parts,'complex',
             'Fresh matching fallen trunk along +X; pale splintered break at -X, intact layered green crown at +X.',leaves)
finish_asset('SM_SF_OldMossLog',old_log(),'complex',
             'Old hollow fallen log along +X; open dark passage, eroded thick rims, fissures, moss cushions and shelf fungi.')
PINK_FORMS=[
    [((0,.05,4.45),(1.58,1.48,1.56)),((-1.40,-.12,3.37),(1.16,1.18,1.13)),((1.35,.31,3.48),(1.13,1.15,1.14))],
    [((-.17,.05,4.02),(1.57,1.52,1.55)),((1.16,-.30,3.25),(1.18,1.13,1.13)),((-.99,.50,3.11),(1.25,1.10,1.08))],
    [((0,.10,4.93),(1.56,1.46,1.69)),((-1.31,-.25,3.55),(1.22,1.18,1.20)),((1.20,.12,3.73),(1.17,1.17,1.21))],
]
for i,lobes in enumerate(PINK_FORMS):
    parts=roots_and_trunk(4.1,.28,102+i);leaves=0
    for j,(center,radii) in enumerate(lobes):
        objects,count=leaf_shell('LayeredPinkCanopyLobe',center,radii,True,202+i*4+j,10)
        parts.extend(objects);leaves+=count
    finish_asset(f'SM_SF_PinkTree_{i+1:02}',parts,'trunk',
                 'Three overlapping round canopy lobes wrapped in staggered broad pointed closed leaves; pink and blush layers with cool rose undersides.',
                 leaves,height=(6.10,5.75,6.75)[i])

# Reimport each actual FBX and compare grounded transforms, dimensions, UVs,
# triangle counts and ordered material slots. Import files are not trusted blindly.
ROUNDTRIP=[]
for original,item in zip(ASSETS,INFOS):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(OUT/f'{original.name}.fbx'),use_custom_normals=True)
    imported=[o for o in set(bpy.data.objects)-before if o.type=='MESH']
    assert len(imported)==1
    obj=imported[0];bpy.context.view_layer.update()
    delta=max(abs(obj.dimensions[i]-original.dimensions[i]) for i in range(3))
    assert delta<1e-5 and obj.location.length<1e-6
    assert len(obj.data.polygons)==item['triangles'] and obj.data.uv_layers.active
    assert all(p.use_smooth for p in obj.data.polygons)
    slots=[s.material.name.split('.')[0] for s in obj.material_slots]
    assert slots==item['materials'],(slots,item['materials'])
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free()
    assert nonmanifold==0,(original.name,nonmanifold)
    result={'asset_id':original.name,'passed':True,'bounds_max_error_m':delta,
            'origin_zero':True,'triangle_count_preserved':True,'material_slots_match':True,
            'smooth_normals_preserved':True,'non_manifold_edges':0,'uv0_present':True}
    item['validation']['fbx_roundtrip']=result
    ROUNDTRIP.append(result)
    for imported_obj in set(bpy.data.objects)-before:bpy.data.objects.remove(imported_obj,do_unlink=True)

metadata={'source':'ArtSource/Blender/StarfallTrees.blend','script':'Scripts/build_starfall_trees.py',
          'reference':'ArtSource/Reference/Starfall/Ref_StarfallTrees.png','units':'metres',
          'unreal_conversion':'(Blender X, -Blender Y, Blender Z) * 100; yaw negated',
          'materials':{name:{'base_color':value,'roughness':.84,'metallic':0.0} for name,value in PALETTE.items()},
          'assets':INFOS,'placement_notes':'Fallen tree and log long axis is +X. Stump and living trees ground at local Z=0. Living tree collision must use the metadata trunk cylinder and exclude the leaf canopy. Fresh fallen tree matches the stump species; arrange its -X broken end toward the standing stump, leaving a visible fresh gap.'}
(ART/'Layout'/'starfall_trees.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
(ART/'Previews'/'StarfallTrees_Validation.json').write_text(json.dumps({'passed':True,'asset_count':len(INFOS),'assets':INFOS,'fbx_roundtrip':ROUNDTRIP},indent=2)+'\n',encoding='utf-8')

# Asset-board render: three pink canopy variants at back, freshly broken wood
# and the dark hollow aged log in front. All visible geometry is exported FBX.
placements=[(-5.0,-3.5,0),(2.8,-2.6,0),(-.6,-6.0,0),(-5.2,3.5,0),(0,3.6,0),(5.2,5.3,0)]
for obj,position in zip(ASSETS,placements):
    preview=bpy.data.objects.new('Preview_'+obj.name,obj.data);PREVIEW.objects.link(preview)
    preview.location=position
    if obj.name=='SM_SF_OldMossLog':preview.rotation_euler.z=math.radians(-15)
ground=bpy.data.materials.new('StarfallTreePreviewGround');ground.use_nodes=True
ground.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.28,.36,.20,1)
ground.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.95
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025));bpy.context.object.data.materials.append(ground)
SCENE.world=bpy.data.worlds.new('StarfallTreesSky');SCENE.world.use_nodes=True
SCENE.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.59,.73,.93,1)
SCENE.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.7
bpy.ops.object.light_add(type='SUN',location=(-8,-10,18));sun=bpy.context.object
sun.name='SoftSun_50deg';sun.rotation_euler=(.4,-.5,-.55);sun.data.energy=2.4;sun.data.angle=math.radians(50)
bpy.ops.object.camera_add(location=(-14,-22,19));camera=bpy.context.object
camera.rotation_euler=(Vector((0,1.0,2.0))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=23.0;SCENE.camera=camera
SCENE.render.engine='CYCLES';SCENE.cycles.samples=40;SCENE.cycles.use_denoising=True
SCENE.render.resolution_x=1800;SCENE.render.resolution_y=1450;SCENE.render.resolution_percentage=100
SCENE.render.image_settings.file_format='PNG';SCENE.render.filepath=str(ART/'Previews'/'Blender_StarfallTrees.png')
SCENE.view_settings.view_transform='AgX';SCENE.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'Blender'/'StarfallTrees.blend'))
bpy.ops.render.render(write_still=True)
print('STARFALL TREES COMPLETE '+json.dumps(INFOS))
