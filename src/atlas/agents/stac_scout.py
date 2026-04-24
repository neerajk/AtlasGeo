"""
STAC Scout agent — searches Element84 Earth Search for Sentinel-2 scenes.
Returns raw results + GeoJSON features ready for the globe.
"""

import asyncio
import pystac_client

from atlas.config import settings
from atlas.state import AtlasState

# Element84 Earth Search v1 uses semantic names, not band numbers
ASSET_KEYS = {"visual", "thumbnail", "red", "green", "blue", "nir", "nir08", "swir16", "swir22", "scl"}


def _do_search(params: dict) -> tuple[list, list]:
    print(f"[stac_scout] opening STAC client → {settings.stac_url_element84}")
    client = pystac_client.Client.open(settings.stac_url_element84)

    date_range = params.get("date_range", [])
    datetime_str = f"{date_range[0]}/{date_range[1]}" if len(date_range) == 2 else None
    cloud_cover_max = params.get("cloud_cover_max", 20)

    print(f"[stac_scout] searching — bbox={params.get('bbox')}, datetime={datetime_str}, cloud<{cloud_cover_max}")
    # Element84 v1 does not support CQL2 FILTER — apply cloud cover client-side after fetch
    search = client.search(
        collections=[params.get("collection", "sentinel-2-l2a")],
        bbox=params.get("bbox"),
        datetime=datetime_str,
        max_items=params.get("max_results", 10) * 3,  # fetch extra to allow for filtering
    )

    print("[stac_scout] fetching items...")
    all_items = list(search.items())
    items = [
        i for i in all_items
        if (i.properties.get("eo:cloud_cover") or 100) < cloud_cover_max
    ][:params.get("max_results", 10)]
    print(f"[stac_scout] got {len(all_items)} item(s), {len(items)} after cloud filter (<{cloud_cover_max}%)")
    print(f"[stac_scout] got {len(items)} item(s)")

    results = []
    for item in items:
        results.append({
            "id": item.id,
            "datetime": item.datetime.isoformat() if item.datetime else None,
            "cloud_cover": item.properties.get("eo:cloud_cover"),
            "platform": item.properties.get("platform", ""),
            "bbox": list(item.bbox) if item.bbox else None,
            "geometry": item.geometry,
            "assets": {
                k: {"href": v.href, "type": getattr(v, "media_type", None)}
                for k, v in item.assets.items()
                if k in ASSET_KEYS
            },
        })

    features = [
        {
            "type": "Feature",
            "id": r["id"],
            "geometry": r["geometry"],
            "properties": {
                "id": r["id"],
                "datetime": r["datetime"],
                "cloud_cover": r["cloud_cover"],
                "platform": r["platform"],
                "thumbnail": r["assets"].get("thumbnail", {}).get("href"),
                "download_links": {
                    k: v["href"] for k, v in r["assets"].items() if k != "thumbnail"
                },
            },
        }
        for r in results
    ]

    return results, features


async def stac_scout_node(state: AtlasState) -> dict:
    params = state["search_params"] or {}
    print("[stac_scout] node start — handing off to thread executor")
    loop = asyncio.get_event_loop()
    results, features = await loop.run_in_executor(None, _do_search, params)
    print(f"[stac_scout] node done — {len(results)} result(s), {len(features)} feature(s)")
    return {"stac_results": results, "geojson_features": features}
