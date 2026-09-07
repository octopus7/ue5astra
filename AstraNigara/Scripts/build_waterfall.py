"""Import the original Blender kit and author animated anime water in UE 5.7."""
import json, runpy
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
DEST='/Game/VFX/Waterfall'
MAP='/Game/Maps/L_AnimeWaterfall'
EAL=unreal.EditorAssetLibrary
ML=unreal.MaterialEditingLibrary
AT=unreal.AssetToolsHelpers.get_asset_tools()
helpers=runpy.run_path(str(ROOT/'Scripts'/'build_explosion_variants.py'))
set_struct=helpers['set_struct']
distribution=helpers['distribution']
def emitter_objects(system):
    # Handle names can be edited normally in Niagara without breaking rebuilding.
    aliases={'Ripples':'Debris','Splash':'Flame','Mist':'Smoke','Upwash':'Smoke','Foam':'Distortion'}
    result={}
    for obj in unreal.ObjectIterator(unreal.NiagaraEmitterBase):
        if obj.get_outer()==system and obj.get_class().get_name()=='NiagaraStatelessEmitter':
            name=obj.get_name().rsplit('_',1)[0]
            result[aliases.get(name,name)]=obj
    assert set(result)=={'Debris','Flame','Smoke','Distortion'},result
    return result


def node(m,cls): return ML.create_material_expression(m,cls)


def scalar(m,v):
    n=node(m,unreal.MaterialExpressionConstant);n.set_editor_property('r',v);return n


def color(m,rgb):
    n=node(m,unreal.MaterialExpressionConstant3Vector)
    n.set_editor_property('constant',unreal.LinearColor(*rgb,1));return n


