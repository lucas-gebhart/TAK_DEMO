# NTC TAK Demo Test Plan

Servers: backend uvicorn :8000 (started), frontend vite :5173 (started).

## Part A — Backend APIs (shell, no recording)
1. **Sim ticks & movement**: GET /api/state twice, 6s apart. PASS: tick strictly increases; at least one unit's lat/lon changes; 18 units (14 friendly + 4 OPFOR), links array non-empty, stats present.
2. **CoT XML**: GET /api/cot/recent; parse each XML with ElementTree. PASS: root `event` with version="2.0", uid, type, time/start/stale; child `point` with lat/lon/hae/ce/le; `detail` with contact callsign. Friendly types start `a-f-`, hostile `a-h-`; both present across recent events.
3. **Stats sanity**: GET /api/stats. PASS: per_mesh has MESH-ALPHA/BRAVO/CHARLIE + mesh_to_mesh; all completion_rate in [0,1]; attempts grow between two samples 6s apart.
4. **Messages**: GET /api/messages/recent. PASS: contains both delivered=1 (hops>=1, quality>0) and delivered=0 rows.
5. **WebSocket**: connect to ws://localhost:8000/ws/state with python, read 2 messages. PASS: two snapshots with increasing tick.

## Part B — Frontend UI (recorded browser at http://localhost:5173)
6. **Map loads on Fort Irwin** with topo tiles; unit markers with permanent callsign labels visible; colors: Alpha blue (#58a6ff), Bravo purple, Charlie teal, OPFOR red. PASS iff screenshot shows colored markers + labels near Fort Irwin.
7. **Link lines**: green and red lines between units; at least one dashed thicker mesh-to-mesh line. PASS iff visible in screenshot (hover a dashed line → tooltip contains "mesh-to-mesh" and quality %).
8. **Sidebar live stats**: 4 stat cards (MESH-ALPHA/BRAVO/CHARLIE, Mesh ↔ Mesh) show percentage and "X/Y messages delivered"; tick counter line "tick N · 18 units · M links". PASS: after waiting ~10s, tick N increases and delivered/attempts numbers change (screenshot before/after).
9. **Unit popup**: click a unit marker. PASS: popup shows "CALLSIGN · role · MESH · <n>m MSL · <s> m/s".
