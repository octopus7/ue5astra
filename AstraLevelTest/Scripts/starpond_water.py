"""Dedicated magical water; shared real-sky puddle materials are untouched."""
from pathlib import Path
import unreal

def build(api):
    m=api.new_material('M_SP_StarWater')
    m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property('two_sided',True)
    m.set_editor_property('tangent_space_normal',False)
    pos=api.expression(m,unreal.MaterialExpressionWorldPosition)
    time=api.expression(m,unreal.MaterialExpressionTime)
    edge=api.expression(m,unreal.MaterialExpressionVertexColor)
    alignment=api.expression(m,unreal.MaterialExpressionScalarParameter)
    alignment.set_editor_property('parameter_name','Alignment');alignment.set_editor_property('default_value',1.)
    uv=api.custom(m,'return Pos.xy/float2(2400.,2900.)+.5+float2(sin(T*.09),cos(T*.07))*.0015;',{'Pos':pos,'T':time},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    tex=api.expression(m,unreal.MaterialExpressionTextureSample)
    tex.set_editor_property('texture',api.texture_from_file('ArtSource/Textures/StarPond/T_SP_SubmergedStars.png'))
    api.ML.connect_material_expressions(uv,'',tex,'UVs')
    distance='float2 p=Pos.xy*.01;float2 v=p/float2(12.,14.5);float a=atan2(v.y,v.x);float r=length(v)/(1+.042*sin(a*3+.4)+.024*sin(a*7));'
    base=api.custom(m,distance+'''
float shore=smoothstep(.68,1.,r);
float ripple=pow(.5+.5*sin(r*140.-T*.62+sin(a*5.)*.30),16.)*smoothstep(.85,.97,r);
return lerp(float3(.003,.012,.030),float3(.075,.24,.16),shore)+ripple*float3(.08,.13,.10);
''',{'Pos':pos,'T':time})
    api.ML.connect_material_property(base,'',unreal.MaterialProperty.MP_BASE_COLOR)
    code=distance+'''
float2 stars[6]={float2(-8,0),float2(-5.2,-4),float2(-2,1.7),float2(1.1,-2.4),float2(4,.9),float2(7,0)};
float points=0;float lines=0;
for(int i=0;i<6;i++){
  float2 q=p-stars[i];float r2=dot(q,q);float tw=.80+.20*sin(T*1.1+float(i)*1.7);
  points+=tw*(exp(-r2*150.)*2.8+exp(-r2*10.)*.18);
  points+=tw*.32*exp(-abs(q.x)*48.-abs(q.y)*5.)+tw*.32*exp(-abs(q.x)*5.-abs(q.y)*48.);
  if(i<5){float2 v=stars[i+1]-stars[i];float t=saturate(dot(q,v)/dot(v,v));float dist=length(q-v*t);lines=max(lines,1-smoothstep(.015,.044,dist));}
}
float2 cell=floor(p*4.);float2 local=frac(p*4.);
float rnd=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453);
float tiny=exp(-dot(local-.5,local-.5)*380.)*step(.94,rnd)*(.34+.20*sin(T*.75+rnd*42.));
float center=1-smoothstep(.78,.97,r);
return (Tex.rgb*1.65+float3(.055,.28,.46)*tiny)*center
 +float3(.30,.78,1.0)*points*center
 +float3(.14,.52,.82)*lines*saturate(Align)*center*.82;
'''
    (api.ART/'Layout/starpond_water.hlsl').write_text(code,encoding='utf-8')
    emission=api.custom(m,code,{'Pos':pos,'T':time,'Tex':tex,'Align':alignment})
    api.ML.connect_material_property(emission,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    normal=api.custom(m,'float2 p=Pos.xy*.01;return normalize(float3(sin(p.x*1.9+p.y*.3+T*.2)*.006,cos(p.y*1.5-p.x*.4-T*.17)*.006,1));',{'Pos':pos,'T':time})
    api.ML.connect_material_property(normal,'',unreal.MaterialProperty.MP_NORMAL)
    # World-locked fine dither confines the soft water boundary to the authored mesh.
    mask=api.custom(m,'float n=frac(sin(dot(floor(Pos.xy*1.2),float2(12.9898,78.233)))*43758.5453);return Edge.r-n*.45;',{'Pos':pos,'Edge':edge},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    api.ML.connect_material_property(mask,'',unreal.MaterialProperty.MP_OPACITY_MASK)
    m.set_editor_property('opacity_mask_clip_value',.03)
    api.ML.connect_material_property(api.constant(m,.13),'',unreal.MaterialProperty.MP_ROUGHNESS)
    api.ML.connect_material_property(api.constant(m,.16),'',unreal.MaterialProperty.MP_SPECULAR)
    api.ML.connect_material_property(api.constant(m,0),'',unreal.MaterialProperty.MP_METALLIC)
    api.EAL.set_metadata_tag(m,'StarPondMode','daylight_night_sky_portal; authored_texture + animated procedural stars; proximity constellation')
    return api.finish_material(m)
