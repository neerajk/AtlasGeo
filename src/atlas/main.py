"""FastAPI entrypoint with WebSocket chat endpoint."""

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from langchain_core.messages import AIMessage, HumanMessage

from atlas.config import settings
from atlas.graph import build_graph
from atlas.state import AtlasState

_graph = None
_OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "outputs"

ANALYSIS_TASKS = {"ndvi", "ndwi", "ndbi", "evi", "flood_mapping", "burn_scar"}
_OUTPUT_TTL_HOURS = 24


def _cleanup_old_outputs():
    """Delete GeoTIFFs older than _OUTPUT_TTL_HOURS from the outputs directory."""
    cutoff = time.time() - _OUTPUT_TTL_HOURS * 3600
    removed = 0
    for f in _OUTPUTS_DIR.glob("*.tif"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            removed += 1
    if removed:
        print(f"[startup] cleaned up {removed} output file(s) older than {_OUTPUT_TTL_HOURS}h")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    key = settings.openrouter_api_key
    print(f"[startup] OPENROUTER_API_KEY loaded: {bool(key)} | length: {len(key)} | prefix: {key[:6]!r}")
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_old_outputs()
    _graph = build_graph()
    yield


app = FastAPI(title="Atlas GeoAI", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve analysis output GeoTIFFs so titiler can read them over HTTP
_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(_OUTPUTS_DIR)), name="outputs")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


async def _send_tif_result(websocket: WebSocket, task_type: str, output_tifs: list):
    """Build and send a tif_layers WS message for any analysis result type."""
    if not output_tifs:
        return

    if task_type in {"ndvi", "ndwi", "ndbi", "evi"}:
        tif_layers = [
            {
                "id": f"{t['scene_id']}_{t['index_type']}",
                "name": t["index_name"],
                "sceneId": t["scene_id"],
                "band": t["index_type"],
                "tileUrl": (
                    f"{{TITILER_URL}}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png"
                    f"?url={{BACKEND_URL}}/outputs/{t['output_filename']}"
                    f"&rescale=-1,1"
                    f"&colormap_name={t['colormap']}"
                ),
                "outputUrl": f"{{BACKEND_URL}}/outputs/{t['output_filename']}",
                "visible": True,
                "opacity": 0.8,
                "meanValue": t.get("mean_value"),
            }
            for t in output_tifs
        ]

    elif task_type == "burn_scar":
        tif_layers = [
            {
                "id": f"{t['scene_id']}_burn_scar",
                "name": "Burn Scar",
                "sceneId": t["scene_id"],
                "band": "burn_scar",
                "tileUrl": (
                    f"{{TITILER_URL}}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png"
                    f"?url={{BACKEND_URL}}/outputs/{t['output_filename']}"
                    f"&rescale=0,1"
                ),
                "outputUrl": f"{{BACKEND_URL}}/outputs/{t['output_filename']}",
                "visible": True,
                "opacity": 0.75,
                "burnAreaKm2": t.get("burn_area_km2"),
            }
            for t in output_tifs
        ]

    elif task_type == "flood_mapping":
        tif_layers = [
            {
                "id": f"{t['scene_id']}_flood",
                "name": "Flood Extent",
                "sceneId": t["scene_id"],
                "band": "flood",
                "tileUrl": (
                    f"{{TITILER_URL}}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}.png"
                    f"?url={{BACKEND_URL}}/outputs/{t['output_filename']}"
                    f"&rescale=0,1"
                ),
                "outputUrl": f"{{BACKEND_URL}}/outputs/{t['output_filename']}",
                "visible": True,
                "opacity": 0.75,
                "floodAreaKm2": t.get("flood_area_km2"),
            }
            for t in output_tifs
        ]
    else:
        return

    await websocket.send_json({"type": "tif_layers", "tif_layers": tif_layers})


