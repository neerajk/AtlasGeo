# Atlas GeoAI — v2

**Talk to satellite imagery. No GIS degree required.**

```
You:   "Show me Sentinel-2 over Mumbai last month, under 10% cloud cover"
Atlas: Found 8 scenes → footprints on globe → click any scene → pixels stream in
       Done in 4 seconds.

You:   "Now show the same area but last week"
Atlas: [remembers context] → searches Mumbai, previous week → new results
```

[screenshot placeholder]

---

## The problem

Satellite data is everywhere. Accessing it isn't.

You need to know STAC, pystac, EPSG codes, cloud-optimized GeoTIFFs, tile servers, and a dozen CLI tools just to look at a single image. Most people give up before they start.

Atlas makes it a conversation.

---

## How it works

Type a question. Atlas runs a pipeline under the hood:

```
[Planner]     →  extract bbox + date + cloud filter from your words
    ↓              (conversation history included — follow-up queries work)
[STAC Scout]  →  search Element84 Earth Search (500M+ scenes)
    ↓
[Router]      →  stac_search or flood_mapping based on task type
    ↓
[Response]    →  render footprints on globe + format results
    ↓
[titiler]     →  click a footprint → full-screen scene viewer → stream pixels
```

Every step streams back to your browser in real time. You see it thinking.

---

## Inspect scenes

Click any footprint on the globe. A **full-screen scene viewer** opens showing:

- Your own isolated map with the scene loaded
- **Left panel:**
  - Scene metadata (ID, date, cloud cover, platform, source)
  - Loaded layers — visibility toggle, opacity slider, remove
  - Add bands: True Color, Red, NIR, Green, Blue, SWIR
  - Download links for every available band

Bands stream as Cloud-Optimized GeoTIFF tiles via titiler — no download required.

---

## Flood mapping

Ask about floods and Atlas switches automatically to analysis mode:

```
"Show flood extent over Punjab in September 2024"
```

→ Finds Sentinel-2 scene → computes MNDWI (green − SWIR) → writes GeoTIFF →
streams blue flood-extent layer directly into the scene viewer.

---

## Stack

| | |
|---|---|
| **Frontend** | React 18 + Vite + TypeScript |
| **Globe** | MapLibre GL v4 + deck.gl v9 — no Mapbox token, no cost |
| **Base map** | ESRI World Imagery (satellite, free) |
| **Pixels** | titiler 2.0 — COG tile server, streams Sentinel-2 bands on demand |
| **Backend** | FastAPI + WebSocket streaming |
| **Agents** | LangGraph stateful DAG with conversation history |
| **LLM** | Any — Ollama (local, zero key), Anthropic, OpenRouter, Groq |
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

**Minimum config: Ollama works with zero API keys.**

```bash
cp .env.example .env
# OLLAMA_BASE_URL=http://localhost:11434   ← zero config if Ollama is running
# OPENROUTER_API_KEY=sk-or-v1-...         ← or use any cloud LLM (OR key format)
# ANTHROPIC_API_KEY=sk-ant-...            ← or Anthropic directly
```

**`make dev` starts three services:**

| Service | Port | Role |
|---|---|---|
| Backend (FastAPI + LangGraph) | 8000 | NL → STAC pipeline, WebSocket |
| Titiler (COG tile server) | 8001 | Streams satellite pixels on demand |
| Frontend (React + Vite) | 5173 | Globe, chat, scene viewer |

---

## Try these queries

```
"Sentinel-2 over the Amazon deforestation front, last 3 months"
"Show flood extent over Bangladesh in September 2024"
"Nairobi in March 2024, less than 5% cloud cover"
"Cloud-free imagery over Tokyo this week"
```

Then click any footprint. Follow up with "show the same area last year" — Atlas remembers.

---

## Add a tool in one function

Every Atlas capability is a decorated Python function. Drop one file and it's live:

```python
# tools/burn_scar/tool.py
from atlas.tools import atlas_tool

@atlas_tool(
    name="burn_scar_mapping",
    description="Map wildfire burn scars from Sentinel-2 using NBR (nir - swir22)",
    tags=["sentinel-2", "fire", "burn-scar", "nbr"],
)
def burn_scar_mapping(nir_url: str, swir22_url: str, bbox: list[float]) -> dict:
    # NBR = (nir - swir22) / (nir + swir22)
    return {"output_path": "...", "burn_area_km2": ...}
```

