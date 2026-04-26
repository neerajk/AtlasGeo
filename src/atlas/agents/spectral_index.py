"""
Spectral index agent node — computes NDVI, NDWI, or NDBI from the best STAC scene.
"""

import asyncio
from atlas.state import AtlasState

# (band1, band2[, band3]) per index type; EVI needs blue as a third band
_BAND_MAP: dict[str, tuple[str, ...]] = {
    "ndvi": ("nir",    "red"),
    "ndwi": ("green",  "nir"),
    "ndbi": ("swir16", "nir"),
    "evi":  ("nir",    "red",  "blue"),
}


def _run_spectral_index(stac_results: list[dict], params: dict, index_type: str) -> list[dict]:
    from atlas.tools.registry import get_tool

    tool_fn = get_tool("compute_spectral_index")
    if not tool_fn:
        print(f"[spectral_index] tool not found")
        return []

    band_keys = _BAND_MAP.get(index_type, ("nir", "red"))
    band1_key, band2_key = band_keys[0], band_keys[1]
    band3_key = band_keys[2] if len(band_keys) > 2 else None

    required_keys = [band1_key, band2_key] + ([band3_key] if band3_key else [])
    candidates = [
        r for r in stac_results
        if all(k in r.get("assets", {}) for k in required_keys)
    ]
    if not candidates:
        print(f"[spectral_index] no scenes with {required_keys} for {index_type}")
        return []

    scene = min(candidates, key=lambda r: r.get("cloud_cover") or 100)
    print(f"[spectral_index] scene {scene['id']} (cloud: {scene.get('cloud_cover')}%) index={index_type}")

    result = tool_fn.fn(
        scene_id=scene["id"],
        index_type=index_type,
        band1_href=scene["assets"][band1_key]["href"],
        band2_href=scene["assets"][band2_key]["href"],
        bbox=scene.get("bbox") or params.get("bbox", []),
        scl_href=scene["assets"].get("scl", {}).get("href"),
        band3_href=scene["assets"][band3_key]["href"] if band3_key else None,
    )
    return [result]


async def spectral_index_node(state: AtlasState) -> dict:
    stac_results = state.get("stac_results") or []
    params = state.get("search_params") or {}
    index_type = params.get("task_type", "ndvi")
    print(f"[spectral_index] node start — index={index_type}, {len(stac_results)} scene(s)")

    loop = asyncio.get_event_loop()
    output_tifs = await loop.run_in_executor(
        None, _run_spectral_index, stac_results, params, index_type
    )
    print(f"[spectral_index] node done — {len(output_tifs)} output(s)")
    return {"output_tifs": output_tifs}
