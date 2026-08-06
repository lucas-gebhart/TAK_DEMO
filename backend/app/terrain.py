"""Terrain elevation service for the NTC area.

Downloads real SRTM-derived elevation data as Terrarium PNG tiles from the
public AWS Open Data elevation-tiles-prod bucket and caches them on disk.
Falls back to a synthetic desert-mountain terrain if tiles are unavailable.
"""
import math
import os
import threading

import numpy as np

TILE_ZOOM = 11
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
CACHE_DIR = os.environ.get(
    "TAKDEMO_TILE_CACHE", os.path.join(os.path.dirname(__file__), "..", "tile_cache")
)


def _latlon_to_tile(lat: float, lon: float, zoom: int):
    n = 2 ** zoom
    xt = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    yt = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xt, yt


class TerrainService:
    """Provides elevation lookups (meters MSL) for arbitrary lat/lon."""

    def __init__(self):
        self._tiles = {}
        self._lock = threading.Lock()
        self._synthetic = False
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _load_tile(self, tx: int, ty: int):
        key = (tx, ty)
        with self._lock:
            if key in self._tiles:
                return self._tiles[key]
        arr = self._fetch_tile(tx, ty)
        with self._lock:
            self._tiles[key] = arr
        return arr

    def _fetch_tile(self, tx: int, ty: int):
        from PIL import Image
        path = os.path.join(CACHE_DIR, f"{TILE_ZOOM}_{tx}_{ty}.png")
        try:
            if not os.path.exists(path):
                import requests
                url = TILE_URL.format(z=TILE_ZOOM, x=tx, y=ty)
                r = requests.get(url, timeout=15)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
            img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
            # Terrarium encoding: elevation = (R*256 + G + B/256) - 32768
            return img[:, :, 0] * 256.0 + img[:, :, 1] + img[:, :, 2] / 256.0 - 32768.0
        except Exception:
            self._synthetic = True
            return None

    def elevation(self, lat: float, lon: float) -> float:
        xt, yt = _latlon_to_tile(lat, lon, TILE_ZOOM)
        tx, ty = int(xt), int(yt)
        arr = self._load_tile(tx, ty)
        if arr is None:
            return self._synthetic_elevation(lat, lon)
        px = min(int((xt - tx) * 256), 255)
        py = min(int((yt - ty) * 256), 255)
        return float(arr[py, px])

    @staticmethod
    def _synthetic_elevation(lat: float, lon: float) -> float:
        """Rough NTC-like desert basin with mountain ridges (fallback only)."""
        base = 700.0
        ridges = (
            250.0 * math.sin((lon + 116.7) * 55.0) * math.cos((lat - 35.2) * 40.0)
            + 180.0 * math.sin((lon + 116.5) * 90.0 + 1.3)
            + 120.0 * math.cos((lat - 35.35) * 120.0 + 0.7)
        )
        return base + max(0.0, ridges)

    def profile(self, lat1, lon1, lat2, lon2, samples=48):
        """Elevation profile between two points."""
        return [
            self.elevation(lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t)
            for t in (i / (samples - 1) for i in range(samples))
        ]


terrain = TerrainService()
