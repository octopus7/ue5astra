"""Small grass-and-earth banks for the lakeside shoreline asset library.

Blender 4.5, metre units.  +X follows the coast, +Y points inland, and the
intended water plane is local Z=0.  The origin sits on the middle shoreline.
These are overlapping/buryable pieces, not mathematically tiling modules.
Only build_assets() creates objects; importing this module has no scene effects.
"""

import math

import bmesh
import bpy


_MATERIAL_KEYS = (
    "M_ShoreGrass",
    "M_ShoreGrassLight",
    "M_ShoreEarth",
    "M_ShoreEarthLight",
)

# Few deliberately spaced sections make broad facets instead of noisy teeth.
_SECTIONS_X = (-2.0, -1.60, -1.05, -0.50, 0.0, 0.57, 1.10, 1.57, 2.0)
_VARIANTS = (
    {
        "name": "SM_ShoreBank_Straight_01",
        "edge": (-0.035, -0.105, -0.075, 0.055, 0.0, 0.095, 0.020, -0.080, -0.015),
        "height": (0.315, 0.355, 0.365, 0.310, 0.340, 0.395, 0.380, 0.325, 0.335),
        "toe": (-0.330, -0.360, -0.395, -0.375, -0.350, -0.365, -0.400, -0.345, -0.330),
        "soil_cap_sections": (2, 3),
        "light_grass_sections": (0, 1, 6, 7),
        "description_ko": "넓고 완만한 굴곡의 풀 상단과 낮은 흙 절개면이 있는 직선형 호숫가. 양끝과 뒤쪽은 지형에 묻어 연결한다.",
    },
    {
        "name": "SM_ShoreBank_Curve_01",
        # Ends project lakeward; the central recess receives water (+Y).
        "edge": (-0.230, -0.200, -0.125, -0.015, 0.0, -0.020, -0.070, -0.170, -0.220),
        "height": (0.355, 0.375, 0.325, 0.310, 0.350, 0.380, 0.395, 0.360, 0.335),
        "toe": (-0.350, -0.385, -0.375, -0.330, -0.345, -0.395, -0.405, -0.370, -0.345),
        "soil_cap_sections": (0, 1, 5),
        "light_grass_sections": (3, 4, 5),
        "description_ko": "호수가 육지 안으로 살짝 들어오는 오목한 해안형. 낮은 풀턱 아래 흙면과 잠긴 받침이 이어지며 양끝은 매립 또는 겹침 배치한다.",
    },
    {
        "name": "SM_ShoreBank_Low_01",
        "edge": (-0.020, 0.065, 0.115, 0.055, 0.0, -0.080, -0.100, 0.015, 0.050),
        "height": (0.170, 0.190, 0.215, 0.195, 0.165, 0.145, 0.180, 0.205, 0.190),
        "toe": (-0.270, -0.290, -0.325, -0.300, -0.270, -0.285, -0.315, -0.300, -0.285),
        "soil_cap_sections": (3, 4, 5),
        "light_grass_sections": (0, 1, 2),
        "description_ko": "흙턱이 낮아지고 물가 쪽으로 부드럽게 닳은 침식형 해안. 얕은 모래 선반으로 전환할 구간에 겹쳐 배치한다.",
    },
)


def _section_points(index, variant):
    """A continuous closed cross section, starting at the submerged toe."""
    x = _SECTIONS_X[index]
    edge = variant["edge"][index]
    crest = variant["height"][index]
    toe_z = variant["toe"][index]
    is_low = variant["name"] == "SM_ShoreBank_Low_01"

    # Large-scale variation is shared by adjacent rings; no per-face randomness.
    phase = math.pi * (x + 2.0) / 4.0
    toe_width = (0.58 if is_low else 0.56) + 0.045 * math.sin(phase * 2.0 + 0.3)
    shoulder_width = 0.275 + 0.035 * math.cos(phase * 2.0 - 0.4)
    rear_y = 1.19 + 0.055 * math.sin(phase * 1.7 + 0.25)
    middle_y = edge + 0.67 + 0.035 * math.cos(phase * 1.5)
    rear_z = (0.185 if is_low else 0.335) + 0.024 * math.sin(phase * 1.4 + 0.3)
    shoulder_z = crest + (0.019 if is_low else 0.030)
    middle_z = 0.52 * shoulder_z + 0.48 * rear_z + 0.014 * math.sin(phase * 1.8)

    # Narrow, near-vertical upper face on the cut banks; longer eroded ramp below.
    water_y = edge - (0.275 if is_low else 0.145)
    face_y = edge - (0.090 if is_low else 0.012)
    face_z = crest * (0.43 if is_low else 0.47)
    return (
        (x, edge - toe_width, toe_z),
        (x, water_y, -0.045 if is_low else -0.065),
        (x, face_y, face_z),
        (x, edge + 0.025, crest),
        (x, edge + shoulder_width, shoulder_z),
        (x, middle_y, middle_z),
        (x, rear_y, rear_z),
        (x, rear_y - 0.025, -0.72),
        (x, edge - toe_width + 0.025, -0.72),
    )


