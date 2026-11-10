"""
services/market_structure_service.py

Market Structure: dominancia + distancia al ATH del top100 (asset_snapshot).
Dos medidas honestas de estructura de mercado en un solo panel. Datos horarios
→ cache largo. Mismo patrón de cache de módulo que attention_service.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from repositories.market_structure_repo import fetch_market_structure

_cache: dict[int, dict] = {}
_cache_at: dict[int, float] = {}
_CACHE_TTL_S = 55 * 60   # datos horarios → 55 min


async def get_market_structure(hours: int = 720) -> dict:
    now = time.time()
    if hours in _cache and (now - _cache_at.get(hours, 0)) < _CACHE_TTL_S:
        return _cache[hours]
    fresh = await _compute(hours)
    _cache[hours] = fresh
    _cache_at[hours] = now
    return fresh


async def _compute(hours: int) -> dict:
    data = await fetch_market_structure(hours)
    dom = data["dominance"]
    ath = data["ath"]

    latest_dom = dom[-1] if dom else None
    latest_ath = ath[-1] if ath else None

    return {
        "ok": True,
        "source": "social-link-asset-snapshot",
        "ts": datetime.now(timezone.utc).isoformat(),
        "window": f"{hours // 24}d",
        # readouts actuales
        "btcDominance": latest_dom["btc"] if latest_dom else None,
        "ethDominance": latest_dom["eth"] if latest_dom else None,
        "avgAthDistance": latest_ath["avg"] if latest_ath else None,   # % promedio bajo ATH
        "nearAth": latest_ath["nearAth"] if latest_ath else None,       # # dentro de 10% de su ATH
        "universe": latest_ath["n"] if latest_ath else None,
        # series
        "dominance": dom,   # [{t, btc, eth}]
        "ath": ath,         # [{t, avg, nearAth, n}]
        "note": "Dominancia y ATH sobre el top 100 rastreado (/coins/markets).",
    }
