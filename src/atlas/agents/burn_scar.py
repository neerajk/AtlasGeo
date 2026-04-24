"""
Burn scar mapping agent node — picks best STAC scene and runs burn_scar_mapping tool.
"""

import asyncio
from atlas.state import AtlasState


def _run_burn_scar(stac_results: list[dict], params: dict) -> list[dict]:
    from atlas.tools.registry import get_tool

    tool_fn = get_tool("burn_scar_mapping")
    if not tool_fn:
        print("[burn_scar] tool not found — skipping")
        return []

    # Need nir (B08) and swir22 (B12)
    candidates = [
        r for r in stac_results
        if "nir" in r.get("assets", {}) and "swir22" in r.get("assets", {})
    ]
    if not candidates:
        print("[burn_scar] no scenes with nir+swir22 found")
        return []

    scene = min(candidates, key=lambda r: r.get("cloud_cover") or 100)
    print(f"[burn_scar] selected scene {scene['id']} (cloud: {scene.get('cloud_cover')}%)")

    result = tool_fn.fn(
        scene_id=scene["id"],
        nir_href=scene["assets"]["nir"]["href"],
        swir22_href=scene["assets"]["swir22"]["href"],
        bbox=scene.get("bbox") or params.get("bbox", []),
        threshold=0.2,
    )

    return [result]


async def burn_scar_node(state: AtlasState) -> dict:
    stac_results = state.get("stac_results") or []
    params = state.get("search_params") or {}
    print(f"[burn_scar] node start — {len(stac_results)} scene(s) available")

    loop = asyncio.get_event_loop()
    output_tifs = await loop.run_in_executor(None, _run_burn_scar, stac_results, params)
    print(f"[burn_scar] node done — {len(output_tifs)} output(s)")
    return {"output_tifs": output_tifs}
