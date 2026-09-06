"""Build four submerged-stone assets in metres for Blender 4.5.

The integration script owns collections, scene setup, saving and exports. This
module only creates and links the returned meshes. Stone colours are supplied by
the caller: water colour and depth masks belong to placement and water shading.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping

import bmesh
import bpy
from mathutils import Vector


_MATERIAL_KEYS = (
    "M_SubmergedStone",
    "M_SubmergedStoneLight",
    "M_SubmergedStoneDark",
)


def _stone_geometry(
    dimensions: tuple[float, float, float],
    seed: int,
    *,
    small: bool = False,
    flat: bool = False,
) -> tuple[list[Vector], list[tuple[int, ...]]]:
    """Form a closed, rounded hull from deliberately unequal latitude rings.

    Differing ring populations, offset angles and correlated silhouette changes
    avoid the repeated equilateral facets of a subdivision-one icosphere. The
    shallow upper ring leaves a few broad crown facets instead of a pointed tip.
    """
    rng = random.Random(seed)
    counts = (7, 9, 8, 7, 5) if small else (9, 11, 10, 8, 5)
    heights = (0.0, 0.19, 0.48, 0.82, 1.0)
    radii = (0.44, 0.84, 1.0, 0.79, 0.38)
    if flat:
        heights = (0.0, 0.18, 0.44, 0.78, 1.0)
        radii = (0.48, 0.87, 1.0, 0.86, 0.46)

    phase = rng.uniform(0.0, math.tau)
    lobe_phase = rng.uniform(0.0, math.tau)
    crown_shift = Vector((rng.uniform(-0.13, 0.13), rng.uniform(-0.12, 0.12)))
    points = []
    for ring, (count, height, radius) in enumerate(zip(counts, heights, radii)):
        angular_offset = phase + (0.12, -0.03, 0.10, -0.08, 0.20)[ring]
        for step in range(count):
            angle = angular_offset + math.tau * (step + rng.uniform(-0.11, 0.11)) / count
            silhouette = (
                1.0
                + 0.075 * math.sin(3.0 * angle + lobe_phase)
                + 0.04 * math.cos(2.0 * angle - 0.6)
            )
            reach = radius * silhouette * rng.uniform(0.965, 1.035)
            x = math.cos(angle) * reach + crown_shift.x * height
            y = math.sin(angle) * reach + crown_shift.y * height
            # Keep the crown/base rings planar. Intermediate asymmetry gives
            # broad irregular facets without corrugating the contact surface.
            z = height if ring in (0, 4) else height + rng.uniform(-0.037, 0.037)
            points.append((x + 0.055 * y * y, y, z))

    bm = bmesh.new()
    try:
        for point in points:
            bm.verts.new(point)
        bm.verts.ensure_lookup_table()
        bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
        unused = [vertex for vertex in bm.verts if not vertex.link_faces]
        if unused:
            bmesh.ops.delete(bm, geom=unused, context="VERTS")
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.verts.index_update()
        vertices = [vertex.co.copy() for vertex in bm.verts]
        faces = [tuple(vertex.index for vertex in face.verts) for face in bm.faces]
    finally:
        bm.free()

    return _fit_dimensions(vertices, dimensions), faces


def _fit_dimensions(vertices: list[Vector], dimensions: tuple[float, float, float]) -> list[Vector]:
    """Bake exact dimensions, centred XY bounds and bottom contact at z = 0."""
    minimum = Vector(tuple(min(vertex[axis] for vertex in vertices) for axis in range(3)))
    maximum = Vector(tuple(max(vertex[axis] for vertex in vertices) for axis in range(3)))
    extent = maximum - minimum
    result = []
    for vertex in vertices:
        point = Vector(tuple((vertex[axis] - minimum[axis]) / extent[axis] * dimensions[axis] for axis in range(3)))
        point.x -= dimensions[0] * 0.5
        point.y -= dimensions[1] * 0.5
        result.append(point)
    return result


def _face_uv_atlas(mesh: bpy.types.Mesh) -> None:
    """Assign separate, non-overlapping planar UV islands without operators."""
    uv = mesh.uv_layers.new(name="UVMap")
    columns = math.ceil(math.sqrt(len(mesh.polygons)))
    rows = math.ceil(len(mesh.polygons) / columns)
    for face in mesh.polygons:
        points = [mesh.vertices[index].co for index in face.vertices]
        origin = points[0]
        tangent = (points[1] - origin).normalized()
        bitangent = face.normal.cross(tangent).normalized()
        coordinates = [((point - origin).dot(tangent), (point - origin).dot(bitangent)) for point in points]
        min_u = min(point[0] for point in coordinates)
        min_v = min(point[1] for point in coordinates)
        span = max(
            max(point[0] for point in coordinates) - min_u,
            max(point[1] for point in coordinates) - min_v,
        )
        column, row = face.index % columns, face.index // columns
        for loop_index, (u, v) in zip(face.loop_indices, coordinates):
            uv.data[loop_index].uv = (
                (column + 0.10 + 0.80 * (u - min_u) / span) / columns,
                (row + 0.10 + 0.80 * (v - min_v) / span) / rows,
            )


def _make_object(
    name: str,
    vertices: list[Vector],
    faces: list[tuple[int, ...]],
    materials: Mapping[str, bpy.types.Material],
    seed: int,
    description: str,
    *,
    cluster: bool = False,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for key in _MATERIAL_KEYS:
        mesh.materials.append(materials[key])

    rng = random.Random(seed + 1024)
    light_direction = Vector((-0.35, -0.48, 0.80)).normalized()
    for face in mesh.polygons:
        face.use_smooth = True
        # Restrained neutral facets keep rocks legible below the water without
        # baking teal colour, caustics, moss blankets or directional shadows.
        if face.normal.z < -0.12:
            face.material_index = 2
        elif face.normal.dot(light_direction) > 0.38 and rng.random() < 0.63:
            face.material_index = 1
        elif face.normal.z < 0.34 and rng.random() < 0.16:
            face.material_index = 2
        else:
            face.material_index = 0

    _face_uv_atlas(mesh)
    shore = mesh.color_attributes.new(name="ShoreData", type="FLOAT_COLOR", domain="POINT")
    for value in shore.data:
        value.color = (0.0, 0.0, 0.0, 1.0)
    mesh.color_attributes.active_color = shore

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["asset_id"] = name
    obj["shore_kind"] = "pebble_cluster" if cluster else "submerged_rock"
    obj["collision"] = "none"
    obj["description_ko"] = description
    obj["pivot_note"] = "bottom_contact"
    obj["units"] = "metres"
    obj["generation_seed"] = seed
    return obj


def build_assets(materials: Mapping[str, bpy.types.Material]) -> list[bpy.types.Object]:
    """Create three single stones and one six-pebble cluster, returning them.

    Required keys are M_SubmergedStone, M_SubmergedStoneLight and
    M_SubmergedStoneDark. Existing scene objects and supplied materials are not
    edited. Every returned object has identity transforms and an XY-centred,
    bottom-contact origin; each stone is a closed manifold component.
    """
    missing = [key for key in _MATERIAL_KEYS if key not in materials]
    if missing:
        raise KeyError(f"Missing submerged stone materials: {', '.join(missing)}")

    specifications = (
        ("SM_SubmergedRock_Round_01", (1.0, 0.8, 0.45), 7401, False, False,
         "얕은 호수 바닥용 둥근 회베이지 돌. 넓은 윗면과 낮은 옆면으로 수중 실루엣을 구분한다."),
        ("SM_SubmergedRock_Flat_01", (1.25, 0.8, 0.25), 7402, False, True,
         "모래 선반에 놓는 납작하고 넓은 수중돌. 불규칙한 둥근 모서리와 큰 상단 면을 가진다."),
        ("SM_SubmergedRock_Small_01", (0.6, 0.45, 0.28), 7403, True, False,
         "큰 돌 사이에 배치하는 작은 수중돌. 중성 석재색을 유지하며 물의 청록색은 수면에서 표현한다."),
    )
    result = []
    for name, dimensions, seed, small, flat, description in specifications:
        vertices, faces = _stone_geometry(dimensions, seed, small=small, flat=flat)
        result.append(_make_object(name, vertices, faces, materials, seed, description))

    # Six distinct closed components, with open gaps and no hidden sand plane.
    # A dominant stone, three medium companions and two small outliers form an
    # asymmetric scatter. Unequal offsets break both rows and regular rings.
    # Placement rotations are baked into coordinates so integration can instance
    # the cluster using the same simple transform conventions as single stones.
    pebble_layout = (
        ((-0.21, 0.00), (0.60, 0.44, 0.29), 0.62),
        ((0.39, 0.13), (0.42, 0.32, 0.23), -0.93),
        ((-0.55, -0.31), (0.25, 0.20, 0.16), -0.21),
        ((-0.52, 0.42), (0.32, 0.24, 0.19), 1.23),
        ((0.24, -0.39), (0.33, 0.25, 0.21), 0.37),
        ((0.02, 0.36), (0.20, 0.16, 0.12), -1.48),
    )
    cluster_vertices, cluster_faces = [], []
    for index, (position, dimensions, yaw) in enumerate(pebble_layout):
        vertices, faces = _stone_geometry(dimensions, 7420 + index, small=True, flat=index % 2 == 0)
        offset = len(cluster_vertices)
        cosine, sine = math.cos(yaw), math.sin(yaw)
        for vertex in vertices:
            cluster_vertices.append(Vector((
                vertex.x * cosine - vertex.y * sine + position[0],
                vertex.x * sine + vertex.y * cosine + position[1],
                vertex.z,
            )))
        cluster_faces.extend(tuple(offset + vertex for vertex in face) for face in faces)
    cluster_vertices = _fit_dimensions(cluster_vertices, (1.6, 1.1, 0.32))
    cluster = _make_object(
        "SM_SubmergedPebbles_01", cluster_vertices, cluster_faces, materials, 7420,
        "모래 바닥에 드문드문 놓인 작은 수중돌 여섯 개. 각 돌은 닫힌 메시이며 모래판이나 물 색은 포함하지 않는다.",
        cluster=True,
    )
    cluster["component_count"] = len(pebble_layout)
    result.append(cluster)
    return result
