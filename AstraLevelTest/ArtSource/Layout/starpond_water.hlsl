float2 p=Pos.xy*.01;float2 v=p/float2(12.,14.5);float a=atan2(v.y,v.x);float r=length(v)/(1+.042*sin(a*3+.4)+.024*sin(a*7));
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
