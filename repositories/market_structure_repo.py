"""
repositories/market_structure_repo.py

Explota asset_snapshot (fundamentos del top100 de /coins/markets). Dos lecturas
MEDIDAS de estructura, AGRUPADAS POR HORA (el job captura cada 10 min; por hora
basta para estructura y de paso diluye glitches tomando el ÚLTIMO snapshot/hora):
  - Dominancia: BTC/ETH como % del mcap del top100 rastreado.
  - Distancia al ATH: promedio de ath_change_pct = posicionamiento vs máximos.

Una sola query (barata). Mismo get_session que attention_repo/collapse_repo.
symbol de /coins/markets viene en minúsculas → upper() para BTC/ETH.
"""
from __future__ import annotations

from sqlalchemy import text

from db.session import get_session   # <-- mismo import que los otros repos


async def fetch_market_structure(hours: int) -> dict:
    async with get_session() as session:
        rows = (await session.execute(text("""
            WITH last_snap_per_hr AS (
                -- un snapshot por hora: el más reciente de cada hora
                SELECT DISTINCT ON (date_trunc('hour', captured_at))
                       snapshot_id,
                       date_trunc('hour', captured_at) AS hr
                FROM asset_snapshot
                WHERE captured_at >= now() - :hours * interval '1 hour'
                ORDER BY date_trunc('hour', captured_at), captured_at DESC
            )
            SELECT l.hr AS t,
                   ROUND(SUM(a.market_cap) FILTER (WHERE upper(a.symbol) = 'BTC')
                         / NULLIF(SUM(a.market_cap), 0) * 100, 2)              AS btc_dom,
                   ROUND(COALESCE(SUM(a.market_cap) FILTER (WHERE upper(a.symbol) = 'ETH'), 0)
                         / NULLIF(SUM(a.market_cap), 0) * 100, 2)              AS eth_dom,
                   ROUND(AVG(a.ath_change_pct)::numeric, 2)                     AS avg_ath,
                   COUNT(*) FILTER (WHERE a.ath_change_pct >= -10)              AS near_ath,
                   COUNT(a.ath_change_pct)                                      AS n
            FROM last_snap_per_hr l
            JOIN asset_snapshot a ON a.snapshot_id = l.snapshot_id
            GROUP BY l.hr
            ORDER BY l.hr ASC
        """), {"hours": hours})).all()

    dominance: list[dict] = []
    ath: list[dict] = []
    for r in rows:
        t = int(r.t.timestamp())
        if r.btc_dom is not None:
            dominance.append({"t": t, "btc": float(r.btc_dom), "eth": float(r.eth_dom or 0)})
        if r.avg_ath is not None:
            ath.append({"t": t, "avg": float(r.avg_ath), "nearAth": int(r.near_ath), "n": int(r.n)})

    return {"dominance": dominance, "ath": ath}
