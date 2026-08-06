"""Force-on-force scenario: "Battle of the Central Corridor".

Modeled on a classic NTC rotation fight: an OPFOR motorized regiment attacks
west-to-east through the Central Corridor (between the Granite Mountains and
Tiefort Mountain) toward the Whale Gap / Brown-Debnam pass complex, while a
BLUFOR task force defends in sector and commits a reserve counterattack.

Units follow timed waypoint routes (tick, lat, lon). Positions are linearly
interpolated between waypoints; a unit holds at its last waypoint.
Contact events (destruction) remove units at scripted ticks.
"""

# One tick = 2 s of wall time, but represents ~1 min of battle time.
SCENARIO_LENGTH_TICKS = 600

# Key NTC terrain references (approximate)
# Central Corridor runs roughly E-W around lat 35.33, lon -116.75 .. -116.55
# The Whale: ~35.335, -116.665 | Hill 876: ~35.34, -116.72 | Debnam pass area

SCENARIO = {
    "name": "Battle of the Central Corridor",
    "description": (
        "OPFOR motorized regiment attacks east through the Central Corridor "
        "toward the Whale Gap. BLUFOR TF defends with two company teams "
        "forward, scouts screening, and a reserve counterattack at H+5."
    ),
    "length_ticks": SCENARIO_LENGTH_TICKS,
    "phases": [
        {"tick": 0, "name": "Screen / OPFOR approach march"},
        {"tick": 120, "name": "Scouts report; OPFOR deploys to attack formation"},
        {"tick": 240, "name": "Main battle at the Whale Gap"},
        {"tick": 380, "name": "BLUFOR reserve counterattack"},
        {"tick": 500, "name": "OPFOR culminates; consolidation"},
    ],
}

