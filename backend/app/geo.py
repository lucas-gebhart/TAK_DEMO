"""Geographic coordinate validation shared by the inject/CoT entry points."""
import math

LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0
# Web-Mercator tiling is undefined beyond this latitude.
MERCATOR_LAT_LIMIT = 85.05112878
SPEED_MAX_MPS = 10000.0


def validate_lat(value) -> float:
    return _coerce(value, "lat", LAT_MIN, LAT_MAX)


def validate_lon(value) -> float:
    return _coerce(value, "lon", LON_MIN, LON_MAX)


def validate_latlon(lat, lon) -> tuple[float, float]:
    return validate_lat(lat), validate_lon(lon)


def validate_speed(value) -> float:
    return _coerce(value, "speed_mps", 0.0, SPEED_MAX_MPS)


def _coerce(value, name: str, lo: float, hi: float) -> float:
    if value is None:
        raise ValueError(f"missing {name}")
    try:
        f = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid {name}: {value!r}") from e
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if not lo <= f <= hi:
        raise ValueError(f"{name} must be within [{lo}, {hi}], got {f}")
    return f


def clamp_for_tiles(lat: float, lon: float) -> tuple[float, float]:
    """Clamp a coordinate into the range where tile math is defined.

    Non-finite input is mapped to 0.0 so that elevation lookups can never
    raise and abort a simulation tick.
    """
    lat = 0.0 if not math.isfinite(lat) else min(max(lat, -MERCATOR_LAT_LIMIT), MERCATOR_LAT_LIMIT)
    lon = 0.0 if not math.isfinite(lon) else min(max(lon, LON_MIN), LON_MAX)
    return lat, lon
