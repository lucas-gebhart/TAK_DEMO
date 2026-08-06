"""Mock battlefield simulation for the National Training Center (Fort Irwin).

Spawns friendly units organized into mesh networks plus OPFOR units,
moves them each tick, evaluates radio links with the terrain-aware
propagation model, routes mock messages across the mesh (multi-hop),
and records delivery statistics.
"""
import math
import random
import threading
import time
from collections import deque

from . import db
from .cot import cot_xml, new_uid
from .propagation import delivery_probability, haversine_m, link_quality
from .terrain import terrain

# National Training Center, Fort Irwin CA
NTC_CENTER = {"lat": 35.3703, "lon": -116.6470}

TICK_SECONDS = 2.0
MESSAGES_PER_UNIT_PER_TICK = 2
LINK_GOOD_THRESHOLD = 0.5

MESH_DEFS = [
    {"id": "MESH-ALPHA", "name": "Alpha Mesh", "anchor": (35.395, -116.680),
     "units": [("ALPHA-6", "command"), ("A-1", "infantry"), ("A-2", "infantry"), ("A-3", "armor"), ("A-4", "recon")]},
    {"id": "MESH-BRAVO", "name": "Bravo Mesh", "anchor": (35.345, -116.600),
     "units": [("BRAVO-6", "command"), ("B-1", "infantry"), ("B-2", "armor"), ("B-3", "armor"), ("B-4", "recon")]},
    {"id": "MESH-CHARLIE", "name": "Charlie Mesh", "anchor": (35.410, -116.570),
     "units": [("CHARLIE-6", "command"), ("C-1", "infantry"), ("C-2", "infantry"), ("C-3", "recon")]},
]

OPFOR_DEFS = [
    ("KRASNO-1", "opfor_armor", (35.320, -116.700)),
    ("KRASNO-2", "opfor_armor", (35.310, -116.680)),
    ("KRASNO-3", "opfor_infantry", (35.440, -116.640)),
    ("KRASNO-4", "opfor_infantry", (35.430, -116.530)),
]

SPEEDS = {"infantry": 1.5, "recon": 8.0, "armor": 6.0, "command": 3.0,
          "opfor_infantry": 1.5, "opfor_armor": 6.0}


