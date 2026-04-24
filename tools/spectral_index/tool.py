"""
Spectral index computation — normalised difference indices from Sentinel-2 COGs.

  NDVI  (NIR  - Red)   / (NIR  + Red)    vegetation health     nir   + red
  NDWI  (Green - NIR)  / (Green + NIR)   water bodies          green + nir
  NDBI  (SWIR1 - NIR)  / (SWIR1 + NIR)   built-up / urban      swir16 + nir

Outputs a float32 GeoTIFF clipped to [-1, 1]; nodata = -9999.
titiler renders it with a named colormap (e.g. rdylgn, blues, hot_r).
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

INDEX_META: dict[str, dict] = {
    "ndvi": {"name": "NDVI", "colormap": "rdylgn",  "label": "Vegetation Index"},
    "ndwi": {"name": "NDWI", "colormap": "blues_r",   "label": "Water Index"},
    "ndbi": {"name": "NDBI", "colormap": "hot_r",   "label": "Built-up Index"},
}


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
            "dtype": "float32",
            "width": TARGET_SIZE,
            "height": TARGET_SIZE,
            "count": 1,
            "crs": src.crs,
            "transform": transform,
            "compress": "deflate",
            "nodata": -9999.0,
        }

    data[data == 0] = np.nan
    return data, profile


@atlas_tool(
    name="compute_spectral_index",
    description=(
        "Compute a spectral index from two Sentinel-2 COG bands and return a "
        "coloured GeoTIFF. Supports NDVI (vegetation health), "
        "NDWI (water bodies), NDBI (built-up / urban extent)."
    ),
    tags=["ndvi", "ndwi", "ndbi", "vegetation", "water", "urban",
          "spectral-index", "sentinel-2", "analysis"],
)
def compute_spectral_index(
    scene_id: str,
    index_type: str,
    band1_href: str,
    band2_href: str,
    bbox: list,
) -> dict:
    """
    Args:
        scene_id:    Sentinel-2 scene identifier
        index_type:  One of: ndvi, ndwi, ndbi
        band1_href:  COG URL for the first band (numerator)
        band2_href:  COG URL for the second band (denominator)
        bbox:        [minx, miny, maxx, maxy] in WGS84
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = INDEX_META.get(index_type, INDEX_META["ndvi"])
    out_path = _OUTPUT_DIR / f"{scene_id}_{index_type}.tif"

    print(f"[spectral_index] reading band1 ({index_type}) from {band1_href}")
    band1, profile = _read_band(band1_href)

    print(f"[spectral_index] reading band2 ({index_type}) from {band2_href}")
    band2, _ = _read_band(band2_href)

    denom = band1 + band2
    denom[denom == 0] = np.nan
    index = (band1 - band2) / denom
    index = np.clip(index, -1.0, 1.0)

    nodata_mask = np.isnan(band1) | np.isnan(band2) | np.isnan(index)
    index_out = np.where(nodata_mask, -9999.0, index)

    valid = index[~nodata_mask]
    mean_val = float(np.mean(valid)) if valid.size > 0 else 0.0

    print(f"[spectral_index] writing {out_path} ({meta['name']} mean={mean_val:.3f})")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(index_out.astype(np.float32), 1)

    return {
        "output_path": str(out_path),
        "output_filename": out_path.name,
        "scene_id": scene_id,
        "index_type": index_type,
        "index_name": meta["name"],
        "index_label": meta["label"],
        "colormap": meta["colormap"],
        "mean_value": round(mean_val, 3),
        "bbox": bbox,
    }
