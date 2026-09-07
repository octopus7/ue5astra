"""Deterministic metre-space design shared by Blender, UE and validation."""
import math
SEED=90792
MAP='/Game/Astra/Maps/L_AstraRootBelltower'
TOWER=(6.,0.);TREE=(11.,0.);COURTYARD=(-6.,0.);ARCH=(-3.,-14.);CLOISTER=(-13.,12.)
PATHS=[
 [(-49,-2),(-36,-2),(-28,-2),(-21,0),(-13,0),(-6,0),(0,0)],
 [(-21,0),(-18,-10),(-12,-14),(-8,-14),(-3,-14),(3,-14),(13,-18),(23,-12),(24,-3),(22,10),(14,19),(6,20),(-4,21),(-13,17),(-21,15),(-24,6),(-21,0)],
 [(-13,0),(-13,6),(-13,12),(-13,17)],
 [(14,19),(23,29),(26,40),(26,49)],
 [(-21,15),(-34,23),(-49,27)],
]
DEMO=[
 dict(name='RBArrival',points=[[-3600,-200],[-2800,-200],[-2100,0]],seconds=9,width=3600,offset=[650,0,420]),
 dict(name='RBCourtyard',points=[[-1300,0],[-800,-200],[-600,0]],seconds=8,width=3600,offset=[700,0,520]),
 dict(name='RBRootArch',points=[[-800,-1400],[-300,-1400],[300,-1400]],seconds=9,width=3000,offset=[400,180,150]),
 dict(name='RBOldTree',points=[[2300,-1200],[2400,-300],[2200,1000]],seconds=13,width=3800,offset=[-500,0,520]),
 dict(name='RBFallenGarden',points=[[600,2000],[-400,2100],[-1200,2000]],seconds=11,width=3000,offset=[0,-300,160]),
 dict(name='RBCloister',points=[[-1300,600],[-1300,1200],[-1300,1700]],seconds=9,width=2800,offset=[250,0,130]),
 dict(name='RBReturn',points=[[-2100,1500],[-2400,600],[-2700,-200]],seconds=11,width=3300,offset=[550,0,400]),
]
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def segment_distance(x,y,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1];l=dx*dx+dy*dy
    t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/l)) if l else 0
    return math.hypot(x-a[0]-dx*t,y-a[1]-dy*t)
def path_distance(x,y):return min(segment_distance(x,y,a,b) for line in PATHS for a,b in zip(line,line[1:]))
def demo_distance(x,y):return min(segment_distance(x,y,[a[0]/100,a[1]/100],[b[0]/100,b[1]/100]) for s in DEMO for a,b in zip(s['points'],s['points'][1:]))
def height(x,y):
    radius=math.hypot(x-2,y*.95)
    h=1.2+.32*math.sin(x*.10)*math.cos(y*.09)+.18*math.sin((x+y)*.2)
    return 1.55*(1-smooth(22,31,radius))+h*smooth(22,31,radius)
def reserved(x,y,pad=0):
    if path_distance(x,y)<2.15+pad or demo_distance(x,y)<1.2+pad:return True
    if -18-pad<x<20+pad and abs(y)<10+pad:return True
    if any(math.hypot(x-c[0],y-c[1])<r+pad for c,r in [(COURTYARD,8),(ARCH,5),(CLOISTER,4)]):return True
    return False
