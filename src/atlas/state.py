from typing import TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage


class AtlasState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    query: str
    search_params: dict | None          # extracted by planner (includes task_type)
    stac_results: list[dict] | None     # raw STAC items from stac_scout
    geojson_features: list[dict] | None # GeoJSON features for frontend globe
    output_tifs: list[dict] | None      # analysis outputs (flood, LULC, etc.)
    response: str | None                # final markdown text for chat
