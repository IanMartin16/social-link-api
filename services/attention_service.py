"""Calcula attentionScore (sostenida) + direction/delta (emergente) sobre la
historia del trending, filtrado al stock. window=14d, recent=3d."""
from repositories.attention_repo import fetch_attention_window
from utils.symbol_policy import ALLOWED_SOCIAL_ASSETS
from adapters.coingecko_adapter import infer_tags   # reusa el que ya existe
from datetime import datetime, timezone
from clients.alternative_client import fetch_fear_greed
from adapters.alternative_adapter import map_fear_greed_to_backdrop

# posición del trending: 0..14 (0 = más buscado). Normalizamos a "cercanía a top".
TRENDING_SLOTS = 15


def _sustained_score(appearances: int, avg_pos: float | None, max_appearances: int) -> float:
    """0-100. Combina cuánto apareció (frecuencia) y qué tan arriba (posición)."""
    if max_appearances <= 0:
        return 0.0
    freq = appearances / max_appearances                     # 0..1
    pos = 1.0 - ((avg_pos or TRENDING_SLOTS) / TRENDING_SLOTS)  # 0..1 (mejor pos = más alto)
    pos = max(0.0, min(1.0, pos))
    # pesos: frecuencia manda un poco más que posición
    score = (freq * 0.6 + pos * 0.4) * 100
    return round(score, 1)


def _emergent(recent, prev) -> tuple[float, str]:
    """Compara reciente vs previo. Devuelve (deltaPct, direction).
       Emergente = aparece más ahora que antes, o mejora posición."""
    r_app = recent.appearances if recent else 0
    p_app = prev.appearances if prev else 0
    # delta de frecuencia normalizado (evita div/0)
    if p_app == 0 and r_app == 0:
        return 0.0, "flat"
    if p_app == 0:
        return 100.0, "up"           # apareció ahora, no antes = emergente fuerte
    delta = ((r_app - p_app) / p_app) * 100
    delta = round(delta, 2)
    direction = "up" if delta > 5 else "down" if delta < -5 else "flat"
    return delta, direction


async def get_attention(limit: int = 15) -> dict:
    data = await fetch_attention_window(days=14, recent_days=3)
    total, recent, prev, series = data["total"], data["recent"], data["prev"], data["series"]

    max_app = max((r.appearances for r in total.values()), default=1)

    leaders = []
    for sym, row in total.items():
        if sym not in ALLOWED_SOCIAL_ASSETS:
            continue
        score = _sustained_score(row.appearances, float(row.avg_pos) if row.avg_pos else None, max_app)
        delta, direction = _emergent(recent.get(sym), prev.get(sym))
        leaders.append({
            "asset": sym,
            "attentionScore": score,
            "attentionDeltaPct": delta,
            "direction": direction,
            "appearances": row.appearances,
            "avgPosition": round(float(row.avg_pos), 1) if row.avg_pos else None,
            "spark": series.get(sym, []),
            "tags": infer_tags(sym, sym),
        })

    leaders.sort(key=lambda x: x["attentionScore"], reverse=True)
    leaders = leaders[:limit]

    # 1) armar el result en una VARIABLE (no retornar directo)
    result = {
        "ok": True,
        "source": "social-link-trending-history-v2",
        "ts": datetime.now(timezone.utc).isoformat(),
        "window": "14d",
        "market": {
            "attentionLeaders": leaders,
            "coverage": "broad" if len(leaders) >= 8 else "moderate" if len(leaders) >= 4 else "low",
        },
    }

    # 2) agregar el backdrop (fng) ANTES del return
    try:
        fng = await fetch_fear_greed()
        result["backdrop"] = map_fear_greed_to_backdrop(fng)
    except Exception:
        result["backdrop"] = None

    # 3) UN solo return, al final
    return result