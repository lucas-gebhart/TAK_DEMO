"""SQLite persistence for units, CoT events, links, and message stats."""
import os
import sqlite3
import threading

DB_PATH = os.environ.get(
    "TAKDEMO_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "takdemo.db")
)

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    uid TEXT PRIMARY KEY,
    callsign TEXT NOT NULL,
    affiliation TEXT NOT NULL,
    role TEXT NOT NULL,
    mesh_id TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    hae REAL NOT NULL DEFAULT 0,
    speed_mps REAL NOT NULL DEFAULT 0,
    course_deg REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cot_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL,
    xml TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS message_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL,
    src_uid TEXT NOT NULL,
    dst_uid TEXT NOT NULL,
    src_mesh TEXT,
    dst_mesh TEXT,
    hops INTEGER NOT NULL,
    quality REAL NOT NULL,
    delivered INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS snapshots (
    tick INTEGER PRIMARY KEY,
    json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS link_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL,
    a_uid TEXT NOT NULL,
    b_uid TEXT NOT NULL,
    quality REAL NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_unit(u: dict):
    get_conn().execute(
        """INSERT INTO units (uid, callsign, affiliation, role, mesh_id, lat, lon, hae, speed_mps, course_deg, updated_at)
           VALUES (:uid, :callsign, :affiliation, :role, :mesh_id, :lat, :lon, :hae, :speed_mps, :course_deg, datetime('now'))
           ON CONFLICT(uid) DO UPDATE SET
             lat=:lat, lon=:lon, hae=:hae, speed_mps=:speed_mps,
             course_deg=:course_deg, updated_at=datetime('now')""",
        u,
    )


def insert_cot(uid: str, xml: str):
    get_conn().execute("INSERT INTO cot_events (uid, xml) VALUES (?, ?)", (uid, xml))


def insert_message(tick, src, dst, src_mesh, dst_mesh, hops, quality, delivered):
    get_conn().execute(
        """INSERT INTO message_log (tick, src_uid, dst_uid, src_mesh, dst_mesh, hops, quality, delivered)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (tick, src, dst, src_mesh, dst_mesh, hops, quality, int(delivered)),
    )


def insert_link(tick, a, b, quality, kind):
    get_conn().execute(
        "INSERT INTO link_snapshots (tick, a_uid, b_uid, quality, kind) VALUES (?, ?, ?, ?, ?)",
        (tick, a, b, quality, kind),
    )


def insert_snapshot(tick: int, payload: str):
    get_conn().execute(
        "INSERT OR REPLACE INTO snapshots (tick, json) VALUES (?, ?)", (tick, payload)
    )


def commit():
    get_conn().commit()


def message_stats(last_n_ticks: int = 50, current_tick: int = 0):
    cutoff = max(0, current_tick - last_n_ticks)
    rows = get_conn().execute(
        """SELECT src_mesh, dst_mesh,
                  COUNT(*) AS attempts,
                  SUM(delivered) AS delivered
           FROM message_log WHERE tick > ?
           GROUP BY src_mesh, dst_mesh""",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]
