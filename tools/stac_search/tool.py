"""
Tool: stac_search
Search Sentinel-2 L2A scenes by bbox + date range via Element84 STAC.
"""

import pystac_client
from atlas.tools import atlas_tool


@atlas_tool(
    name="stac_search",
    description=(
        "Search Sentinel-2 L2A satellite scenes. "
        "Returns scene IDs, dates, cloud cover, geometry, and asset download URLs."
    ),
    tags=["sentinel-2", "stac", "search"],
)
def stac_search(
    bbox: list[float],
    date_start: str,
    date_end: str,
    cloud_cover_max: int = 20,
    max_results: int = 10,
) -> dict:
    """
    Args:
        bbox: [minx, miny, maxx, maxy] in EPSG:4326
        date_start: ISO date string YYYY-MM-DD
        date_end: ISO date string YYYY-MM-DD
        cloud_cover_max: max cloud cover percentage (0-100)
        max_results: max number of scenes to return
    """
    client = pystac_client.Client.open("https://earth-search.aws.element84.com/v1")

    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{date_start}/{date_end}",
        filter_lang="cql2-json",
        filter={"op": "lt", "args": [{"property": "eo:cloud_cover"}, cloud_cover_max]},
        max_items=max_results,
    )

    items = list(search.items())
    return {
        "count": len(items),
        "scenes": [
            {
                "id": item.id,
                "datetime": item.datetime.isoformat() if item.datetime else None,
                "cloud_cover": item.properties.get("eo:cloud_cover"),
                "bbox": list(item.bbox) if item.bbox else None,
                "geometry": item.geometry,
                "thumbnail": item.assets.get("thumbnail", {}).href
                if hasattr(item.assets.get("thumbnail", object()), "href")
                else None,
            }
            for item in items
        ],
    }
