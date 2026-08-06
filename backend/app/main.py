"""FastAPI backend for the NTC TAK demo."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .simulation import simulation


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


@app.websocket("/ws/state")
async def ws_state(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(simulation.snapshot())
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
