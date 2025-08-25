# DTCC-Table

Workflow for generating 3D printable tiles of a city model using the [DTCC platform](https://github.com/dtcc-platform/dtcc) and Blender.  
The goal is to create a physical table surface with scaled, magnetized city tiles.

---

## Repository Structure

```

DTCC-TABLE/
├─ data/                  # Input datasets
│   ├─ BuildingsKept.gpkg
│   └─ BuildingsRemoved.gpkg
├─ output/                # Generated meshes and tiles (created automatically)
├─ scripts/               # Python scripts
│   ├─ get_city_mesh.py   # Downloads pointcloud, builds terrain, creates scaled city mesh
│   └─ tile_city_mesh.py  # Cuts the mesh into tiles with magnet holes (Blender script)
├─ requirements.txt       # Python dependencies
├─ LICENSE
└─ README.md

````

---

## Workflow

### 1. Generate City Mesh
Run the script to download data, process footprints, and build a scaled STL mesh.

```bash
python scripts/get_city_mesh.py
````

This will create:

* `output/mesh.stl` → full raw city mesh
* `output/scaled_mesh.stl` → scaled and centered mesh for printing

---

### 2. Tile the Mesh (Blender)

Use Blender in **headless mode** to split the mesh into printable tiles with magnet holes.

```bash
blender -b -P scripts/tile_city_mesh.py
```

Outputs will be written to:

* `output/tile_{col}_{row}.stl`

---

## Parameters

* **Scale**: Default is `1:1250`
* **Tile size**: `0.20 m` (printed dimension)
* **Magnets**: 5 mm radius × 2 mm depth, with countersink and 4 mm inset from edges
* **Underside fill**: Quantized to 20 mm steps, anchored at Z=0

You can modify these directly in the scripts or extend them to accept CLI arguments.

---

## Requirements

Python packages (for `get_city_mesh.py`):

```
dtcc
dtcc-core
trimesh
```

For tiling you need **Blender 3.x** with the `io_mesh_stl` add-on enabled (default).

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Notes

* Place your `BuildingsKept.gpkg` and `BuildingsRemoved.gpkg` files into the `data/` folder.
* The `output/` folder is created automatically.
* `scripts/get_city_mesh.py` can be used standalone (no Blender).
* `scripts/tile_city_mesh.py` must be run inside Blender.

---