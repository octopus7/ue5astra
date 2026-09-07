"""Author medium/large Niagara explosions from the repaired small showcase.

Run in the UE editor: py ".../Scripts/build_explosion_variants.py"
Creates four independent systems and L_ExplosionScaleShowcase. Existing small
assets are only read. Re-running updates only the named generated assets/map.
"""
import json
from pathlib import Path
import unreal

EAL = unreal.EditorAssetLibrary
ROOT = Path(unreal.Paths.project_dir()).resolve()
SOURCE = '/Game/VFX/SmallDestruction/NS_SmallDestruction_Showcase'
DEST = '/Game/VFX/Explosions'
MAP = '/Game/Maps/L_ExplosionScaleShowcase'
PROFILES = {
    'Medium': dict(diameter=300, loop=4.0, bounds=220,
        counts=[52, 26, 32, 3],
        lives=[(.60, .85), (.28, .48), (1.5, 2.2), (.30, .50)],
        sizes=[(1.0, 1.7), (55, 85), (70, 100), (140, 180)],
        radii=[12, 18, 20, 2],
        velocities=[((-85,-85,220),(85,85,330)),
                    ((-65,-65,25),(65,65,100)),
                    ((-18,-18,25),(18,18,50)), ((0,0,8),(0,0,8))]),
    'Large': dict(diameter=1000, loop=6.0, bounds=650,
        counts=[104, 48, 64, 4],
        lives=[(1.0, 1.4), (.45, .75), (2.8, 4.2), (.45, .75)],
        sizes=[(1.2, 2.4), (160, 240), (180, 250), (450, 600)],
        radii=[35, 55, 60, 5],
        velocities=[((-230,-230,430),(230,230,620)),
                    ((-180,-180,50),(180,180,200)),
                    ((-35,-35,35),(35,35,65)), ((0,0,15),(0,0,15))]),
}


def vector_text(values):
    return '(' + ','.join(f'{axis}={value}' for axis,value in zip('XYZ', values)) + ')'


def set_struct(obj, prop, text):
    value = obj.get_editor_property(prop).copy()
    if not value.import_text(text):
        raise RuntimeError(f'Cannot import {prop}: {text}')
    obj.set_editor_property(prop, value)


def distribution(obj, prop, low, high=None, dimensions=1, uniform=True):
    high = low if high is None else high
    is_constant = low == high
    mode = ('Uniform' if uniform else 'NonUniform') + ('Constant' if is_constant else 'Range')
    if dimensions == 1:
        lo, hi = str(low), str(high)
        channels = [low] if is_constant else [low, high]
    else:
        lows = [low]*dimensions if uniform else list(low)
        highs = [high]*dimensions if uniform else list(high)
        lo, hi = vector_text(lows), vector_text(highs)
        channels = ([low] if is_constant else [low,high]) if uniform else (lows if is_constant else lows+highs)
    text = f'(Mode={mode},Min={lo},Max={hi},ChannelConstantsAndRanges=({",".join(map(str,channels))}),ChannelCurves=())'
    set_struct(obj, prop, text)


def emitter_objects(system):
    result = {}
    for obj in unreal.ObjectIterator(unreal.NiagaraEmitterBase):
        if obj.get_outer() == system and obj.get_class().get_name() == 'NiagaraStatelessEmitter':
            name = obj.get_name().rsplit('_',1)[0]
            if name in result:
                raise RuntimeError('Ambiguous emitter: ' + name)
            result[name] = obj
    assert set(result) == {'Debris','Flame','Smoke','Distortion'}, result
    return result


