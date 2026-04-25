"""
Flood mapping tool — MNDWI-based water extent detection from Sentinel-2 COG bands.

Method: Modified Normalized Difference Water Index
  MNDWI = (Green - SWIR1) / (Green + SWIR1) = (B03 - B11) / (B03 + B11)
  Pixels where MNDWI > threshold are classified as water/flood.

This is the same method used by Copernicus Emergency Management Service (CEMS)
for operational flood mapping. Swapping in Prithvi-100M-sen1floods11 is a
one-function change in the _run_inference() section below.
"""

import math
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

# SCL classes that indicate cloud, shadow, or no-data — masked before analysis
_SCL_MASK_CLASSES = {0, 1, 3, 8, 9, 10}


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


def _read_scl_mask(href: str) -> np.ndarray | None:
    """Read SCL band and return boolean cloud/shadow mask (True = bad pixel)."""
    try:
        with rasterio.open(href) as src:
            scl = src.read(
                1,
                out_shape=(TARGET_SIZE, TARGET_SIZE),
                resampling=Resampling.nearest,
            )
        mask = np.zeros(scl.shape, dtype=bool)
        for cls in _SCL_MASK_CLASSES:
            mask |= (scl == cls)
        pct = mask.mean() * 100
        print(f"[flood_mapping] SCL mask: {pct:.1f}% pixels masked as cloud/shadow")
        return mask
    except Exception as exc:
        print(f"[flood_mapping] SCL read failed ({exc}) — skipping cloud mask")
        return None


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
    scl_href: str | None = None,
) -> dict:
    """
    Args:
        scene_id:    Sentinel-2 scene identifier
        green_href:  COG URL for B03 (Green band)
        swir1_href:  COG URL for B11 (SWIR1 band)
        bbox:        [minx, miny, maxx, maxy] in WGS84
        threshold:   MNDWI threshold above which pixels are classed as water (default 0.0)
        scl_href:    Optional COG URL for SCL band — used to mask clouds and shadows
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / f"{scene_id}_flood.tif"

    print(f"[flood_mapping] reading B03 from {green_href}")
    green, profile = _read_band(green_href)

    print(f"[flood_mapping] reading B11 from {swir1_href}")
    swir1, _ = _read_band(swir1_href)

    if scl_href:
        cloud_mask = _read_scl_mask(scl_href)
        if cloud_mask is not None:
            green[cloud_mask] = np.nan
            swir1[cloud_mask] = np.nan

    # MNDWI = (B03 - B11) / (B03 + B11)
    denom = green + swir1
    denom[denom == 0] = np.nan
    mndwi = (green - swir1) / denom

    flood_mask = np.where(np.isnan(mndwi), 0, (mndwi > threshold).astype(np.uint8))

    flood_pixels = int(flood_mask.sum())
    # Pixel area derived from the resampled transform (not hardcoded native resolution).
    # Bands vary: Green = 10m native, SWIR1 = 20m native; both are resampled to TARGET_SIZE,
    # so actual pixel footprint depends on scene bbox extent and latitude.
    t = profile["transform"]
    center_lat = t.f + (TARGET_SIZE / 2) * t.e
    px_km2 = (abs(t.a) * 111.0 * math.cos(math.radians(abs(center_lat)))) * (abs(t.e) * 111.0)
    flood_area_km2 = round(flood_pixels * px_km2, 2)

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