No registration. No config. Agents discover it at startup.

---

## Project layout

```
atlas-geoai/
├── src/atlas/
│   ├── agents/
│   │   ├── planner.py       # extracts bbox, dates, task_type; Nominatim fallback
│   │   ├── stac_scout.py    # Element84 search; semantic asset keys
│   │   ├── flood_mapping.py # MNDWI node; picks best scene by cloud cover
│   │   └── response.py      # markdown formatting; flood-area stats
│   ├── models/
│   │   └── router.py        # routes ollama/ anthropic/ openrouter/ prefixes
│   ├── tools/               # @atlas_tool registry + auto-loader
│   ├── state.py             # AtlasState — shared dict + conversation messages
│   └── main.py              # WebSocket handler; history parsing; /outputs serving
├── tools/                   # community tools (drop a folder here)
│   ├── stac_search/
│   ├── flood_mapping/       # MNDWI → GeoTIFF
│   └── get_cog_url/
├── frontend/src/
│   ├── api/atlas.ts         # AtlasSocket — sends {query, history[]}
│   ├── components/
│   │   ├── Globe.tsx        # MapLibre + deck.gl footprints + COG raster layers
│   │   ├── SceneDrawer.tsx  # full-screen popup; own MapLibre map; layer panel
│   │   └── ChatPanel.tsx    # WebSocket messages; streams thinking steps
│   └── types/index.ts       # GeoJsonFeature, CogLayer, WsMessage
└── config/models.yaml       # per-agent LLM routing (primary + fallback)
```

---

## LLM routing

Atlas works with any LLM. Set the prefix in `config/models.yaml`:

```yaml
agents:
  planner:
    primary: "ollama/gemma4:31b-cloud"      # local, free — recommended
    fallback: "ollama/nemotron-3-nano:30b-cloud"
  stac_scout:
    primary: "ollama/gemma4:31b-cloud"
  response:
    primary: "anthropic/claude-haiku-4-5"   # or any cloud model
```

```bash
# override at runtime
ATLAS_MODEL_PLANNER=anthropic/claude-sonnet-4-6 make dev
```

Supported prefixes: `ollama/` · `anthropic/` · `openrouter/` · `groq/` · `google/`

---

## Conversation history

Every query includes prior conversation turns. The planner sees context so follow-ups resolve correctly:

```
"Show Sentinel-2 over Nairobi last month"       → searches Nairobi, March 2026
"Now filter to less than 5% cloud cover"         → re-searches same bbox + dates
"What about the week before?"                    → expands date range backward
```

History flows: `ChatPanel → WebSocket → main.py → AtlasState.messages → planner LLM`

---

## Deploy free

| Service | What |
|---|---|
| Cloudflare Pages | Frontend (`npm run build` → deploy `dist/`) |
| Hugging Face Spaces | Backend + titiler (Docker SDK, free CPU tier) |
| Fly.io | Backend + titiler alternative (free tier) |

Set `VITE_TITILER_URL` and `VITE_BACKEND_URL` in your frontend build env.

---

## Roadmap

```
✅ v1 — Natural language → STAC search → globe footprints + download links
✅ v1 — titiler: stream actual pixels, band selector, per-layer toggle + opacity
✅ v2 — Full-screen scene viewer (SceneDrawer) with isolated MapLibre map
✅ v2 — Flood mapping (MNDWI) with auto-overlay
✅ v2 — Conversation history: follow-up queries resolve from context
✅ v2 — Geocoding fallback (Nominatim) when LLM bbox is null
⬜ v3 — Burn scar tool (NBR) — same pipeline as flood, ~1 day
⬜ v3 — ml-intern: auto-discover HuggingFace models for new task types
⬜ v4 — Community Tool Registry: developers publish @atlas_tool functions
⬜ v5 — Self-improving feedback loop: user corrections → fine-tune → new version
```

Full roadmap: **[ROADMAP.md](ROADMAP.md)**

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The fastest contribution: add a tool in `tools/`. One function, one file, open a PR.

---

MIT License
