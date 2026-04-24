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
micromamba run -n atlas pytest tools/my_tool/test_tool.py -v
```

6. Open a PR. CI will lint + run your test automatically.

---

## Tool guidelines

- Return a `dict` always (not a string, not None)
- Accept only JSON-serializable inputs (`str`, `int`, `float`, `list`, `dict`, `bool`)
- Raise descriptive exceptions on bad input — don't swallow errors
- Keep side effects minimal (no writing to shared state)
- Tag correctly — agents use tags to find relevant tools

## Available tags

`sentinel-2` `landsat` `stac` `cog` `gdal` `vegetation` `water` `urban` `agriculture`
`spectral-index` `download` `search` `analysis` `visualization` `flood` `change-detection`
`object-detection` `segmentation` `inference` `huggingface`

---

## Dev setup

```bash
git clone https://github.com/your-org/atlas-geoai
cd atlas-geoai

# Create conda env + install frontend deps
make env

# Copy and configure env
cp .env.example .env
# Set at minimum one of:
#   OLLAMA_BASE_URL=http://localhost:11434   (local, zero cost)
#   OPENROUTER_API_KEY=sk-or-v1-...

# Start all three services
make dev
# backend  → http://localhost:8000
# titiler  → http://localhost:8001
# frontend → http://localhost:5173
```

**Individual services:**

```bash
make backend   # FastAPI + LangGraph only
make titiler   # COG tile server only
make frontend  # Vite dev server only
```

**Lint + test:**

```bash
make lint   # ruff + tsc --noEmit
make test   # pytest (16 tests, all mocked, ~1s)
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OPENROUTER_API_KEY` | — | OpenRouter key (`sk-or-v1-*` format) |
| `ANTHROPIC_API_KEY` | — | Anthropic key |
| `GROQ_API_KEY` | — | Groq key |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | WebSocket URL for frontend |
| `VITE_TITILER_URL` | `http://localhost:8001` | titiler URL for COG tile streaming |

---

## Architecture overview

```
User prompt
    │
    ▼
FastAPI WebSocket (/ws)
    │
    ▼
LangGraph DAG  ──────────────────────────────────────┐
    │                                                  │
    ├── planner_node      (LLM: extracts bbox/dates)   │
    ├── stac_scout_node   (pystac-client → Element84)  │
    └── response_node     (LLM: formats reply)         │
                                                       │
    ◄──────── stream_mode="updates" ───────────────────┘
    │
    ▼
Frontend WebSocket client
    │
    ├── footprint polygons → deck.gl GeoJsonLayer on MapLibre globe
    └── scene click → LayerPanel → band URL → titiler tiles → MapLibre raster layer
```

**Adding a LangGraph node:** add a function to `src/atlas/agents/`, register it in `src/atlas/graph.py`, add it to `AtlasState` in `src/atlas/state.py`.

**Adding a tool:** drop `tools/<name>/tool.py` with `@atlas_tool`. Auto-discovered at startup.

**Switching LLM:** edit `config/models.yaml` or set `ATLAS_MODEL_<AGENT>=prefix/model-id` at runtime.