def _strip_material(section, profile_edge, variant):
    """Contiguous surface regions avoid random triangle/checkerboard colours."""
    if profile_edge in (3, 4, 5):
        if profile_edge == 3 and section in variant["soil_cap_sections"]:
            return 3  # Exposed dry earth on a worn part of the upper rim.
        if profile_edge >= 4 and section in variant["light_grass_sections"]:
            return 1
        return 0
    if profile_edge == 2:
        # A dry upper earth band remains distinct from the submerged lower face.
        return 3
    if profile_edge == 1 and section in variant["soil_cap_sections"]:
        return 3
    return 2


def _add_uvs_and_data(mesh):
    uv = mesh.uv_layers.new(name="UVMap")
    # Metre-based coordinates keep texel density equal on separate bank pieces.
    # Choose each face's dominant plane so vertical cuts do not collapse in UVs.
    for face in mesh.polygons:
        normal = face.normal
        axis = max(range(3), key=lambda candidate: abs(normal[candidate]))
        for loop_index in face.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            if axis == 2:
                pair = (co.x / 2.0, co.y / 2.0)
            elif axis == 1:
                pair = (co.x / 2.0, co.z / 2.0)
            else:
                pair = (co.y / 2.0, co.z / 2.0)
            uv.data[loop_index].uv = pair

    shore_data = mesh.color_attributes.new(
        name="ShoreData", type="FLOAT_COLOR", domain="POINT"
    )
    for vertex, color in zip(mesh.vertices, shore_data.data):
        color.color = (
            min(1.0, max(0.0, -vertex.co.z / 1.5)),
            min(1.0, max(0.0, -vertex.co.y / 4.0)),
            0.0,
            1.0,
        )


def _build_bank(variant, materials):
    vertices = []
    faces = []
    material_indices = []
    points_per_section = 9
    for index in range(len(_SECTIONS_X)):
        vertices.extend(_section_points(index, variant))

    for section in range(len(_SECTIONS_X) - 1):
        for edge in range(points_per_section):
            next_edge = (edge + 1) % points_per_section
            left = section * points_per_section
            right = (section + 1) * points_per_section
            faces.append((left + edge, right + edge, right + next_edge, left + next_edge))
            material_indices.append(_strip_material(section, edge, variant))

    # End caps close the skirt as well. They are intentionally buried/overlapped.
    faces.append(tuple(range(points_per_section - 1, -1, -1)))
    material_indices.append(2)
    last = (len(_SECTIONS_X) - 1) * points_per_section
    faces.append(tuple(last + index for index in range(points_per_section)))
    material_indices.append(2)

    name = variant["name"]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    for key in _MATERIAL_KEYS:
        mesh.materials.append(materials[key])
    for face, material_index in zip(mesh.polygons, material_indices):
        face.material_index = material_index
        face.use_smooth = False
    mesh.update()

    # Explicit triangles keep the authored faceted silhouette identical in FBX.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    _add_uvs_and_data(mesh)

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["asset_id"] = name
    obj["shore_kind"] = "low_bank"
    obj["nominal_length_m"] = 4.0
    obj["waterline_z_m"] = 0.0
    obj["collision"] = "none"
    obj["description_ko"] = variant["description_ko"]
    obj["placement_note_ko"] = "육지는 로컬 +Y, 호수는 -Y. 물높이는 Z=0. 밑면은 Z=-0.72m까지 매립한다. 반복 타일 규격이 아니므로 양끝과 뒤쪽을 지형 안에 묻거나 겹친다."
    return obj


def build_assets(materials) -> list[bpy.types.Object]:
    """Build three independent manifold bank meshes using the shared palette.

    The caller owns scene setup, object arrangement, saving, exporting, rendering,
    and eventual level-specific collision decisions.
    """
    missing = [key for key in _MATERIAL_KEYS if key not in materials]
    if missing:
        raise KeyError("Missing shoreline materials: " + ", ".join(missing))
    return [_build_bank(variant, materials) for variant in _VARIANTS]