def custom(m,code,inputs,kind=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    n=node(m,unreal.MaterialExpressionCustom)
    n.set_editor_property('code',code);n.set_editor_property('output_type',kind)
    pins=[]
    for name in inputs:
        p=unreal.CustomInput();p.set_editor_property('input_name',name);pins.append(p)
    n.set_editor_property('inputs',pins)
    for name,value in inputs.items():
        source,output=value if isinstance(value,tuple) else (value,'')
        assert ML.connect_material_expressions(source,output,n,name)
    return n


def connect(m,n,prop):
    assert ML.connect_material_property(n,'',getattr(unreal.MaterialProperty,'MP_'+prop))


def material(name,blend=unreal.BlendMode.BLEND_OPAQUE,unlit=True):
    path=DEST+'/Materials/'+name
    m=EAL.load_asset(path) if EAL.does_asset_exist(path) else AT.create_asset(name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    ML.delete_all_material_expressions(m)
    m.set_editor_property('blend_mode',blend)
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT if unlit else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    m.set_editor_property('two_sided',True)
    return m


def finish(m):
    ML.recompile_material(m);assert EAL.save_loaded_asset(m);return m


def build_materials():
    result={}
    palette={'WF_Rock':(.24,.31,.34),'WF_Moss':(.22,.39,.15),'WF_Earth':(.12,.19,.15),
             'WF_Leaf':(.095,.28,.13),'WF_LeafLight':(.31,.49,.17),'WF_Flower':(.84,.82,.49)}
    for key,rgb in palette.items():
        m=material('M_'+key)
        p=node(m,unreal.MaterialExpressionWorldPosition)
        n=node(m,unreal.MaterialExpressionVertexNormalWS)
        base=color(m,rgb)
        shading=custom(m,'''float light=dot(normalize(N),normalize(float3(-0.4,-0.6,0.8)))*0.5+0.5;
float bands=lerp(0.58,1.13,smoothstep(0.30,0.75,light));
float mottling=0.97+0.055*sin(P.x*0.041+sin(P.y*0.032)*2)*sin(P.z*0.034+P.y*0.011);
float3 shade=lerp(float3(0.80,0.91,1.03),float3(1.06,1.035,0.90),light);
return Base*bands*mottling*shade;''',{'N':n,'P':p,'Base':base})
        connect(m,shading,'EMISSIVE_COLOR');result[key]=finish(m)

    m=material('M_WF_Waterfall_UV')
    uv=node(m,unreal.MaterialExpressionTextureCoordinate);t=node(m,unreal.MaterialExpressionTime)
    speed=node(m,unreal.MaterialExpressionScalarParameter)
    speed.set_editor_property('parameter_name','FlowSpeed');speed.set_editor_property('default_value',.85)
    # UE's FBX importer flips V for DirectX. Restore Blender's downstream V.
    flow=custom(m,'''float v=(1-UV.y)-T*Speed;
float u=UV.x+0.009*sin(v*15+UV.x*16);
float lane=sin(u*83+sin(v*8)*0.65)+0.35*sin(u*151-v*3);
float streak=smoothstep(0.68,1.02,lane);
float breaks=smoothstep(-0.45,0.30,sin(v*22+u*13));
float fine=pow(saturate(sin(u*161+sin(v*10))),18)*0.30;
float edge=pow(saturate(abs(UV.x-.5)*2),12)*.65;
float white=saturate(streak*breaks*.74+fine+edge);
float shade=.5+.5*sin(u*16+v*2);
float3 blue=lerp(float3(0.035,0.39,0.49),float3(0.17,0.70,0.73),shade);
float churn=(1-smoothstep(.015,.14,UV.y))*(.32+.20*sin(u*35+v*9));
return lerp(blue,float3(0.78,0.98,0.93),saturate(white+churn));''',{'UV':uv,'T':t,'Speed':speed})
    connect(m,flow,'EMISSIVE_COLOR');result['WF_Water']=finish(m)

    m=material('M_WF_ImpactFoam',unreal.BlendMode.BLEND_TRANSLUCENT)
    uv=node(m,unreal.MaterialExpressionTextureCoordinate);t=node(m,unreal.MaterialExpressionTime)
    # Advected cells break into patches as the falling water spreads downstream.
    foamfield='''float2 p=float2(UV.x,1-UV.y);
float2 q=p*float2(11,5)-float2(0,T*.72);
q+=float2(sin(q.y*1.7+T*.3),sin(q.x*1.3-T*.24))*.32;
float2 cell=floor(q),f=frac(q);float d=9;
for(int j=-1;j<=1;j++){for(int i=-1;i<=1;i++){
float2 g=float2(i,j);float2 c=cell+g;
float2 h=frac(sin(float2(dot(c,float2(127.1,311.7)),dot(c,float2(269.5,183.3))))*43758.5453);
d=min(d,length(g+h-f));}}
float wave=.055*sin(p.x*29+T*.83)+.035*sin(p.x*53-T*.61);
float side=1-smoothstep(.72,.98,abs(p.x*2-1)+.055*sin(p.y*21+T));
float back=smoothstep(0,.14,p.y);
float front=1-smoothstep(.40+wave,.94+wave,p.y);
float core=1-smoothstep(.25,.59,p.y);
float cells=smoothstep(.22,.39,d);
float patch=smoothstep(.10,.60,sin(p.x*21+sin(p.y*16-T)*1.4)+sin(p.y*23-T*1.25));
float density=lerp(cells*.63+patch*.25,.76+cells*.24,core);
'''
    connect(m,custom(m,foamfield+'return lerp(float3(.24,.67,.64),float3(.78,.97,.90),saturate(density));',{'UV':uv,'T':t}),'EMISSIVE_COLOR')
    connect(m,custom(m,foamfield+'return saturate(side*back*front*density*.88);',{'UV':uv,'T':t},unreal.CustomMaterialOutputType.CMOT_FLOAT1),'OPACITY')
    result['WF_ImpactFoam']=finish(m)

    m=material('M_WF_Pool')
    uv=node(m,unreal.MaterialExpressionTextureCoordinate);t=node(m,unreal.MaterialExpressionTime)
    pool=custom(m,'''float2 p=(UV-.5)*2;float r=length(p);
float2 q=UV*17+float2(T*.12,-T*.08);
float a=sin(q.x*2+sin(q.y*1.5+T*.18));float b=sin(q.y*2.1+sin(q.x*1.9-T*.12));
float caustic=pow(saturate(1-abs(a+b)*2.8),7);
float glint=pow(saturate(sin(UV.x*130+sin(UV.y*45+T)*2)),35)*pow(saturate(sin(UV.y*85-T*.7)),13);
float shallow=smoothstep(.48,1,r);
float3 c=lerp(float3(.028,.28,.32),float3(.14,.58,.52),shallow);
float bank=smoothstep(.92,.97,r)*(1-smoothstep(.985,1.035,r));
return c+caustic*.075+glint*.14+bank*float3(.24,.35,.26);''',{'UV':uv,'T':t})
    connect(m,pool,'EMISSIVE_COLOR');result['WF_Pool']=finish(m)

    for name,code,opacity in [
        ('M_WF_Ripple','return float3(.50,.84,.78);','''float a=UV.x*6.2831853;float phase=C.r*6.2831853;
float center=.5+.12*sin(a*3+phase+T*.24);
float width=.16+.07*sin(a*4+phase*1.7);
float edge=1-smoothstep(width*.45,width,abs(UV.y-center));
float broken=sin(a*3+phase)+.48*sin(a*5-phase*1.3)+.20*sin(a*9+phase*2);
float arcs=smoothstep(-.12,.34,broken);
return edge*arcs*A*.44;'''),
        ('M_WF_Splash','return float3(.75,.97,.95);','float2 p=(UV-.5)*2;p.x*=1.15+.35*p.y;return smoothstep(1,.40,length(p))*A*.90;'),
        ('M_WF_Mist','return float3(.50,.79,.76);','float2 p=(UV-.5)*2;return pow(saturate(1-length(p)),2)*A*.12;'),
        ('M_WF_Foam','return float3(.68,.93,.84);','''float2 p=(UV-.5)*2;float a=atan2(p.y,p.x);float phase=C.r*6.2831853;
float e=.67+.13*sin(a*3+phase+T*.45)+.08*sin(a*5-phase);
float shape=1-smoothstep(e-.19,e,length(p));
float holes=smoothstep(-.5,.25,sin(p.x*9+phase+sin(p.y*7-T*.6))+.5*sin(p.y*11+phase));
return shape*lerp(.23,.70,holes)*A;''')]:
        m=material(name,unreal.BlendMode.BLEND_TRANSLUCENT)
        m.set_editor_property('used_with_niagara_mesh_particles',name=='M_WF_Ripple')
        m.set_editor_property('used_with_niagara_sprites',name!='M_WF_Ripple')
        uv=node(m,unreal.MaterialExpressionTextureCoordinate);p=node(m,unreal.MaterialExpressionParticleColor)
        t=node(m,unreal.MaterialExpressionTime)
        position=node(m,unreal.MaterialExpressionWorldPosition)
        connect(m,custom(m,code,{}),'EMISSIVE_COLOR')
        connect(m,custom(m,opacity,{'UV':uv,'A':(p,'A'),'C':(p,'RGB'),'T':t,'P':position},unreal.CustomMaterialOutputType.CMOT_FLOAT1),'OPACITY')
        result[name.removeprefix('M_')]=finish(m)
    result['WF_SurfaceFoam']=result['WF_Foam']
    result['WF_Foam']=result['WF_Ripple']
    result.update(build_impact_materials())
    return result


def build_impact_materials():
    """Torn vertical water tongues and dense, wet upwash along the impact rim."""
    result={}
    specs=[('Splash',(.75,.97,.94),'''float2 p=(UV-.5)*2;float phase=C.r*6.2831853;
p.x+=.12*sin(p.y*7+phase)+.065*sin(p.y*16-phase);
float edge=.78+.11*sin(p.y*13+phase)+.06*sin(p.y*25-phase*2);
float body=1-smoothstep(edge-.22,edge,length(p*float2(1.2+.18*p.y,1)));
float cuts=smoothstep(-.65,-.10,sin(p.y*12+phase)+.65*sin(p.x*13+p.y*7-phase));
return body*lerp(.55,1,cuts)*A*.97;'''),
           ('Upwash',(.64,.90,.84),'''float2 p=(UV-.5)*2;float phase=C.r*6.2831853;
float a=atan2(p.y,p.x);float radius=length(p*float2(1.05,.92));
float edge=.74+.13*sin(a*5+phase)+.08*sin(a*9-phase*1.7);
float outline=1-smoothstep(edge-.21,edge,radius);
float grain=sin(p.x*10+sin(p.y*8+phase)*1.4)+.55*sin(p.y*15+p.x*6-phase+T*.7);
float wet=smoothstep(-.6,.45,grain);
return outline*lerp(.66,1,wet)*A*.92;''')]
    for name,rgb,code in specs:
        m=material('M_WF_'+name,unreal.BlendMode.BLEND_TRANSLUCENT)
        m.set_editor_property('used_with_niagara_sprites',True)
        uv=node(m,unreal.MaterialExpressionTextureCoordinate)
        p=node(m,unreal.MaterialExpressionParticleColor);t=node(m,unreal.MaterialExpressionTime)
        if name=='Upwash':
            shade='''float phase=C.r*6.2831853;
float shade=saturate(.20+.58*C.g+.22*sin(UV.y*11+UV.x*8+phase));
return lerp(float3(.20,.52,.55),float3(.72,.94,.87),shade);'''
        else:
            shade='return lerp(float3(.40,.73,.74),float3(.78,.97,.94),.35+.65*C.g);'
        connect(m,custom(m,shade,{'UV':uv,'C':(p,'RGB')}),'EMISSIVE_COLOR')
        connect(m,custom(m,code,{'UV':uv,'C':(p,'RGB'),'A':(p,'A'),'T':t},unreal.CustomMaterialOutputType.CMOT_FLOAT1),'OPACITY')
        result['WF_'+name]=finish(m)
    return result


def import_meshes(materials):
    manifest=json.loads((ROOT/'ArtSource'/'Waterfall'/'waterfall_manifest.json').read_text())
    tasks=[]
    for entry in manifest['assets']:
        task=unreal.AssetImportTask();task.filename=str(ROOT/'ArtSource'/'Waterfall'/entry['fbx'])
        task.destination_path=DEST+'/Meshes';task.destination_name=entry['name']
        task.automated=True;task.save=False;task.replace_existing=True;task.factory=unreal.FbxFactory()
        opt=unreal.FbxImportUI();opt.import_mesh=True;opt.import_as_skeletal=False
        opt.import_materials=False;opt.import_textures=False;opt.import_animations=False
        opt.automated_import_should_detect_type=False;opt.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
        s=opt.static_mesh_import_data;s.combine_meshes=True;s.build_nanite=False
        s.generate_lightmap_u_vs=False;s.auto_generate_collision=False;s.convert_scene=True;s.convert_scene_unit=True
        s.import_uniform_scale=1.;s.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        task.options=opt;tasks.append(task)
    AT.import_asset_tasks(tasks)
    meshes={};report=[]
    sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for entry in manifest['assets']:
        mesh=EAL.load_asset(DEST+'/Meshes/'+entry['name']);assert isinstance(mesh,unreal.StaticMesh),entry
        for index,slot in enumerate(mesh.get_editor_property('static_materials')):
            slot_name=str(slot.get_editor_property('imported_material_slot_name'))
            key=slot_name if slot_name in materials else entry['materials'][min(index,len(entry['materials'])-1)]
            mesh.set_material(index,materials[key])
        assert sub.get_num_uv_channels(mesh,0)>=1
        bounds=mesh.get_bounding_box()
        actual=sorted([getattr(bounds.max,a)-getattr(bounds.min,a) for a in 'xyz'])
        assert all(abs(a-b)<.2 for a,b in zip(actual,sorted(entry['dimensions_cm']))),(entry['name'],actual)
        assert EAL.save_loaded_asset(mesh)
        meshes[entry['name']]=mesh
        report.append({'name':entry['name'],'asset':mesh.get_path_name(),'source_triangles':entry['triangles'],'uv_channels':sub.get_num_uv_channels(mesh,0)})
    return meshes,report


def vector_curve(obj,prop,keys,dimensions=3):
    curve='(Keys=('+','.join(f'(InterpMode=RCIM_Linear,Time={t},Value={v})' for t,v in keys)+'))'
    values=','.join('('+','.join(f'{axis}={v}' for axis in 'XYZ'[:dimensions])+')' for t,v in keys)
    set_struct(obj,prop,f'(Mode=UniformCurve,LookupValueMode=0,ChannelCurves=({curve}),Values=({values}),ValuesTimeRange=(X=0,Y=1))')


def alpha_curve(obj,keys):
    identity='(Keys=((InterpMode=RCIM_Linear,Time=0,Value=1),(InterpMode=RCIM_Linear,Time=1,Value=1)))'
    alpha='(Keys=('+','.join(f'(InterpMode=RCIM_Linear,Time={t},Value={a})' for t,a in keys)+'))'
    set_struct(obj,'ScaleDistribution',f'(Mode=NonUniformCurve,LookupValueMode=0,ChannelCurves=({identity},{identity},{identity},{alpha}))')


def position_range(obj,low,high):
    values=','.join('('+','.join(f'{a}={v}' for a,v in zip('XYZ',point))+')' for point in (low,high))
    channels=','.join(map(str,low+high))
    set_struct(obj,'InitialPositionDistribution',f'(Mode=NonUniformRange,LookupValueMode=255,Values=({values}),ChannelConstantsAndRanges=({channels}),ChannelCurves=())')


def impact_ring(shape,init):
    # Native enum is not Python-exported; the public UObject reflection API
    # invokes the engine setter, which explicitly supports FEnumProperty.
    shape.modify()
    unreal.get_default_object(unreal.SystemLibrary).call_method('SetBytePropertyByName',args=(shape,'ShapePrimitive',3))
    distribution(shape,'RingRadius',60)
    distribution(shape,'DiscCoverage',.12)
    distribution(shape,'RingUDistribution',0)  # 0 = the complete circumference.
    distribution(shape,'ShapeScale',(1,.17,1),dimensions=3,uniform=False)
    position_range(init,(0,5,0),(0,5,0))


def build_niagara(meshes,materials):
    path=DEST+'/NS_AnimeWaterfall'
    system=EAL.load_asset(path) if EAL.does_asset_exist(path) else EAL.duplicate_asset(helpers['SOURCE'],path)
    assert system
    specs=[('Debris',3.2,(1.15,2.10),1.4,2.0,0,((-4,7,0),(4,15,0))),
           ('Flame',180,(.58,.94),4,9,0,((-8,-4,240),(8,8,330))),
           ('Smoke',96,(.48,.80),14,24,0,((-4,-2,135),(4,6,205))),
           ('Distortion',30,(.85,1.55),18,32,0,((-8,14,0),(8,29,0)))]
    footprints=[((-40,8,-1.7),(40,24,-1.2)),((-65,-3,-1),(65,13,4)),
                ((-61,2,1),(61,20,6)),((-69,5,-1.4),(69,26,-.8))]
    for index,(name,rate,life,lo,hi,radius,vel) in enumerate(specs):
        emitter=emitter_objects(system)[name]
        mods={m.get_class().get_name().removeprefix('NiagaraStatelessModule_'):m for m in emitter.get_editor_property('Modules')}
        required=[['ScaleMeshSize','InitialMeshOrientation'],['GravityForce'],['GravityForce'],['SpriteFacingAndAlignment']][index]
        for key in required:
            if key not in mods:
                mods[key]=unreal.new_object(unreal.load_class(None,'/Script/Niagara.NiagaraStatelessModule_'+key),outer=emitter)
        if index==0:
            # The mode enum is not Python-exported. A fresh native module starts
            # in None mode, so Rotation below applies Z yaw without random tilt.
            mods['InitialMeshOrientation']=unreal.new_object(unreal.load_class(None,'/Script/Niagara.NiagaraStatelessModule_InitialMeshOrientation'),outer=emitter)
        emitter.set_editor_property('Modules',list(mods.values()))
        active={'InitializeParticle','SolveVelocitiesAndForces','ScaleColor'}
        active.add('AddVelocity')
        active.update({'ScaleMeshSize','InitialMeshOrientation'} if index==0 else {'ScaleSpriteSize'})
        if index in (1,2): active.update({'GravityForce','ShapeLocation'})
        if index==3: active.add('SpriteFacingAndAlignment')
        for key,m in mods.items(): m.set_editor_property('bModuleEnabled',key in active)
        init=mods['InitializeParticle']
        distribution(init,'LifetimeDistribution',*life)
        distribution(init,'MeshScaleDistribution' if index==0 else 'SpriteSizeDistribution',lo,hi,dimensions=3 if index==0 else 2)
        # RGB carries a per-particle stable shader phase; emission has its own palette.
        set_struct(init,'ColorDistribution','(Mode=NonUniformRange,LookupValueMode=255,Values=((R=0,G=0,B=0,A=1),(R=1,G=1,B=1,A=1)),ChannelConstantsAndRanges=(0,0,0,1,1,1,1,1),ChannelCurves=())')
        position_range(init,*footprints[index])
        distribution(mods['AddVelocity'],'LinearVelocityDistribution',*vel,dimensions=3,uniform=False)
        distribution(mods['ShapeLocation'],'SphereRadius',radius)
        distribution(mods['ShapeLocation'],'ShapeScale',(1,1,0),dimensions=3,uniform=False)
        if index in (1,2): impact_ring(mods['ShapeLocation'],init)
        alpha_curve(mods['ScaleColor'],[(0,0),(.11,.9),(.45,.7),(1,0)])
        if index==0:
            distribution(init,'MeshScaleDistribution',(1.4,1.0,1),(2.0,1.55,1),dimensions=3,uniform=False)
            orientation=mods['InitialMeshOrientation']
            distribution(orientation,'Rotation',(0,0,0),(0,0,360),dimensions=3,uniform=False)
            vector_curve(mods['ScaleMeshSize'],'ScaleDistribution',[(0,.75),(.25,2.2),(.6,3.6),(1,4.65)])
        else:
            vector_curve(mods['ScaleSpriteSize'],'ScaleDistribution',[(0,.55),(.25,1),(1,1.8 if index in (2,3) else .4)],2)
        if index==1:
            distribution(init,'SpriteSizeDistribution',(4,14),(9,28),dimensions=2,uniform=False)
            distribution(mods['GravityForce'],'GravityDistribution',(0,0,-640),dimensions=3,uniform=False)
            vector_curve(mods['ScaleSpriteSize'],'ScaleDistribution',[(0,.35),(.12,1),(.62,.8),(1,.15)],2)
            alpha_curve(mods['ScaleColor'],[(0,0),(.045,1),(.50,.95),(1,0)])
        if index==2:
            distribution(init,'SpriteSizeDistribution',(14,24),(24,42),dimensions=2,uniform=False)
            distribution(mods['GravityForce'],'GravityDistribution',(0,0,-470),dimensions=3,uniform=False)
            vector_curve(mods['ScaleSpriteSize'],'ScaleDistribution',[(0,.55),(.14,1),(.70,1.15),(1,.4)],2)
            alpha_curve(mods['ScaleColor'],[(0,0),(.06,.95),(.62,.95),(1,0)])
        if index==3: distribution(init,'SpriteRotationDistribution',0,360)
        if index==2: distribution(mods['Drag'],'DragDistribution',.8)
        renderer=emitter.get_editor_property('RendererProperties')[0]
        if index==0:
            slots=list(renderer.get_editor_property('Meshes'));slot=slots[0].copy()
            slot.set_editor_property('Mesh',meshes['SM_WF_RippleRing'])
            slot.set_editor_property('Scale',unreal.Vector(1,1,1))
            renderer.set_editor_property('Meshes',[slot])
            override=renderer.get_editor_property('OverrideMaterials')[0].copy()
            override.set_editor_property('ExplicitMat',materials['WF_Ripple'])
            renderer.set_editor_property('OverrideMaterials',[override]);renderer.set_editor_property('bOverrideMaterials',True)
        else:
            renderer.set_editor_property('Material',materials[['','WF_Splash','WF_Upwash','WF_SurfaceFoam'][index]])
            if index==3:
                facing=mods['SpriteFacingAndAlignment']
                facing.set_editor_property('bSpriteFacingEnabled',True)
                distribution(facing,'SpriteFacing',(0,0,1),dimensions=3,uniform=False)
                renderer.set_editor_property('FacingMode',unreal.NiagaraSpriteFacingMode.CUSTOM_FACING_VECTOR)
        spawn=emitter.get_editor_property('SpawnInfos')[0].copy()
        assert spawn.import_text(f'(Type=Rate,SpawnTime=0,Rate=(Mode=UniformConstant,Min={rate},Max={rate},ChannelConstantsAndRanges=({rate})),bEnabled=True,bLoopCountLimitEnabled=False,bSpawnProbabilityEnabled=False)')
        emitter.set_editor_property('SpawnInfos',[spawn])
        set_struct(emitter,'EmitterState','(LoopBehavior=Infinite,LoopDurationMode=Fixed,LoopDuration=(Mode=UniformConstant,Min=4,Max=4,ChannelConstantsAndRanges=(4)),InactiveResponse=Complete)')
        emitter.set_editor_property('bDeterministic',True);emitter.set_editor_property('RandomSeed',782+index)
        set_struct(emitter,'FixedBounds','(Min=(X=-180,Y=-120,Z=-35),Max=(X=180,Y=180,Z=120),IsValid=True)')
    set_struct(system,'FixedBounds','(Min=(X=-180,Y=-120,Z=-35),Max=(X=180,Y=180,Z=120),IsValid=True)')
    system.set_editor_property('bFixedBounds',True)
    assert EAL.save_loaded_asset(system)
    return system


def build_level(meshes,system):
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert levels.save_current_level()
    assert levels.load_level(MAP) if EAL.does_asset_exist(MAP) else levels.new_level(MAP)
    existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
    def actor(label,cls,pos=unreal.Vector(0,0,0),rot=unreal.Rotator()):
        a=existing.get(label) or actors.spawn_actor_from_class(cls,pos,rot)
        a.set_actor_label(label);a.set_actor_location(pos,False,False);a.set_actor_rotation(rot,False)
        return a
    for suffix in ['WaterCurtain','Pool','UpperStream','Rockwork','Moss','Ground','Foliage','ImpactApron']:
        a=actor('WF_'+suffix,unreal.StaticMeshActor)
        a.static_mesh_component.set_static_mesh(meshes['SM_WF_'+suffix])
        a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        if suffix=='ImpactApron':a.static_mesh_component.set_editor_property('translucency_sort_priority',1)
    def center(name):
        b=meshes['SM_WF_Locator'+name].get_bounding_box()
        return (b.min+b.max)*.5
    impact=center('Impact')
    effect=actor('WF_Impact_Niagara',unreal.NiagaraActor,impact)
    c=effect.get_component_by_class(unreal.NiagaraComponent)
    c.set_asset(system);c.set_auto_activate(True);c.activate(True)
    c.set_editor_property('translucency_sort_priority',2)
    bg=material('M_WF_Background')
    connect(bg,color(bg,(.26,.39,.34)),'EMISSIVE_COLOR');finish(bg)
    a=actor('WF_Background',unreal.StaticMeshActor,unreal.Vector(0,0,-45))
    a.static_mesh_component.set_static_mesh(EAL.load_asset('/Engine/BasicShapes/Plane'))
    a.static_mesh_component.set_material(0,bg);a.set_actor_scale3d(unreal.Vector(200,200,1))
    a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    camera_pos=center('View');look_at=center('LookAt')
    rotation=unreal.MathLibrary.find_look_at_rotation(camera_pos,look_at)
    camera=actor('WF_ShowcaseCamera',unreal.CameraActor,camera_pos,rotation)
    camera.camera_component.set_editor_property('field_of_view',50)
    camera.set_editor_property('auto_activate_for_player',unreal.AutoReceiveInput.PLAYER0)
    pp=actor('WF_Exposure',unreal.PostProcessVolume)
    pp.set_editor_property('unbound',True)
    settings=pp.get_editor_property('settings').copy()
    settings.set_editor_property('override_auto_exposure_min_brightness',True)
    settings.set_editor_property('override_auto_exposure_max_brightness',True)
    settings.set_editor_property('auto_exposure_min_brightness',1)
    settings.set_editor_property('auto_exposure_max_brightness',1)
    settings.set_editor_property('override_auto_exposure_bias',True)
    settings.set_editor_property('auto_exposure_bias',0)
    pp.set_editor_property('settings',settings)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_pos,rotation)
    levels.pilot_level_actor(camera)
    actors.set_selected_level_actors([])
    unreal.AstraNiagaraLibrary.enable_viewport_realtime()
    assert levels.save_current_level()
    return {'map':MAP,'impact_cm':[impact.x,impact.y,impact.z],'camera_cm':[camera_pos.x,camera_pos.y,camera_pos.z]}


def main():
    materials=build_materials()
    meshes,report=import_meshes(materials)
    system=build_niagara(meshes,materials)
    scene=build_level(meshes,system)
    scene.update(meshes=report,niagara=json.loads(unreal.AstraNiagaraLibrary.describe_system(system)))
    (ROOT/'Saved'/'waterfall_build_report.json').write_text(json.dumps(scene,indent=2),encoding='utf-8')
    unreal.log('ANIME_WATERFALL_BUILD_COMPLETE')


if __name__=='__main__':
    main()
