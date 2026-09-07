"""Deterministic 100.8m Sunken Stars forest design; UE-facing metres."""
import math

MAP = '/Game/Astra/Maps/L_AstraStarPond'
SEED = 90784
RX, RY, WATER_Z = 12.0, 14.5, .80
DAIS = (-16., 0.)
GATE = (17.8, 0.)
ELEPHANT = (-1., 23.)
STARS = [(-8.,0.),(-5.2,-4.),(-2.,1.7),(1.1,-2.4),(4.,.9),(7.,0.)]
RING = [(17.4*math.cos(i*math.tau/48),20.2*math.sin(i*math.tau/48)) for i in range(49)]
PATHS = [[(-48,0),(-37,-2),(-28,1),DAIS],RING,
         [GATE,(25,0),(32,0),(39,5),(48,5)],[(0,20.2),ELEPHANT,(7,24),(11,18)]]
DEMO = [
 {'name':'SPArrival','points':[[-3000,80],[-2400,50],[-1950,0]],'seconds':8,'width':3700,'offset':[550,0,90]},
 {'name':'SPConstellation','points':[[-1740,0],[-1620,0],[-1510,0]],'seconds':8,'width':3500,'offset':[850,0,50]},
 {'name':'SPSilverLilies','points':[[-1500,-970],[-1230,-1420],[-900,-1720]],'seconds':8,'width':2400,'offset':[400,380,50]},
 {'name':'SPWillow','points':[[-700,-1840],[0,-2020],[700,-1840]],'seconds':9,'width':2900,'offset':[250,-400,170]},
 {'name':'SPCrescentGate','points':[[1580,-800],[1740,0],[2180,0]],'seconds':9,'width':3100,'offset':[250,0,230]},
 {'name':'SPElephant','points':[[650,1880],[200,2020],[-380,2020]],'seconds':9,'width':2200,'offset':[50,260,70]},
 {'name':'SPReturn','points':[[-1050,1600],[-1450,1100],[-1720,300]],'seconds':8,'width':3200,'offset':[550,-240,60]}
]

def smooth(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)

def segment_distance(x,y,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0.,min(1.,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)

def path_distance(x,y):
    return min(segment_distance(x,y,a,b) for path in PATHS for a,b in zip(path,path[1:]))

def demo_distance(x,y):
    return min(segment_distance(x,y,[a[0]/100,a[1]/100],[b[0]/100,b[1]/100]) for shot in DEMO for a,b in zip(shot['points'],shot['points'][1:]))

def rim(a):
    return 1+.042*math.sin(a*3+.4)+.024*math.sin(a*7)

def pond_distance(x,y):
    a=math.atan2(y/RY,x/RX)
    return math.hypot(x/RX,y/RY)/rim(a)

def height(x,y):
    r=pond_distance(x,y)
    h=1.18+.16*math.sin(x/9)*math.cos(y/7)+.06*math.sin((x+y)/5)
    forest=smooth(1.25,2.3,r)
    h+=forest*(.24*math.sin(x/6)*math.sin(y/8))
    edge=max(0,(max(abs(x),abs(y))-35)/15.4);h+=edge*edge*2.3
    # Flat accessible dais and guardian clearings with gradual joins.
    for c,rad in [(DAIS,3.5),(GATE,4.5),(ELEPHANT,3.8),((31,0),4.5)]:
        f=1-smooth(rad,rad+2,math.hypot(x-c[0],y-c[1]));h=h*(1-f)+1.18*f
    f=1-smooth(.90,1.12,r)
    bowl=-.70+1.25*min(r*r,1.)
    h=h*(1-f)+bowl*f
    return round(h*128)/128

def reserved(x,y,margin=0):
    if pond_distance(x,y)<1.30+margin/RX:return True
    if path_distance(x,y)<2.35+margin or demo_distance(x,y)<1.2+margin:return True
    return any(math.hypot(x-c[0],y-c[1])<r+margin for c,r in [(DAIS,5),(GATE,6),(ELEPHANT,5.5),((31,0),5.5)])
