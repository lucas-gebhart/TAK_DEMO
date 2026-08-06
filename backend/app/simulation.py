"""Force-on-force scenario simulation with full playback recording.

Precomputes the entire scripted battle (see scenario.py) tick by tick in a
background thread: unit positions from timed waypoints, terrain-aware link
qualities, multi-hop message routing, and rolling completion stats. Every
tick's snapshot is kept in memory and persisted to SQLite, so the frontend
can play, pause, rewind, and fast-forward through the battle.

A "live" pointer advances one tick every TICK_SECONDS for the live view.
"""
import json
import math
import random
import threading
from collections import deque

from . import db
from .cot import cot_xml, new_uid
from .propagation import delivery_probability, haversine_m, link_quality
from .scenario import SCENARIO, UNITS, phase_at, position_at
from .terrain import terrain

NTC_CENTER = {"lat": 35.335, "lon": -116.680}

TICK_SECONDS = 2.0
MESSAGES_PER_UNIT_PER_TICK = 2
LINK_GOOD_THRESHOLD = 0.5
STATS_WINDOW_TICKS = 60

MESH_DEFS = [
    {"id": "MESH-ALPHA", "name": "Alpha Mesh (Team A - north shoulder)"},
    {"id": "MESH-BRAVO", "name": "Bravo Mesh (Team B - the Whale)"},
    {"id": "MESH-CHARLIE", "name": "Charlie Mesh (TF Reserve)"},
]


class ScenarioUnit:
    def __init__(self, spec):
        self.uid = new_uid()
        self.callsign = spec["callsign"]
        self.role = spec["role"]
        self.affiliation = spec["affiliation"]
        self.mesh_id = spec.get("mesh_id")
        self.waypoints = spec["waypoints"]
        self.destroyed_at = spec.get("destroyed_at")

    def alive_at(self, tick: int) -> bool:
        return self.destroyed_at is None or tick < self.destroyed_at

    def state_at(self, tick: int) -> dict:
        lat, lon = position_at(self.waypoints, tick)
        # course/speed from a small forward difference
        lat2, lon2 = position_at(self.waypoints, tick + 1)
        d = haversine_m(lat, lon, lat2, lon2)
        speed = d / TICK_SECONDS
        dy = lat2 - lat
        dx = (lon2 - lon) * math.cos(math.radians(lat))
        course = math.degrees(math.atan2(dx, dy)) % 360 if d > 0.1 else 0.0
        return {
            "uid": self.uid, "callsign": self.callsign, "affiliation": self.affiliation,
            "role": self.role, "mesh_id": self.mesh_id, "lat": lat, "lon": lon,
            "hae": terrain.elevation(lat, lon),
            "speed_mps": speed, "course_deg": course,
            "team": "Cyan" if self.affiliation == "friendly" else "Red",
            "destroyed_at": self.destroyed_at,
        }


