"""Crystal cave design, meters in Unreal XY; Y runs entrance to crystal chamber."""
import math

SEED = 90726
ISLANDS = [(0, -9), (0, 8)]
SPAWN = (0, -21)

def height(x, y):
    # Shallow natural bedrock; all walking slopes remain gentle.
    return .23 + .10*math.sin(y*.27)*math.cos(x*.31) + .06*math.sin(x*.7+y*.23)

def half_width(y):
    return 6.8 + 2.9*math.exp(-((y+9)/5.8)**2) + 2.6*math.exp(-((y-8)/5.8)**2) + 1.7*math.exp(-((y-20)/4.5)**2) + 1.1*math.exp(-((y+21)/4)**2)

BRANCHES = {
    'fork1_left': [(0,-16),(-5.5,-14),(-5.5,-4),(0,-2)],
    'fork1_right': [(0,-16),(5.5,-14),(5.5,-4),(0,-2)],
    'fork2_left': [(0,1),(-5.5,3),(-5.5,13),(0,16)],
    'fork2_right': [(0,1),(5.5,3),(5.5,13),(0,16)],
}
FULL = [SPAWN,(0,-16),(-5.5,-14),(-5.5,-4),(0,-2),(0,1),(5.5,3),(5.5,13),(0,16),(0,21)]

def route_distance(x, y):
    d=1000
    for points in list(BRANCHES.values()) + [FULL]:
        for a,b in zip(points,points[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1]
            t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
            d=min(d,math.hypot(x-a[0]-t*dx,y-a[1]-t*dy))
    return d

def routes_json():
    def cm(points):return [[x*100,y*100] for x,y in points]
    return dict(schema_version=1, waypoint_tolerance_cm=45, max_segment_seconds=20, walk_speed_cm_s=260,
        bounds_cm=dict(min_x=-1480,max_x=1480,min_y=-2480,max_y=2480),
        routes=[dict(name='full_traversal',kind='walk',waypoints=cm(FULL))] +
        [dict(name=n,kind='walk',waypoints=cm(p)) for n,p in BRANCHES.items()] +
        [
         dict(name='island1_collision',kind='collision',expected_blocker_tag='CaveIsland',waypoints=cm([(-5.5,-9),(0,-9)])),
         dict(name='island2_collision',kind='collision',expected_blocker_tag='CaveIsland',waypoints=cm([(5.5,8),(0,8)])),
         dict(name='boundary_collision',kind='collision',expected_blocker_tag='CaveBoundary',waypoints=cm([(-5.5,-19),(-14,-19)])),
         dict(name='entrance_collision',kind='collision',expected_blocker_tag='CaveBoundary',waypoints=cm([(0,-21),(0,-26)]))])
