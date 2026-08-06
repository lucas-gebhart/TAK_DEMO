# TAK_DEMO — NTC Mesh Network Simulation

A TAK-style situational awareness demo centered on the **National Training Center (Fort Irwin, CA)**:

- **Backend** (FastAPI + SQLite): mock unit simulation, Cursor-on-Target (CoT) event generation, terrain-aware line-of-sight radio propagation, mesh routing, and message-completion statistics.
- **Frontend** (React + Leaflet): live map with friendly mesh groups, OPFOR tracks, and link lines colored by connectivity — **green** = good link, **red** = degraded link, **no line** = out of radio range.

## Features

- **Force-on-force scenario — "Battle of the Central Corridor"**: a scripted OPFOR motorized-regiment attack east through the NTC Central Corridor toward the Whale Gap against a defending BLUFOR task force (two company teams forward, scouts screening, reserve counterattack). Units follow timed waypoint routes; scripted losses remove units mid-battle.
- **TAK-style playback**: the whole battle (600 ticks ≈ 10 h of battle time) is precomputed at startup and recorded per tick (SQLite `snapshots` table). The UI has rewind, play/pause, fast-forward (1/2/4/8x), jump-to-start/end, a LIVE follow mode, and a scrubbable timeline slider (`/api/playback/meta`, `/api/playback/snapshot?tick=N`).
- **External inject API + console**: after the scripted battle, the sim keeps ticking live (one tick per 2 s, still recorded/rewindable). Outside sources can inject units via REST — JSON (`POST /api/inject/unit`) or raw CoT 2.0 XML (`POST /api/inject/cot`) — give them move orders, and kill them. Injected friendly units with a `mesh_id` join link/routing/stats computation automatically. A lightweight inject console is served at `http://localhost:8000/console`: click the map to place units, click again to send move orders, or paste raw CoT.

- 3 friendly mesh networks (Alpha / Bravo / Charlie), each with a command node, infantry, armor, and recon units. 6 OPFOR tracks in two attack echelons plus regimental recon.
- CoT 2.0 XML events generated every tick for each unit and stored in SQLite (`/api/cot/recent`).
- **Radio propagation model**: real SRTM elevation (AWS Open Data Terrarium tiles, cached locally) sampled along each link path, with 4/3-earth refraction, first-Fresnel-zone clearance, and a free-space range limit (915 MHz mesh radios, 15 km max).
- **Mesh routing**: messages route multi-hop (BFS) through the connectivity graph; per-hop delivery probability derives from link quality. Mesh-to-mesh traffic flows between command nodes and is drawn as thicker dashed lines.
- **Message completion rate** collected per mesh and for mesh-to-mesh traffic over a rolling window, shown live in the sidebar and persisted in the `message_log` table.

## Running

### Docker (recommended)

```bash
docker compose up --build
```

Open http://localhost:8080. The frontend container (nginx) proxies `/api` and `/ws`
to the backend container; the SQLite DB and terrain tile cache persist in named volumes.

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` and `/ws` to the backend on port 8000.

## API

| Endpoint | Description |
|---|---|
| `GET /api/state` | Full snapshot: units, links, meshes, stats |
| `GET /api/units` | Current unit positions |
| `GET /api/stats` | Message completion rates (rolling window) |
| `GET /api/playback/meta` | Scenario info, length, computed ticks |
| `GET /api/playback/snapshot?tick=N` | Recorded snapshot at tick N |
| `POST /api/inject/unit` | Inject a unit (JSON: callsign, role, affiliation, mesh_id, lat, lon, target_lat/lon, speed_mps) |
| `POST /api/inject/cot` | Inject/update a unit from raw CoT 2.0 XML |
| `POST /api/inject/unit/{uid}/move` | Send a move order to an injected unit |
| `DELETE /api/inject/unit/{uid}` | Remove an injected unit |
| `GET /api/inject/units` | List injected units |
| `GET /console` | Lightweight inject console web app |
| `GET /api/cot/recent` | Recent CoT XML events |
| `GET /api/messages/recent` | Recent message attempts (hops, quality, delivered) |
| `WS /ws/state` | Snapshot pushed every 2 s |

## Database

SQLite (`backend/takdemo.db`, or `TAKDEMO_DB_PATH`) tables: `units`, `cot_events`, `message_log`, `link_snapshots`, `snapshots`.

## External injects

See [docs/INJECT_API_PROPOSAL.md](docs/INJECT_API_PROPOSAL.md) for the design proposal
to accept CoT/unit/event injects from outside sources (REST + native CoT listener).