class Simulation:
    def __init__(self):
        random.seed(42)  # deterministic playback
        self.units = [ScenarioUnit(s) for s in UNITS]
        self.length = SCENARIO["length_ticks"]
        self.snapshots: list[dict] = []
        self.msg_window = deque()  # (tick, src_mesh, dst_mesh, delivered)
        self.live_tick = 0
        self.lock = threading.Lock()
        self._stop = threading.Event()

    # ---- link & routing helpers -------------------------------------------

    @staticmethod
    def _neighbors(quality):
        nbrs = {}
        for (a, b), q in quality.items():
            nbrs.setdefault(a, {})[b] = q
            nbrs.setdefault(b, {})[a] = q
        return nbrs

    @staticmethod
    def _route(src_uid, dst_uid, nbrs):
        if src_uid == dst_uid:
            return [src_uid]
        seen = {src_uid}
        q = deque([[src_uid]])
        while q:
            path = q.popleft()
            for nxt in nbrs.get(path[-1], {}):
                if nxt in seen:
                    continue
                if nxt == dst_uid:
                    return path + [nxt]
                seen.add(nxt)
                q.append(path + [nxt])
        return None

    # ---- tick computation --------------------------------------------------

    def _compute_tick(self, tick: int) -> dict:
        states = []
        for u in self.units:
            if not u.alive_at(tick):
                continue
            s = u.state_at(tick)
            states.append(s)
            db.upsert_unit({k: s[k] for k in
                            ("uid", "callsign", "affiliation", "role", "mesh_id",
                             "lat", "lon", "hae", "speed_mps", "course_deg")})
            db.insert_cot(u.uid, cot_xml(s))

        friendly = [s for s in states if s["affiliation"] == "friendly"]
        quality = {}
        for i, a in enumerate(friendly):
            for b in friendly[i + 1:]:
                q = link_quality(a["lat"], a["lon"], b["lat"], b["lon"])
                if q > 0:
                    quality[(a["uid"], b["uid"])] = q
        nbrs = self._neighbors(quality)
        by_uid = {s["uid"]: s for s in friendly}

        links = []
        for (a, b), q in quality.items():
            kind = "intra" if by_uid[a]["mesh_id"] == by_uid[b]["mesh_id"] else "inter"
            links.append({"a": a, "b": b, "quality": round(q, 3), "kind": kind,
                          "good": q >= LINK_GOOD_THRESHOLD})
            db.insert_link(tick, a, b, q, kind)

        # message traffic: intra-mesh chatter + command-to-command reports
        mesh_ids = sorted({s["mesh_id"] for s in friendly})
        commands = {s["mesh_id"]: s for s in friendly if s["role"] == "command"}
        attempts = []
        for s in friendly:
            peers = [v for v in friendly if v["mesh_id"] == s["mesh_id"] and v["uid"] != s["uid"]]
            for _ in range(MESSAGES_PER_UNIT_PER_TICK):
                if peers:
                    attempts.append((s, random.choice(peers)))
        for sm in mesh_ids:
            for dm in mesh_ids:
                if sm != dm and sm in commands and dm in commands:
                    attempts.append((commands[sm], commands[dm]))

        for src, dst in attempts:
            path = self._route(src["uid"], dst["uid"], nbrs)
            if path is None:
                delivered, hops, worst_q = False, 0, 0.0
            else:
                p_total, worst_q = 1.0, 1.0
                for h in range(len(path) - 1):
                    q = quality.get((path[h], path[h + 1])) or quality.get((path[h + 1], path[h]))
                    p_total *= delivery_probability(q)
                    worst_q = min(worst_q, q)
                hops = len(path) - 1
                delivered = random.random() < p_total
            db.insert_message(tick, src["uid"], dst["uid"], src["mesh_id"],
                              dst["mesh_id"], hops, worst_q, delivered)
            self.msg_window.append((tick, src["mesh_id"], dst["mesh_id"], delivered))

        while self.msg_window and self.msg_window[0][0] <= tick - STATS_WINDOW_TICKS:
            self.msg_window.popleft()

        per_mesh, inter = {}, {"attempts": 0, "delivered": 0}
        for _, sm, dm, delivered in self.msg_window:
            if sm == dm:
                agg = per_mesh.setdefault(sm, {"attempts": 0, "delivered": 0})
            else:
                agg = inter
            agg["attempts"] += 1
            agg["delivered"] += int(delivered)
        stats = {
            "per_mesh": {
                m: {**v, "completion_rate": round(v["delivered"] / v["attempts"], 3) if v["attempts"] else None}
                for m, v in per_mesh.items()
            },
            "mesh_to_mesh": {**inter, "completion_rate":
                             round(inter["delivered"] / inter["attempts"], 3) if inter["attempts"] else None},
            "window_ticks": STATS_WINDOW_TICKS,
        }

        db.commit()
        return {
            "tick": tick,
            "length": self.length,
            "phase": phase_at(tick),
            "scenario": {"name": SCENARIO["name"], "description": SCENARIO["description"],
                         "phases": SCENARIO["phases"]},
            "center": NTC_CENTER,
            "meshes": MESH_DEFS,
            "units": states,
            "links": links,
            "stats": stats,
            "link_good_threshold": LINK_GOOD_THRESHOLD,
        }

    # ---- public API ---------------------------------------------------------

    def ready_ticks(self) -> int:
        with self.lock:
            return len(self.snapshots)

    def snapshot_at(self, tick: int):
        with self.lock:
            if not self.snapshots:
                return None
            return self.snapshots[max(0, min(tick, len(self.snapshots) - 1))]

    def snapshot(self):
        """Live view: snapshot at the advancing live pointer."""
        with self.lock:
            if not self.snapshots:
                return {"tick": 0, "length": self.length, "center": NTC_CENTER,
                        "meshes": MESH_DEFS, "units": [], "links": [], "stats": {},
                        "phase": "precomputing…", "scenario": {"name": SCENARIO["name"]},
                        "link_good_threshold": LINK_GOOD_THRESHOLD,
                        "ready_ticks": 0}
            t = min(self.live_tick, len(self.snapshots) - 1)
            snap = dict(self.snapshots[t])
            snap["ready_ticks"] = len(self.snapshots)
            return snap

    def meta(self):
        with self.lock:
            return {
                "scenario": {"name": SCENARIO["name"], "description": SCENARIO["description"],
                             "phases": SCENARIO["phases"]},
                "length": self.length,
                "ready_ticks": len(self.snapshots),
                "live_tick": self.live_tick,
                "tick_seconds": TICK_SECONDS,
            }

    # ---- threads -------------------------------------------------------------

    def precompute(self):
        for tick in range(self.length):
            if self._stop.is_set():
                return
            try:
                snap = self._compute_tick(tick)
            except Exception as e:
                print(f"precompute error at tick {tick}: {e}")
                continue
            with self.lock:
                self.snapshots.append(snap)
            db.insert_snapshot(tick, json.dumps(snap))
            if tick % 50 == 0:
                db.commit()
        db.commit()
        print("scenario precompute complete")

    def run_live_pointer(self):
        while not self._stop.is_set():
            self._stop.wait(TICK_SECONDS)
            with self.lock:
                if self.snapshots:
                    self.live_tick = (self.live_tick + 1) % len(self.snapshots)

    def start(self):
        threading.Thread(target=self.precompute, daemon=True).start()
        threading.Thread(target=self.run_live_pointer, daemon=True).start()

    def stop(self):
        self._stop.set()


simulation = Simulation()
