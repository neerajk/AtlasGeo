"""
STAC Scout agent — searches Element84 Earth Search for Sentinel-2 scenes.
Returns raw results + GeoJSON features ready for the globe.

Automatic fallback: if 0 scenes pass the cloud filter, retries with progressively
relaxed cloud cover and wider date windows before returning empty.
"""

import asyncio
from datetime import datetime, timedelta

import pystac_client

from atlas.config import settings
from atlas.state import AtlasState

# Element84 Earth Search v1 uses semantic names, not band numbers
ASSET_KEYS = {"visual", "thumbnail", "red", "green", "blue", "nir", "nir08", "swir16", "swir22", "scl"}

# Fallback cascade: (cloud_cover_max, extra_days_back)
# Tried in order until results are found. None = keep original date range.
_FALLBACKS = [
    (None, None),    # 1. original params
    (20,   None),    # 2. relax to 20% cloud if original was stricter
    (40,   None),    # 3. relax to 40% cloud, same dates
    (40,   90),      # 4. 40% cloud + 90-day window
    (80,   180),     # 5. 80% cloud + 180-day window (last resort)
]


def _do_search(params: dict) -> tuple[list, list]:
    """Single STAC search with exact params. Returns (results, features)."""
    client = pystac_client.Client.open(settings.stac_url_element84)

    date_range = params.get("date_range", [])
    datetime_str = f"{date_range[0]}/{date_range[1]}" if len(date_range) == 2 else None
    cloud_max = params.get("cloud_cover_max", 20)

    print(f"[stac_scout] searching — bbox={params.get('bbox')}, datetime={datetime_str}, cloud<{cloud_max}")
    search = client.search(
        collections=[params.get("collection", "sentinel-2-l2a")],
        bbox=params.get("bbox"),
        datetime=datetime_str,
        max_items=params.get("max_results", 10) * 3,
    )

    all_items = list(search.items())
    items = [
        i for i in all_items
        if (i.properties.get("eo:cloud_cover") or 100) < cloud_max
    ][:params.get("max_results", 10)]
    print(f"[stac_scout] {len(all_items)} fetched, {len(items)} after cloud filter (<{cloud_max}%)")

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


def _search_with_fallback(params: dict) -> tuple[list, list, dict]:
    """
    Try _do_search with progressively relaxed params.
    Returns (results, features, actual_params_used).
    """
    original_cloud = params.get("cloud_cover_max", 20)
    original_end   = params.get("date_range", [None, None])[1]

    seen = set()  # skip duplicate (cloud, date_range) combos

    for cloud_override, extra_days in _FALLBACKS:
        cloud = cloud_override if cloud_override is not None else original_cloud

        if extra_days and original_end:
            end_dt  = datetime.strptime(original_end, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=extra_days)
            date_range = [start_dt.strftime("%Y-%m-%d"), original_end]
        else:
            date_range = params.get("date_range")

        key = (cloud, tuple(date_range) if date_range else None)
        if key in seen:
            continue
        seen.add(key)

        attempt = {**params, "cloud_cover_max": cloud, "date_range": date_range}
        results, features = _do_search(attempt)

        if results:
            if attempt["cloud_cover_max"] != original_cloud or date_range != params.get("date_range"):
                print(
                    f"[stac_scout] fallback succeeded — cloud<{cloud}%, "
                    f"dates={date_range[0]}→{date_range[1]}"
                )
                attempt["_original_cloud_cover_max"] = original_cloud
                attempt["_original_date_range"] = params.get("date_range")
            return results, features, attempt

        print(f"[stac_scout] 0 results at cloud<{cloud}%, dates={date_range} — trying next fallback")

    print("[stac_scout] all fallbacks exhausted — returning empty")
    return [], [], params


async def stac_scout_node(state: AtlasState) -> dict:
    params = state["search_params"] or {}
    print("[stac_scout] node start")
    loop = asyncio.get_event_loop()
    results, features, actual_params = await loop.run_in_executor(
        None, _search_with_fallback, params
    )
    print(f"[stac_scout] node done — {len(results)} result(s)")
    return {
        "stac_results": results,
        "geojson_features": features,
        "search_params": actual_params,  # update state so response shows what was actually used
    }
