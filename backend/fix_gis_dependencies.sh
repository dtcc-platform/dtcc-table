#!/bin/bash
# Fix GIS dependencies on Ubuntu/EC2

echo "🔧 Fixing GIS dependencies for DTCC-Table..."

# Update system packages
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    libspatialindex-dev \
    libgeos-dev \
    libproj-dev

# Export GDAL version for pip
export GDAL_VERSION=$(gdal-config --version)
echo "ℹ️ GDAL version: $GDAL_VERSION"

# Activate virtual environment
cd /home/ubuntu/dtcc-table/backend
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Clean install GIS packages
echo "📦 Reinstalling GIS packages..."
pip uninstall -y fiona geopandas rasterio shapely pyproj
pip install --no-cache-dir \
    pyproj>=3.4.0 \
    shapely==2.0.4 \
    fiona==1.9.6 \
    rasterio==1.3.10 \
    geopandas==0.14.4

# Test the installation
echo "🧪 Testing GIS packages..."
python3.11 -c "
import sys
try:
    import fiona
    import geopandas as gpd
    import rasterio
    print('✅ All GIS packages imported successfully!')
    print(f'  Fiona version: {fiona.__version__}')
    print(f'  GeoPandas version: {gpd.__version__}')
    print(f'  Rasterio version: {rasterio.__version__}')
except ImportError as e:
    print(f'❌ Import failed: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ GIS dependencies fixed successfully!"
    echo "🔄 Restarting service..."
    sudo systemctl restart dtcc-table
    echo "✅ Service restarted. Check status with: sudo systemctl status dtcc-table"
else
    echo "❌ Failed to fix dependencies. Please check the error messages above."
fi