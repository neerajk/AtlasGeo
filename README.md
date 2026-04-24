# Atlas GeoAI

**Talk to satellite imagery. No GIS degree required.**

```
You:   "Show me Sentinel-2 over Mumbai last month, under 10% cloud cover"
Atlas: Found 8 scenes → footprints on globe → click any scene → pixels stream in
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

Type a question. Atlas runs a 4-step pipeline under the hood:

```
[Planner]     →  extract bbox + date + cloud filter from your words
    ↓
[STAC Scout]  →  search Element84 Earth Search (500M+ scenes)
    ↓
[Response]    →  render footprints on globe + format results
    ↓
[titiler]     →  click a footprint, stream actual pixels from Cloud-Optimized GeoTIFFs
```

Every step streams back to your browser in real time. You see it thinking.

---

## See actual pixels

Once footprints appear on the globe, click any scene. A **Layer Panel** opens showing:

- Scene metadata (date, cloud cover, platform)
- Band buttons: **True Color · Red · NIR · Green · Blue**
- Per-layer controls: **toggle visibility · opacity slider · remove**

Click a band — titiler streams the Cloud-Optimized GeoTIFF tiles directly into MapLibre. No download required.

---

## Stack

| | |
|---|---|
| **Frontend** | React + Vite + TypeScript |
| **Globe** | MapLibre GL v4 + deck.gl v9 — no Mapbox token, no cost |
| **Base map** | ESRI World Imagery (satellite, free) |
| **Pixels** | titiler — COG tile server, streams Sentinel-2 bands on demand |
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

# Install (micromamba recommended)
make env      # creates atlas conda env + npm install
make dev      # starts backend :8000 + titiler :8001 + frontend :5173
```

Open `http://localhost:5173`. Ask about anywhere on Earth.

**Minimum config:** Ollama (local) works with zero keys.

```bash
cp .env.example .env
# OLLAMA_BASE_URL=http://localhost:11434   ← zero config if Ollama is running
# OPENROUTER_API_KEY=sk-or-v1-...         ← or use any cloud LLM
```

**`make dev` starts three services:**

| Service | Port | Role |
|---|---|---|
| Backend (FastAPI + LangGraph) | 8000 | NL → STAC pipeline, WebSocket |
| Titiler (COG tile server) | 8001 | Streams satellite pixels on demand |
| Frontend (React + Vite) | 5173 | Globe, chat, layer panel |

---

## Try these queries

```
"Sentinel-2 over the Amazon deforestation front, last 3 months"
"Show me cloud-free imagery over Tokyo this week"
"Nairobi in March 2024, less than 5% cloud cover"
"Any Sentinel-2 scenes over the Nile Delta from 2025?"
```

Then click any footprint to stream its pixels.

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
│   ├── agents/              # planner, stac_scout, response — LangGraph nodes
│   ├── models/router.py     # routes "ollama/..." "anthropic/..." "openrouter/..."
│   ├── tools/               # @atlas_tool registry + auto-loader
│   └── state.py             # AtlasState — shared dict flowing through all nodes
├── tools/                   # community tools (drop a folder here)
│   ├── stac_search/
│   └── get_cog_url/
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Globe.tsx    # MapLibre + deck.gl + COG raster layer sync
│       │   ├── ChatPanel.tsx
│       │   └── LayerPanel.tsx  # band selector + per-layer toggle/opacity
│       └── types/index.ts   # GeoJsonFeature, CogLayer, WsMessage
└── config/models.yaml       # per-agent LLM routing
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
# override at runtime
ATLAS_MODEL_PLANNER=anthropic/claude-opus-4-7 make dev
```

---

## Deploy free

| Service | What |
|---|---|
| Cloudflare Pages | Frontend (`npm run build` → deploy `dist/`) |
| Hugging Face Spaces | Backend + titiler (Docker SDK, free CPU tier) |
| Fly.io | Backend + titiler alternative (free tier) |

Set `VITE_TITILER_URL` in your frontend build env to point at the deployed titiler instance.

---

## Roadmap

```
✅ L1 — Natural language → STAC search → globe footprints + download links
✅ L2 — titiler: stream actual pixels, band selector, per-layer toggle + opacity
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
