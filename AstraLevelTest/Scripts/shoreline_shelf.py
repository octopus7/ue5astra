"""Low-poly sand overlays for the lakeside asset library (Blender 4.5).

All coordinates are metres, with the nominal water plane at local Z = 0.
X follows the shore, +Y is land, and -Y points into the lake.  ``build_assets``
only creates linked mesh objects; scene assembly, saving and export belong to
the caller.  No bpy operators or context selection changes are required.
"""

from __future__ import annotations

import math
import random

import bpy


_MATERIAL_NAMES = ("M_ShoreSand", "M_ShoreSandLight", "M_ShoreSandDark")
_X_STATIONS = (-3.0, -2.2, -1.45, -0.7, 0.0, 0.8, 1.5, 2.25, 3.0)


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _bed_height(distance: float) -> float:
    """Artist-authored depth profile; distance is positive toward the lake."""
    profile = ((-0.4, 0.055), (0.0, 0.02), (0.6, -0.12),
               (1.25, -0.205), (2.0, -0.35), (3.0, -0.565),
               (4.0, -0.85), (4.5, -1.0))
    for (start, z_start), (end, z_end) in zip(profile, profile[1:]):
        if distance <= end:
            fraction = (distance - start) / (end - start)
            return z_start + fraction * (z_end - z_start)
    return profile[-1][1]


def _shore_offset(x: float, cove: bool) -> float:
    # The cove retreats into the land at its centre.  Its central nominal
    # waterline stays at the origin while both ends extend into the lake.
    if cove:
        return -0.70 * (1.0 - math.cos(math.pi * x / 3.0)) * 0.5
    return 0.045 * math.sin(math.pi * x / 3.0)


def _sand_region(x: float, y: float, z: float) -> int:
    """Continuous metre-scale colour fields, never per-face random colours."""
    tone = (0.49 + 0.16 * math.cos(x * 0.84 + y * 0.29)
            + 0.18 * math.sin(y * 1.02 - x * 0.34)
            - 0.09 * _clamp(-z / 1.5))
    if tone > 0.62:
        return 1
    if tone < 0.32:
        return 2
    return 0


