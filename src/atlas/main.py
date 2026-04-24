"""FastAPI entrypoint with WebSocket chat endpoint."""

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    key = settings.openrouter_api_key
    print(f"[startup] OPENROUTER_API_KEY loaded: {bool(key)} | length: {len(key)} | prefix: {key[:6]!r}")
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
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


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    print("[ws] client connected")

    try:
        while True:
            data = await websocket.receive_json()
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
                async for chunk in _graph.astream(initial_state, stream_mode="updates"):
                    print(f"[ws] chunk from node(s): {list(chunk.keys())}")

                    if "planner" in chunk:
                        sp = chunk["planner"].get("search_params") or {}
                        task = sp.get("task_type", "stac_search")
                        print(f"[ws] planner done → task={task}, params: {sp}")
                        await websocket.send_json({
                            "type": "thinking",
                            "message": "Searching satellite archives...",
                        })

                    if "stac_scout" in chunk:
                        features = chunk["stac_scout"].get("geojson_features") or []
                        n = len(features)
                        print(f"[ws] stac_scout done → {n} scene(s) found")
                        await websocket.send_json({
                            "type": "thinking",
                            "message": f"Found {n} scene{'s' if n != 1 else ''}. Formatting...",
                        })
                        if features:
                            await websocket.send_json({
                                "type": "geojson",
                                "features": features,
                            })

                    if "flood_mapping" in chunk:
                        output_tifs = chunk["flood_mapping"].get("output_tifs") or []
                        print(f"[ws] flood_mapping done → {len(output_tifs)} output(s)")
                        if output_tifs:
                            await websocket.send_json({
                                "type": "thinking",
                                "message": "Flood analysis complete. Rendering layer...",
                            })
                            # Build CogLayer objects the frontend understands
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
                            await websocket.send_json({
                                "type": "tif_layers",
                                "tif_layers": tif_layers,
                            })

                    if "response" in chunk:
                        text = chunk["response"].get("response") or ""
                        print(f"[ws] response done → {len(text)} chars")
                        if text:
                            await websocket.send_json({"type": "message", "content": text})

                print("[ws] graph stream complete")
                await websocket.send_json({"type": "done"})

            except Exception as exc:
                import traceback
                print(f"[ws] ERROR during graph run:\n{traceback.format_exc()}")
                await websocket.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        print("[ws] client disconnected")
