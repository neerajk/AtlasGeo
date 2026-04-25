"""
Burn scar mapping tool — NBR-based fire scar detection from Sentinel-2 COG bands.

Method: Normalised Burn Ratio
  NBR = (NIR - SWIR2) / (NIR + SWIR2) = (B08 - B12) / (B08 + B12)
  Pixels where NBR < threshold are classified as burned.

Healthy vegetation has NBR 0.3–0.8; burn scars drop to -0.5 or lower.
Default threshold 0.2 catches moderate-to-high severity scars.

Note: single-image NBR can misclassify bare soil or dark rock as burned.
For higher accuracy use dNBR (pre/post image pair) when available.
"""

import math
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

# SCL classes that indicate cloud, shadow, or no-data — masked before analysis
_SCL_MASK_CLASSES = {0, 1, 3, 8, 9, 10}


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
        print(f"[burn_scar] SCL mask: {pct:.1f}% pixels masked as cloud/shadow")
        return mask
    except Exception as exc:
        print(f"[burn_scar] SCL read failed ({exc}) — skipping cloud mask")
        return None


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
    scl_href: str | None = None,
) -> dict:
    """
    Args:
        scene_id:    Sentinel-2 scene identifier
        nir_href:    COG URL for B08 (NIR band)
        swir22_href: COG URL for B12 (SWIR2 band)
        bbox:        [minx, miny, maxx, maxy] in WGS84
        threshold:   NBR threshold below which pixels are classed as burned (default 0.2)
        scl_href:    Optional COG URL for SCL band — used to mask clouds and shadows
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / f"{scene_id}_burn_scar.tif"

    print(f"[burn_scar] reading NIR from {nir_href}")
    nir, profile = _read_band(nir_href)

    print(f"[burn_scar] reading SWIR2 from {swir22_href}")
    swir22, _ = _read_band(swir22_href)

    if scl_href:
        cloud_mask = _read_scl_mask(scl_href)
        if cloud_mask is not None:
            nir[cloud_mask] = np.nan
            swir22[cloud_mask] = np.nan

    # NBR = (NIR - SWIR2) / (NIR + SWIR2)
    denom = nir + swir22
    denom[denom == 0] = np.nan
    nbr = (nir - swir22) / denom

    burn_mask = np.where(np.isnan(nbr), 0, (nbr < threshold).astype(np.uint8))

    burn_pixels = int(burn_mask.sum())
    # Pixel area derived from the resampled transform (not hardcoded native resolution).
    # Bands vary: NIR = 10m native, SWIR2 = 20m native; both are resampled to TARGET_SIZE,
    # so actual pixel footprint depends on scene bbox extent and latitude.
    t = profile["transform"]
    center_lat = t.f + (TARGET_SIZE / 2) * t.e
    px_km2 = (abs(t.a) * 111.0 * math.cos(math.radians(abs(center_lat)))) * (abs(t.e) * 111.0)
    burn_area_km2 = round(burn_pixels * px_km2, 2)

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
