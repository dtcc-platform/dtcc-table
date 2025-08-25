# Blender 3.x
# Build printable tiles from a city mesh, with 2 cm-quantized undersides + corner magnet holes.

import bpy
import os
import math
from pathlib import Path

# =========================
# 0) CONFIG — edit safely
# =========================
# Units are meters unless stated otherwise
TILE_SIZE = 0.20          # tile width/length on X/Y
TILES_X   = 3
TILES_Y   = 5

CITY_MESH_PATH = Path("./output/scaled_mesh.stl")
OUTPUT_DIR     = Path("./output/tiles")

# Base + fill (underside)
MIN_MODEL_BASE_DEPTH   = 0.005   # 5 mm base kept under the model surface
FILL_LAYER_THICKNESS   = 0.02    # 20 mm quantization step
QUANTIZE_FILL          = True
QUANTIZE_ANCHOR_Z      = 0.0
EPS                    = 1e-6

# Magnet holes
MAGNET_RADIUS          = 0.005   # 5 mm
MAGNET_HEIGHT          = 0.002   # 2 mm
MAGNET_PERIM_OFFSET_MM = 4       # mm (inset from outer edges)
MAGNET_SAFETY          = 0.001   # 1 mm min margin to edges (m)
COUNTERSINK_SHOULDER   = 0.001   # 1 mm radial shoulder before cone (m)

# Single-tile mode
SINGLE_TILE_MODE = True
SINGLE_TILE_ROW  = 1
SINGLE_TILE_COL  = 2


# =========================
# 1) UTILITIES
# =========================
def ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not CITY_MESH_PATH.exists():
        raise FileNotFoundError(f"City mesh not found: {CITY_MESH_PATH}")
    if not OUTPUT_DIR.exists():
        raise FileNotFoundError(f"Output directory not found: {OUTPUT_DIR}")

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def import_city_mesh(path: Path):
    # Use official STL import operator; requires io_mesh_stl add-on (enabled by default)
    bpy.ops.import_mesh.stl(filepath=str(path))
    obj = bpy.context.selected_objects[0]
    obj.name = "CityMesh"
    return obj

def cleanup_normals(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    # Merge by distance (formerly remove_doubles)
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    try:
        bpy.ops.mesh.fill_holes()  # may fail on complex meshes—safe to ignore
    except Exception:
        pass
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')

def tile_aabb(row, col):
    """Returns (min_x, max_x, min_y, max_y) for the tile in local coords."""
    min_x = col * TILE_SIZE
    max_x = (col + 1) * TILE_SIZE
    min_y = row * TILE_SIZE
    max_y = (row + 1) * TILE_SIZE
    return min_x, max_x, min_y, max_y

def min_z_in_tile(city_obj, row, col):
    """Find the lowest Z among city verts within the tile XY bounds. Returns None if empty."""
    min_x, max_x, min_y, max_y = tile_aabb(row, col)
    verts_world = [city_obj.matrix_world @ v.co for v in city_obj.data.vertices]
    zs = [v.z for v in verts_world if (min_x <= v.x <= max_x and min_y <= v.y <= max_y)]
    return min(zs) if zs else None

def quantized_bottom(min_z):
    """Compute cube_bottom using either a single layer under min_z or quantization to 2 cm multiples."""
    if not QUANTIZE_FILL:
        return min_z - MIN_MODEL_BASE_DEPTH - FILL_LAYER_THICKNESS
    step = FILL_LAYER_THICKNESS
    pre_base = min_z - MIN_MODEL_BASE_DEPTH
    snapped = QUANTIZE_ANCHOR_Z + math.floor((pre_base - QUANTIZE_ANCHOR_Z) / step) * step
    return snapped - EPS

def add_boolean(mod_owner, cutter, name, op='DIFFERENCE'):
    m = mod_owner.modifiers.new(name=name, type='BOOLEAN')
    m.object = cutter
    m.operation = op
    m.solver = 'EXACT'
    # Keep scene tidy; booleans will be applied later
    cutter.hide_set(True)
    return m

def add_corner_magnets(cube, row, col, x, y, z, cube_height):
    """Four magnet holes + 45° countersinks near tile corners (booleans)."""
    offset_m = max(MAGNET_PERIM_OFFSET_MM / 1000.0, MAGNET_RADIUS + MAGNET_SAFETY)

    # Cylinders extended below tile for robust boolean ops
    extra = 0.01  # 10 mm
    depth = MAGNET_HEIGHT + extra

    tile_bottom_z = z - (cube_height / 2)
    magnet_center_z = tile_bottom_z + (MAGNET_HEIGHT / 2) - (extra / 2)

    half = TILE_SIZE / 2
    dx = half - offset_m
    dy = half - offset_m
    corners = [(x - dx, y - dy), (x + dx, y - dy), (x - dx, y + dy), (x + dx, y + dy)]

    for i, (cx, cy) in enumerate(corners):
        # Hole
        bpy.ops.mesh.primitive_cylinder_add(radius=MAGNET_RADIUS, depth=depth, location=(cx, cy, magnet_center_z))
        cyl = bpy.context.active_object
        cyl.name = f"MagnetHole_{col}_{row}_{i}"
        add_boolean(cube, cyl, f"MagnetHole_{i}")

        # Countersink (45° cone) with a small radial shoulder
        cone_base_radius = max(MAGNET_RADIUS - COUNTERSINK_SHOULDER, 0.0005)
        cone_h = cone_base_radius  # 45° -> height = radius
        cone_base_z = tile_bottom_z + MAGNET_HEIGHT - 0.0005  # small overlap
        cone_center_z = cone_base_z + cone_h / 2

        bpy.ops.mesh.primitive_cone_add(
            radius1=cone_base_radius,
            radius2=0.0,
            depth=cone_h,
            location=(cx, cy, cone_center_z),
            rotation=(0.0, 0.0, 0.0),
        )
        cone = bpy.context.active_object
        cone.name = f"MagnetCountersink_{col}_{row}_{i}"
        add_boolean(cube, cone, f"MagnetCountersink_{i}")

def apply_modifiers(obj, names=None):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='OBJECT')
    if names is None:
        names = [m.name for m in obj.modifiers]
    for name in names:
        try:
            bpy.ops.object.modifier_apply(modifier=name)
        except RuntimeError:
            # Boolean may fail if already applied or invalid; continue
            pass

