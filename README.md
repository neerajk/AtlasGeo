# Atlas GeoAI

**Talk to satellite imagery. No GIS degree required.**

```
You:   "Show me Sentinel-2 over Mumbai last month, under 10% cloud cover"
Atlas: Found 8 scenes → footprints on globe → download links ready
       Done in 4 seconds.
```

[screenshot placeholder]

---

## The problem

Satellite data is everywhere. Accessing it isn't.

You need to know STAC, pystac, EPSG codes, cloud-optimized GeoTIFFs, tile servers, and a dozen CLI tools just to look at a single image. Most people give up before they start.

Atlas makes it a conversation.

---

## How it works

Type a question. Atlas runs a 3-step pipeline under the hood:

```
[Planner]  →  extract bbox + date + cloud filter from your words
    ↓
[STAC Scout]  →  search Element84 Earth Search (500M+ scenes)
    ↓
[Response]  →  render footprints on globe + format results
```

Every step streams back to your browser in real time. You see it thinking.

---

## Stack

| | |
|---|---|
| **Frontend** | React + Vite + TypeScript |
| **Globe** | MapLibre GL v4 + deck.gl v9 — no Mapbox token, no cost |
| **Base map** | ESRI World Imagery (satellite, free) |
| **Backend** | FastAPI + WebSocket streaming |
| **Agents** | LangGraph stateful DAG |
| **LLM** | Any — Ollama (local), OpenRouter, Anthropic, Groq, Google |
| **Satellite data** | STAC — Element84 Earth Search v1 (Sentinel-2, Landsat, more) |
| **Tools** | `@atlas_tool` — one decorator, auto-discovered, auto-schema |

---

## Quickstart

```bash
git clone https://github.com/your-org/atlas-geoai
cd atlas-geoai

# Install (micromamba recommended, plain pip works too)
make env      # creates atlas conda env
make dev      # starts backend :8000 + frontend :5173
```

Open `http://localhost:5173`. Ask about anywhere on Earth.

**Minimum config:** one LLM key in `.env`. Ollama (local) works with zero keys.

```bash
cp .env.example .env
# OPENROUTER_API_KEY=...  or  OLLAMA_BASE_URL=http://localhost:11434
```

---

## Try these queries

```
"Sentinel-2 over the Amazon deforestation front, last 3 months"
"Show me cloud-free imagery over Tokyo this week"
"Nairobi in March 2024, less than 5% cloud cover"
"Any Sentinel-2 scenes over the Nile Delta from 2025?"
```

---

## Add a tool in one function

Every Atlas capability is a decorated Python function. Drop one file and it's live:

```python
# tools/ndvi/tool.py
from atlas.tools import atlas_tool

@atlas_tool(
    name="calculate_ndvi",
    description="Compute vegetation index from Sentinel-2 red/NIR bands",
    tags=["vegetation", "sentinel-2", "ndvi"],
)
def calculate_ndvi(red_url: str, nir_url: str, bbox: list[float]) -> dict:
    # your logic
    return {"ndvi_path": "...", "stats": {...}}
```

No registration. No config. Agents discover it by description at startup.

---

## Project layout

```
atlas-geoai/
├── src/atlas/
│   ├── agents/          # planner, stac_scout, response — LangGraph nodes
│   ├── models/router.py # routes "ollama/..." "anthropic/..." "openrouter/..."
│   ├── tools/           # @atlas_tool registry + auto-loader
│   └── state.py         # AtlasState — the shared dict that flows through all nodes
├── tools/               # community tools (drop a folder here)
│   ├── stac_search/
│   └── get_cog_url/
├── frontend/            # Vite + React + MapLibre + deck.gl
└── config/models.yaml   # per-agent LLM routing
```

---

## LLM routing

Atlas works with any LLM. Set the prefix in `config/models.yaml` or override per-agent at runtime:

```yaml
# config/models.yaml
agents:
  planner:
    primary: "ollama/nemotron-3-nano:30b-cloud"   # local, free
  stac_scout:
    primary: "openrouter/meta-llama/llama-3.3-70b-instruct:free"
  response:
    primary: "anthropic/claude-sonnet-4-6"
```

```bash
# or override at runtime
ATLAS_MODEL_PLANNER=anthropic/claude-opus-4-7 make dev
```

---

## Deploy free

| Service | What |
|---|---|
| Cloudflare Pages | Frontend (`npm run build` → deploy `dist/`) |
| Hugging Face Spaces | Backend (Docker SDK, free CPU tier) |
| Fly.io | Backend alternative (free tier) |

---

## Roadmap

```
✅ L1 — Natural language → STAC search → globe footprints + download links
⬜ L2 — titiler: see actual pixels, not just footprints
⬜ L2 — ml-intern: auto-discover HuggingFace models for new task types
⬜ L3 — Community Tool Registry: developers publish @atlas_tool functions
⬜ L3 — Self-improving feedback loop: user corrections → fine-tune → new version
⬜ L4 — Full GeoAI platform: LULC, flood mapping, object detection, OSINT, and more
```

Full roadmap with architecture diagrams, all task categories, ready-to-use models, and community design: **[ROADMAP.md](ROADMAP.md)**

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The fastest contribution: add a tool in `tools/`. One function, one file, open a PR.

---

MIT License
