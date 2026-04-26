"""
Spectral index computation — normalised difference indices from Sentinel-2 COGs.

  NDVI  (NIR  - Red)   / (NIR  + Red)         vegetation health    nir + red
  NDWI  (Green - NIR)  / (Green + NIR)         water bodies         green + nir
  NDBI  (SWIR1 - NIR)  / (SWIR1 + NIR)         built-up / urban     swir16 + nir
  EVI   2.5*(NIR-Red)/(NIR+6*Red-7.5*Blue+1)  enhanced vegetation  nir + red + blue

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
    "ndwi": {"name": "NDWI", "colormap": "blues_r", "label": "Water Index"},
    "ndbi": {"name": "NDBI", "colormap": "hot_r",   "label": "Built-up Index"},
    "evi":  {"name": "EVI",  "colormap": "rdylgn",  "label": "Enhanced Vegetation Index"},
}

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
        print(f"[spectral_index] SCL mask: {pct:.1f}% pixels masked as cloud/shadow")
        return mask
    except Exception as exc:
        print(f"[spectral_index] SCL read failed ({exc}) — skipping cloud mask")
        return None


@atlas_tool(
    name="compute_spectral_index",
    description=(
        "Compute a spectral index from Sentinel-2 COG bands and return a "
        "coloured GeoTIFF. Supports NDVI (vegetation health), "
        "NDWI (water bodies), NDBI (built-up / urban extent), "
        "EVI (enhanced vegetation — reduces atmosphere and soil noise)."
    ),
    tags=["ndvi", "ndwi", "ndbi", "evi", "vegetation", "water", "urban",
          "spectral-index", "sentinel-2", "analysis"],
)
def compute_spectral_index(
    scene_id: str,
    index_type: str,
    band1_href: str,
    band2_href: str,
    bbox: list,
    scl_href: str | None = None,
    band3_href: str | None = None,
) -> dict:
    """
    Args:
        scene_id:    Sentinel-2 scene identifier
        index_type:  One of: ndvi, ndwi, ndbi, evi
        band1_href:  COG URL for the first band  (NIR for ndvi/evi, Green for ndwi, SWIR1 for ndbi)
        band2_href:  COG URL for the second band (Red for ndvi/evi, NIR for ndwi/ndbi)
        bbox:        [minx, miny, maxx, maxy] in WGS84
        scl_href:    Optional COG URL for SCL band — used to mask clouds and shadows
        band3_href:  Optional COG URL for a third band (Blue for EVI)
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = INDEX_META.get(index_type, INDEX_META["ndvi"])
    out_path = _OUTPUT_DIR / f"{scene_id}_{index_type}.tif"

    print(f"[spectral_index] reading band1 ({index_type}) from {band1_href}")
    band1, profile = _read_band(band1_href)

    print(f"[spectral_index] reading band2 ({index_type}) from {band2_href}")
    band2, _ = _read_band(band2_href)

    band3: np.ndarray | None = None
    if band3_href:
        print(f"[spectral_index] reading band3 ({index_type}) from {band3_href}")
        band3, _ = _read_band(band3_href)

    if scl_href:
        cloud_mask = _read_scl_mask(scl_href)
        if cloud_mask is not None:
            band1[cloud_mask] = np.nan
            band2[cloud_mask] = np.nan
            if band3 is not None:
                band3[cloud_mask] = np.nan

    if index_type == "evi" and band3 is not None:
        # EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
        nir, red, blue = band1, band2, band3
        denom = nir + 6.0 * red - 7.5 * blue + 1.0
        denom[denom == 0] = np.nan
        index = 2.5 * (nir - red) / denom
        nodata_mask = np.isnan(nir) | np.isnan(red) | np.isnan(blue) | np.isnan(index)
    else:
        denom = band1 + band2
        denom[denom == 0] = np.nan
        index = (band1 - band2) / denom
        nodata_mask = np.isnan(band1) | np.isnan(band2) | np.isnan(index)

    index = np.clip(index, -1.0, 1.0)
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