# waypoints: (tick, lat, lon)
UNITS = [
    # ---------------- BLUFOR: TF 1-64 (defending) --------------------------
    # Mesh Alpha: Team A defends northern shoulder of the corridor
    {"callsign": "ALPHA-6", "role": "command", "affiliation": "friendly", "mesh_id": "MESH-ALPHA",
     "waypoints": [(0, 35.352, -116.622), (240, 35.350, -116.618), (600, 35.348, -116.615)]},
    {"callsign": "A-1", "role": "armor", "affiliation": "friendly", "mesh_id": "MESH-ALPHA",
     "waypoints": [(0, 35.356, -116.640), (200, 35.352, -116.648), (360, 35.348, -116.652), (600, 35.346, -116.650)]},
    {"callsign": "A-2", "role": "armor", "affiliation": "friendly", "mesh_id": "MESH-ALPHA",
     "waypoints": [(0, 35.360, -116.634), (240, 35.356, -116.640), (600, 35.352, -116.644)]},
    {"callsign": "A-3", "role": "infantry", "affiliation": "friendly", "mesh_id": "MESH-ALPHA",
     "waypoints": [(0, 35.349, -116.630), (600, 35.349, -116.630)]},
    {"callsign": "A-4", "role": "recon", "affiliation": "friendly", "mesh_id": "MESH-ALPHA",
     "waypoints": [(0, 35.352, -116.700), (100, 35.354, -116.720), (160, 35.358, -116.700),
                   (240, 35.356, -116.670), (600, 35.354, -116.655)]},

    # Mesh Bravo: Team B defends southern shoulder near the Whale
    {"callsign": "BRAVO-6", "role": "command", "affiliation": "friendly", "mesh_id": "MESH-BRAVO",
     "waypoints": [(0, 35.322, -116.612), (600, 35.322, -116.612)]},
    {"callsign": "B-1", "role": "armor", "affiliation": "friendly", "mesh_id": "MESH-BRAVO",
     "waypoints": [(0, 35.328, -116.648), (260, 35.330, -116.656), (420, 35.326, -116.660), (600, 35.324, -116.655)]},
    {"callsign": "B-2", "role": "armor", "affiliation": "friendly", "mesh_id": "MESH-BRAVO",
     "waypoints": [(0, 35.318, -116.640), (300, 35.320, -116.650), (600, 35.318, -116.648)]},
    {"callsign": "B-3", "role": "infantry", "affiliation": "friendly", "mesh_id": "MESH-BRAVO",
     "waypoints": [(0, 35.330, -116.662), (600, 35.330, -116.662)],
     "destroyed_at": 320},
    {"callsign": "B-4", "role": "recon", "affiliation": "friendly", "mesh_id": "MESH-BRAVO",
     "waypoints": [(0, 35.316, -116.700), (90, 35.312, -116.724), (150, 35.318, -116.740),
                   (220, 35.322, -116.716), (300, 35.320, -116.690), (600, 35.318, -116.672)]},

    # Mesh Charlie: TF reserve — counterattacks at ~tick 380
    {"callsign": "CHARLIE-6", "role": "command", "affiliation": "friendly", "mesh_id": "MESH-CHARLIE",
     "waypoints": [(0, 35.372, -116.590), (380, 35.372, -116.590), (450, 35.360, -116.625),
                   (520, 35.350, -116.660), (600, 35.346, -116.672)]},
    {"callsign": "C-1", "role": "armor", "affiliation": "friendly", "mesh_id": "MESH-CHARLIE",
     "waypoints": [(0, 35.376, -116.585), (380, 35.376, -116.585), (440, 35.366, -116.620),
                   (510, 35.354, -116.658), (600, 35.348, -116.678)]},
    {"callsign": "C-2", "role": "armor", "affiliation": "friendly", "mesh_id": "MESH-CHARLIE",
     "waypoints": [(0, 35.369, -116.582), (380, 35.369, -116.582), (450, 35.358, -116.618),
                   (530, 35.348, -116.652), (600, 35.344, -116.668)]},
    {"callsign": "C-3", "role": "infantry", "affiliation": "friendly", "mesh_id": "MESH-CHARLIE",
     "waypoints": [(0, 35.374, -116.596), (420, 35.374, -116.596), (520, 35.362, -116.630), (600, 35.356, -116.648)]},

    # ---------------- OPFOR: motorized regiment (attacking east) -----------
    # 1st echelon
    {"callsign": "KRASNO-11", "role": "opfor_armor", "affiliation": "hostile",
     "waypoints": [(0, 35.330, -116.850), (120, 35.332, -116.790), (240, 35.334, -116.730),
                   (340, 35.332, -116.690), (600, 35.330, -116.668)],
     "destroyed_at": 470},
    {"callsign": "KRASNO-12", "role": "opfor_armor", "affiliation": "hostile",
     "waypoints": [(0, 35.322, -116.856), (130, 35.320, -116.795), (250, 35.322, -116.735),
                   (360, 35.324, -116.688), (600, 35.322, -116.664)],
     "destroyed_at": 430},
    {"callsign": "KRASNO-13", "role": "opfor_infantry", "affiliation": "hostile",
     "waypoints": [(0, 35.340, -116.845), (140, 35.342, -116.780), (280, 35.344, -116.715),
                   (420, 35.342, -116.680), (600, 35.340, -116.664)]},
    # 2nd echelon
    {"callsign": "KRASNO-21", "role": "opfor_armor", "affiliation": "hostile",
     "waypoints": [(0, 35.328, -116.900), (200, 35.330, -116.820), (360, 35.330, -116.740),
                   (480, 35.328, -116.700), (600, 35.326, -116.680)],
     "destroyed_at": 560},
    {"callsign": "KRASNO-22", "role": "opfor_armor", "affiliation": "hostile",
     "waypoints": [(0, 35.316, -116.905), (220, 35.314, -116.822), (380, 35.316, -116.745), (600, 35.314, -116.700)]},
    # Regimental recon (leads the attack)
    {"callsign": "KRASNO-R1", "role": "opfor_recon", "affiliation": "hostile",
     "waypoints": [(0, 35.334, -116.800), (80, 35.336, -116.755), (160, 35.334, -116.715),
                   (240, 35.332, -116.685), (600, 35.330, -116.672)],
     "destroyed_at": 260},
]


def phase_at(tick: int) -> str:
    current = SCENARIO["phases"][0]["name"]
    for p in SCENARIO["phases"]:
        if tick >= p["tick"]:
            current = p["name"]
    return current


def position_at(waypoints, tick: int):
    """Linear interpolation along timed waypoints; holds at the ends."""
    if tick <= waypoints[0][0]:
        return waypoints[0][1], waypoints[0][2]
    for i in range(len(waypoints) - 1):
        t0, lat0, lon0 = waypoints[i]
        t1, lat1, lon1 = waypoints[i + 1]
        if t0 <= tick <= t1:
            f = (tick - t0) / max(1, (t1 - t0))
            return lat0 + (lat1 - lat0) * f, lon0 + (lon1 - lon0) * f
    return waypoints[-1][1], waypoints[-1][2]
