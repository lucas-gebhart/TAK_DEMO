"""Line-of-sight radio propagation model.

Simplified terrain-aware model for VHF/UHF mesh radios:
  1. Free-space range limit based on TX power / receiver sensitivity.
  2. Terrain LOS check with 4/3-earth-radius refraction and 60% first
     Fresnel zone clearance along the great-circle path.
Returns a link quality in [0, 1]:
  0            -> no link (out of range or fully obstructed)
  (0, 0.5)     -> degraded link (marginal Fresnel clearance / long range)
  [0.5, 1]     -> good link
"""
import math

from .terrain import terrain

EARTH_R = 6371000.0
K_FACTOR = 4.0 / 3.0  # standard atmospheric refraction
FREQ_MHZ = 915.0      # typical ISM-band mesh radio
ANTENNA_HEIGHT_M = 2.0
MAX_RANGE_M = 15000.0  # hard free-space range limit for the radio
PROFILE_SAMPLES = 48


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def fresnel_radius_m(d1_m: float, d2_m: float, freq_mhz: float) -> float:
    d_total = d1_m + d2_m
    if d_total <= 0:
        return 0.0
    wavelength = 299.792458 / freq_mhz  # meters
    return math.sqrt(wavelength * d1_m * d2_m / d_total)


def link_quality(lat1, lon1, lat2, lon2) -> float:
    dist = haversine_m(lat1, lon1, lat2, lon2)
    if dist < 1.0:
        return 1.0
    if dist > MAX_RANGE_M:
        return 0.0

    elev1 = terrain.elevation(lat1, lon1) + ANTENNA_HEIGHT_M
    elev2 = terrain.elevation(lat2, lon2) + ANTENNA_HEIGHT_M
    profile = terrain.profile(lat1, lon1, lat2, lon2, PROFILE_SAMPLES)

    # Worst-case Fresnel clearance ratio along the path.
    worst = 1.0
    for i in range(1, PROFILE_SAMPLES - 1):
        t = i / (PROFILE_SAMPLES - 1)
        d1 = dist * t
        d2 = dist * (1 - t)
        # Height of the direct ray above MSL at this point.
        ray_h = elev1 + (elev2 - elev1) * t
        # Earth curvature bulge with refraction correction.
        bulge = (d1 * d2) / (2 * K_FACTOR * EARTH_R)
        ground = profile[i] + bulge
        f1 = fresnel_radius_m(d1, d2, FREQ_MHZ)
        if f1 <= 0:
            continue
        clearance = (ray_h - ground) / f1  # 1.0 == full first-Fresnel clearance
        worst = min(worst, clearance)

    if worst <= 0.0:
        return 0.0  # ray blocked by terrain
    # 60% Fresnel clearance is considered unobstructed.
    los_factor = min(worst / 0.6, 1.0)
    # Range factor: quality degrades with distance toward MAX_RANGE_M.
    range_factor = max(0.0, 1.0 - (dist / MAX_RANGE_M) ** 2)
    return max(0.0, min(1.0, los_factor * (0.4 + 0.6 * range_factor)))


def delivery_probability(quality: float) -> float:
    """Probability a single message is delivered over a link of given quality."""
    if quality <= 0.0:
        return 0.0
    return min(0.99, 0.35 + 0.64 * quality)
