"""Lee trending_snapshot para calcular atención sostenida + emergente."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_
from db.session import get_session
from db.models import TrendingSnapshot   # ajustar import real


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