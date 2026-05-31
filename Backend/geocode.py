# ─── Server-side geocoding with a permanent DB cache ─────────────────────────
# Resolves free-text Bengaluru places (e.g. "JP Nagar", "Whitefield PS") to
# lat/lng via OpenStreetMap Nominatim, caching every result in the geocode_cache
# table so each place is only ever geocoded ONCE across the whole deployment.
#
# This replaces per-browser client geocoding: the map endpoint returns
# coordinates directly, so the admin map renders instantly after the first warm-up.

import threading
import time
import logging

import requests

try:
    from . import queries
except ImportError:
    import queries

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim usage policy asks for a descriptive User-Agent and <= 1 req/sec.
_HEADERS = {"User-Agent": "ThemisDomain-CRMS/1.0 (police case map)"}
_REQUEST_GAP_SECONDS = 1.1

# Serialise all outbound geocode calls process-wide so we never exceed the rate
# limit even if two requests trigger a warm-up at once.
_geocode_lock = threading.Lock()


def _normalized_key(kind: str, place: str) -> str:
    return f"{kind}:{place.strip()}"


def _query_variants(kind: str, place: str):
    """Ordered query variants; first hit wins. Mirrors the old client logic."""
    place = place.strip()
    variants = []

    def add(s):
        v = " ".join(s.split())
        if v and v not in variants:
            variants.append(v)

    if kind == "station":
        base = place
        for token in ("police station", "p.s.", "ps"):
            base = base.replace(token, "").replace(token.upper(), "").replace(token.title(), "")
        base = base.strip(" .")
        add(f"{place} Police Station")
        if base:
            add(base)
        add(place)
    else:
        add(place)
    return variants


def _geocode_one(kind: str, place: str):
    """Calls Nominatim for a place. Returns (lat, lng) or None. Rate-limited."""
    for variant in _query_variants(kind, place):
        query = f"{variant}, Bengaluru, Karnataka, India"
        try:
            with _geocode_lock:
                resp = requests.get(
                    NOMINATIM_URL,
                    params={"format": "jsonv2", "limit": 1, "q": query},
                    headers=_HEADERS,
                    timeout=8,
                )
                time.sleep(_REQUEST_GAP_SECONDS)  # politeness gap, inside the lock
            if resp.status_code != 200:
                continue
            data = resp.json()
            if isinstance(data, list) and data:
                try:
                    return float(data[0]["lat"]), float(data[0]["lon"])
                except (KeyError, ValueError, TypeError):
                    continue
        except requests.RequestException as e:
            logger.warning(f"[geocode] request failed for '{variant}': {e}")
            return None  # transient — don't cache a miss, allow retry later
    return None  # all variants exhausted -> confirmed miss


def resolve_places(items):
    """
    items: list of (kind, place) tuples.
    Returns {place: {"lat":.., "lng":..}} for everything we can resolve, using the
    DB cache first and only calling Nominatim for places never seen before.
    New results (hits and confirmed misses) are persisted to the cache.
    """
    cache = queries.get_geocode_cache()
    out = {}
    for kind, place in items:
        if not place or not place.strip():
            continue
        key = _normalized_key(kind, place)
        cached = cache.get(key)
        if cached is not None:
            # Cached hit or confirmed miss — never re-geocode.
            if cached["resolved"] and cached["lat"] is not None:
                out[place] = {"lat": cached["lat"], "lng": cached["lng"]}
            continue

        coord = _geocode_one(kind, place)
        if coord:
            lat, lng = coord
            queries.upsert_geocode(key, lat, lng, True)
            out[place] = {"lat": lat, "lng": lng}
        else:
            queries.upsert_geocode(key, None, None, False)
    return out
