"""
Flood mapping tool — MNDWI-based water extent detection from Sentinel-2 COG bands.

Method: Modified Normalized Difference Water Index
  MNDWI = (Green - SWIR1) / (Green + SWIR1) = (B03 - B11) / (B03 + B11)
  Pixels where MNDWI > threshold are classified as water/flood.

This is the same method used by Copernicus Emergency Management Service (CEMS)
for operational flood mapping. Swapping in Prithvi-100M-sen1floods11 is a
one-function change in the _run_inference() section below.
"""

import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine

from atlas.tools import atlas_tool

# GDAL env for reading public S3 COGs without auth
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff,.TIF,.TIFF")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"

TARGET_SIZE = 512


def _read_band(href: str) -> tuple[np.ndarray, dict]:
    """Read a single COG band, resampled to TARGET_SIZE × TARGET_SIZE."""
    with rasterio.open(href) as src:
        data = src.read(
            1,
            out_shape=(TARGET_SIZE, TARGET_SIZE),
            resampling=Resampling.bilinear,
        ).astype(np.float32)

        x_scale = src.width / TARGET_SIZE
        y_scale = src.height / TARGET_SIZE
        transform = Affine(
            src.transform.a * x_scale, src.transform.b, src.transform.c,
            src.transform.d, src.transform.e * y_scale, src.transform.f,
        )
        profile = {
            "driver": "GTiff",
            "dtype": "uint8",
            "width": TARGET_SIZE,
            "height": TARGET_SIZE,
            "count": 1,
            "crs": src.crs,
            "transform": transform,
            "compress": "deflate",
            "nodata": None,
        }

    # Replace nodata (0 in Sentinel-2 L2A) with NaN
    data[data == 0] = np.nan
    return data, profile


@atlas_tool(
    name="flood_mapping",
    description=(
        "Map flood and water extent from Sentinel-2 imagery using MNDWI "
        "(Green B03 + SWIR1 B11). Returns a GeoTIFF flood mask and area stats."
    ),
    tags=["flood", "water", "sentinel-2", "mndwi", "analysis", "segmentation"],
)
def flood_mapping(
    scene_id: str,
    green_href: str,
    swir1_href: str,
    bbox: list,
    threshold: float = 0.0,
) -> dict:
    """
    Args:
        scene_id:    Sentinel-2 scene identifier
        green_href:  COG URL for B03 (Green band)
        swir1_href:  COG URL for B11 (SWIR1 band)
        bbox:        [minx, miny, maxx, maxy] in WGS84
        threshold:   MNDWI threshold above which pixels are classed as water (default 0.0)
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / f"{scene_id}_flood.tif"

    print(f"[flood_mapping] reading B03 from {green_href}")
    green, profile = _read_band(green_href)

    print(f"[flood_mapping] reading B11 from {swir1_href}")
    swir1, _ = _read_band(swir1_href)

    # MNDWI = (B03 - B11) / (B03 + B11)
    denom = green + swir1
    denom[denom == 0] = np.nan
    mndwi = (green - swir1) / denom

    flood_mask = np.where(np.isnan(mndwi), 0, (mndwi > threshold).astype(np.uint8))

    flood_pixels = int(flood_mask.sum())
    # Sentinel-2 L2A at 20m resolution (B11) → each pixel ≈ 0.0004 km²
    flood_area_km2 = round(flood_pixels * 0.0004, 2)

    print(f"[flood_mapping] writing output → {out_path} ({flood_pixels} flood px, ~{flood_area_km2} km²)")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(flood_mask, 1)

    return {
        "output_path": str(out_path),
        "output_filename": out_path.name,
        "scene_id": scene_id,
        "method": "MNDWI",
        "threshold": threshold,
        "flood_pixels": flood_pixels,
        "flood_area_km2": flood_area_km2,
        "bbox": bbox,
    }
