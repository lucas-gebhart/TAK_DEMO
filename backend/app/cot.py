"""Cursor-on-Target (CoT) event generation."""
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

COT_TYPES = {
    "infantry": "a-f-G-U-C-I",
    "armor": "a-f-G-U-C-A",
    "recon": "a-f-G-U-C-R",
    "command": "a-f-G-U-H",
    "opfor_infantry": "a-h-G-U-C-I",
    "opfor_armor": "a-h-G-U-C-A",
    "opfor_recon": "a-h-G-U-C-R",
}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def cot_xml(unit: dict, stale_seconds: int = 60) -> str:
    now = datetime.now(timezone.utc)
    cot_type = COT_TYPES.get(unit["role"], "a-f-G-U-C")
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<event version="2.0" uid="{escape(unit["uid"])}" type="{cot_type}" '
        f'time="{_iso(now)}" start="{_iso(now)}" '
        f'stale="{_iso(now + timedelta(seconds=stale_seconds))}" how="m-g">'
        f'<point lat="{unit["lat"]:.6f}" lon="{unit["lon"]:.6f}" '
        f'hae="{unit.get("hae", 0.0):.1f}" ce="10.0" le="10.0"/>'
        f'<detail>'
        f'<contact callsign="{escape(unit["callsign"])}"/>'
        f'<__group name="{escape(unit.get("team", "Cyan"))}" role="Team Member"/>'
        f'<track speed="{unit.get("speed_mps", 0.0):.1f}" course="{unit.get("course_deg", 0.0):.1f}"/>'
        f'</detail>'
        f'</event>'
    )


def new_uid() -> str:
    return str(uuid.uuid4())


def parse_cot(xml_text: str) -> dict:
    """Parse a CoT 2.0 event into an inject-unit spec. Raises ValueError."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"invalid XML: {e}") from e
    if root.tag != "event":
        raise ValueError("root element must be <event>")
    point = root.find("point")
    if point is None:
        raise ValueError("missing <point>")
    cot_type = root.get("type", "a-f-G-U-C")
    affiliation = "hostile" if cot_type.startswith("a-h") else "friendly"
    role_by_type = {v: k for k, v in COT_TYPES.items()}
    contact = root.find("detail/contact")
    callsign = (contact.get("callsign") if contact is not None else None) or root.get("uid", "UNKNOWN")
    return {
        "uid": root.get("uid"),
        "callsign": callsign,
        "affiliation": affiliation,
        "role": role_by_type.get(cot_type, "infantry" if affiliation == "friendly" else "opfor_infantry"),
        "lat": float(point.get("lat")),
        "lon": float(point.get("lon")),
    }
