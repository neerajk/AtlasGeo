import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from atlas.agents.planner import planner_node
from atlas.state import AtlasState


def _state(query: str) -> AtlasState:
    return {
        "messages": [], "query": query,
        "search_params": None, "stac_results": None,
        "geojson_features": None, "response": None,
    }


def _mock_llm(content: str):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content=content))
    return llm


VALID_JSON = (
    '{"bbox":[36.6,-1.4,37.1,-1.2],"date_range":["2026-03-01","2026-03-31"],'
    '"collection":"sentinel-2-l2a","cloud_cover_max":15,"max_results":5,"location_name":"Nairobi"}'
)


@pytest.mark.asyncio
@patch("atlas.agents.planner.get_llm")
async def test_valid_json_parsed(mock_get_llm):
    mock_get_llm.return_value = _mock_llm(VALID_JSON)
    result = await planner_node(_state("Sentinel-2 over Nairobi"))
    p = result["search_params"]
    assert p["bbox"] == [36.6, -1.4, 37.1, -1.2]
    assert p["date_range"] == ["2026-03-01", "2026-03-31"]
    assert p["cloud_cover_max"] == 15
    assert p["location_name"] == "Nairobi"


@pytest.mark.asyncio
@patch("atlas.agents.planner.get_llm")
async def test_invalid_json_falls_back_to_defaults(mock_get_llm):
    mock_get_llm.return_value = _mock_llm("Sorry, I cannot help.")
    result = await planner_node(_state("anything"))
    p = result["search_params"]
    assert p["bbox"] == [-180.0, -90.0, 180.0, 90.0]
    assert p["collection"] == "sentinel-2-l2a"
    assert p["cloud_cover_max"] == 20
    assert p["max_results"] == 10
    assert len(p["date_range"]) == 2


@pytest.mark.asyncio
@patch("atlas.agents.planner.get_llm")
async def test_null_bbox_replaced_with_global(mock_get_llm):
    mock_get_llm.return_value = _mock_llm(
        '{"bbox":null,"date_range":["2026-03-01","2026-03-31"],'
        '"collection":"sentinel-2-l2a","cloud_cover_max":20,"max_results":10,"location_name":"Earth"}'
    )
    result = await planner_node(_state("global"))
    assert result["search_params"]["bbox"] == [-180.0, -90.0, 180.0, 90.0]


@pytest.mark.asyncio
@patch("atlas.agents.planner.get_llm")
async def test_markdown_fences_stripped(mock_get_llm):
    mock_get_llm.return_value = _mock_llm(f"```json\n{VALID_JSON}\n```")
    result = await planner_node(_state("Nairobi"))
    assert result["search_params"]["location_name"] == "Nairobi"


@pytest.mark.asyncio
@patch("atlas.agents.planner.get_llm")
async def test_null_date_range_replaced_with_last_30_days(mock_get_llm):
    mock_get_llm.return_value = _mock_llm(
        '{"bbox":null,"date_range":null,"collection":"sentinel-2-l2a",'
        '"cloud_cover_max":20,"max_results":10,"location_name":"test"}'
    )
    result = await planner_node(_state("recent imagery"))
    dr = result["search_params"]["date_range"]
    assert len(dr) == 2
    assert dr[0] < dr[1]
