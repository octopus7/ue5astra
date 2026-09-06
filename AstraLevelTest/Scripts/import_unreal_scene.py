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
    ML.recompile_material(mat);EAL.save_loaded_asset(mat);return mat
def import_texture(name):
    path='/Game/Astra/Textures/'+name
    if EAL.does_asset_exist(path):
        tex=EAL.load_asset(path)
        tex.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
        EAL.save_loaded_asset(tex)
        return tex
    task=unreal.AssetImportTask();task.filename=str(ART/'Textures'/f'{name}.png');task.destination_path='/Game/Astra/Textures';task.destination_name=name
    task.automated=True;task.save=True;task.replace_existing=True
    AT.import_asset_tasks([task])
    tex=EAL.load_asset(path)
    if not tex:raise RuntimeError('Texture import failed: '+name)
    tex.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
    EAL.save_loaded_asset(tex)
    return tex

def build_materials():
    mats={}
    for name,h in DATA['palette_srgb_hex'].items():
        if EAL.does_asset_exist('/Game/Astra/Materials/'+name):
            mats[name]=EAL.load_asset('/Game/Astra/Materials/'+name)
            continue
        m=newmat(name);connect(color(m,linear(h)),unreal.MaterialProperty.MP_BASE_COLOR)
        connect(const(m,.86),unreal.MaterialProperty.MP_ROUGHNESS);connect(const(m,.15),unreal.MaterialProperty.MP_SPECULAR)
        if any(s in name for s in ['Grass','Reed','Lily','Lotus']):m.set_editor_property('two_sided',True)
        mats[name]=finish(m)
    groundtex=import_texture('T_ForestFloor');skytex=import_texture('T_AnimeSkyReflection')
    m=newmat('M_Landscape');wp=expression(m,unreal.MaterialExpressionWorldPosition)
    uv=custom(m,'return Pos.xy/480.0;',{'Pos':wp},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    tex=expression(m,unreal.MaterialExpressionTextureSample);tex.texture=groundtex
    ML.connect_material_expressions(uv,'',tex,'UVs')
    code='float2 p=Pos.xy*0.01; float d=10000; float2 a,b,ab; float t;\n'
    for points,width in DATA['paths']:
        for a,b in zip(points,points[1:]):
            code+=f'a=float2({a[0]},{a[1]}); b=float2({b[0]},{b[1]}); ab=b-a; t=saturate(dot(p-a,ab)/dot(ab,ab)); d=min(d,length(p-a-t*ab)-{width});\n'
    code+='d=min(d,length(float2((p.x+5)*.9,p.y+10))-7.2);\n'
    code+='d += .22*sin(p.x*2.7+sin(p.y*2.1))+.12*cos(p.y*4.3); float alpha=1-smoothstep(-.15,.45,d); float shore=(1-smoothstep(0.0,50.0,abs(Pos.z-10)))*.55; alpha=max(alpha,shore);\n'
    rgb=linear('B79B66')
    code+=f'float3 dirt=float3({rgb[0]},{rgb[1]},{rgb[2]})*(.83+.25*saturate(dot(Ground,float3(.3,.59,.11))*4));\n'
    code+='float3 grass=Ground*float3(.70,.91,.67)*(.95+.05*sin(p.x*.73)*cos(p.y*.81)); return lerp(grass,dirt,alpha);'
    connect(custom(m,code,{'Pos':wp,'Ground':tex}),unreal.MaterialProperty.MP_BASE_COLOR)
    connect(const(m,.95),unreal.MaterialProperty.MP_ROUGHNESS);connect(const(m,.08),unreal.MaterialProperty.MP_SPECULAR)
    mats['M_Landscape']=finish(m)
    for name,puddle in [('M_Water',False),('M_PuddleReflection',True)]:
        m=newmat(name);m.set_editor_property('two_sided',True)
        wp=expression(m,unreal.MaterialExpressionWorldPosition);time=expression(m,unreal.MaterialExpressionTime)
        if puddle:
            uv=expression(m,unreal.MaterialExpressionTextureCoordinate)
            uvm=custom(m,'return UV+float2(sin(T*.65+UV.y*24),cos(T*.5+UV.x*21))*.006;',{'UV':uv,'T':time},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
            tex=expression(m,unreal.MaterialExpressionTextureSample);tex.texture=skytex;ML.connect_material_expressions(uvm,'',tex,'UVs')
            c=custom(m,'float edge=smoothstep(.24,.52,length(UV-.5)); return lerp(Sky*.72,float3(.08,.15,.12),.15+edge*.58);',{'Sky':tex,'UV':uv})
            connect(c,unreal.MaterialProperty.MP_BASE_COLOR)
            emit=custom(m,'return Sky*.12*(1-smoothstep(.24,.54,length(UV-.5)));',{'Sky':tex,'UV':uv});connect(emit,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        else:
            c=custom(m,'float2 p=Pos.xy*.01; float lake=length(float2((p.x-19)/15.1,(p.y-20.7)/12.4)); float shallow=smoothstep(.72,1.08,lake); float wave=pow(saturate(sin(p.x*7+sin(p.y*4)*2-T*.9)*sin(p.y*5+cos(p.x*3)-T*.7)*.5+.5),18)*.016; float mottles=.5+.5*sin(p.x*1.7+sin(p.y*2.2))*cos(p.y*2.5); return lerp(float3(.045,.13,.105),float3(.14,.25,.19),shallow*.7+mottles*.18)+wave;',{'Pos':wp,'T':time})
            connect(c,unreal.MaterialProperty.MP_BASE_COLOR)
        normal=custom(m,'return normalize(float3(.03*sin(Pos.x*.035+T*.8),.03*cos(Pos.y*.033-T*.6),1));',{'Pos':wp,'T':time})
        connect(normal,unreal.MaterialProperty.MP_NORMAL)
        connect(const(m,.27 if puddle else .22),unreal.MaterialProperty.MP_ROUGHNESS)
        connect(const(m,.65),unreal.MaterialProperty.MP_SPECULAR)
        mats[name]=finish(m)
    return mats

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
            options.static_mesh_import_data.convert_scene=True
            options.static_mesh_import_data.convert_scene_unit=True
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
