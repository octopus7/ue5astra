"""Water surfaces in Blender metres, with a dedicated zero-opacity perimeter."""
import math

def disc(n,rx,ry,inner,puddle=False):
    verts=[(0,0,0)];weights=[1.0];faces=[]
    for radius,weight in [(inner,1.0),(1.0,0.0)]:
        for i in range(n):
            a=i*math.tau/n
            irregular=1+.055*math.sin(5*a)+.03*math.sin(9*a) if puddle else 1
            verts.append((math.cos(a)*rx*radius*irregular,math.sin(a)*ry*radius*irregular,0))
            weights.append(weight)
    for i in range(n):
        j=(i+1)%n
        faces.append((0,1+i,1+j))
        faces.append((1+i,1+n+i,1+n+j,1+j))
    return verts,faces,weights

def water_geometry(asset):
    if asset=='SM_LakeSurface':return disc(96,15.1*1.10,12.4*1.10,.89)
    if asset=='SM_Puddle':return disc(64,1,1,.70,True)
    if asset!='SM_StreamSurface':raise ValueError(asset)
    verts=[];faces=[];weights=[]
    for i in range(161):
        x=-51+i*64/160;y=.6*x+8.5+1.9*math.sin(x/6.8)
        w=2.75+.24*math.sin(x/4.3)
        end_fade=max(0,min(1,(13-x)/3.0))
        for offset,alpha in [(-w,0),(-w+.8,1),(w-.8,1),(w,0)]:
            verts.append((x,-(y+offset),.10));weights.append(alpha*end_fade)
        if i:
            for j in range(3):faces.append((4*i-4+j,4*i+j,4*i+j+1,4*i-3+j))
    return verts,faces,weights

def add_edge_mask(mesh,weights):
    colors=mesh.color_attributes.new(name='WaterEdgeMask',type='FLOAT_COLOR',domain='POINT')
    for data,weight in zip(colors.data,weights):data.color=(weight,weight,weight,1)
    mesh.color_attributes.active_color_index=len(mesh.color_attributes)-1
