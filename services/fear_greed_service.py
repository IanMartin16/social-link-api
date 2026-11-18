# services/fear_greed_service.py
from __future__ import annotations
import time
from datetime import datetime, timezone
from repositories.fear_greed_repo import fetch_fear_greed

_cache: dict[str, dict] = {}
_cache_at: dict[str, float] = {}
_CACHE_TTL_S = 55 * 60              # F&G cambia ~diario → cache largo
_WINDOWS = {"1y": 365, "all": None}

async def get_fear_greed(window: str = "all") -> dict:
    now = time.time()
    if window in _cache and (now - _cache_at.get(window, 0)) < _CACHE_TTL_S:
        return _cache[window]
    data = await fetch_fear_greed(_WINDOWS.get(window, None))
    fresh = {"ok": True, "source": "alternative.me",
             "ts": datetime.now(timezone.utc).isoformat(), "window": window, **data}
    _cache[window] = fresh
    _cache_at[window] = now
    return fresh