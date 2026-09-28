"""Lee trending_snapshot para calcular atención sostenida + emergente."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_
from db.session import get_session
from db.models import TrendingSnapshot 


async def fetch_attention_window(days: int = 14, recent_days: int = 3) -> dict:
    """Devuelve, por símbolo, las métricas crudas de las dos ventanas:
       - total: apariciones y posición promedio en `days` (sostenida)
       - recent: apariciones y posición en los últimos `recent_days` (emergente)
       - prev: apariciones y posición en la ventana previa (para comparar)
       - serie: lista de (captured_at, position) para el sparkline
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    recent_start = now - timedelta(days=recent_days)

    async with get_session() as db:
        # --- agregado TOTAL (sostenida) por símbolo, últimos `days` ---
        total_q = (
            select(
                TrendingSnapshot.symbol,
                func.count().label("appearances"),
                func.avg(TrendingSnapshot.position).label("avg_pos"),
                func.min(TrendingSnapshot.position).label("best_pos"),
                func.max(TrendingSnapshot.captured_at).label("last_seen"),
            )
            .where(TrendingSnapshot.captured_at >= start)
            .group_by(TrendingSnapshot.symbol)
        )
        total_rows = (await db.execute(total_q)).all()

        # --- agregado RECIENTE (últimos recent_days) por símbolo ---
        recent_q = (
            select(
                TrendingSnapshot.symbol,
                func.count().label("appearances"),
                func.avg(TrendingSnapshot.position).label("avg_pos"),
            )
            .where(TrendingSnapshot.captured_at >= recent_start)
            .group_by(TrendingSnapshot.symbol)
        )
        recent_rows = (await db.execute(recent_q)).all()

        # --- agregado PREVIO (de start a recent_start) por símbolo ---
        prev_q = (
            select(
                TrendingSnapshot.symbol,
                func.count().label("appearances"),
                func.avg(TrendingSnapshot.position).label("avg_pos"),
            )
            .where(and_(
                TrendingSnapshot.captured_at >= start,
                TrendingSnapshot.captured_at < recent_start,
            ))
            .group_by(TrendingSnapshot.symbol)
        )
        prev_rows = (await db.execute(prev_q)).all()

        # --- serie de posición por símbolo (para sparkline), últimos `days` ---
        # downsample: una lectura por día (evita traer miles de puntos).
        # Postgres: date_trunc('day') + avg(position) por día.
        # series con label para reusar en group_by y order_by
        day_col = func.date_trunc("day", TrendingSnapshot.captured_at).label("day")
        series_q = (
            select(
                TrendingSnapshot.symbol,
                day_col,
                func.avg(TrendingSnapshot.position).label("avg_pos"),
            )
            .where(TrendingSnapshot.captured_at >= start)
            .group_by(TrendingSnapshot.symbol, day_col)
            .order_by(TrendingSnapshot.symbol, day_col)
        )
        series_rows = (await db.execute(series_q)).all()

    # armar dicts por símbolo
    total = {r.symbol: r for r in total_rows}
    recent = {r.symbol: r for r in recent_rows}
    prev = {r.symbol: r for r in prev_rows}

    series: dict[str, list] = {}
    for r in series_rows:
        series.setdefault(r.symbol, []).append(float(r.avg_pos) if r.avg_pos is not None else None)

    return {"total": total, "recent": recent, "prev": prev, "series": series,
            "window_days": days, "recent_days": recent_days}

async def fetch_pulse_series(days: int = 14, top_n: int = 15) -> list[dict]:
    """Serie del composite de atención por día (últimos `days`).
       composite del día = promedio de (15 - position) de los top_n mejores de ese día.
       Refleja la atención de ESE día → evoluciona (no el score-14d estable)."""

    start = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_session() as db:
        # posición promedio por símbolo POR DÍA (solo los que aparecieron ese día)
        day_col = func.date_trunc("day", TrendingSnapshot.captured_at).label("day")
        per_symbol_day = (
            select(
                day_col,
                TrendingSnapshot.symbol,
                func.avg(TrendingSnapshot.position).label("avg_pos"),
            )
            .where(TrendingSnapshot.captured_at >= start)
            .group_by(day_col, TrendingSnapshot.symbol)
        ).subquery()

        rows = (await db.execute(
            select(per_symbol_day.c.day, per_symbol_day.c.symbol, per_symbol_day.c.avg_pos)
            .order_by(per_symbol_day.c.day)
        )).all()

    # agrupar por día en Python: tomar los top_n (mejor posición = menor avg_pos)
    # y promediar su "atención" (15 - pos)
    from collections import defaultdict
    by_day: dict = defaultdict(list)
    for r in rows:
        by_day[r.day].append((r.symbol, float(r.avg_pos)))

    TRENDING_SLOTS = 15
    series = []
    for day in sorted(by_day.keys()):
        # top_n por mejor posición (menor avg_pos)
        best = sorted(by_day[day], key=lambda x: x[1])[:top_n]
        if not best:
            continue
        composite = sum(max(0.0, TRENDING_SLOTS - pos) for _, pos in best) / len(best)
        # a escala 0..100 (posición invertida 0..15 → *~6.67)
        composite_100 = round(composite / TRENDING_SLOTS * 100, 1)
        series.append({
            "day": day.date().isoformat(),   # "2026-09-28"
            "composite": composite_100,
        })
    return series            