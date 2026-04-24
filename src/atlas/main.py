"""FastAPI entrypoint with WebSocket chat endpoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from atlas.config import settings
from atlas.graph import build_graph
from atlas.state import AtlasState

_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    key = settings.openrouter_api_key
    print(f"[startup] OPENROUTER_API_KEY loaded: {bool(key)} | length: {len(key)} | prefix: {key[:6]!r}")
    _graph = build_graph()
    yield


app = FastAPI(title="Atlas GeoAI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


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

            initial_state: AtlasState = {
                "messages": [],
                "query": query,
                "search_params": None,
                "stac_results": None,
                "geojson_features": None,
                "response": None,
            }

            try:
                print("[ws] starting graph stream")
                async for chunk in _graph.astream(initial_state, stream_mode="updates"):
                    print(f"[ws] chunk from node(s): {list(chunk.keys())}")

                    if "planner" in chunk:
                        print(f"[ws] planner done → search_params: {chunk['planner'].get('search_params')}")
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