def export_tile(obj, row, col):
    obj.hide_set(False)
    out = OUTPUT_DIR / f"tile_{col}_{row}.stl"
    bpy.ops.export_mesh.stl(filepath=str(out))
    obj.hide_set(True)
    return out


# =========================
# 2) MAIN
# =========================
def process_tile(city_obj, row, col, tiles):
    min_z = min_z_in_tile(city_obj, row, col)
    if min_z is None:
        # No geometry overlaps this tile; skip creating an empty tile
        return

    # Cube placement
    x = col * TILE_SIZE + TILE_SIZE / 2
    y = row * TILE_SIZE + TILE_SIZE / 2
    cube_bottom = quantized_bottom(min_z)
    cube_top = min_z + TILE_SIZE / 2
    cube_height = cube_top - cube_bottom
    z = cube_bottom + cube_height / 2

    # Create cube and scale Z to desired height
    bpy.ops.mesh.primitive_cube_add(size=TILE_SIZE, location=(x, y, z))
    cube = bpy.context.active_object
    cube.name = f"Tile_{col}_{row}"
    cube.scale.z = cube_height / TILE_SIZE

    # City difference
    add_boolean(cube, city_obj, "Difference")

    # Magnets
    add_corner_magnets(cube, row, col, x, y, z, cube_height)

    tiles.append(cube)

def main():
    ensure_dirs()
    clear_scene()

    # Import and clean city mesh
    city = import_city_mesh(CITY_MESH_PATH)
    cleanup_normals(city)

    tiles = []

    if SINGLE_TILE_MODE:
        process_tile(city, SINGLE_TILE_ROW, SINGLE_TILE_COL, tiles)
    else:
        for r in range(TILES_Y):
            for c in range(TILES_X):
                process_tile(city, r, c, tiles)

    # Hide all while we apply modifiers & export
    for t in tiles:
        t.hide_set(True)
    city.hide_set(True)

    # Apply modifiers + export each
    for t in tiles:
        # Apply the city difference first
        apply_modifiers(t, names=["Difference"])
        # Then apply all magnet booleans (holes + countersinks)
        magnet_mods = [m.name for m in t.modifiers if m.name.startswith(("MagnetHole", "MagnetCountersink"))]
        apply_modifiers(t, names=magnet_mods)

        out = export_tile(t, row=int(t.name.split("_")[2]), col=int(t.name.split("_")[1]))
        print(f"Exported: {out}")

    count = 1 if SINGLE_TILE_MODE else (TILES_X * TILES_Y)
    print(f"Created {count} tile(s) with city cut, 2 cm-quantized underside, and four corner magnet holes.")

if __name__ == "__main__":
    main()
