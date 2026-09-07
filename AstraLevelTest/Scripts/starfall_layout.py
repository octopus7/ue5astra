"""Shared, deterministic Starfall design in Unreal-facing metres (X north, Y east)."""
import math
MAP='/Game/Astra/Maps/L_AstraStarfall'
SIZE=100.8
SEED=90773
SHIP=(3.5,1.0)
MUSHROOM=(8.0,-28.0)
GLOW=(-24.0,-29.0)
SPRING=(30.0,27.0)
PONDS=[{'name':'WestPuddle','center':(-18,-9),'radii':(5.4,3.7),'z':.62},
       {'name':'EastPuddle','center':(-21,24),'radii':(6.0,4.1),'z':.73},
       {'name':'NorthPuddle','center':(26,-6),'radii':(4.2,3.1),'z':.93}]
PATHS=[
 [(-48,0),(-37,0),(-30,-4),(-27,-16),(-21,-23),(-12,-22),(-7,-16),(-13,-6),(-14,4),(-7,14),(4,17),(15,18),(24,20),(27,25)],
 [(-7,-16),(0,-17),(8,-17),(17,-20),(20,-27),(28,-28),(35,-20),(35,-8),(29,4),(20,9),(15,18)],
 [(-14,4),(-19,8),(-27,12),(-31,23),(-30,33),(-21,36),(-12,31),(-7,22),(-7,14)],
 [(24,20),(35,21),(38,28),(35,35),(27,37),(23,31),(24,20)]
]
DEMO=[
 {'name':'SFClearing','points':[[-900,-450],[-700,0],[-550,600]],'seconds':9,'width':3000,'offset':[530,50,260]},
 {'name':'SFMushrooms','points':[[0,-1700],[600,-1700],[1300,-1800]],'seconds':10,'width':2700,'offset':[0,-550,70]},
 {'name':'SFGlow','points':[[-2750,-1750],[-2350,-2200],[-1900,-2300]],'seconds':9,'width':2400,'offset':[-150,-480,65]},
 {'name':'SFSpring','points':[[2400,2000],[3000,2100],[3500,2100]],'seconds':10,'width':2800,'offset':[80,450,90]},
 {'name':'SFOldLogs','points':[[2000,-2700],[2800,-2800],[3400,-2100]],'seconds':10,'width':2700,'offset':[100,130,80]},
 {'name':'SFPuddles','points':[[-1900,800],[-2500,1100],[-3000,1800]],'seconds':10,'width':2800,'offset':[500,600,90]},
 {'name':'SFLanding','points':[[-800,850],[-100,1200],[750,1000]],'seconds':11,'width':3400,'offset':[300,-250,320]}
]
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def segment_distance(x,y,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)
def path_distance(x,y):return min(segment_distance(x,y,a,b) for path in PATHS for a,b in zip(path,path[1:]))
def demo_distance(x,y):return min(segment_distance(x,y,[a[0]/100,a[1]/100],[b[0]/100,b[1]/100]) for shot in DEMO for a,b in zip(shot['points'],shot['points'][1:]))
def ellipse(x,y,center,radii):return math.hypot((x-center[0])/radii[0],(y-center[1])/radii[1])
def pond_radius(angle,index):return 1+.047*math.sin(3*angle+index)+.033*math.sin(7*angle+.7*index)
def pond_distance(x,y,p,index):
    a=math.atan2((y-p['center'][1])/p['radii'][1],(x-p['center'][0])/p['radii'][0])
    return ellipse(x,y,p['center'],p['radii'])/pond_radius(a,index)
def height(x,y):
    h=1.06+.18*math.sin(x/8)*math.cos(y/11)+.08*math.sin((x+y)/5)
    edge=max(0,(max(abs(x),abs(y))-34)/16.4);h+=edge*edge*1.8
    h+=.45*math.exp(-((x-29)/18)**2-((y-27)/15)**2)
    clearing=1-smooth(11,16,math.hypot(x-SHIP[0],y-SHIP[1]));h=h*(1-clearing)+1.1*clearing
    for i,p in enumerate(PONDS):
        d=pond_distance(x,y,p,i);mix=1-smooth(.84,1.18,d)
        floor=p['z']-.28+.075*min(d*d,1);h=h*(1-mix)+floor*mix
    sr=math.hypot(x-SPRING[0],y-SPRING[1]);rim=1-smooth(2.6,4.9,sr)
    h=h*(1-rim)+1.49*rim
    bowl=1-smooth(1.55,2.05,sr);h=h*(1-bowl)+.93*bowl
    return round(h*128)/128
def habitat(x,y):
    if abs(x-MUSHROOM[0])<=7.5 and abs(y-MUSHROOM[1])<=7.5:return 'MushroomMeadow15m'
    if abs(x-GLOW[0])<=2.5 and abs(y-GLOW[1])<=2.5:return 'GlowGrove5m'
    return 'Forest'
def reserved(x,y,margin=0):
    if path_distance(x,y)<1.8+margin or demo_distance(x,y)<.85+margin:return True
    if math.hypot(x-SHIP[0],y-SHIP[1])<14+margin:return True
    if abs(x-MUSHROOM[0])<8+margin and abs(y-MUSHROOM[1])<8+margin:return True
    if abs(x-GLOW[0])<3.3+margin and abs(y-GLOW[1])<3.3+margin:return True
    if math.hypot(x-SPRING[0],y-SPRING[1])<9+margin:return True
    return any(pond_distance(x,y,p,i)<1.2+margin/min(p['radii']) for i,p in enumerate(PONDS))