def _build_shelf(materials: dict, *, name: str, cove: bool,
                 wet_width: float, seed: int) -> bpy.types.Object:
    rng = random.Random(seed)
    y_stations = (0.4, 0.0, -0.6, -1.25, -2.0,
                  -3.3 if cove else -3.0, -wet_width)
    columns, rows = len(_X_STATIONS), len(y_stations)
    vertices = []
    faces = []
    material_indices = []

    for row, base_y in enumerate(y_stations):
        for column, base_x in enumerate(_X_STATIONS):
            x, profile_y = base_x, base_y
            # Preserve all boundary points and the nominal waterline row.
            # Only wet interior samples jitter; this avoids regular diamonds
            # without creating gaps at a placed module's ends.
            interior = 0 < row < rows - 1 and 0 < column < columns - 1
            if interior and row != 1:
                x += rng.uniform(-0.14, 0.14)
                profile_y += rng.uniform(-0.075, 0.075)
            distance = -profile_y
            shore_weight = 1.0 - _clamp(distance / wet_width)
            y = profile_y + _shore_offset(x, cove) * shore_weight
            z = _bed_height(distance)
            # Very broad submerged relief, tapering out at dry and far edges.
            relief_weight = (math.sin(math.pi * _clamp(distance / wet_width))
                             * math.sin(math.pi * (x + 3.0) / 6.0))
            z += 0.029 * relief_weight * math.sin(x * 1.12 + distance * 0.73)
            vertices.append((x, y, z))

    def top_face(indices: tuple[int, int, int]) -> None:
        faces.append(indices)
        centre = tuple(sum(vertices[i][axis] for i in indices) / 3.0
                       for axis in range(3))
        material_indices.append(_sand_region(*centre))

    for row in range(rows - 1):
        for column in range(columns - 1):
            a = row * columns + column
            b, c, d = a + 1, a + columns, a + columns + 1
            # Choose mostly by the shorter diagonal, with deterministic
            # tie-breaking.  All top triangles face +Z.
            diagonal_ad = sum((vertices[a][axis] - vertices[d][axis]) ** 2
                              for axis in range(2))
            diagonal_bc = sum((vertices[b][axis] - vertices[c][axis]) ** 2
                              for axis in range(2))
            if diagonal_ad + rng.uniform(-0.12, 0.12) < diagonal_bc:
                top_face((a, c, d))
                top_face((a, d, b))
            else:
                top_face((a, c, b))
                top_face((b, c, d))

    top_face_count = len(faces)
    # Clockwise boundary viewed from above: top-left, top-right, bottom-right,
    # bottom-left.  Duplicate only this ring, not the whole top lattice.
    boundary = list(range(columns))
    boundary += [row * columns + columns - 1 for row in range(1, rows)]
    boundary += [(rows - 1) * columns + column
                 for column in range(columns - 2, -1, -1)]
    boundary += [row * columns for row in range(rows - 2, 0, -1)]
    bottom_start = len(vertices)
    bottom_z = -1.52
    for index in boundary:
        x, y, _ = vertices[index]
        vertices.append((x, y, bottom_z))
    bottom_centre = len(vertices)
    vertices.append((0.0, (0.4 - wet_width) * 0.5, bottom_z))

    for ring_index, top_a in enumerate(boundary):
        next_ring = (ring_index + 1) % len(boundary)
        top_b = boundary[next_ring]
        bottom_a, bottom_b = bottom_start + ring_index, bottom_start + next_ring
        # This winding is the opposite of the adjoining top boundary edge.
        faces.extend(((top_a, top_b, bottom_b), (top_a, bottom_b, bottom_a)))
        material_indices.extend((2, 2))
        faces.append((bottom_centre, bottom_a, bottom_b))
        material_indices.append(2)

    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for material_name in _MATERIAL_NAMES:
        mesh.materials.append(materials[material_name])
    for polygon, material_index in zip(mesh.polygons, material_indices):
        polygon.material_index = material_index
        polygon.use_smooth = False

    uv_map = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        # Preserve metre-scaled XY on the visible sand.  Vertical closure
        # skirts need their own projection: XY would collapse each into a
        # line.  Dominant-plane projection also keeps the bottom nonzero.
        if polygon.index < top_face_count:
            axes = (0, 1)
        else:
            dominant_axis = max(range(3), key=lambda axis: abs(polygon.normal[axis]))
            axes = ((1, 2), (0, 2), (0, 1))[dominant_axis]
        for loop_index in polygon.loop_indices:
            co = vertices[mesh.loops[loop_index].vertex_index]
            uv_map.data[loop_index].uv = (co[axes[0]], co[axes[1]])

    shore_data = mesh.color_attributes.new(name="ShoreData", type="FLOAT_COLOR",
                                           domain="POINT")
    for index, (_, y, z) in enumerate(vertices):
        shore_data.data[index].color = (_clamp(-z / 1.5), _clamp(-y / 4.0), 0.0, 1.0)

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["shore_kind"] = "shallow_shelf"
    obj["nominal_length_m"] = 6.0
    obj["nominal_wet_width_m"] = wet_width
    obj["land_underlap_m"] = 0.4
    obj["waterline_z_m"] = 0.0
    obj["collision"] = "none"
    obj["top_triangle_count"] = top_face_count
    obj["generation_seed"] = seed
    obj["description_ko"] = (
        "중앙으로 완만하게 들어간 작은 만의 밝은 모래 수중 선반. "
        if cove else "완만하게 깊어지는 밝은 모래 수중 선반. "
    ) + "해안 중앙이 원점이며 +Y는 육지, -Y는 호수. 기존 지형 위 배치용."
    return obj


def build_assets(materials: dict) -> list[bpy.types.Object]:
    """Create two closed, flat-shaded shelf meshes using caller materials.

    The nominal widths refer to the water-side span; each mesh also includes
    0.4 m of land underlap.  Geometry is authored at the origin with rotation
    zero and scale one.  Side/bottom skirts must be buried in the landscape.
    ShoreData G intentionally uses the shared 4 m normalisation for both.
    """
    missing = [name for name in _MATERIAL_NAMES if name not in materials]
    if missing:
        raise KeyError("Missing shelf materials: " + ", ".join(missing))
    return [
        _build_shelf(materials, name="SM_ShallowShelf_01", cove=False,
                     wet_width=4.0, seed=58014),
        _build_shelf(materials, name="SM_ShallowShelf_Cove_01", cove=True,
                     wet_width=4.5, seed=58015),
    ]
