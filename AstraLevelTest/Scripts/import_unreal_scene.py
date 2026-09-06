"""Run inside the UE 5.7 editor; builds the map from Blender's exported layout."""
import unreal, json, math, traceback
from pathlib import Path
ROOT=Path(unreal.Paths.project_dir()).resolve()
ART=ROOT/'ArtSource'
DATA=json.loads((ART/'Layout'/'woodland_layout.json').read_text(encoding='utf-8'))
EAL=unreal.EditorAssetLibrary
AT=unreal.AssetToolsHelpers.get_asset_tools()
ML=unreal.MaterialEditingLibrary
ES=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
SM=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
OUT=ROOT/'Saved'/'AstraBuild';OUT.mkdir(parents=True,exist_ok=True)

def report(message):
    unreal.log('ASTRA: '+message)
    with open(OUT/'build_progress.txt','a',encoding='utf-8') as f:f.write(message+'\n')
def linear(h):
    def v(c):return c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
    return tuple(v(int(h[i:i+2],16)/255) for i in (0,2,4))
def expression(mat,cls,x=0,y=0):return ML.create_material_expression(mat,cls,x,y)
def const(mat,value,x=0,y=0):
    e=expression(mat,unreal.MaterialExpressionConstant,x,y);e.set_editor_property('r',value);return e
def color(mat,rgb):
    e=expression(mat,unreal.MaterialExpressionConstant3Vector);e.set_editor_property('constant',unreal.LinearColor(*rgb,1));return e
