# Contributing to Atlas GeoAI

## Adding a new tool (5 minutes)

1. Fork the repo
2. Create `tools/<your_tool_name>/tool.py`
3. Write your function with `@atlas_tool`:

```python
from atlas.tools import atlas_tool

@atlas_tool(
    name="my_tool",
    description="One sentence — what this tool does and when to use it.",
    tags=["sentinel-2", "your-topic"],
)
def my_tool(param_a: str, param_b: float) -> dict:
    """
    Args:
        param_a: description
        param_b: description
    """
    # your logic
    return {"result": ...}
```

4. Add `tools/<your_tool_name>/test_tool.py`:

```python
from tools.my_tool.tool import my_tool

def test_my_tool():
    result = my_tool(param_a="test", param_b=1.0)
    assert "result" in result
```

5. Test locally:
```bash
pip install -e ".[dev]"
pytest tools/my_tool/test_tool.py -v
```

6. Open a PR. CI will lint + run your test automatically.

## Tool guidelines

- Return a `dict` always (not a string, not None)
- Accept only JSON-serializable inputs (str, int, float, list, dict, bool)
- Raise descriptive exceptions on bad input — don't swallow errors
- Keep side effects minimal (no writing to shared state)
- Tag correctly — agents use tags to find relevant tools

## Available tags

`sentinel-2` `landsat` `stac` `cog` `gdal` `vegetation` `water` `urban` `agriculture` `spectral-index` `download` `search` `analysis` `visualization`

## Dev setup

```bash
git clone https://github.com/your-org/atlas-geoai
cd atlas-geoai
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # add your OPENROUTER_API_KEY
make dev
```
