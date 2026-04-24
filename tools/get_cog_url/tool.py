"""
Tool: get_cog_url
Get direct COG (Cloud-Optimized GeoTIFF) URLs for a specific Sentinel-2 scene and band.
"""

import pystac_client
from atlas.tools import atlas_tool

BAND_ALIASES = {
    "red": "B04", "green": "B03", "blue": "B02",
    "nir": "B08", "nir_narrow": "B8A", "swir1": "B11", "swir2": "B12",
    "scl": "SCL", "visual": "visual",
}


@atlas_tool(
    name="get_cog_url",
    description=(
        "Get the direct download URL (COG) for a specific band of a Sentinel-2 scene. "
        "Use band aliases: red, green, blue, nir, nir_narrow, swir1, swir2, scl, visual."
    ),
    tags=["sentinel-2", "stac", "cog", "download"],
)
def get_cog_url(scene_id: str, band: str) -> dict:
    """
    Args:
        scene_id: Sentinel-2 scene ID from stac_search
        band: Band name or alias (red, green, blue, nir, B04, B08, visual, etc.)
    """
    asset_key = BAND_ALIASES.get(band.lower(), band.upper())

    client = pystac_client.Client.open("https://earth-search.aws.element84.com/v1")
    search = client.search(collections=["sentinel-2-l2a"], ids=[scene_id], max_items=1)
    items = list(search.items())

    if not items:
        return {"error": f"Scene {scene_id!r} not found"}

    item = items[0]
    asset = item.assets.get(asset_key)

    if not asset:
        available = list(item.assets.keys())
        return {"error": f"Band {asset_key!r} not found. Available: {available}"}

    return {
        "scene_id": scene_id,
        "band": asset_key,
        "href": asset.href,
        "media_type": getattr(asset, "media_type", None),
        "epsg": item.properties.get("proj:epsg"),
        "datetime": item.datetime.isoformat() if item.datetime else None,
    }