def _offset(lat, lon, dist_m, bearing_deg):
    dlat = dist_m * math.cos(math.radians(bearing_deg)) / 111320.0
    dlon = dist_m * math.sin(math.radians(bearing_deg)) / (111320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


class Unit:
    def __init__(self, callsign, role, affiliation, mesh_id, lat, lon):
        self.uid = new_uid()
        self.callsign = callsign
        self.role = role
        self.affiliation = affiliation
        self.mesh_id = mesh_id
        self.lat = lat
        self.lon = lon
        self.course = random.uniform(0, 360)
        self.speed = SPEEDS[role]
        self.anchor = (lat, lon)

    def step(self, dt: float):
        # Random-walk with soft tether to the unit's anchor area.
        self.course += random.uniform(-25, 25)
        if haversine_m(self.lat, self.lon, *self.anchor) > 3500:
            # steer back toward anchor
            dy = self.anchor[0] - self.lat
            dx = (self.anchor[1] - self.lon) * math.cos(math.radians(self.lat))
            self.course = math.degrees(math.atan2(dx, dy))
        self.lat, self.lon = _offset(self.lat, self.lon, self.speed * dt, self.course)

    def to_dict(self):
        return {
            "uid": self.uid, "callsign": self.callsign, "affiliation": self.affiliation,
            "role": self.role, "mesh_id": self.mesh_id, "lat": self.lat, "lon": self.lon,
            "hae": terrain.elevation(self.lat, self.lon),
            "speed_mps": self.speed, "course_deg": self.course % 360,
            "team": "Cyan" if self.affiliation == "friendly" else "Red",
        }


class Simulation:
    def __init__(self):
        self.units: list[Unit] = []
        self.tick = 0
        self.links = []          # intra-mesh link snapshots for UI
        self.mesh_links = []     # mesh-to-mesh bridge links for UI
        self.stats = {}
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._spawn()

    def _spawn(self):
        for mesh in MESH_DEFS:
            alat, alon = mesh["anchor"]
            for callsign, role in mesh["units"]:
                lat, lon = _offset(alat, alon, random.uniform(200, 2000), random.uniform(0, 360))
                self.units.append(Unit(callsign, role, "friendly", mesh["id"], lat, lon))
        for callsign, role, (lat, lon) in OPFOR_DEFS:
            lat, lon = _offset(lat, lon, random.uniform(0, 800), random.uniform(0, 360))
            self.units.append(Unit(callsign, role, "hostile", None, lat, lon))

    # ---- link & routing helpers -------------------------------------------

    def _friendly_units(self):
        return [u for u in self.units if u.affiliation == "friendly"]

    def _compute_links(self):
        """All-pairs link quality between friendly units (they share radios)."""
        friendly = self._friendly_units()
        quality = {}
        for i, a in enumerate(friendly):
            for b in friendly[i + 1:]:
                q = link_quality(a.lat, a.lon, b.lat, b.lon)
                if q > 0:
                    quality[(a.uid, b.uid)] = q
        return friendly, quality

    @staticmethod
    def _neighbors(quality):
        nbrs = {}
        for (a, b), q in quality.items():
            nbrs.setdefault(a, {})[b] = q
            nbrs.setdefault(b, {})[a] = q
        return nbrs

    @staticmethod
    def _route(src_uid, dst_uid, nbrs):
        """BFS shortest hop path through the connectivity graph."""
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

    # ---- main tick ---------------------------------------------------------

    def step(self):
        self.tick += 1
        for u in self.units:
            u.step(TICK_SECONDS)
            d = u.to_dict()
            db.upsert_unit(d)
            db.insert_cot(u.uid, cot_xml(d))

        friendly, quality = self._compute_links()
        nbrs = self._neighbors(quality)
        by_uid = {u.uid: u for u in friendly}

        # UI link lists: intra-mesh links and best inter-mesh bridges.
        links = []
        for (a, b), q in quality.items():
            ua, ub = by_uid[a], by_uid[b]
            kind = "intra" if ua.mesh_id == ub.mesh_id else "inter"
            entry = {"a": a, "b": b, "quality": round(q, 3), "kind": kind,
                     "good": q >= LINK_GOOD_THRESHOLD}
            links.append(entry)
            db.insert_link(self.tick, a, b, q, kind)

        # Simulate message traffic: intra-mesh chatter plus mesh-to-mesh
        # reports from each mesh's command node to the other command nodes.
        mesh_ids = sorted({u.mesh_id for u in friendly})
        commands = {u.mesh_id: u for u in friendly if u.role == "command"}
        attempts = []
        for u in friendly:
            peers = [v for v in friendly if v.mesh_id == u.mesh_id and v.uid != u.uid]
            for _ in range(MESSAGES_PER_UNIT_PER_TICK):
                if peers:
                    attempts.append((u, random.choice(peers)))
        for src_mesh in mesh_ids:
            for dst_mesh in mesh_ids:
                if src_mesh != dst_mesh and src_mesh in commands and dst_mesh in commands:
                    attempts.append((commands[src_mesh], commands[dst_mesh]))

        for src, dst in attempts:
            path = self._route(src.uid, dst.uid, nbrs)
            if path is None:
                db.insert_message(self.tick, src.uid, dst.uid, src.mesh_id,
                                  dst.mesh_id, 0, 0.0, False)
                continue
            p_total, worst_q = 1.0, 1.0
            for h in range(len(path) - 1):
                q = quality.get((path[h], path[h + 1])) or quality.get((path[h + 1], path[h]))
                p_total *= delivery_probability(q)
                worst_q = min(worst_q, q)
            delivered = random.random() < p_total
            db.insert_message(self.tick, src.uid, dst.uid, src.mesh_id,
                              dst.mesh_id, len(path) - 1, worst_q, delivered)

        db.commit()

        # Aggregate stats for the UI (rolling window).
        raw = db.message_stats(last_n_ticks=60, current_tick=self.tick)
        per_mesh, inter = {}, {"attempts": 0, "delivered": 0}
        for r in raw:
            if r["src_mesh"] == r["dst_mesh"]:
                agg = per_mesh.setdefault(r["src_mesh"], {"attempts": 0, "delivered": 0})
                agg["attempts"] += r["attempts"]
                agg["delivered"] += r["delivered"] or 0
            else:
                inter["attempts"] += r["attempts"]
                inter["delivered"] += r["delivered"] or 0
        stats = {
            "per_mesh": {
                m: {"attempts": v["attempts"], "delivered": v["delivered"],
                    "completion_rate": round(v["delivered"] / v["attempts"], 3) if v["attempts"] else None}
                for m, v in per_mesh.items()
            },
            "mesh_to_mesh": {
                "attempts": inter["attempts"], "delivered": inter["delivered"],
                "completion_rate": round(inter["delivered"] / inter["attempts"], 3) if inter["attempts"] else None,
            },
            "window_ticks": 60,
        }

        with self.lock:
            self.links = links
            self.stats = stats

    def snapshot(self):
        with self.lock:
            return {
                "tick": self.tick,
                "center": NTC_CENTER,
                "meshes": [{"id": m["id"], "name": m["name"]} for m in MESH_DEFS],
                "units": [u.to_dict() for u in self.units],
                "links": self.links,
                "stats": self.stats,
                "link_good_threshold": LINK_GOOD_THRESHOLD,
            }

    def run_forever(self):
        while not self._stop.is_set():
            start = time.time()
            try:
                self.step()
            except Exception as e:  # keep the sim alive
                print(f"simulation tick error: {e}")
            elapsed = time.time() - start
            self._stop.wait(max(0.1, TICK_SECONDS - elapsed))

    def stop(self):
        self._stop.set()


simulation = Simulation()
