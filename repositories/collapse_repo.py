"""
repositories/collapse_repo.py

Capa de BD del insight collapse-risk. Lee SOLO filas-resumen de `trending_episode`
(las que NO se podan), así que es barato. n chico → traemos las filas crudas de
los EVENT y agregamos en Python (el service), para no pelear con percentile_cont.

NOTA DE INTEGRACIÓN: usa la MISMA factory de sesión async que `attention_repo`.
Ajusta este import a tu proyecto si el nombre difiere.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import text

# <-- usa el MISMO import que attention_repo (ajusta la ruta del módulo si difiere)
from db.session import get_session

MATURE_DAYS = 14


async def fetch_collapse_stats(mature_days: int = MATURE_DAYS) -> dict:
    """Agregados crudos de la cohorte madura (entró hace >= mature_days)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=mature_days)

    async with get_session() as session:   # mismo patrón que attention_repo
        # base rate: EVENT vs CENSORED en cohorte madura
        base_rows = (await session.execute(text("""
            SELECT label, count(*) AS n
            FROM trending_episode
            WHERE entered_trend_at <= :cutoff
              AND label IN ('EVENT', 'CENSORED')
            GROUP BY label
        """), {"cutoff": cutoff})).all()

        # sanity: maduros que NO cerraron (debería ser 0)
        stuck = (await session.execute(text("""
            SELECT count(*) AS n
            FROM trending_episode
            WHERE entered_trend_at <= :cutoff
              AND state <> 'CLOSED'
        """), {"cutoff": cutoff})).scalar_one()

        # dinámica: filas crudas de los EVENT maduros (n chico → se agrega en Python)
        ev_rows = (await session.execute(text("""
            SELECT time_to_event_h, dump_speed_h, max_drawdown
            FROM trending_episode
            WHERE label = 'EVENT'
              AND entered_trend_at <= :cutoff
              AND time_to_event_h IS NOT NULL
        """), {"cutoff": cutoff})).all()

    base = {r.label: int(r.n) for r in base_rows}
    event_rows = [
        {
            "tte_h": float(r.time_to_event_h) if r.time_to_event_h is not None else None,
            "dump_h": float(r.dump_speed_h) if r.dump_speed_h is not None else None,
            "max_dd": float(r.max_drawdown) if r.max_drawdown is not None else None,
        }
        for r in ev_rows
    ]

    return {
        "events": base.get("EVENT", 0),
        "censored": base.get("CENSORED", 0),
        "stuck": int(stuck),
        "event_rows": event_rows,
    }
