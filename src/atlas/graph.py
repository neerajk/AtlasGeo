"""LangGraph state machine for Atlas."""

from langgraph.graph import StateGraph, END

from atlas.state import AtlasState
from atlas.agents import (
    planner_node, stac_scout_node,
    flood_mapping_node, burn_scar_node, spectral_index_node,
    response_node,
)
from atlas.tools.loader import load_all_tools

_SPECTRAL_TASKS = {"ndvi", "ndwi", "ndbi"}


def _route_after_stac(state: AtlasState) -> str:
    task_type = (state.get("search_params") or {}).get("task_type", "stac_search")
    if task_type == "flood_mapping":
        return "flood_mapping"
    if task_type == "burn_scar":
        return "burn_scar"
    if task_type in _SPECTRAL_TASKS:
        return "spectral_index"
    return "response"


def build_graph():
    loaded = load_all_tools()
    if loaded:
        print(f"[atlas] loaded tools: {loaded}")

    g = StateGraph(AtlasState)

    g.add_node("planner",        planner_node)
    g.add_node("stac_scout",     stac_scout_node)
    g.add_node("flood_mapping",  flood_mapping_node)
    g.add_node("burn_scar",      burn_scar_node)
    g.add_node("spectral_index", spectral_index_node)
    g.add_node("response",       response_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "stac_scout")
    g.add_conditional_edges("stac_scout", _route_after_stac, {
        "flood_mapping":  "flood_mapping",
        "burn_scar":      "burn_scar",
        "spectral_index": "spectral_index",
        "response":       "response",
    })
    g.add_edge("flood_mapping",  "response")
    g.add_edge("burn_scar",      "response")
    g.add_edge("spectral_index", "response")
    g.add_edge("response",       END)

    return g.compile()