async def _run_analysis(
    websocket: WebSocket,
    search_params: dict,
    stac_results: list,
    geojson_features: list,
):
    """Run a single-scene analysis and stream results back over the websocket."""
    from atlas.agents import flood_mapping_node, burn_scar_node, spectral_index_node, response_node

    task_type = (search_params or {}).get("task_type", "stac_search")
    print(f"[analysis] running {task_type} on {len(stac_results)} scene(s)")

    state: AtlasState = {
        "messages": [],
        "query": "",
        "search_params": search_params,
        "stac_results": stac_results,
        "geojson_features": geojson_features,
        "output_tifs": None,
        "response": None,
    }

    label_map = {
        "ndvi": "NDVI vegetation", "ndwi": "NDWI water", "ndbi": "NDBI built-up",
        "evi": "EVI vegetation", "flood_mapping": "flood mapping", "burn_scar": "burn scar",
    }
    label = label_map.get(task_type, task_type)
    await websocket.send_json({"type": "thinking", "message": f"Running {label} analysis…"})

    try:
        if task_type == "flood_mapping":
            result = await flood_mapping_node(state)
        elif task_type == "burn_scar":
            result = await burn_scar_node(state)
        elif task_type in {"ndvi", "ndwi", "ndbi", "evi"}:
            result = await spectral_index_node(state)
        else:
            result = {}
    except Exception as exc:
        import traceback
        print(f"[analysis] node error:\n{traceback.format_exc()}")
        await websocket.send_json({"type": "error", "message": str(exc)})
        return

    state = {**state, **result}
    output_tifs = result.get("output_tifs") or []

    if output_tifs:
        await websocket.send_json({
            "type": "thinking",
            "message": f"{label.capitalize()} complete. Rendering layer…",
        })
        await _send_tif_result(websocket, task_type, output_tifs)

    await websocket.send_json({"type": "thinking", "message": "Formatting results…"})
    response_result = await response_node(state)
    text = response_result.get("response") or ""
    if text:
        await websocket.send_json({"type": "message", "content": text})

    await websocket.send_json({"type": "done"})


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    print("[ws] client connected")

    pending_analysis: dict | None = None

    try:
        while True:
            data = await websocket.receive_json()

            # ── Scene picker: user clicked a scene ──────────────────────────
            if data.get("type") == "run_analysis":
                if not pending_analysis:
                    await websocket.send_json({"type": "error", "message": "No pending analysis."})
                    continue

                scene_id = data.get("scene_id", "")
                stac_results = pending_analysis["stac_results"]
                selected = next((r for r in stac_results if r["id"] == scene_id), None)

                if not selected:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Scene '{scene_id}' not found in results.",
                    })
                    continue

                try:
                    await _run_analysis(
                        websocket,
                        search_params=pending_analysis["search_params"],
                        stac_results=[selected],
                        geojson_features=pending_analysis["geojson_features"],
                    )
                except WebSocketDisconnect:
                    print("[ws] client disconnected during analysis")
                    return
                except Exception as exc:
                    import traceback
                    print(f"[ws] ERROR during _run_analysis:\n{traceback.format_exc()}")
                    try:
                        await websocket.send_json({"type": "error", "message": str(exc)})
                    except Exception:
                        pass

                pending_analysis = None
                continue

            # ── Normal query ─────────────────────────────────────────────────
            query = (data.get("query") or "").strip()
            if not query:
                continue

            print(f"[ws] query received: {query!r}")
            await websocket.send_json({"type": "thinking", "message": "Planning search..."})

            raw_history = data.get("history") or []
            lc_messages = [
                HumanMessage(content=m["content"]) if m.get("role") == "user"
                else AIMessage(content=m["content"])
                for m in raw_history
                if m.get("content")
            ]

            initial_state: AtlasState = {
                "messages": lc_messages,
                "query": query,
                "search_params": None,
                "stac_results": None,
                "geojson_features": None,
                "output_tifs": None,
                "response": None,
            }

            try:
                print("[ws] starting graph stream")
                current_search_params: dict = {}

                async for chunk in _graph.astream(initial_state, stream_mode="updates"):
                    print(f"[ws] chunk from node(s): {list(chunk.keys())}")

                    if "planner" in chunk:
                        sp = chunk["planner"].get("search_params") or {}
                        current_search_params = sp
                        task = sp.get("task_type", "stac_search")
                        print(f"[ws] planner done → task={task}, params: {sp}")
                        await websocket.send_json({
                            "type": "thinking",
                            "message": "Searching satellite archives...",
                        })

                    if "stac_scout" in chunk:
                        # stac_scout returns updated search_params (fallback-adjusted)
                        updated_sp = chunk["stac_scout"].get("search_params")
                        if updated_sp:
                            current_search_params = updated_sp
                        stac_results_data = chunk["stac_scout"].get("stac_results") or []
                        features = chunk["stac_scout"].get("geojson_features") or []
                        n = len(features)
                        task_type = current_search_params.get("task_type", "stac_search")

                        print(f"[ws] stac_scout done → {n} scene(s), task={task_type}")

                        if task_type in ANALYSIS_TASKS and n > 0:
                            # Scene picker flow: pause graph, prompt user to select
                            pending_analysis = {
                                "task_type": task_type,
                                "stac_results": stac_results_data,
                                "search_params": current_search_params,
                                "geojson_features": features,
                            }
                            await websocket.send_json({"type": "geojson", "features": features})
                            await websocket.send_json({
                                "type": "scene_picker",
                                "task_type": task_type,
                                "scene_count": n,
                            })
                            await websocket.send_json({"type": "done"})
                            break  # stop graph — wait for run_analysis message

                        if task_type in ANALYSIS_TASKS and n == 0:
                            # Analysis requested but no scenes found — let graph produce error response
                            await websocket.send_json({
                                "type": "thinking",
                                "message": "No scenes found. Preparing response...",
                            })
                        else:
                            await websocket.send_json({
                                "type": "thinking",
                                "message": f"Found {n} scene{'s' if n != 1 else ''}. Formatting...",
                            })
                            if features:
                                await websocket.send_json({"type": "geojson", "features": features})

                    if "spectral_index" in chunk:
                        output_tifs = chunk["spectral_index"].get("output_tifs") or []
                        print(f"[ws] spectral_index done → {len(output_tifs)} output(s)")
                        if output_tifs:
                            idx = output_tifs[0].get("index_name", "Index")
                            await websocket.send_json({
                                "type": "thinking",
                                "message": f"{idx} analysis complete. Rendering layer...",
                            })
                            await _send_tif_result(
                                websocket,
                                current_search_params.get("task_type", "ndvi"),
                                output_tifs,
                            )

                    if "burn_scar" in chunk:
                        output_tifs = chunk["burn_scar"].get("output_tifs") or []
                        print(f"[ws] burn_scar done → {len(output_tifs)} output(s)")
                        if output_tifs:
                            await websocket.send_json({
                                "type": "thinking",
                                "message": "Burn scar analysis complete. Rendering layer...",
                            })
                            await _send_tif_result(websocket, "burn_scar", output_tifs)

                    if "flood_mapping" in chunk:
                        output_tifs = chunk["flood_mapping"].get("output_tifs") or []
                        print(f"[ws] flood_mapping done → {len(output_tifs)} output(s)")
                        if output_tifs:
                            await websocket.send_json({
                                "type": "thinking",
                                "message": "Flood analysis complete. Rendering layer...",
                            })
                            await _send_tif_result(websocket, "flood_mapping", output_tifs)

                    if "response" in chunk:
                        text = chunk["response"].get("response") or ""
                        print(f"[ws] response done → {len(text)} chars")
                        if text:
                            await websocket.send_json({"type": "message", "content": text})

                else:
                    # Graph ran to completion (not broken by scene_picker)
                    print("[ws] graph stream complete")
                    await websocket.send_json({"type": "done"})

            except WebSocketDisconnect:
                print("[ws] client disconnected mid-stream — aborting")
                return
            except Exception as exc:
                import traceback
                print(f"[ws] ERROR during graph run:\n{traceback.format_exc()}")
                try:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                except Exception:
                    pass

    except WebSocketDisconnect:
        print("[ws] client disconnected")
