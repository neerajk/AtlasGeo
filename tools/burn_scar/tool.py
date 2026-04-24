"""
Burn scar mapping tool — NBR-based fire scar detection from Sentinel-2 COG bands.

Method: Normalised Burn Ratio
  NBR = (NIR - SWIR2) / (NIR + SWIR2) = (B08 - B12) / (B08 + B12)
  Pixels where NBR < threshold are classified as burned.

Healthy vegetation has NBR 0.3–0.8; burn scars drop to -0.5 or lower.
Default threshold 0.2 catches moderate-to-high severity scars.
"""

import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine

from atlas.tools import atlas_tool

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff,.TIF,.TIFF")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"

TARGET_SIZE = 512


def _read_band(href: str) -> tuple[np.ndarray, dict]:
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

    data[data == 0] = np.nan
    return data, profile


@atlas_tool(
    name="burn_scar_mapping",
    description=(
        "Map wildfire burn scars from Sentinel-2 imagery using NBR "
        "(NIR B08 + SWIR2 B12). Returns a GeoTIFF burn mask and area stats."
    ),
    tags=["fire", "burn-scar", "wildfire", "sentinel-2", "nbr", "analysis", "segmentation"],
)
def burn_scar_mapping(
    scene_id: str,
    nir_href: str,
    swir22_href: str,
    bbox: list,
    threshold: float = 0.2,
) -> dict:
    """
    Args:
        scene_id:    Sentinel-2 scene identifier
        nir_href:    COG URL for B08 (NIR band)
        swir22_href: COG URL for B12 (SWIR2 band)
        bbox:        [minx, miny, maxx, maxy] in WGS84
        threshold:   NBR threshold below which pixels are classed as burned (default 0.2)
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / f"{scene_id}_burn_scar.tif"

    print(f"[burn_scar] reading NIR from {nir_href}")
    nir, profile = _read_band(nir_href)

    print(f"[burn_scar] reading SWIR2 from {swir22_href}")
    swir22, _ = _read_band(swir22_href)

    # NBR = (NIR - SWIR2) / (NIR + SWIR2)
    denom = nir + swir22
    denom[denom == 0] = np.nan
    nbr = (nir - swir22) / denom

    burn_mask = np.where(np.isnan(nbr), 0, (nbr < threshold).astype(np.uint8))

    burn_pixels = int(burn_mask.sum())
    # Sentinel-2 B12 at 20m resolution → each pixel ≈ 0.0004 km²
    burn_area_km2 = round(burn_pixels * 0.0004, 2)

    print(f"[burn_scar] writing output → {out_path} ({burn_pixels} burned px, ~{burn_area_km2} km²)")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(burn_mask, 1)

    return {
        "output_path": str(out_path),
        "output_filename": out_path.name,
        "scene_id": scene_id,
        "method": "NBR",
        "threshold": threshold,
        "burn_pixels": burn_pixels,
        "burn_area_km2": burn_area_km2,
        "bbox": bbox,
    }
