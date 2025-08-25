#!/usr/bin/env python3
"""
Generate a printable, scaled city mesh from pointcloud + footprints using DTCC.

- Computes bounds from tile layout at a given print scale.
- Downloads pointcloud, builds terrain, extracts roof points & heights.
- Builds a city mesh, saves it, scales it to print scale, recenters to origin.

Requires:
  - dtcc, dtcc_core
  - trimesh

Based on dtcc platform demo : https://github.com/dtcc-platform/dtcc/blob/develop/demos/build_city_mesh.py

Author: Sanjay Somanath sanjay.somanath@chalmers.se
"""

from pathlib import Path
import dtcc
from dtcc import GeometryType
from dtcc_core.io import footprints as fp_io
import trimesh

# 0) --- Setup (edit these as needed) -----------------------------------------

# Project root = one level up from /scripts (this file assumed in /scripts)
BASE_DIR = Path(__file__).resolve().parent.parent

# Input data
BUILDINGS_REMOVED = BASE_DIR / "data" / "BuildingsRemoved.gpkg"
BUILDINGS_KEPT    = BASE_DIR / "data" / "BuildingsKept.gpkg"

# Output files
OUTPUT_DIR        = BASE_DIR / "output"
MESH_STL          = OUTPUT_DIR / "mesh.stl"         # raw DTCC mesh
SCALED_MESH_STL   = OUTPUT_DIR / "scaled_mesh.stl"   # scaled + centered

# Print/tiles
SCALE             = 1250.0      # 1:1250 (printed : real)
TILE_SIZE_PRINT_M = 0.20        # meters on the print
TILES_X           = 3
TILES_Y           = 5
BUFFER_M          = 10.0        # add margin around area

# Location (real-world coordinates, same CRS as your data)
MIN_X = 319_470.0
MAX_Y = 6_398_660.0

# Terrain/meshing + cleaning
RASTER_CELL_SIZE  = 2.0
RASTER_RADIUS     = 3.0
OUTLIER_STDDEV    = 3.0
MAX_MESH_SIZE     = 5.0
MIN_MESH_ANGLE    = 25.0
SMOOTHING         = 3

# Footprint processing
MERGE_MAX_DIST    = 0.5
MERGE_MIN_AREA    = 10.0
SIMPLIFY_TOL      = 0.25
CLEARANCE         = 0.5

SHOW_PREVIEW      = False  # set True to open the viewer


# 1) --- Make sure inputs exist and outputs folder is ready -------------------

def ensure_paths():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in [BUILDINGS_REMOVED, BUILDINGS_KEPT]:
        if not p.exists():
            raise FileNotFoundError(f"Missing input: {p}")

# 2) --- Compute the area bounds from tiles, scale, and buffer ----------------

def compute_bounds():
    real_tile_size = TILE_SIZE_PRINT_M * SCALE   # meters in reality per tile
    width  = TILES_X * real_tile_size
    height = TILES_Y * real_tile_size

    min_x = MIN_X
    max_y = MAX_Y
    min_y = max_y - height
    max_x = min_x + width

    # Apply buffer on all sides
    return dtcc.Bounds(
        min_x - BUFFER_M,
        min_y - BUFFER_M,
        max_x + BUFFER_M,
        max_y + BUFFER_M,
    )

# 3) --- Load data: pointcloud + building footprints -------------------------

def load_data(bounds):
    print("Downloading pointcloud…")
    pc = dtcc.download_pointcloud(bounds=bounds)
    pc = pc.remove_global_outliers(OUTLIER_STDDEV)

    print("Loading building footprints…")
    b_removed = fp_io.load(str(BUILDINGS_REMOVED), bounds=bounds)
    b_kept    = fp_io.load(str(BUILDINGS_KEPT),    bounds=bounds)

    # Clean/process the “kept” set for additional meshing detail
    b_kept = dtcc.merge_building_footprints(b_kept, max_distance=MERGE_MAX_DIST, min_area=MERGE_MIN_AREA)
    b_kept = dtcc.simplify_building_footprints(b_kept, tolerance=SIMPLIFY_TOL)
    b_kept = dtcc.fix_building_footprint_clearance(b_kept, CLEARANCE)

    # Extract simple 2D outlines to guide meshing
    extra_footprints = [b.get_footprint(GeometryType.LOD0) for b in b_kept]

    return pc, b_removed, extra_footprints

# 4) --- Build terrain + compute building heights -----------------------------

def make_terrain_and_buildings(pointcloud, buildings_removed, bounds):
    print("Building terrain raster…")
    raster = dtcc.build_terrain_raster(
        pointcloud,
        cell_size=RASTER_CELL_SIZE,
        radius=RASTER_RADIUS,
        ground_only=True
    )

    print("Extracting roof points + computing heights…")
    buildings = dtcc.extract_roof_points(buildings_removed, pointcloud)
    buildings = dtcc.compute_building_heights(buildings, raster, overwrite=True)

    return raster, buildings

# 5) --- Build city + mesh ----------------------------------------------------

def make_mesh(raster, buildings, extra_footprints):
    print("Creating city and meshing…")
    city = dtcc.City()
    city.add_terrain(raster)
    city.add_buildings(buildings, remove_outside_terrain=True)

    mesh = dtcc.build_city_mesh(
        city,
        lod=GeometryType.LOD0,
        max_mesh_size=MAX_MESH_SIZE,
        min_mesh_angle=MIN_MESH_ANGLE,
        smoothing=SMOOTHING,
        additional_building_footprints=extra_footprints,
    )
    return mesh

# 6) --- Save raw mesh, scale + center for printing ---------------------------

def save_and_scale(mesh, ref_min_x, ref_min_y_unbuffered):
    print("Saving raw mesh…")
    mesh.save(str(MESH_STL))

    print("Scaling and centering for print…")
    tri = trimesh.load(str(MESH_STL))

    # scale down to print scale, e.g. 1/1250
    tri.apply_scale(1.0 / SCALE)

    # move origin to (min_x,min_y) and lift so ground = Z 0
    tri.apply_translation([
        -ref_min_x / SCALE,
        -ref_min_y_unbuffered / SCALE,
        -tri.bounds[0][2]            # shift so min Z -> 0
    ])

    tri.export(str(SCALED_MESH_STL))
    print(f"Done.\n  Raw:    {MESH_STL}\n  Scaled: {SCALED_MESH_STL}")

# --- Main --------------------------------------------------------------------

def main():
    ensure_paths()

    bounds = compute_bounds()
    pointcloud, buildings_removed, extra_footprints = load_data(bounds)
    raster, buildings = make_terrain_and_buildings(pointcloud, buildings_removed, bounds)

    # ref_min_y_unbuffered = bounds.ymin + (bounds.ymax - BUFFER_M)
    # Note: In the original logic this calculated a min_y before buffer.
    # Here we reconstruct that explicitly:
    real_tile_size = TILE_SIZE_PRINT_M * SCALE
    area_height = TILES_Y * real_tile_size
    ref_min_y_unbuffered = MAX_Y - area_height

    mesh = make_mesh(raster, buildings, extra_footprints)

    if SHOW_PREVIEW:
        mesh.view()  # optional preview

    save_and_scale(mesh, ref_min_x=MIN_X, ref_min_y_unbuffered=ref_min_y_unbuffered)

if __name__ == "__main__":
    main()
