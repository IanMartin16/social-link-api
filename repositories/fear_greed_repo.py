# repositories/fear_greed_repo.py
from __future__ import annotations
import httpx   # o el cliente http que ya uses para CoinGecko

FNG_URL = "https://api.alternative.me/fng/?limit=0&format=json"

async def fetch_fear_greed(days: int | None) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(FNG_URL, headers={"accept": "application/json"})
        r.raise_for_status()
        raw = r.json().get("data", [])

    # alternative.me viene más-reciente-primero; normaliza ascendente
    pts = sorted(
        ({"t": int(d["timestamp"]), "value": int(d["value"]),
          "label": d.get("value_classification", "")} for d in raw if d.get("value")),
        key=lambda p: p["t"],
    )
    if not pts:
        return {"series": [], "current": None, "comparisons": {},
                "extremes": {}, "trackingSince": None}

    latest = pts[-1]

    series = pts if not days else [p for p in pts if p["t"] >= latest["t"] - days * 86400]

    def as_of(n: int):
        target = latest["t"] - n * 86400
        prior = [p for p in pts if p["t"] <= target]
        return {"value": prior[-1]["value"], "label": prior[-1]["label"]} if prior else None

    # extremos "yearly" (últimos 365d) con fecha — estilo CMC
    yearly = [p for p in pts if p["t"] >= latest["t"] - 365 * 86400] or pts
    hi = max(yearly, key=lambda p: p["value"])
    lo = min(yearly, key=lambda p: p["value"])

    return {
        "series": [{"t": p["t"], "value": p["value"], "label": p["label"]} for p in series],
        "current": {"value": latest["value"], "label": latest["label"]},
        "comparisons": {"yesterday": as_of(1), "lastWeek": as_of(7), "lastMonth": as_of(30)},
        "extremes": {
            "high": {"value": hi["value"], "label": hi["label"], "t": hi["t"]},
            "low":  {"value": lo["value"], "label": lo["label"], "t": lo["t"]},
        },
        "trackingSince": pts[0]["t"],   # inicio real de alternative.me (~2018)
    }