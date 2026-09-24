"""Continuous waterfall surface, split into two assets on an identical edge (cm)."""
import math


def build_flow_surfaces():
    cols = 12
    # One ordered centerline: shallow stream, rounded crest, unchanged lower fall.
    rows = []
    for j in range(9):
        q = j / 8
        rows.append((180 - 50*q, 229 - 5*(3*q*q - 2*q*q*q), -.18*50/55*(1-q)))
    seam = len(rows)-1
    for j in range(1, 13):
        q = j/12
        a = 1-q
        y = a**3*130 + 3*a*a*q*102 + 3*a*q*q*75.75 + q**3*75
        z = a**3*224 + 3*a*a*q*224 + 3*a*q*q*220 + q**3*212
        rows.append((y, z, .18*q))
    for j in range(1, 26):
        q = j/25
        rows.append((75-42*q+7*math.sin(q*math.pi), 212-214*q, .18+.82*q))
    distances = [0.0]
    for a, b in zip(rows, rows[1:]):
        distances.append(distances[-1]+math.hypot(b[0]-a[0], b[1]-a[1]))
    length = distances[-1]-distances[seam]
    vertices, uvs = [], []
    for row, distance in zip(rows, distances):
        y, z, t = row
        width = 47+9*t+12*t**7
        for i in range(cols+1):
            u = i/cols
            vertices.append(((u*2-1)*width,
                y+2.3*math.sin(u*math.pi*5+t*10), z+1.1*math.cos(u*math.pi*4)))
            # Both assets share the same metric and phase. Upstream V is negative.
            uvs.append((u, (distance-distances[seam])/length))

    def section(first, last):
        start = first*(cols+1)
        end = (last+1)*(cols+1)
        faces = []
        for j in range(last-first):
            for i in range(cols):
                a = j*(cols+1)+i
                faces.append((a,a+1,a+cols+2,a+cols+1))
        return vertices[start:end], faces, uvs[start:end]

    upper = section(0, seam)
    curtain = section(seam, len(rows)-1)
    assert upper[0][-(cols+1):] == curtain[0][:cols+1]
    assert upper[2][-(cols+1):] == curtain[2][:cols+1]
    return {'SM_WF_UpperStream': upper, 'SM_WF_WaterCurtain': curtain}
