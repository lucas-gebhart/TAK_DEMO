import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Popup, LayersControl,
} from 'react-leaflet'

const MESH_COLORS = {
  'MESH-ALPHA': '#58a6ff',
  'MESH-BRAVO': '#bc8cff',
  'MESH-CHARLIE': '#39d2c0',
}

const TICK_MS = 500 // playback base rate: 2 ticks/sec at 1x
const SPEEDS = [1, 2, 4, 8]

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
  const [meta, setMeta] = useState(null)
  const [snap, setSnap] = useState(null)
  const [tick, setTick] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [direction, setDirection] = useState(1) // 1 forward, -1 rewind
  const [speed, setSpeed] = useState(1)
  const cache = useRef(new Map())

  // poll playback meta (ready_ticks grows while backend precomputes)
  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch('/api/playback/meta')
        setMeta(await r.json())
      } catch { /* backend starting */ }
    }
    load()
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [])

  const readyTicks = meta?.ready_ticks ?? 0
  const length = meta?.length ?? 600

  // playback clock
  useEffect(() => {
    if (!playing || readyTicks === 0) return undefined
    const id = setInterval(() => {
      setTick((t) => {
        let next = t + direction * speed
        if (next >= readyTicks) next = 0 // loop
        if (next < 0) { next = 0 }
        return next
      })
    }, TICK_MS)
    return () => clearInterval(id)
  }, [playing, direction, speed, readyTicks])

  // fetch snapshot for current tick (cached)
  useEffect(() => {
    if (readyTicks === 0) return
    const t = Math.min(tick, readyTicks - 1)
    if (cache.current.has(t)) { setSnap(cache.current.get(t)); return }
    let cancelled = false
    fetch(`/api/playback/snapshot?tick=${t}`)
      .then((r) => r.json())
      .then((s) => {
        cache.current.set(t, s)
        if (!cancelled) setSnap(s)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [tick, readyTicks])

  const unitsByUid = useMemo(() => {
    const m = {}
    snap?.units?.forEach((u) => { m[u.uid] = u })
    return m
  }, [snap])

  const center = snap?.center ?? { lat: 35.335, lon: -116.680 }
  const pct = length ? (Math.min(tick, length) / length) * 100 : 0
  const battleTime = `H+${Math.floor(tick / 60)}:${String(tick % 60).padStart(2, '0')}`

  const playbackControls = (
    <>
      <button title="Jump to start" onClick={() => { setTick(0) }}>⏮</button>
      <button
        title="Rewind"
        className={direction === -1 && playing ? 'active' : ''}
        onClick={() => { setDirection(-1); setPlaying(true) }}
      >⏪</button>
      <button
        title={playing ? 'Pause' : 'Play'}
        onClick={() => {
          if (playing && direction === 1) setPlaying(false)
          else { setDirection(1); setPlaying(true) }
        }}
      >{playing && direction === 1 ? '⏸' : '▶'}</button>
      <button
        title="Fast forward (cycle speed)"
        className={speed > 1 ? 'active' : ''}
        onClick={() => {
          setDirection(1); setPlaying(true)
          setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])
        }}
      >⏩ {speed}x</button>
      <button title="Jump to end" onClick={() => { setTick(Math.max(0, readyTicks - 1)); setPlaying(false) }}>⏭</button>

      <input
        type="range"
        min={0}
        max={Math.max(0, length - 1)}
        value={Math.min(tick, length - 1)}
        onChange={(e) => { setTick(Number(e.target.value)); setPlaying(false) }}
        style={{ '--ready': `${(readyTicks / length) * 100}%`, '--pos': `${pct}%` }}
      />
      <span className="time">
        {battleTime} {readyTicks < length ? `· computing ${Math.round((readyTicks / length) * 100)}%` : ''}
      </span>
    </>
  )

  return (
    <div className="app">
      <div className="map-column">
        <div className="map-container">
          <MapContainer center={[center.lat, center.lon]} zoom={12} style={{ height: '100%' }}>
            <LayersControl position="topright">
              <LayersControl.BaseLayer checked name="Clean (light)">
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                  attribution="&copy; OpenStreetMap contributors &copy; CARTO"
                />
              </LayersControl.BaseLayer>
              <LayersControl.BaseLayer name="Clean (dark)">
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                  attribution="&copy; OpenStreetMap contributors &copy; CARTO"
                />
              </LayersControl.BaseLayer>
              <LayersControl.BaseLayer name="Terrain (Esri)">
                <TileLayer
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}"
                  attribution="&copy; Esri"
                />
              </LayersControl.BaseLayer>
              <LayersControl.BaseLayer name="Topographic">
                <TileLayer
                  url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
                  attribution="&copy; OpenTopoMap, &copy; OpenStreetMap contributors"
                />
              </LayersControl.BaseLayer>
            </LayersControl>

            {snap?.links?.map((l, i) => {
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

            {snap?.units?.map((u) => {
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

        <div className="playback-bar">{playbackControls}</div>
      </div>

      <div className="sidebar">
        <h1>NTC TAK Demo</h1>
        <div className="sub">National Training Center · Fort Irwin, CA</div>

        <h2>Playback</h2>
        <div className="playback-panel">{playbackControls}</div>

        <h2>Scenario</h2>
        <div className="scenario">
          <div className="scenario-name">{snap?.scenario?.name ?? meta?.scenario?.name ?? '—'}</div>
          <div className="phase">{snap?.phase ?? ''}</div>
          <div className="sub">{meta?.scenario?.description ?? ''}</div>
        </div>

        <h2>Message Completion (rolling)</h2>
        {snap?.meshes?.map((m) => (
          <StatCard key={m.id} name={m.name} stats={snap?.stats?.per_mesh?.[m.id]} />
        ))}
        <StatCard name="Mesh ↔ Mesh" stats={snap?.stats?.mesh_to_mesh} />

        <h2>Legend</h2>
        <div className="legend">
          <div><span className="swatch" style={{ background: '#3fb950' }} />Good link (LOS clear)</div>
          <div><span className="swatch" style={{ background: '#f85149' }} />Degraded link (terrain masked / long range)</div>
          <div>No line = out of radio range</div>
          <div style={{ marginTop: 6 }}>
            {Object.entries(MESH_COLORS).map(([id, c]) => (
              <div key={id}><span className="swatch" style={{ background: c, height: 10, width: 10, borderRadius: 5 }} />{id}</div>
            ))}
            <div><span className="swatch" style={{ background: '#f85149', height: 10, width: 10, borderRadius: 5 }} />OPFOR</div>
          </div>
        </div>

        <div className="tick">
          {snap ? `tick ${snap.tick}/${length} · ${snap.units.length} units · ${snap.links.length} links` : 'connecting to backend…'}
        </div>
      </div>
    </div>
  )
}