def author_system(name, profile, looping):
    asset_path = f'{DEST}/NS_{name}Explosion' + ('_Showcase' if looping else '')
    system = EAL.load_asset(asset_path) if EAL.does_asset_exist(asset_path) else EAL.duplicate_asset(SOURCE, asset_path)
    assert system
    for index, emitter_name in enumerate(['Debris','Flame','Smoke','Distortion']):
        emitter = emitter_objects(system)[emitter_name]
        modules = {m.get_class().get_name().removeprefix('NiagaraStatelessModule_'): m
                   for m in emitter.get_editor_property('Modules')}
        init, velocity, shape = (modules[key] for key in ['InitializeParticle','AddVelocity','ShapeLocation'])
        distribution(init, 'LifetimeDistribution', *profile['lives'][index])
        distribution(init, 'MeshScaleDistribution' if index == 0 else 'SpriteSizeDistribution',
                     *profile['sizes'][index], dimensions=3 if index == 0 else 2)
        distribution(velocity, 'LinearVelocityDistribution', *profile['velocities'][index], dimensions=3, uniform=False)
        distribution(shape, 'SphereRadius', profile['radii'][index])
        if index == 0:
            distribution(modules['GravityForce'], 'GravityDistribution', (0,0,-700), dimensions=3, uniform=False)
        if index == 2:
            distribution(modules['Drag'], 'DragDistribution', .65 if name == 'Medium' else .5)
            alpha = .28 if name == 'Medium' else .24
            set_struct(init, 'ColorDistribution', f'(Mode=NonUniformConstant,ChannelConstantsAndRanges=(0.11,0.10,0.09,{alpha}),ChannelCurves=(),Values=((R=0.11,G=0.10,B=0.09,A={alpha})))')
        spawns = list(emitter.get_editor_property('SpawnInfos'))
        assert len(spawns) == 1
        spawn = spawns[0].copy()
        count = profile['counts'][index]
        delay = (.18 if name == 'Medium' else .32) if index == 2 else 0
        assert spawn.import_text(f'(Type=Burst,SpawnTime={delay},Amount=(Mode=UniformConstant,Min={count},Max={count}),bEnabled=True)')
        emitter.set_editor_property('SpawnInfos', [spawn])
        loop = profile['loop']
        set_struct(emitter, 'EmitterState', f'(LoopBehavior={"Infinite" if looping else "Once"},LoopDurationMode=Fixed,LoopDuration=(Mode=UniformConstant,Min={loop},Max={loop},ChannelConstantsAndRanges=({loop})),InactiveResponse=Complete)')
        emitter.set_editor_property('bDeterministic', True)
        emitter.set_editor_property('RandomSeed', 410 + index)
        b = profile['bounds']
        set_struct(emitter, 'FixedBounds', f'(Min=(X={-b},Y={-b},Z={-b}),Max=(X={b},Y={b},Z={b}),IsValid=True)')
    b = profile['bounds']
    set_struct(system, 'FixedBounds', f'(Min=(X={-b},Y={-b},Z={-b}),Max=(X={b},Y={b},Z={b}),IsValid=True)')
    system.set_editor_property('bFixedBounds', True)
    assert EAL.save_loaded_asset(system)
    return system


