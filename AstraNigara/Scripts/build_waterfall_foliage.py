"""Plant original Blender clumps as real UE Foliage and author wind/color.

Run from the UE editor console: py ".../Scripts/build_waterfall_foliage.py"
Reruns replace only the three FoliageTypes owned by this script.
"""
import json
import math
import random
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
ART=ROOT/'ArtSource'/'WaterfallFoliage'
DEST='/Game/VFX/Waterfall/Foliage'
MAP='/Game/Maps/L_AnimeWaterfall'
EAL=unreal.EditorAssetLibrary
ML=unreal.MaterialEditingLibrary
AT=unreal.AssetToolsHelpers.get_asset_tools()


def node(m, cls):
    return ML.create_material_expression(m, cls)


def custom(m, code, inputs, output=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    n=node(m, unreal.MaterialExpressionCustom)
    n.set_editor_property('code',code)
    n.set_editor_property('output_type',output)
    pins=[]
    for name in inputs:
        pin=unreal.CustomInput()
        pin.set_editor_property('input_name',name)
        pins.append(pin)
    n.set_editor_property('inputs',pins)
    for name,value in inputs.items():
        source,output_name=value if isinstance(value,tuple) else (value,'')
        assert ML.connect_material_expressions(source,output_name,n,name)
    return n


def make_material():
    name='M_WF_GrassWind'
    m=EAL.load_asset(DEST+'/'+name)
    if not m:
        m=AT.create_asset(name,DEST,unreal.Material,unreal.MaterialFactoryNew())
    ML.delete_all_material_expressions(m)
    m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided',True)
    m.set_editor_property('used_with_instanced_static_meshes',True)
    m.set_editor_property('opacity_mask_clip_value',.08)
    world=node(m,unreal.MaterialExpressionWorldPosition)
    world.set_editor_property('world_position_shader_offset',
        unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    vc=node(m,unreal.MaterialExpressionVertexColor)
    uv=node(m,unreal.MaterialExpressionTextureCoordinate)
    normal=node(m,unreal.MaterialExpressionVertexNormalWS)
    rnd=node(m,unreal.MaterialExpressionPerInstanceRandom)
    time=node(m,unreal.MaterialExpressionTime)
    strength=node(m,unreal.MaterialExpressionScalarParameter)
    strength.set_editor_property('parameter_name','WindStrengthCm')
    strength.set_editor_property('default_value',3.8)
    speed=node(m,unreal.MaterialExpressionScalarParameter)
    speed.set_editor_property('parameter_name','WindSpeed')
    speed.set_editor_property('default_value',1.1)
    shade=custom(m,'''// Slow spatial fields keep neighboring tufts in coherent color masses.
float broad=sin(P.x*.021+sin(P.y*.014)*1.4)*.55+sin(P.y*.027-P.x*.009)*.45;
float patch=smoothstep(-.65,.75,broad);
float bank=1-saturate((length(float2(P.x/180,(P.y-50)/145))-1.05)*1.9);
float3 jade=float3(.075,.245,.16);
float3 olive=float3(.30,.43,.105);
float3 yellowGreen=float3(.48,.57,.18);
float3 body=lerp(jade,olive,patch);
body=lerp(body,yellowGreen,smoothstep(.5,.94,patch)*.58);
body=lerp(body,float3(.07,.29,.19),bank*.30);
body*=lerp(.87,1.12,Rnd)*lerp(.92,1.08,C.g);
float rootShade=lerp(.40,1.0,smoothstep(0,.80,C.r));
float lit=abs(dot(normalize(N),normalize(float3(-.4,-.65,.85))));
float facet=lerp(.78,1.16,smoothstep(.2,.82,lit));
float rib=pow(saturate(1-abs(UV.x-.5)*2),5)*.12;
float3 tip=lerp(body,float3(.57,.64,.27),patch*.24+C.g*.12);
return lerp(body,tip,smoothstep(.55,1,C.r))*rootShade*facet+rib*C.r*body;''',
        {'P':world,'C':vc,'UV':uv,'N':normal,'Rnd':rnd})
    wind=custom(m,'''// R=0 roots remain exact; wind sweeps through patches with small blade flutter.
float weight=pow(saturate(C.r),1.8);
float wave=P.x*.022+P.y*.014-T*Speed*1.65;
float gust=.68+.32*sin(T*Speed*.43-P.y*.009);
float sweep=sin(wave)*.73+sin(wave*1.77+Rnd*2.5)*.20;
float flutter=sin(T*Speed*4.7+C.b*6.283+P.x*.05)*.13;
float bend=(sweep*gust+flutter)*Strength*weight;
return float3(bend*.9,bend*.43,-abs(bend)*.12*weight);''',
        {'P':world,'C':vc,'Rnd':rnd,'T':time,'Strength':strength,'Speed':speed})
    fade=node(m,unreal.MaterialExpressionPerInstanceFadeAmount)
    assert ML.connect_material_property(shade,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assert ML.connect_material_property(wind,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    assert ML.connect_material_property(fade,'',unreal.MaterialProperty.MP_OPACITY_MASK)
    ML.recompile_material(m)
    assert EAL.save_loaded_asset(m)
    return m


def import_meshes(material):
    manifest=json.loads((ART/'foliage_manifest.json').read_text())
    tasks=[]
    for entry in manifest['assets']:
        task=unreal.AssetImportTask()
        task.filename=str(ART/entry['fbx'])
        task.destination_path=DEST+'/Meshes'
        task.destination_name=entry['name']
        task.automated=True
        task.replace_existing=True
        task.save=False
        task.factory=unreal.FbxFactory()
        opt=unreal.FbxImportUI()
        opt.import_mesh=True
        opt.import_as_skeletal=False
        opt.import_materials=False
        opt.import_textures=False
        opt.import_animations=False
        opt.automated_import_should_detect_type=False
        opt.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
        data=opt.static_mesh_import_data
        data.combine_meshes=True
        data.build_nanite=False
        data.generate_lightmap_u_vs=False
        data.auto_generate_collision=False
        data.convert_scene=True
        data.convert_scene_unit=True
        data.import_uniform_scale=1
        data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        data.vertex_color_import_option=unreal.VertexColorImportOption.REPLACE
        task.options=opt
        tasks.append(task)
    AT.import_asset_tasks(tasks)
    meshes={}
    sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for entry in manifest['assets']:
        mesh=EAL.load_asset(DEST+'/Meshes/'+entry['name'])
        assert isinstance(mesh,unreal.StaticMesh),entry['name']
        assert sub.get_num_uv_channels(mesh,0)>=1
        mesh.set_material(0,material)
        # Wind is at most ~4 cm; expanded bounds keep bent tips from popping.
        mesh.set_editor_property('positive_bounds_extension',unreal.Vector(6,6,2))
        mesh.set_editor_property('negative_bounds_extension',unreal.Vector(6,6,2))
        assert EAL.save_loaded_asset(mesh)
        meshes[entry['name']]=mesh
    return manifest,meshes


def make_type(mesh):
    name='FT_'+mesh.get_name().removeprefix('SM_')
    foliage=EAL.load_asset(DEST+'/'+name)
    if not foliage:
        foliage=AT.create_asset(name,DEST,unreal.FoliageType_InstancedStaticMesh,
            unreal.FoliageType_InstancedStaticMeshFactory())
    assert foliage
    foliage.set_editor_property('mesh',mesh)
    foliage.set_editor_property('density',260)
    foliage.set_editor_property('radius',8)
    foliage.set_editor_property('align_to_normal',False)
    foliage.set_editor_property('random_yaw',True)
    interval=foliage.get_editor_property('cull_distance').copy()
    assert interval.import_text('(Min=1300,Max=2200)')
    foliage.set_editor_property('cull_distance',interval)
    foliage.set_editor_property('cast_shadow',False)
    foliage.set_editor_property('evaluate_world_position_offset',True)
    foliage.set_editor_property('world_position_offset_disable_distance',2000)
    foliage.set_editor_property('enable_density_scaling',False)
    body=foliage.get_editor_property('body_instance').copy()
    body.set_editor_property('collision_profile_name','NoCollision')
    body.set_editor_property('collision_enabled',unreal.CollisionEnabled.NO_COLLISION)
    foliage.set_editor_property('body_instance',body)
    assert EAL.save_loaded_asset(foliage)
    return foliage


def placements(names, count=855):
    rng=random.Random(92831)
    result={name:[] for name in names}
    points=[]
    for attempt in range(100000):
        if len(points)>=count:
            break
        x,y=rng.uniform(-340,340),rng.uniform(-275,295)
        # Match the authored irregular diorama boundary, mirrored through FBX Y.
        angle=math.atan2(-(y-10)/285,x/340)
        boundary=1+.075*math.sin(angle*5+.8)+.0375*math.sin(angle*9)
        if math.hypot(x/340,(y-10)/285)>boundary-.065:
            continue
        # Leave water/bank rocks and the waterfall throat readable.
        if (x/224)**2+((y-50)/187)**2<1:
            continue
        if y < -52 and abs(x)<192:
            continue
        patch=.5+.24*math.sin(x*.036+math.sin(y*.024)*1.6)+.22*math.sin(y*.043-x*.012)
        if rng.random()>.30+.70*max(0,min(1,patch)):
            continue
        # Clusters are dense, but roots never coincide and no grid is visible.
        if any((x-px)**2+(y-py)**2<7.2**2 for px,py in points):
            continue
        points.append((x,y))
        pick=rng.random()
        name=names[0] if pick<.52 else names[1] if pick<.88 else names[2]
        coherent_heading=25+22*math.sin(x*.014+y*.012)
        yaw=coherent_heading+rng.uniform(-32,32)
        size=rng.uniform(.76,1.18)
        # Shorter low fans at the front keep a clear pool silhouette.
        height=size*(.82 if y>205 else 1)
        transform=unreal.Transform(
            location=unreal.Vector(x,y,-13),
            rotation=unreal.Rotator(0,yaw,0),
            scale=unreal.Vector(size,size,height))
        result[name].append(transform)
    assert len(points)==count,(len(points),count)
    return result


def verify(meshes, transforms):
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    counts={name:0 for name in meshes}
    foliage_actors=[]
    for actor in actors:
        if isinstance(actor,unreal.InstancedFoliageActor):
            foliage_actors.append(actor.get_path_name())
            for component in actor.get_components_by_class(unreal.FoliageInstancedStaticMeshComponent):
                mesh=component.get_editor_property('static_mesh')
                if mesh and mesh.get_name() in counts:
                    counts[mesh.get_name()]+=component.get_instance_count()
    expected={name:len(items) for name,items in transforms.items()}
    assert counts==expected,(counts,expected)
    return {'foliage_actors':foliage_actors,'instance_counts':counts,
            'total_instances':sum(counts.values()),'actual_foliage':True}


def main():
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world=editor.get_editor_world()
    assert world and world.get_path_name().startswith(MAP),world.get_path_name() if world else None
    material=make_material()
    manifest,meshes=import_meshes(material)
    transforms=placements(list(meshes))
    types={name:make_type(mesh) for name,mesh in meshes.items()}
    with unreal.ScopedEditorTransaction('Plant waterfall meadow foliage'):
        for name,foliage in types.items():
            unreal.InstancedFoliageActor.remove_all_instances(world,foliage)
            unreal.InstancedFoliageActor.add_instances(world,foliage,transforms[name])
    report=verify(meshes,transforms)
    report['triangles_if_all_visible']=sum(entry['triangles']*len(transforms[entry['name']]) for entry in manifest['assets'])
    assert report['triangles_if_all_visible']<100000,report
    report['foliage_types']=[x.get_path_name() for x in types.values()]
    report['material']=material.get_path_name()
    report['wind_strength_cm']=3.8
    report['root_wind_weight']=0
    report['cull_distance_cm']=[1300,2200]
    report['passed']=True
    assert unreal.EditorLevelLibrary.save_current_level()
    (ROOT/'Saved'/'waterfall_foliage_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('ASTRA_WATERFALL_FOLIAGE_OK '+json.dumps(report))
    return report


if __name__=='__main__':
    main()
