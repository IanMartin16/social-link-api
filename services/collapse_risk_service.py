"""
services/collapse_risk_service.py

Insight collapse-risk: la base rate honesta (cohorte madura) + dinámica del colapso.
Mismo patrón de cache de módulo que attention_service. TTL largo: la base rate
cambia lento (solo se mueve cuando maduran/cierran episodios).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from statistics import mean, median

from repositories.collapse_repo import fetch_collapse_stats

_cache: dict | None = None
_cache_at: float = 0.0
_CACHE_TTL_S = 60 * 60  # 1h — cambia lento

WINDOW_DAYS = 14
BUCKETS = ["0-1d", "1-3d", "3-7d", "7-14d"]


def _bucket(tte_h: float) -> str:
    if tte_h <= 24:
        return "0-1d"
    if tte_h <= 72:
        return "1-3d"
    if tte_h <= 168:
        return "3-7d"
    return "7-14d"


async def get_collapse_risk() -> dict:
    """Puerta con cache: sirve el cacheado si es fresco, si no recalcula."""
    global _cache, _cache_at
    now = time.time()
    if _cache is not None and (now - _cache_at) < _CACHE_TTL_S:
        return _cache
    fresh = await _compute_collapse_risk()
    _cache = fresh
    _cache_at = now
    return fresh


async def _compute_collapse_risk() -> dict:
    s = await fetch_collapse_stats(mature_days=WINDOW_DAYS)

    events = s["events"]
    censored = s["censored"]
    matured = events + censored

    base_rate = round(events / matured * 100, 1) if matured else None
    survive = round(100 - base_rate, 1) if base_rate is not None else None
    one_in = round(matured / events, 1) if events else None

    rows = s["event_rows"]
    tte = [r["tte_h"] for r in rows if r["tte_h"] is not None]
    dump = [r["dump_h"] for r in rows if r["dump_h"] is not None]
    dd = [r["max_dd"] for r in rows if r["max_dd"] is not None]

    dynamics = {
        "medianTimeToEventH": round(median(tte), 1) if tte else None,
        "avgTimeToEventH": round(mean(tte), 1) if tte else None,
        "medianDumpSpeedH": round(median(dump), 1) if dump else None,
        "avgMaxDrawdownPct": round(mean(dd) * 100, 1) if dd else None,  # max_drawdown es 0..1
    }

    counts = {b: 0 for b in BUCKETS}
    for v in tte:
        counts[_bucket(v)] += 1
    n_ev = len(tte)
    distribution = [
        {
            "bucket": b,
            "events": counts[b],
            "pct": round(counts[b] / n_ev * 100, 1) if n_ev else 0.0,
        }
        for b in BUCKETS
    ]

    return {
        "ok": True,
        "source": "social-link-detector-collapse-risk",
        "ts": datetime.now(timezone.utc).isoformat(),
        "window": f"{WINDOW_DAYS}d",
        "cohort": {
            "matured": matured,
            "events": events,
            "censored": censored,
            "stuck": s["stuck"],
        },
        "baseRate": {
            "collapsePct": base_rate,
            "survivePct": survive,
            "oneInN": one_in,
        },
        "dynamics": dynamics,
        "distribution": distribution,
        "method": (
            "EVENT = caída ≥80% desde un pico confirmado en vivo; "
            "CENSORED = sobrevivió 14d sin eso. Tasa sobre cohorte madura "
            "(entró a trending hace ≥14d, donde todos ya cerraron)."
        ),
        "disclaimer": "Direccional — muestra chica, se afina con más cohortes. No es consejo financiero.",
    }
