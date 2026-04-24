"""
Planner agent — converts natural language query into structured STAC search params.
"""

import json
import re
from datetime import datetime, timedelta

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
  "location_name": "human readable place"
}}

Rules:
- bbox: WGS84 degrees for the named location. Use known coordinates (e.g. Nairobi ≈ [36.6,-1.4,37.1,-1.2], London ≈ [-0.5,51.3,0.3,51.7], NYC ≈ [-74.3,40.5,-73.7,40.9]). Return null only if truly unknown.
- date_range: resolve relative expressions like "last month", "this week" using today={today}. "last month" means the calendar month before today.
- cloud_cover_max: default 20, higher if user says "cloudy" or "any"
- max_results: default 10

User query: {query}

Respond with ONLY the JSON object. No markdown, no explanation."""


async def planner_node(state: AtlasState) -> dict:
    query = state["query"]
    print(f"[planner] start — query: {query!r}")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    llm = get_llm("planner")
    print(f"[planner] calling LLM...")

    msg = await llm.ainvoke(_PROMPT.format(query=query, today=today))
    text = msg.content.strip()
    print(f"[planner] LLM raw response: {text[:200]!r}")

    # strip markdown fences if model wraps in ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        params = json.loads(text)
        print(f"[planner] JSON parsed OK")
    except json.JSONDecodeError as e:
        print(f"[planner] JSON parse failed ({e}) — using defaults")
        params = {}

    # Apply defaults
    if not params.get("bbox"):
        params["bbox"] = [-180.0, -90.0, 180.0, 90.0]

    if not params.get("date_range"):
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        params["date_range"] = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]

    params.setdefault("collection", "sentinel-2-l2a")
    params.setdefault("cloud_cover_max", 20)
    params.setdefault("max_results", 10)
    params.setdefault("location_name", query[:60])

    print(f"[planner] done — params: {params}")
    return {"search_params": params}
