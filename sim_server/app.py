# sim_server/app.py
"""FastAPI：场景配置 REST + 仿真 WebSocket 推帧。"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Literal, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DT
from .scene_schema import SceneConfig, default_scene_config, list_presets
from .session import SimSession

_session = SimSession(default_scene_config())
_clients: Set[WebSocket] = set()
_lock = asyncio.Lock()
_loop_task: asyncio.Task | None = None


class ControlBody(BaseModel):
    action: Literal["start", "pause", "resume", "reset"]


def get_session() -> SimSession:
    return _session


async def _broadcast(message: Dict[str, Any]) -> None:
    if not _clients:
        return
    payload = json.dumps(message, default=list)
    dead: list[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


async def _sim_loop() -> None:
    """后台按 DT 推进仿真并广播帧。"""
    try:
        while True:
            async with _lock:
                sess = _session
                snap = None
                if sess.status == "running":
                    snap = sess.step_once()
                status_msg = {"type": "status", "data": sess.status_payload()}

            await _broadcast(status_msg)
            if snap is not None:
                await _broadcast({"type": "frame", "data": snap})
            await asyncio.sleep(DT)
    except asyncio.CancelledError:
        return


def _ensure_loop() -> None:
    global _loop_task
    if _loop_task is None or _loop_task.done():
        _loop_task = asyncio.create_task(_sim_loop())


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    global _loop_task
    _ensure_loop()
    try:
        yield
    finally:
        if _loop_task is not None:
            _loop_task.cancel()
            try:
                await _loop_task
            except asyncio.CancelledError:
                pass
            _loop_task = None


app = FastAPI(title="AutoSim Web", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"ok": "true"}


@app.get("/api/presets")
async def get_presets() -> Dict[str, Any]:
    """预设路线/场景（含转弯与主辅路示例）。"""
    presets = list_presets()
    return {
        "presets": [
            {
                "id": p["id"],
                "title": p["title"],
                "description": p["description"],
            }
            for p in presets.values()
        ],
        "scenes": {k: v["scene"] for k, v in presets.items()},
    }


@app.get("/api/scene")
async def get_scene() -> Dict[str, Any]:
    async with _lock:
        return {
            "draft": _session.draft_config.model_dump(),
            "applied": _session.applied_config.model_dump(),
            "status": _session.status_payload(),
        }


@app.put("/api/scene")
async def put_scene(body: SceneConfig) -> Dict[str, Any]:
    """写入草稿配置（不立刻重建 episode）。"""
    async with _lock:
        try:
            body.to_route()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _session.set_draft(body)
        return {"ok": True, "draft": _session.draft_config.model_dump()}


@app.post("/api/control")
async def control(body: ControlBody) -> Dict[str, Any]:
    async with _lock:
        if body.action == "start":
            _session.start()
        elif body.action == "pause":
            _session.pause()
        elif body.action == "resume":
            _session.resume()
        elif body.action == "reset":
            _session.reset()
        _ensure_loop()
        return {"ok": True, "status": _session.status_payload()}


@app.websocket("/ws/sim")
async def ws_sim(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)
    _ensure_loop()
    try:
        async with _lock:
            status = _session.status_payload()
            last = _session.current_snapshot()
        await websocket.send_text(json.dumps({"type": "status", "data": status}))
        if last is not None:
            await websocket.send_text(
                json.dumps({"type": "frame", "data": last}, default=list)
            )
        while True:
            # 客户端可发 ping；忽略内容，保持连接
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)


_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@app.get("/")
async def index() -> Any:
    index_html = _WEB_DIST / "index.html"
    if index_html.is_file():
        return FileResponse(index_html)
    return {
        "message": "AutoSim API running. Build web UI with: cd web && npm install && npm run build",
        "docs": "/docs",
        "ws": "/ws/sim",
    }


if _WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_WEB_DIST / "assets"), name="assets")


def main() -> None:
    import uvicorn

    uvicorn.run("sim_server.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
