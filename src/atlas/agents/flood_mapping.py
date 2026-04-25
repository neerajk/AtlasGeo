"""
Flood mapping agent node — picks best STAC scene and runs flood_mapping tool.
"""

import asyncio
from atlas.state import AtlasState


def _run_flood_mapping(stac_results: list[dict], params: dict) -> list[dict]:
    from atlas.tools.registry import get_tool

    tool_fn = get_tool("flood_mapping")
    if not tool_fn:
        print("[flood_mapping] tool not found — skipping")
        return []

    # Pick scene with lowest cloud cover that has both B03 and B11
    # Element84 Earth Search v1 uses semantic names: green=B03, swir16=B11
    candidates = [
        r for r in stac_results
        if "green" in r.get("assets", {}) and "swir16" in r.get("assets", {})
    ]
    if not candidates:
        print("[flood_mapping] no scenes with green+swir16 found")
        return []

    scene = min(candidates, key=lambda r: r.get("cloud_cover") or 100)
    print(f"[flood_mapping] selected scene {scene['id']} (cloud: {scene.get('cloud_cover')}%)")

    result = tool_fn.fn(
        scene_id=scene["id"],
        green_href=scene["assets"]["green"]["href"],
        swir1_href=scene["assets"]["swir16"]["href"],
        bbox=scene.get("bbox") or params.get("bbox", []),
        threshold=0.0,
        scl_href=scene["assets"].get("scl", {}).get("href"),
    )

    return [result]


async def flood_mapping_node(state: AtlasState) -> dict:
    stac_results = state.get("stac_results") or []
    params = state.get("search_params") or {}
    print(f"[flood_mapping] node start — {len(stac_results)} scene(s) available")

    loop = asyncio.get_event_loop()
    output_tifs = await loop.run_in_executor(None, _run_flood_mapping, stac_results, params)
    print(f"[flood_mapping] node done — {len(output_tifs)} output(s)")
    return {"output_tifs": output_tifs}
