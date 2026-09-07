"""Run in this worktree's full UE editor. Writes only cave assets and cave map."""
import unreal, json, math, traceback
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve();ART=ROOT/'ArtSource'
DATA=json.loads((ART/'Layout/CrystalCave/cave_layout.json').read_text(encoding='utf-8'))
DEST='/Game/Astra/CrystalCave';MAP='/Game/Astra/Maps/L_AstraCrystalCave'
OUT=ART/'Previews/CrystalCave';OUT.mkdir(parents=True,exist_ok=True)
EAL=unreal.EditorAssetLibrary;AT=unreal.AssetToolsHelpers.get_asset_tools();ML=unreal.MaterialEditingLibrary
ES=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);SM=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

def log(s):
    unreal.log('CAVE: '+s)
    with (ROOT/'Saved/CaveImportProgress.txt').open('a',encoding='utf-8') as f:f.write(s+'\n')

def linear(value):
    if isinstance(value,str):
        value=value.lstrip('#');value=[int(value[i:i+2],16)/255 for i in (0,2,4)]
    return [v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in value[:3]]
def expr(m,cls):return ML.create_material_expression(m,cls)
def scalar(m,v):
    e=expr(m,unreal.MaterialExpressionConstant);e.set_editor_property('r',v);return e
def color(m,v):
    e=expr(m,unreal.MaterialExpressionConstant3Vector);e.set_editor_property('constant',unreal.LinearColor(*v,1));return e
