"""FastAPI backend for the NTC TAK demo."""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db
from .cot import parse_cot
from .simulation import simulation

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    simulation.start()
    yield
    simulation.stop()


app = FastAPI(title="NTC TAK Demo", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/state")
def get_state():
    return simulation.snapshot()


@app.get("/api/units")
def get_units():
    return simulation.snapshot()["units"]


@app.get("/api/stats")
def get_stats():
    return simulation.snapshot()["stats"]


@app.get("/api/playback/meta")
def playback_meta():
    return simulation.meta()


@app.get("/api/playback/snapshot")
def playback_snapshot(tick: int):
    snap = simulation.snapshot_at(tick)
    if snap is None:
        raise HTTPException(status_code=404, detail="no snapshots computed yet")
    return snap


@app.get("/api/cot/recent")
def recent_cot(limit: int = 20):
    rows = db.get_conn().execute(
        "SELECT uid, xml, created_at FROM cot_events ORDER BY id DESC LIMIT ?",
        (min(limit, 200),),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/messages/recent")
def recent_messages(limit: int = 50):
    rows = db.get_conn().execute(
        """SELECT tick, src_uid, dst_uid, src_mesh, dst_mesh, hops, quality, delivered, created_at
           FROM message_log ORDER BY id DESC LIMIT ?""",
        (min(limit, 500),),
    ).fetchall()
    return [dict(r) for r in rows]


class InjectUnit(BaseModel):
    callsign: str
    role: str = "infantry"
    affiliation: str = "friendly"
    mesh_id: str | None = None
    lat: float
    lon: float
    target_lat: float | None = None
    target_lon: float | None = None
    speed_mps: float = 5.0


class MoveOrder(BaseModel):
    target_lat: float
    target_lon: float
    speed_mps: float | None = None


@app.post("/api/inject/unit")
def inject_unit(spec: InjectUnit):
    return simulation.inject_unit(spec.model_dump())


@app.post("/api/inject/cot")
async def inject_cot(request: Request):
    xml = (await request.body()).decode("utf-8", errors="replace")
    try:
        spec = parse_cot(xml)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    existing = {u["uid"]: u for u in simulation.injected_units()}
    if spec["uid"] in existing:
        simulation.move_unit(spec["uid"], spec["lat"], spec["lon"], speed_mps=999.0)
        return {**existing[spec["uid"]], "updated": True}
    return simulation.inject_unit(spec)


@app.post("/api/inject/unit/{uid}/move")
def move_unit(uid: str, order: MoveOrder):
    if not simulation.move_unit(uid, order.target_lat, order.target_lon, order.speed_mps):
        raise HTTPException(status_code=404, detail="unknown or destroyed injected unit")
    return {"ok": True}


@app.delete("/api/inject/unit/{uid}")
def destroy_unit(uid: str):
    if not simulation.destroy_unit(uid):
        raise HTTPException(status_code=404, detail="unknown injected unit")
    return {"ok": True}


@app.get("/api/inject/units")
def list_injected():
    return simulation.injected_units()


@app.get("/console")
def console():
    return FileResponse(os.path.join(STATIC_DIR, "console.html"))


@app.websocket("/ws/state")
async def ws_state(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(simulation.snapshot())
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