def connect(e,matprop):ML.connect_material_property(e,'',matprop)
def custom(mat,code,inputs,output=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    e=expression(mat,unreal.MaterialExpressionCustom,0,0)
    e.set_editor_property('code',code);e.set_editor_property('output_type',output)
    arr=[]
    for name in inputs:
        ci=unreal.CustomInput();ci.set_editor_property('input_name',name);arr.append(ci)
    e.set_editor_property('inputs',arr)
    for name,node in inputs.items():ML.connect_material_expressions(node,'',e,name)
    return e
def newmat(name):
    path='/Game/Astra/Materials/'+name
    m=EAL.load_asset(path) if EAL.does_asset_exist(path) else None
    if m:ML.delete_all_material_expressions(m)
    else:m=AT.create_asset(name,'/Game/Astra/Materials',unreal.Material,unreal.MaterialFactoryNew())
    return m
def finish(mat):
    ML.recompile_material(mat)
    if not EAL.save_loaded_asset(mat):raise RuntimeError('Unable to save material: '+mat.get_name())
    return mat
def import_texture(name):
    path='/Game/Astra/Textures/'+name
    if EAL.does_asset_exist(path):
        tex=EAL.load_asset(path)
        tex.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
        if not EAL.save_loaded_asset(tex):raise RuntimeError('Texture save failed: '+name)
        return tex
    task=unreal.AssetImportTask();task.filename=str(ART/'Textures'/f'{name}.png');task.destination_path='/Game/Astra/Textures';task.destination_name=name
    task.automated=True;task.save=True;task.replace_existing=True
    AT.import_asset_tasks([task])
    tex=EAL.load_asset(path)
    if not tex:raise RuntimeError('Texture import failed: '+name)
    tex.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
    if not EAL.save_loaded_asset(tex):raise RuntimeError('Texture save failed: '+name)
    return tex

def build_materials():
    mats={}
    for name,h in DATA['palette_srgb_hex'].items():
        if EAL.does_asset_exist('/Game/Astra/Materials/'+name):
            mats[name]=EAL.load_asset('/Game/Astra/Materials/'+name)
            continue
        m=newmat(name);props=DATA.get('material_properties',{}).get(name,{})
        base=color(m,linear(h))
        if props.get('base_color_texture'):
            tex=expression(m,unreal.MaterialExpressionTextureSample);tex.texture=import_texture(Path(props['base_color_texture']).stem)
            base=custom(m,'return TexColour*Tint;',{'TexColour':tex,'Tint':color(m,props.get('tint_linear',[1,1,1]))})
            # Keep the cliff's painted cool shadow palette readable under the canopy.
            if 'ForestCliff' in name:connect(color(m,(.012,.021,.036)),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        connect(base,unreal.MaterialProperty.MP_BASE_COLOR)
        connect(const(m,props.get('roughness',.86)),unreal.MaterialProperty.MP_ROUGHNESS)
        connect(const(m,props.get('specular',.15)),unreal.MaterialProperty.MP_SPECULAR)
        connect(const(m,props.get('metallic',0)),unreal.MaterialProperty.MP_METALLIC)
        if props.get('emissive_strength',0)>0:
            c=linear(h);connect(color(m,[v*props['emissive_strength'] for v in c]),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        if 'CampFlame' in name:
            t=expression(m,unreal.MaterialExpressionTime);wp=expression(m,unreal.MaterialExpressionWorldPosition)
            connect(custom(m,'return float3(sin(T*5+Pos.x*.013)*2,cos(T*4+Pos.y*.02)*2,sin(T*7)*2);',{'T':t,'Pos':wp}),unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
        if any(s in name for s in ['Grass','Reed','Lily','Lotus']):m.set_editor_property('two_sided',True)
        mats[name]=finish(m)
    groundtex=import_texture('T_ForestFloor')
    m=newmat('M_Landscape');wp=expression(m,unreal.MaterialExpressionWorldPosition)
    uv=custom(m,'return Pos.xy/480.0;',{'Pos':wp},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    tex=expression(m,unreal.MaterialExpressionTextureSample);tex.texture=groundtex
    ML.connect_material_expressions(uv,'',tex,'UVs')
    code='float2 p=Pos.xy*0.01; float d=10000; float2 a,b,ab; float t;\n'
    for points,width in DATA['paths']:
        for a,b in zip(points,points[1:]):
            code+=f'a=float2({a[0]},{a[1]}); b=float2({b[0]},{b[1]}); ab=b-a; t=saturate(dot(p-a,ab)/dot(ab,ab)); d=min(d,length(p-a-t*ab)-{width});\n'
    code+='d=min(d,length(float2((p.x+5)*.9,p.y+10))-7.2);\n'
    for clearing in DATA.get('clearings',[]):
        cx,cy=clearing['center'];rx,ry=clearing['radii']
        code+=f'd=min(d,(length((p-float2({cx},{cy}))/float2({rx},{ry}))-1)*{min(rx,ry)});\n'
    code+='d += .22*sin(p.x*2.7+sin(p.y*2.1))+.12*cos(p.y*4.3); float alpha=1-smoothstep(-.15,.45,d); float shore=(1-smoothstep(0.0,50.0,abs(Pos.z-10)))*.55; alpha=max(alpha,shore);\n'
    rgb=linear('B79B66')
    code+=f'float3 dirt=float3({rgb[0]},{rgb[1]},{rgb[2]})*(.83+.25*saturate(dot(Ground,float3(.3,.59,.11))*4));\n'
    code+='float3 grass=Ground*float3(.70,.91,.67)*(.95+.05*sin(p.x*.73)*cos(p.y*.81)); float3 land=lerp(grass,dirt,alpha); float submerged=1-smoothstep(-25,15,Pos.z); float3 sand=float3(.31,.39,.28)*(.94+.06*sin(p.x*.55)*cos(p.y*.61)); return lerp(land,sand,submerged);'
    connect(custom(m,code,{'Pos':wp,'Ground':tex}),unreal.MaterialProperty.MP_BASE_COLOR)
    connect(const(m,.95),unreal.MaterialProperty.MP_ROUGHNESS);connect(const(m,.08),unreal.MaterialProperty.MP_SPECULAR)
    mats['M_Landscape']=finish(m)
    mats.update(build_water_materials())
    return mats

def build_water_materials():
    import sys
    sys.path.insert(0,str(ROOT/'Scripts'))
    from puddle_sky_reflection import build_puddle_material
    mats={'M_Water':build_lake_material(),'M_PuddleReflection':build_puddle_material()}
    # A separate sky dome remains independent of the lake/creek material.
    mats['M_CloudSky']=build_cloud_sky_material()
    return mats


def build_cloud_sky_material():
    skytex=import_texture('T_AnimeSkyPanorama')
    # Interchange can mistake a predominantly blue sky for a normal map.
    skytex.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_DEFAULT)
    skytex.set_editor_property('srgb',True)
    skytex.set_editor_property('address_x',unreal.TextureAddress.TA_WRAP)
    skytex.set_editor_property('address_y',unreal.TextureAddress.TA_CLAMP)
    if not EAL.save_loaded_asset(skytex):raise RuntimeError('Panorama texture save failed')
    m=newmat('M_CloudSky');m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided',True);m.set_editor_property('is_sky',True)
    wp=expression(m,unreal.MaterialExpressionWorldPosition)
    # Full-sphere longitude/latitude mapping, independent of the sphere mesh UVs.
    uv=custom(m,'float3 d=normalize(Pos); return float2(atan2(d.y,d.x)/6.28318530718+.5,acos(clamp(d.z,-1,1))/3.14159265359);',{'Pos':wp},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    tex=expression(m,unreal.MaterialExpressionTextureSample);tex.texture=skytex
    ML.connect_material_expressions(uv,'',tex,'UVs')
    # Compose wrap/polar colours from the image itself, avoiding a tinted seam stripe.
    def sample_at(code):
        coords=custom(m,code,{'UV':uv},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
        sample=expression(m,unreal.MaterialExpressionTextureSample);sample.texture=skytex
        ML.connect_material_expressions(coords,'',sample,'UVs');return sample
    left=sample_at('return float2(.002,UV.y);')
    right=sample_at('return float2(.998,UV.y);')
    zenith=sample_at('return float2(.5,.005);')
    nadir=sample_at('return float2(.5,.65);')
    code='float wrap=smoothstep(0,.024,min(UV.x,1-UV.x)); float3 c=lerp((West+East)*.5,Sky,wrap); c=lerp(Top,c,smoothstep(.015,.09,UV.y)); c=lerp(c,Bottom,smoothstep(.50,.68,UV.y)); return c*1.15;'
    connect(custom(m,code,{'Sky':tex,'UV':uv,'West':left,'East':right,'Top':zenith,'Bottom':nadir}),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(m)


def build_lake_material():
    """Clear art-directed lake/creek with no sky or cloud reflection."""
    m=newmat('M_Water')
    m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided',True)
    m.set_editor_property('screen_space_reflections',False)
    edge=expression(m,unreal.MaterialExpressionVertexColor)
    fade=expression(m,unreal.MaterialExpressionDepthFade);fade.set_editor_property('fade_distance_default',25.0)
    sd=expression(m,unreal.MaterialExpressionSceneDepth);pd=expression(m,unreal.MaterialExpressionPixelDepth)
    wp=expression(m,unreal.MaterialExpressionWorldPosition);time=expression(m,unreal.MaterialExpressionTime)
    mask=custom(m,'return smoothstep(0,1,Edge.r)*Fade;',{'Edge':edge,'Fade':fade},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    opacity=custom(m,'return Mask*lerp(.48,.80,saturate((Scene-Pixel)/125));',{'Mask':mask,'Scene':sd,'Pixel':pd},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    connect(opacity,unreal.MaterialProperty.MP_OPACITY)
    code='float d=saturate((Scene-Pixel)/125); float2 p=Pos.xy*.01; float3 c=lerp(float3(.10,.39,.38),float3(.026,.30,.40),d); float2 cell=floor(p/float2(5.5,3.7)); float2 h=frac(sin(float2(dot(cell,float2(127.1,311.7)),dot(cell,float2(269.5,183.3))))*43758.5453); float2 q=(frac(p/float2(5.5,3.7))-(.2+.6*h))*float2(5.5,3.7); float glint=(1-smoothstep(.025,.07,abs(q.x+.03*sin(T*.3+h.x*6))))*(1-smoothstep(.10,.34,abs(q.y)))*pow(.5+.5*sin(T*.5+h.y*6),2); return c+float3(.10,.14,.14)*glint;'
    connect(custom(m,code,{'Scene':sd,'Pixel':pd,'Pos':wp,'T':time}),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(m)


def setup_cloud_sky(mats):
    actors=ES.get_all_level_actors()
    dome=next((a for a in actors if a.get_actor_label()=='CloudSkyDome'),None)
    if dome is None:dome=spawn(unreal.StaticMeshActor,[0,0,0],label='CloudSkyDome',folder='Lighting')
    dome.set_actor_enable_collision(False)
    c=dome.static_mesh_component;c.set_static_mesh(EAL.load_asset('/Engine/BasicShapes/Sphere'))
    c.set_material(0,mats['M_CloudSky']);dome.set_actor_scale3d(unreal.Vector(10000,10000,10000))
    c.set_collision_profile_name('NoCollision');c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);c.set_cast_shadow(False)
    c.set_editor_property('affect_distance_field_lighting',False)
    c.set_editor_property('visible_in_ray_tracing',False)
    c.set_editor_property('visible_in_real_time_sky_captures',True)
    fog=next((a for a in actors if isinstance(a,unreal.ExponentialHeightFog)),None)
    if fog is None:fog=spawn(unreal.ExponentialHeightFog,[0,0,0],label='WoodlandHeightFog',folder='Lighting')
    fc=fog.component
    fc.set_fog_density(.001)
    fc.set_fog_height_falloff(.25)
    fc.set_start_distance(3200.0)
    fc.set_fog_max_opacity(.06)
    fc.set_fog_inscattering_color(unreal.LinearColor(.36,.46,.44,1))
    for a in actors:
        if isinstance(a,unreal.DirectionalLight):
            a.light_component.set_editor_property('specular_scale',0.0)
        if isinstance(a,unreal.SkyLight):
            c=a.light_component;c.set_editor_property('real_time_capture',True)
            c.set_editor_property('cubemap_resolution',512);c.set_editor_property('sky_distance_threshold',100000.0)
        if isinstance(a,unreal.PostProcessVolume):
            s=a.get_editor_property('settings')
            s.set_editor_property('override_lumen_front_layer_translucency_reflections',True)
            s.set_editor_property('lumen_front_layer_translucency_reflections',True)
            s.set_editor_property('override_lumen_reflection_quality',True)
            s.set_editor_property('lumen_reflection_quality',2.0)
            a.set_editor_property('settings',s)
    return dome


def import_meshes(mats):
    meshes={};bounds={}
    for name,meta in DATA['assets'].items():
        path='/Game/Astra/Meshes/'+name
        asset=EAL.load_asset(path) if EAL.does_asset_exist(path) else None
        if not asset:
            task=unreal.AssetImportTask();task.filename=str(ART/meta['file']);task.destination_path='/Game/Astra/Meshes';task.destination_name=name
            task.automated=True;task.save=True;task.replace_existing=True
            task.factory=unreal.FbxFactory()
            options=unreal.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=False;options.import_materials=False;options.import_textures=False;options.import_animations=False
            options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
            options.static_mesh_import_data.combine_meshes=True
            options.static_mesh_import_data.generate_lightmap_u_vs=False
            options.static_mesh_import_data.auto_generate_collision=False
            options.static_mesh_import_data.vertex_color_import_option=unreal.VertexColorImportOption.REPLACE
            options.static_mesh_import_data.convert_scene=True
            options.static_mesh_import_data.convert_scene_unit=True
            if meta.get('normal_import_method')=='IMPORT_NORMALS_AND_TANGENTS':
                options.static_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
            task.options=options;AT.import_asset_tasks([task]);asset=EAL.load_asset(path)
        if not asset:raise RuntimeError('Mesh import failed: '+name)
        for i,slot in enumerate(asset.get_editor_property('static_materials')):
            slotname=str(slot.material_slot_name)
            key=slotname if slotname in mats else meta['materials'][min(i,len(meta['materials'])-1)]
            if name=='SM_Puddle':key='M_PuddleReflection'
            asset.set_material(i,mats[key])
        body=asset.get_editor_property('body_setup')
        if meta['collision']=='complex':body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        elif meta['collision']=='solid':
            SM.remove_collisions(asset)
            SM.add_simple_collisions(asset,unreal.ScriptingCollisionShapeType.NDOP26)
        EAL.save_loaded_asset(asset);meshes[name]=asset
        b=asset.get_bounding_box();bounds[name]={'min':[b.min.x,b.min.y,b.min.z],'max':[b.max.x,b.max.y,b.max.z]}
        report('Imported '+name)
    (OUT/'mesh_bounds.json').write_text(json.dumps(bounds,indent=2),encoding='utf-8')
    return meshes

def spawn(cls,location,rotation=None,label=None,folder=None):
    a=ES.spawn_actor_from_class(cls,unreal.Vector(*location),rotation or unreal.Rotator())
    if label:a.set_actor_label(label)
    if folder:a.set_folder_path(folder)
    return a

def build_level(mats,meshes):
    path='/Game/Astra/Maps/L_AstraWoodland'
    unreal.EditorLevelLibrary.new_level(path)
    world=unreal.EditorLevelLibrary.get_editor_world()
    land=unreal.AstraSceneLibrary.create_terrain(mats['M_Landscape'])
    if not land:raise RuntimeError('Landscape import failed')
    land.set_folder_path('Terrain')
    cube=EAL.load_asset('/Engine/BasicShapes/Cube')
    for idx,o in enumerate(DATA['objects']):
        if o['group']=='PreviewOnly':continue
        r=o['ue_rotation_deg'];rot=unreal.Rotator(pitch=r['pitch'],yaw=r['yaw'],roll=r['roll'])
        a=spawn(unreal.StaticMeshActor,o['ue_location_cm'],rot,o['name'],o['group'])
        c=a.static_mesh_component;c.set_static_mesh(meshes[o['asset']]);a.set_actor_scale3d(unreal.Vector(*o['scale']))
        c.set_mobility(unreal.ComponentMobility.STATIC)
        coll=o['collision']
        c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS if coll in ['solid','complex'] else unreal.CollisionEnabled.NO_COLLISION)
        if coll not in ['solid','complex']:c.set_collision_profile_name('NoCollision')
        if o['group'].startswith('Water'):c.set_cast_shadow(False)
        if coll=='trunk':
            # Canopies remain walk-under; a trunk-sized blocker stops the player.
            p=o['ue_location_cm'];s=o['scale'];block=spawn(unreal.StaticMeshActor,[p[0],p[1],p[2]+120*s[2]],label=o['name']+'_TrunkCollision',folder='Collision/Trunks')
            bc=block.static_mesh_component;bc.set_static_mesh(cube);block.set_actor_scale3d(unreal.Vector(.56*s[0],.56*s[1],2.4*s[2]));block.set_actor_hidden_in_game(True);bc.set_visibility(False);bc.set_collision_profile_name('BlockAll')
        if idx%300==0:report(f'Placed {idx}/{len(DATA["objects"])}')
    # Invisible water safety boundaries stop walking into the deep lake.
    # Use the terrain itself for shallows; the player can reach the lotus shoreline.
    for i in range(48):
        a=i*math.tau/48;x=1900+math.cos(a)*1380;y=2070+math.sin(a)*1120
        block=spawn(unreal.StaticMeshActor,[x,y,65],unreal.Rotator(yaw=math.degrees(a)+90),f'LakeBoundary_{i:02}','Collision/Water')
        bc=block.static_mesh_component;bc.set_static_mesh(cube);block.set_actor_scale3d(unreal.Vector(2.1,.65,2.3));block.set_actor_hidden_in_game(True);bc.set_visibility(False);bc.set_collision_profile_name('BlockAll')
    sun=spawn(unreal.DirectionalLight,[0,0,4000],unreal.Rotator(pitch=-48,yaw=-35,roll=0),'Sun_SoftSource50','Lighting')
    light=sun.light_component;light.set_mobility(unreal.ComponentMobility.MOVABLE);light.set_intensity(6.0)
    light.set_editor_property('light_source_angle',50.0)
    light.set_editor_property('light_source_soft_angle',0.0)
    light.set_editor_property('atmosphere_sun_light',True)
    light.set_light_color(unreal.LinearColor(1.0,.94,.83,1))
    sky=spawn(unreal.SkyLight,[0,0,2000],label='SoftSkyFill',folder='Lighting')
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE);sky.light_component.set_intensity(.9)
    sky.light_component.set_editor_property('real_time_capture',True)
    spawn(unreal.SkyAtmosphere,[0,0,0],label='SkyAtmosphere',folder='Lighting')
    pp=spawn(unreal.PostProcessVolume,[0,0,0],label='WoodlandGrade',folder='Lighting');pp.set_editor_property('unbound',True)
    settings=pp.get_editor_property('settings')
    settings.set_editor_property('override_auto_exposure_apply_physical_camera_exposure',True)
    settings.set_editor_property('auto_exposure_apply_physical_camera_exposure',False)
    for n,v in {'override_auto_exposure_method':True,'auto_exposure_method':unreal.AutoExposureMethod.AEM_MANUAL,'override_auto_exposure_bias':True,'auto_exposure_bias':0.0,'override_motion_blur_amount':True,'motion_blur_amount':0.0,'override_vignette_intensity':True,'vignette_intensity':.12,'override_bloom_intensity':True,'bloom_intensity':.12}.items():settings.set_editor_property(n,v)
    pp.set_editor_property('settings',settings)
    setup_cloud_sky(mats)
    from puddle_sky_reflection import configure_reflection_environment
    configure_reflection_environment()
    start=spawn(unreal.PlayerStart,DATA['spawn_cm'],unreal.Rotator(yaw=155),'PlayerStart_Clearing','Gameplay')
    world.get_world_settings().set_editor_property('default_game_mode',unreal.AstraGameMode)
    for name,look,width in [('Overview',[0,0,0],15500),('Gameplay',[-600,-1000,100],3000),('Lake',[1300,2000,70],3700),('Cabin',[2400,-2300,150],2400),('Puddle',[-2000,-1600,60],1300)]:
        pitch=-58;arm=8000 if name=='Overview' else 2700
        rad=math.radians(58);loc=[look[0]-arm*math.cos(rad),look[1],look[2]+arm*math.sin(rad)]
        cam=spawn(unreal.CameraActor,loc,unreal.Rotator(pitch=pitch,yaw=0,roll=0),'Camera_'+name,'ReviewCameras')
        cc=cam.camera_component;cc.set_editor_property('projection_mode',unreal.CameraProjectionMode.ORTHOGRAPHIC);cc.set_editor_property('ortho_width',width);cc.set_editor_property('constrain_aspect_ratio',False)
    # Actual animated cat is spawned by the game mode on Play; the preview mesh is editor only.
    cp=DATA['spawn_cm'];preview=spawn(unreal.StaticMeshActor,[cp[0],cp[1],cp[2]-100],unreal.Rotator(yaw=155),'Cat_EditorPreview','Gameplay')
    preview.static_mesh_component.set_static_mesh(meshes['SM_CalicoPreview']);preview.set_actor_hidden_in_game(True);preview.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(unreal.Vector(-4800,-1000,5300),unreal.Rotator(pitch=-58,yaw=0,roll=0))
    unreal.EditorLevelLibrary.save_current_level()
    EAL.save_directory('/Game/Astra',only_if_is_dirty=False,recursive=True)
    report('Map saved '+path)
    return path

def main():
  try:
    report('Starting editor import from Blender layout')
    unreal.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
    mats=build_materials();report('Materials complete')
    meshes=import_meshes(mats)
    map_path=build_level(mats,meshes)
    result={'status':'success','map':map_path,'mesh_assets':len(meshes),'source_objects':len(DATA['objects']),'landscape_size_m':100.8,'directional_source_angle':50}
    (OUT/'build_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    report('BUILD SUCCESS')
  except Exception:
    error=traceback.format_exc();report(error)
    (OUT/'build_result.json').write_text(json.dumps({'status':'failed','error':error},indent=2),encoding='utf-8')
    raise

if __name__=='__main__':main()