def output(node,prop):ML.connect_material_property(node,'',prop)
def custom(m,code,inputs,type=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    e=expr(m,unreal.MaterialExpressionCustom);e.code=code;e.output_type=type
    arr=[]
    for n in inputs:
        ci=unreal.CustomInput();ci.input_name=n;arr.append(ci)
    e.inputs=arr
    for n,v in inputs.items():ML.connect_material_expressions(v,'',e,n)
    return e
def newmat(name):
    p=DEST+'/Materials/'+name
    m=EAL.load_asset(p) if EAL.does_asset_exist(p) else AT.create_asset(name,DEST+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    ML.delete_all_material_expressions(m);return m
def finish(m):ML.recompile_material(m);assert EAL.save_loaded_asset(m);return m

def textures():
    result={}
    for name in ['T_CC_Rock','T_CC_Floor']:
        task=unreal.AssetImportTask();task.filename=str(ART/'Textures/CrystalCave'/f'{name}.png')
        task.destination_path=DEST+'/Textures';task.destination_name=name;task.automated=True;task.save=True;task.replace_existing=True
        AT.import_asset_tasks([task]);t=EAL.load_asset(DEST+'/Textures/'+name);assert t
        t.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_DEFAULT);t.set_editor_property('srgb',True)
        t.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
        EAL.save_loaded_asset(t);result[name]=t
    return result

def materials(texs):
    result={}
    specs=dict(DATA['materials'])
    specs['M_CC_Rock']=dict(base_color='667395',roughness=.88)
    specs['M_CC_RockDark']=dict(base_color='3C4463',roughness=.94)
    for name,props in specs.items():
        m=newmat(name)
        h=props.get('base_color',props.get('base_color_hex',props.get('color_hex',props.get('hex','718097'))))
        c=linear(h);base=color(m,c)
        if name in ['M_CC_Rock','M_CC_RockDark']:
            wp=expr(m,unreal.MaterialExpressionWorldPosition);normal=expr(m,unreal.MaterialExpressionVertexNormalWS)
            uv=custom(m,'float3 n=abs(N);return n.z>.62?P.xy/260:(n.x>n.y?P.yz/260:P.xz/260);',{'P':wp,'N':normal},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
            t=expr(m,unreal.MaterialExpressionTextureSample);t.texture=texs['T_CC_Rock'];ML.connect_material_expressions(uv,'',t,'UVs')
            base=custom(m,'return T*Tint;',{'T':t,'Tint':color(m,[.63,.70,.84] if name=='M_CC_Rock' else [.3,.34,.45])})
        output(base,unreal.MaterialProperty.MP_BASE_COLOR)
        output(scalar(m,props.get('roughness',.32)),unreal.MaterialProperty.MP_ROUGHNESS)
        output(scalar(m,props.get('metallic',.0)),unreal.MaterialProperty.MP_METALLIC)
        output(scalar(m,.25),unreal.MaterialProperty.MP_SPECULAR)
        em=props.get('emissive_strength',props.get('emission_strength',0))
        if em:
            # Emission supplies a visible luminous mineral; point lights illuminate surroundings.
            ec=linear(props.get('emissive_color',h))
            output(color(m,[v*min(float(em),3.5) for v in ec]),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        result[name]=finish(m)
    m=newmat('M_CC_Landscape');wp=expr(m,unreal.MaterialExpressionWorldPosition)
    uv=custom(m,'return P.xy/450;',{'P':wp},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    t=expr(m,unreal.MaterialExpressionTextureSample);t.texture=texs['T_CC_Floor'];ML.connect_material_expressions(uv,'',t,'UVs')
    import sys
    sys.path.insert(0,str(ROOT/'Scripts'))
    import cave_layout as D
    code='float2 p=P.xy*.01;float d=100;float2 a,b,ab;float t;'
    for points in list(D.BRANCHES.values())+[D.FULL]:
        for a,b in zip(points,points[1:]):
            code+=f'a=float2({a[0]},{a[1]});b=float2({b[0]},{b[1]});ab=b-a;t=saturate(dot(p-a,ab)/dot(ab,ab));d=min(d,length(p-a-t*ab));'
    code+='float path=1-smoothstep(1.0,2.1,d+.13*sin(p.x*3+p.y*2));float edge=smoothstep(10.3,14.5,abs(p.x));edge=max(edge,smoothstep(23,25,abs(p.y)));float3 ground=T*lerp(float3(.43,.48,.67),float3(.74,.83,.95),path);return lerp(ground,float3(.002,.003,.006),edge);'
    output(custom(m,code,{'P':wp,'T':t}),unreal.MaterialProperty.MP_BASE_COLOR)
    output(scalar(m,.86),unreal.MaterialProperty.MP_ROUGHNESS);output(scalar(m,.18),unreal.MaterialProperty.MP_SPECULAR)
    result['M_CC_Landscape']=finish(m);return result

def meshes(mats):
    result={};bounds={}
    for name,meta in DATA['assets'].items():
        task=unreal.AssetImportTask();task.filename=str(ROOT/meta['file']);task.destination_path=DEST+'/Meshes';task.destination_name=name
        task.automated=True;task.save=True;task.replace_existing=True;task.factory=unreal.FbxFactory()
        opt=unreal.FbxImportUI();opt.import_mesh=True;opt.import_as_skeletal=False;opt.import_materials=False;opt.import_textures=False;opt.import_animations=False
        opt.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
        opt.static_mesh_import_data.combine_meshes=True;opt.static_mesh_import_data.generate_lightmap_u_vs=False;opt.static_mesh_import_data.auto_generate_collision=False
        opt.static_mesh_import_data.convert_scene=True;opt.static_mesh_import_data.convert_scene_unit=True
        opt.static_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        task.options=opt;AT.import_asset_tasks([task]);a=EAL.load_asset(DEST+'/Meshes/'+name);assert a,name
        for i,s in enumerate(a.get_editor_property('static_materials')):
            key=str(s.material_slot_name)
            if key not in mats:key=meta['materials'][min(i,len(meta['materials'])-1)]
            assert key in mats,(name,key,list(mats))
            a.set_material(i,mats[key])
        a.get_editor_property('body_setup').set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        EAL.save_loaded_asset(a);result[name]=a
        b=a.get_bounding_box();bounds[name]=dict(min=[b.min.x,b.min.y,b.min.z],max=[b.max.x,b.max.y,b.max.z])
        log('Imported '+name)
    return result,bounds

def spawn(cls,pos,rot=None,name=None,folder=None):
    a=ES.spawn_actor_from_class(cls,unreal.Vector(*pos),rot or unreal.Rotator())
    if name:a.set_actor_label(name)
    if folder:a.set_folder_path(folder)
    return a

def build(mats,meshs):
    assert unreal.EditorLevelLibrary.new_level(MAP)
    world=unreal.EditorLevelLibrary.get_editor_world()
    land=unreal.AstraCrystalCaveLibrary.create_cave_terrain(mats['M_CC_Landscape']);assert land
    land.set_folder_path('CrystalCave/Terrain')
    for o in DATA['objects']:
        r=o['ue_rotation_deg'];a=spawn(unreal.StaticMeshActor,o['ue_location_cm'],unreal.Rotator(pitch=r['pitch'],yaw=r['yaw'],roll=r['roll']),o['name'],'CrystalCave/'+o['group'])
        c=a.static_mesh_component;c.set_static_mesh(meshs[o['asset']]);a.set_actor_scale3d(unreal.Vector(*o['scale']))
        a.tags=[unreal.Name(t) for t in o.get('tags',[])]
        c.set_collision_profile_name('BlockAll' if o['collision']=='complex' else 'NoCollision')
        c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS if o['collision']=='complex' else unreal.CollisionEnabled.NO_COLLISION)
    for l in DATA['lights']:
        a=spawn(unreal.PointLight,l['ue_location_cm'],name=l['name'],folder='CrystalCave/Lighting/CrystalLight')
        a.tags=[unreal.Name('CaveCrystalLight')];c=a.light_component;c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_editor_property('intensity_units',unreal.LightUnits.LUMENS);c.set_intensity(l['intensity'])
        c.set_light_color(unreal.LinearColor(*l['color'],1));c.set_editor_property('attenuation_radius',l['radius_cm'])
        c.set_editor_property('source_radius',l['source_radius_cm']);c.set_editor_property('soft_source_radius',l['source_radius_cm'])
        c.set_cast_shadows(True)
    # Dim diffuse fill maintains silhouettes between localized crystal light pools.
    sun=spawn(unreal.DirectionalLight,[0,0,3500],unreal.Rotator(pitch=-65,yaw=-35),'CC_DimSoftFill','CrystalCave/Lighting')
    c=sun.light_component;c.set_mobility(unreal.ComponentMobility.MOVABLE);c.set_intensity(.32)
    c.set_light_color(unreal.LinearColor(.36,.44,.7,1));c.set_editor_property('light_source_angle',50.0)
    c.set_editor_property('specular_scale',0.0)
    fog=spawn(unreal.ExponentialHeightFog,[0,0,-100],name='CC_GroundHaze',folder='CrystalCave/Lighting')
    c=fog.component;c.set_fog_density(.003);c.set_fog_height_falloff(.5);c.set_start_distance(1600);c.set_fog_max_opacity(.045)
    c.set_fog_inscattering_color(unreal.LinearColor(.025,.032,.08,1))
    pp=spawn(unreal.PostProcessVolume,[0,0,0],name='CC_ExposureAndGrade',folder='CrystalCave/Lighting');pp.set_editor_property('unbound',True)
    s=pp.get_editor_property('settings')
    vals=dict(override_auto_exposure_method=True,auto_exposure_method=unreal.AutoExposureMethod.AEM_MANUAL,
        override_auto_exposure_apply_physical_camera_exposure=True,auto_exposure_apply_physical_camera_exposure=False,
        override_auto_exposure_bias=True,auto_exposure_bias=0.0,override_motion_blur_amount=True,motion_blur_amount=0.,
        override_bloom_intensity=True,bloom_intensity=.28,override_vignette_intensity=True,vignette_intensity=.15)
    for n,v in vals.items():s.set_editor_property(n,v)
    pp.set_editor_property('settings',s)
    spawn(unreal.PlayerStart,DATA['spawn_cm'],unreal.Rotator(yaw=90),'CC_PlayerStart','CrystalCave/Gameplay')
    world.get_world_settings().set_editor_property('default_game_mode',unreal.AstraCrystalCaveGameMode)
    for review in DATA['review_cameras']:
        look=review['look'];arm=7500 if review['name']=='CaveOverview' else 4000
        loc=[look[0]-arm*math.cos(math.radians(58)),look[1],look[2]+arm*math.sin(math.radians(58))]
        cam=spawn(unreal.CameraActor,loc,unreal.Rotator(pitch=-58,yaw=0),name='Camera_'+review['name'],folder='CrystalCave/ReviewCameras')
        cc=cam.camera_component;cc.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC);cc.set_editor_property('ortho_width',review['width']);cc.set_editor_property('constrain_aspect_ratio',False)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(unreal.Vector(-4000,0,6400),unreal.Rotator(pitch=-58,yaw=0))
    assert unreal.EditorLevelLibrary.save_current_level()
    assert EAL.save_directory(DEST,only_if_is_dirty=True,recursive=True)
    return dict(actors=len(ES.get_all_level_actors()),point_lights=len(DATA['lights']),landscape_class=land.get_class().get_name(),landscape_scale=[land.get_actor_scale3d().x,land.get_actor_scale3d().y,land.get_actor_scale3d().z])

def main():
    try:
        unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
        log('Starting isolated cave import')
        texs=textures();mats=materials(texs);ms,bounds=meshes(mats);result=build(mats,ms)
        result.update(status='success',map=MAP,mesh_bounds_cm=bounds,mesh_count=len(ms),material_count=len(mats),source_layout='ArtSource/Layout/CrystalCave/cave_layout.json')
        (OUT/'UE_CaveImport.json').write_text(json.dumps(result,indent=2),encoding='utf-8');log('CAVE BUILD SUCCESS')
    except Exception:
        error=traceback.format_exc();log(error);(OUT/'UE_CaveImport.json').write_text(json.dumps(dict(status='failed',error=error),indent=2),encoding='utf-8');raise

if __name__=='__main__':main()
