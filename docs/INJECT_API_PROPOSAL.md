# External Inject API — Design Proposal

What it would take to let outside sources inject entities and events into the sim.

## Where we are today

The backend precomputes a fixed scripted scenario and serves recorded snapshots.
Nothing external can alter the world state. To accept injects, the sim needs to go
back to a *live authoritative loop* (like the original version) with the scenario
script as just one traffic source, and playback recording continuing as-is.

## Proposed architecture

```
outside sources ──HTTP POST /api/inject/*──┐
outside TAK/ATAK ──TCP/UDP CoT listener────┤
                                           ▼
                                   Inject Queue (validated)
                                           ▼
      scenario script ────────────► Simulation tick loop ───► snapshots (record + live WS)
```

### 1. REST inject endpoints (smallest lift, ~1 day)

- `POST /api/inject/cot` — body is raw CoT 2.0 XML. Parse `uid`, type (`a-f-*`/`a-h-*`),
  point, callsign; upsert the track. Unknown uid = new unit; known uid = position update.
  This single endpoint makes the sim interoperable with anything that speaks CoT.
- `POST /api/inject/unit` — JSON convenience version
  `{callsign, role, affiliation, mesh_id?, lat, lon, waypoints?}`.
- `POST /api/inject/event` — scripted events: `{type: "destroy"|"jam"|"move", uid, at_tick?, params}`.
  (e.g. jamming an area would zero link quality inside a polygon — plugs straight into
  the propagation layer.)
- `DELETE /api/inject/unit/{uid}` — remove a track.
- Auth: API key header (`X-API-Key`) at minimum; per-source keys so injects are attributable.

Injected units with a `mesh_id` automatically participate in link computation, routing,
and completion-rate stats — the propagation model doesn't care where a unit came from.

### 2. Native CoT listener (interop with real TAK tooling, ~1–2 days)

TAK ecosystems push CoT over TCP 8087 / UDP multicast. Add an asyncio TCP/UDP listener
that feeds the same inject queue as `/api/inject/cot`. Then real ATAK/WinTAK clients or a
TAK Server federation feed can populate this map directly, and we can *emit* our sim
tracks back out as CoT so the sim shows up in ATAK.

### 3. Consistency with playback

- Live mode: injects apply on the next tick; snapshots keep recording, so injected
  traffic is rewindable like everything else.
- Replay mode: viewing history is read-only; injects only mutate the live head.
- Store injects in an `injects` table (source, raw payload, tick applied) for audit/AAR.

## Effort summary

| Step | Effort |
|---|---|
| Switch back to live tick loop w/ scenario as a feed + inject queue | ~0.5 day |
| REST inject endpoints + API-key auth + audit table | ~1 day |
| CoT TCP/UDP listener + CoT output stream | ~1–2 days |
| Jamming/effects events on the propagation model | ~0.5 day |
