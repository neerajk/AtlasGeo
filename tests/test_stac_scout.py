import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from atlas.agents.stac_scout import _do_search, stac_scout_node
from atlas.state import AtlasState


def _item(item_id: str, cloud_cover: float) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    item.datetime = datetime(2026, 3, 15)
    item.bbox = [36.6, -1.4, 37.1, -1.2]
    item.geometry = {
        "type": "Polygon",
        "coordinates": [[[36.6, -1.4], [37.1, -1.4], [37.1, -1.2], [36.6, -1.2], [36.6, -1.4]]],
    }
    item.properties = {"eo:cloud_cover": cloud_cover, "platform": "sentinel-2b"}
    thumb = MagicMock()
    thumb.href = "https://example.com/thumb.jpg"
    thumb.media_type = "image/jpeg"
    item.assets = {"thumbnail": thumb}
    return item


def _patched_search(items):
    mock_client = MagicMock()
    mock_search = MagicMock()
    mock_client.search.return_value = mock_search
    mock_search.items.return_value = items
    return mock_client


BASE_PARAMS = {
    "bbox": [36.6, -1.4, 37.1, -1.2],
    "date_range": ["2026-03-01", "2026-03-31"],
    "cloud_cover_max": 20,
    "max_results": 10,
}


@patch("atlas.agents.stac_scout.pystac_client.Client.open")
def test_cloud_filter_drops_high_cover_scenes(mock_open):
    mock_open.return_value = _patched_search([
        _item("S2A_001", 5.0),
        _item("S2A_002", 25.0),  # above threshold
        _item("S2A_003", 15.0),
    ])
    results, features = _do_search(BASE_PARAMS)
    assert len(results) == 2
    assert all(r["cloud_cover"] < 20 for r in results)


@patch("atlas.agents.stac_scout.pystac_client.Client.open")
def test_max_results_capped_after_filter(mock_open):
    mock_open.return_value = _patched_search([
        _item(f"S2A_00{i}", 5.0) for i in range(8)
    ])
    results, _ = _do_search({**BASE_PARAMS, "max_results": 3})
    assert len(results) == 3


@patch("atlas.agents.stac_scout.pystac_client.Client.open")
def test_empty_results_when_all_above_threshold(mock_open):
    mock_open.return_value = _patched_search([
        _item("S2A_001", 50.0),
        _item("S2A_002", 80.0),
    ])
    results, features = _do_search(BASE_PARAMS)
    assert results == []
    assert features == []


@patch("atlas.agents.stac_scout.pystac_client.Client.open")
def test_geojson_feature_shape(mock_open):
    mock_open.return_value = _patched_search([_item("S2A_001", 5.0)])
    _, features = _do_search(BASE_PARAMS)
    f = features[0]
    assert f["type"] == "Feature"
    assert f["id"] == "S2A_001"
    assert "geometry" in f
    assert "cloud_cover" in f["properties"]
    assert "datetime" in f["properties"]


@pytest.mark.asyncio
@patch("atlas.agents.stac_scout.pystac_client.Client.open")
async def test_node_returns_correct_state_keys(mock_open):
    mock_open.return_value = _patched_search([_item("S2A_001", 5.0)])
    state: AtlasState = {
        "messages": [], "query": "test",
        "search_params": BASE_PARAMS,
        "stac_results": None, "geojson_features": None, "response": None,
    }
    result = await stac_scout_node(state)
    assert "stac_results" in result
    assert "geojson_features" in result
    assert len(result["stac_results"]) == 1
    assert len(result["geojson_features"]) == 1
