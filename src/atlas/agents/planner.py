"""
Planner agent — converts natural language query into structured STAC search params.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta

import requests
from langchain_core.messages import HumanMessage

from atlas.models import get_llm
from atlas.state import AtlasState

_PROMPT = """\
You are a geospatial query planner. Today's date is {today}.

Extract satellite search parameters from the user query and return ONLY a valid JSON object:
{{
  "bbox": [minx, miny, maxx, maxy],
  "date_range": ["YYYY-MM-DD", "YYYY-MM-DD"],
  "collection": "sentinel-2-l2a",
  "cloud_cover_max": 20,
  "max_results": 10,
  "location_name": "human readable place",
  "task_type": "stac_search"
}}

Rules:
- bbox: WGS84 degrees for the named location. Use known coordinates (e.g. Nairobi ≈ [36.6,-1.4,37.1,-1.2], London ≈ [-0.5,51.3,0.3,51.7], NYC ≈ [-74.3,40.5,-73.7,40.9], Bangladesh ≈ [88.0,20.5,92.7,26.7], Mumbai ≈ [72.7,18.8,73.1,19.3]). Return null only if truly unknown.
- date_range: resolve relative expressions like "last month", "this week" using today={today}. "last month" means the calendar month before today.
- cloud_cover_max: default 20, higher if user says "cloudy" or "any"
- max_results: default 10
- task_type: one of "stac_search" (default), "flood_mapping", "burn_scar", "ndvi", "ndwi", "ndbi", or "evi".
  Use "flood_mapping" for flood, flooding, inundation, water extent, deluge, submerged land.
  Use "burn_scar" for fire, wildfire, burn, burnt, burned area, NBR.
  Use "ndvi" for vegetation index, plant health, greenness, NDVI, crop monitoring.
  Use "ndwi" for water body detection, lake, river extent, NDWI, surface water.
  Use "ndbi" for built-up index, urbanisation, urban extent, NDBI, impervious surface.
  Use "evi" for enhanced vegetation index, EVI, canopy health, forest density, dense vegetation.

User query: {query}

Respond with ONLY the JSON object. No markdown, no explanation."""


def _geocode(location: str) -> list[float] | None:
    """Nominatim bbox lookup — returns [minx, miny, maxx, maxy] or None."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": "AtlasGeoAI/1.0"},
            timeout=6,
        )
        data = r.json()
        if not data:
            return None
        bb = data[0]["boundingbox"]          # [minlat, maxlat, minlon, maxlon]
        return [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])]
    except Exception as exc:
        print(f"[planner] geocode failed: {exc}")
        return None


async def planner_node(state: AtlasState) -> dict:
    query = state["query"]
    print(f"[planner] start — query: {query!r}")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    llm = get_llm("planner")
    print("[planner] calling LLM...")

    history = state.get("messages", [])
    prompt_msg = HumanMessage(content=_PROMPT.format(query=query, today=today))
    msg = await llm.ainvoke([*history, prompt_msg])
    text = msg.content.strip()
    print(f"[planner] LLM raw response: {text[:200]!r}")

    # strip markdown fences if model wraps in ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        params = json.loads(text)
        print("[planner] JSON parsed OK")
    except json.JSONDecodeError as e:
        print(f"[planner] JSON parse failed ({e}) — using defaults")
        params = {}

    # Apply defaults
    bbox = params.get("bbox")
    if not bbox or any(v is None for v in bbox):
        location = params.get("location_name") or query
        print(f"[planner] bbox missing — geocoding {location!r}")
        geocoded = await asyncio.to_thread(_geocode, location)
        if geocoded:
            print(f"[planner] geocoded bbox: {geocoded}")
            params["bbox"] = geocoded
        else:
            print("[planner] geocode failed — falling back to global bbox")
            params["bbox"] = [-180.0, -90.0, 180.0, 90.0]

    date_range = params.get("date_range")
    if not date_range:
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        params["date_range"] = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
    elif date_range[0] == date_range[1]:
        # LLM collapsed a "latest/recent" query to a single day — expand to 30 days back
        latest_keywords = {"latest", "recent", "newest", "last", "current", "today"}
        if any(kw in query.lower() for kw in latest_keywords):
            end = datetime.strptime(date_range[1], "%Y-%m-%d")
            start = end - timedelta(days=30)
            params["date_range"] = [start.strftime("%Y-%m-%d"), date_range[1]]
            print(f"[planner] expanded single-day range to 30 days: {params['date_range']}")

    # Validate and sanitise bbox
    bbox = params.get("bbox", [])
    if isinstance(bbox, list) and len(bbox) == 4:
        try:
            minx, miny, maxx, maxy = [float(v) for v in bbox]
            # Clamp to WGS84 bounds
            minx = max(-180.0, min(180.0, minx))
            maxx = max(-180.0, min(180.0, maxx))
            miny = max(-90.0,  min(90.0,  miny))
            maxy = max(-90.0,  min(90.0,  maxy))
            # Swap if inverted
            if minx > maxx:
                minx, maxx = maxx, minx
            if miny > maxy:
                miny, maxy = maxy, miny
            params["bbox"] = [minx, miny, maxx, maxy]
        except (TypeError, ValueError) as e:
            print(f"[planner] bbox sanitise failed ({e}) — geocoding instead")
            params.pop("bbox", None)
            location = params.get("location_name") or query
            geocoded = await asyncio.to_thread(_geocode, location)
            params["bbox"] = geocoded or [-180.0, -90.0, 180.0, 90.0]

    params.setdefault("collection", "sentinel-2-l2a")
    params.setdefault("cloud_cover_max", 20)
    params.setdefault("max_results", 10)
    params.setdefault("location_name", query[:60])
    params.setdefault("task_type", "stac_search")

    # Fallback: keyword-based task_type detection if LLM missed it
    if params["task_type"] == "stac_search":
        flood_keywords = {"flood", "flooding", "inundation", "inundated", "water extent", "submerged", "deluge"}
        if any(kw in query.lower() for kw in flood_keywords):
            params["task_type"] = "flood_mapping"

    if params["task_type"] == "stac_search":
        burn_keywords = {"fire", "wildfire", "burn", "burnt", "burned", "burn scar", "nbr"}
        if any(kw in query.lower() for kw in burn_keywords):
            params["task_type"] = "burn_scar"

    if params["task_type"] == "stac_search":
        q = query.lower()
        if any(kw in q for kw in {"evi", "enhanced vegetation", "canopy health", "forest density"}):
            params["task_type"] = "evi"
        elif any(kw in q for kw in {"ndvi", "vegetation index", "plant health", "greenness", "crop health"}):
            params["task_type"] = "ndvi"
        elif any(kw in q for kw in {"ndwi", "water body", "water index", "surface water", "lake extent", "river extent"}):
            params["task_type"] = "ndwi"
        elif any(kw in q for kw in {"ndbi", "built-up index", "urbanisation", "urbanization", "urban extent", "impervious"}):
            params["task_type"] = "ndbi"

    print(f"[planner] done — params: {params}")
    return {"search_params": params}
