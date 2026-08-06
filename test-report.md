# NTC TAK Demo — End-to-End Test Report

PR: https://github.com/lucas-gebhart/TAK_DEMO/pull/1 (branch `devin/1785977713-ntc-tak-sim`)
Environment: backend `uvicorn app.main:app` on :8000 (fresh SQLite/tile cache present), frontend `npm run dev` (Vite) on :5173, tested in Chrome.

## Summary
All 9 planned assertions passed (5 backend API checks via shell, 4 UI checks in a recorded browser session).

## Part A — Backend API tests (shell)

| # | Test | Result | Evidence |
|---|------|--------|----------|
| 1 | Sim ticks & movement | PASS | tick 34 → 37 over 6s; 18 units (14 friendly, 4 hostile); all 18 units changed lat/lon; 34 links; stats keys `per_mesh`, `mesh_to_mesh`, `window_ticks` |
| 2 | CoT XML well-formed | PASS | 20 recent events parsed with ElementTree; every `event` has version="2.0", uid, type, time/start/stale; `point` has lat/lon/hae/ce/le; `detail` has contact callsign. Types seen: `a-f-G-U-C-A/I/R`, `a-f-G-U-H` (friendly) and `a-h-G-U-C-A/I` (hostile) |
| 3 | Stats sanity | PASS | completion_rate all in [0,1] (ALPHA 0.614, BRAVO 0.538, CHARLIE 0.498, mesh_to_mesh 0.321); attempts grew for all meshes and mesh_to_mesh over 6s |
| 4 | Messages recent | PASS | 50 rows; 27 delivered (all with hops≥1, quality>0, e.g. hops=1 quality=0.78) and 23 failed (delivered=0, hops=0, quality=0.0) |
| 5 | WebSocket /ws/state | PASS | Two consecutive snapshots received (tick 43 → 44, 18 units) |

## Part B — Frontend UI tests (recorded)

| # | Test | Result |
|---|------|--------|
| 6 | Map loads on Fort Irwin with labeled, color-coded markers | PASS — 18 markers with callsign labels; Alpha blue, Bravo purple, Charlie teal, OPFOR (KRASNO-*) red; sidebar shows 4 stat cards |
| 7 | Dashed mesh-to-mesh links + quality tooltip | PASS — dashed green inter-mesh lines visible; hover tooltip "B-4 ↔ C-1 · quality 81% · mesh-to-mesh" |
| 8 | Unit popup | PASS — clicking A-1 shows "A-1 · infantry · MESH-ALPHA · 888m MSL · 1.5 m/s" |
| 9 | Live updates | PASS — tick 105 → 120 after ~12s wait; delivered/attempt counts on all stat cards changed; unit positions shifted (popup elevation 888m → 889m) |

### Screenshots

| Initial map (Fort Irwin, markers + links + sidebar) | Mesh-to-mesh tooltip on dashed link |
|---|---|
| ![map](https://app.devin.ai/attachments/01758009-a3ab-490e-816f-ff71b8d08cbb/shot_map_initial.png) | ![tooltip](https://app.devin.ai/attachments/9ea66de0-2147-43ce-92f6-dbe9913ae85f/shot_tooltip.png) |

| Unit popup (A-1) 🔴 before wait, tick 105 | After ~12s 🟢 tick 120, stats changed |
|---|---|
| ![popup](https://app.devin.ai/attachments/31b47fc4-1e8f-4cd1-a024-1f56e21a0a77/shot_popup.png) | ![after](https://app.devin.ai/attachments/2af12e62-2017-4089-bff2-6692926b86d1/shot_after_wait.png) |

## Notes / minor observations
- Live WS updates fed the UI (backend log shows the WS connection; polling fallback code exists but was not exercised since WS stayed up — the fallback path was not end-to-end tested).
- Completion rates are visibly dynamic and sane; mesh-to-mesh rate (~32%) is notably lower than intra-mesh, consistent with terrain-masked long links.
- No console errors observed; OpenTopoMap tiles loaded normally.