def build_stage(systems):
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    # Save the existing editor map first; never discard an unsaved workspace.
    assert levels.save_current_level()
    if EAL.does_asset_exist(MAP):
        assert levels.load_level(MAP)
        existing = {a.get_actor_label(): a for a in actors.get_all_level_actors()}
    else:
        assert levels.new_level(MAP)
        existing = {}

    def actor(label, cls, pos, rot=None):
        a = existing.get(label)
        if a is None:
            a = actors.spawn_actor_from_class(cls, unreal.Vector(*pos), rot or unreal.Rotator())
        a.set_actor_label(label)
        a.set_actor_location(unreal.Vector(*pos), False, False)
        if rot is not None: a.set_actor_rotation(rot, False)
        return a

    materials = '/Game/VFX/SmallDestruction/Materials/'
    # A one-metre antialiased grid remains readable at the large effect's distance.
    ml = unreal.MaterialEditingLibrary
    stage_path = DEST + '/Materials/M_ExplosionStage'
    stage = EAL.load_asset(stage_path) if EAL.does_asset_exist(stage_path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_ExplosionStage', DEST+'/Materials', unreal.Material, unreal.MaterialFactoryNew())
    ml.delete_all_material_expressions(stage)
    stage.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    position = ml.create_material_expression(stage, unreal.MaterialExpressionWorldPosition)
    pattern = ml.create_material_expression(stage, unreal.MaterialExpressionCustom)
    pattern.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pin = unreal.CustomInput()
    pin.set_editor_property('input_name', 'Pos')
    pattern.set_editor_property('inputs', [pin])
    pattern.set_editor_property('code', 'float2 q=Pos.xy/100.0; float2 d=abs(frac(q-0.5)-0.5)/max(fwidth(q),0.001); float line=1-saturate(min(d.x,d.y)); return lerp(float3(0.018,0.024,0.035),float3(0.075,0.10,0.14),line);')
    assert ml.connect_material_expressions(position, '', pattern, 'Pos')
    assert ml.connect_material_property(pattern, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ml.recompile_material(stage)
    assert EAL.save_loaded_asset(stage)
    rim = EAL.load_asset(materials+'M_MeterRim')

    def mesh(label, model, pos, scale, mat):
        a = actor(label, unreal.StaticMeshActor, pos)
        a.static_mesh_component.set_static_mesh(EAL.load_asset('/Engine/BasicShapes/'+model))
        a.static_mesh_component.set_material(0, mat)
        a.set_actor_scale3d(unreal.Vector(*scale))
        return a

    mesh('EX_Floor', 'Cube', (0,0,-16), (28,34,.2), stage)
    for name,y,diameter in [('Small',-1050,100),('Medium',-650,300),('Large',450,1000)]:
        size = diameter/100
        mesh('EX_'+name+'_Diameter', 'Cylinder', (0,y,0), (size,size,.06), rim)
        mesh('EX_'+name+'_Platform', 'Cylinder', (0,y,4), (size*.985,size*.985,.03), stage)
        effect = actor('EX_'+name+'_Looping', unreal.NiagaraActor, (0,y,18 if name!='Large' else 45))
        component = effect.get_component_by_class(unreal.NiagaraComponent)
        component.set_asset(systems[name])
        component.set_auto_activate(True)
        component.activate(True)
        label = actor('EX_'+name+'_Label', unreal.TextRenderActor, (diameter*.5+45,y,10), unreal.Rotator(pitch=0,yaw=0,roll=0))
        text = label.get_component_by_class(unreal.TextRenderComponent)
        text.set_text(f'{name.upper()} / {diameter/100:g} m')
        text.set_world_size(45)
        text.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
    light = actor('EX_KeyLight', unreal.DirectionalLight, (0,0,1200), unreal.Rotator(pitch=-50,yaw=-25,roll=0)).light_component
    light.set_mobility(unreal.ComponentMobility.MOVABLE)
    light.set_editor_property('intensity', 7)
    camera_pos = unreal.Vector(1800,-1200,1150)
    rotation = unreal.MathLibrary.find_look_at_rotation(camera_pos, unreal.Vector(0,-100,100))
    camera = actor('EX_OverviewCamera', unreal.CameraActor, (camera_pos.x,camera_pos.y,camera_pos.z), rotation)
    camera.camera_component.set_editor_property('field_of_view', 55)
    camera.set_editor_property('auto_activate_for_player', unreal.AutoReceiveInput.PLAYER0)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_pos, rotation)
    actors.set_selected_level_actors([])
    unreal.AstraNiagaraLibrary.enable_viewport_realtime()
    assert levels.save_current_level()


def main():
    report = {}
    systems = {'Small': EAL.load_asset(SOURCE)}
    for name,profile in PROFILES.items():
        for looping in [False, True]:
            system = author_system(name, profile, looping)
            report[system.get_name()] = json.loads(unreal.AstraNiagaraLibrary.describe_system(system))
            if looping: systems[name] = system
    build_stage(systems)
    (ROOT/'Saved'/'explosion_variants_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('EXPLOSION_VARIANTS_COMPLETE: four systems and comparison level saved')


if __name__ == '__main__':
    main()
