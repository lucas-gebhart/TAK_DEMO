import React, { useEffect, useMemo, useState } from 'react'
import {
  MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Popup, LayersControl,
} from 'react-leaflet'

const MESH_COLORS = {
  'MESH-ALPHA': '#58a6ff',
  'MESH-BRAVO': '#bc8cff',
  'MESH-CHARLIE': '#39d2c0',
}

function rateClass(r) {
  if (r == null) return ''
  if (r >= 0.85) return 'good'
  if (r >= 0.6) return 'mid'
  return 'bad'
}

function StatCard({ name, stats }) {
  const rate = stats?.completion_rate
  return (
    <div className="stat-card">
      <div className="mesh-name">{name}</div>
      <div className={`rate ${rateClass(rate)}`}>
        {rate == null ? '—' : `${(rate * 100).toFixed(1)}%`}
      </div>
      <div className="detail">
        {stats ? `${stats.delivered}/${stats.attempts} messages delivered` : 'no traffic yet'}
      </div>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(null)

  useEffect(() => {
    let ws
    let poller
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${window.location.host}/ws/state`)
      ws.onmessage = (e) => setState(JSON.parse(e.data))
      ws.onclose = () => {
        // fall back to polling, retry ws periodically
        poller = setInterval(async () => {
          try {
            const r = await fetch('/api/state')
            setState(await r.json())
          } catch { /* backend not up yet */ }
        }, 2000)
        setTimeout(() => { clearInterval(poller); connect() }, 10000)
      }
    }
    connect()
    return () => { ws?.close(); clearInterval(poller) }
  }, [])

  const unitsByUid = useMemo(() => {
    const m = {}
    state?.units?.forEach((u) => { m[u.uid] = u })
    return m
  }, [state])

  const center = state?.center ?? { lat: 35.3703, lon: -116.647 }

  return (
    <div className="app">
      <div className="map-container">
        <MapContainer center={[center.lat, center.lon]} zoom={12} style={{ height: '100%' }}>
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="Topographic">
              <TileLayer
                url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
                attribution="&copy; OpenTopoMap, &copy; OpenStreetMap contributors"
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Streets">
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution="&copy; OpenStreetMap contributors"
              />
            </LayersControl.BaseLayer>
          </LayersControl>

          {state?.links?.map((l, i) => {
            const a = unitsByUid[l.a]
            const b = unitsByUid[l.b]
            if (!a || !b) return null
            return (
              <Polyline
                key={`${l.a}-${l.b}-${i}`}
                positions={[[a.lat, a.lon], [b.lat, b.lon]]}
                pathOptions={{
                  color: l.good ? '#3fb950' : '#f85149',
                  weight: l.kind === 'inter' ? 2.5 : 1.2,
                  opacity: l.kind === 'inter' ? 0.95 : 0.65,
                  dashArray: l.kind === 'inter' ? '6 4' : undefined,
                }}
              >
                <Tooltip sticky>
                  {a.callsign} ↔ {b.callsign} · quality {(l.quality * 100).toFixed(0)}%
                  {l.kind === 'inter' ? ' · mesh-to-mesh' : ''}
                </Tooltip>
              </Polyline>
            )
          })}

          {state?.units?.map((u) => {
            const hostile = u.affiliation === 'hostile'
            const color = hostile ? '#f85149' : (MESH_COLORS[u.mesh_id] ?? '#58a6ff')
            return (
              <CircleMarker
                key={u.uid}
                center={[u.lat, u.lon]}
                radius={u.role === 'command' ? 9 : 6}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: hostile ? 0.5 : 0.85,
                  weight: u.role === 'command' ? 3 : 1.5,
                }}
              >
                <Tooltip permanent direction="top" offset={[0, -8]} className="unit-label">
                  {u.callsign}
                </Tooltip>
                <Popup>
                  {u.callsign} · {u.role} · {u.mesh_id ?? 'OPFOR'} ·
                  {' '}{u.hae?.toFixed(0)}m MSL · {u.speed_mps?.toFixed(1)} m/s
                </Popup>
              </CircleMarker>
            )
          })}
        </MapContainer>
      </div>

      <div className="sidebar">
        <h1>NTC TAK Demo</h1>
        <div className="sub">National Training Center · Fort Irwin, CA</div>

        <h2>Message Completion (rolling)</h2>
        {state?.meshes?.map((m) => (
          <StatCard key={m.id} name={m.name} stats={state?.stats?.per_mesh?.[m.id]} />
        ))}
        <StatCard name="Mesh ↔ Mesh" stats={state?.stats?.mesh_to_mesh} />

        <h2>Legend</h2>
        <div className="legend">
          <div><span className="swatch" style={{ background: '#3fb950' }} />Good link (LOS clear)</div>
          <div><span className="swatch" style={{ background: '#f85149' }} />Degraded link (terrain masked / long range)</div>
          <div><span className="swatch" style={{ background: 'transparent', border: '1px dashed #8b949e', height: 0 }} />No line = out of radio range</div>
          <div style={{ marginTop: 6 }}>
            {Object.entries(MESH_COLORS).map(([id, c]) => (
              <div key={id}><span className="swatch" style={{ background: c, height: 10, width: 10, borderRadius: 5 }} />{id}</div>
            ))}
            <div><span className="swatch" style={{ background: '#f85149', height: 10, width: 10, borderRadius: 5 }} />OPFOR</div>
          </div>
        </div>

        <div className="tick">
          {state ? `tick ${state.tick} · ${state.units.length} units · ${state.links.length} links` : 'connecting to backend…'}
        </div>
      </div>
    </div>
  )
}
