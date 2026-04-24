"""LangGraph state machine for Atlas. L1: Planner → STAC Scout → Response."""

from langgraph.graph import StateGraph, END

from atlas.state import AtlasState
from atlas.agents import planner_node, stac_scout_node, response_node
from atlas.tools.loader import load_all_tools


def build_graph():
    loaded = load_all_tools()
    if loaded:
        print(f"[atlas] loaded tools: {loaded}")

    g = StateGraph(AtlasState)

    g.add_node("planner", planner_node)
    g.add_node("stac_scout", stac_scout_node)
    g.add_node("response", response_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "stac_scout")
    g.add_edge("stac_scout", "response")
    g.add_edge("response", END)

    return g.compile()
