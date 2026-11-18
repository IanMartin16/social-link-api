# repositories/fear_greed_repo.py
from __future__ import annotations
from sqlalchemy import text
from db.session import get_session


async def fetch_fear_greed(days: int | None) -> dict:
    async with get_session() as session:
        win = "AND captured_at >= now() - :days * interval '1 day'" if days else ""

        series = (await session.execute(text(f"""
            SELECT extract(epoch FROM day)::bigint AS t, value, label
            FROM (
                SELECT DISTINCT ON (date_trunc('day', captured_at))
                       date_trunc('day', captured_at) AS day,
                       fng_value AS value, fng_label AS label
                FROM snapshot
                WHERE fng_value IS NOT NULL {win}
                ORDER BY date_trunc('day', captured_at), captured_at DESC
            ) s
            ORDER BY t ASC
        """), ({"days": days} if days else {}))).mappings().all()

        cur = (await session.execute(text("""
            SELECT fng_value AS value, fng_label AS label
            FROM snapshot WHERE fng_value IS NOT NULL
            ORDER BY captured_at DESC LIMIT 1
        """))).mappings().first()

        async def as_of(n: int):
            r = (await session.execute(text("""
                SELECT fng_value AS value, fng_label AS label
                FROM snapshot
                WHERE fng_value IS NOT NULL AND captured_at <= now() - :n * interval '1 day'
                ORDER BY captured_at DESC LIMIT 1
            """), {"n": n})).mappings().first()
            return {"value": int(r["value"]), "label": r["label"]} if r else None

        yesterday, last_week, last_month = await as_of(1), await as_of(7), await as_of(30)

        high = (await session.execute(text("""
            SELECT fng_value AS value, fng_label AS label, extract(epoch FROM captured_at)::bigint AS t
            FROM snapshot WHERE fng_value IS NOT NULL
            ORDER BY fng_value DESC, captured_at ASC LIMIT 1
        """))).mappings().first()
        low = (await session.execute(text("""
            SELECT fng_value AS value, fng_label AS label, extract(epoch FROM captured_at)::bigint AS t
            FROM snapshot WHERE fng_value IS NOT NULL
            ORDER BY fng_value ASC, captured_at ASC LIMIT 1
        """))).mappings().first()

        since = (await session.execute(text("""
            SELECT extract(epoch FROM min(captured_at))::bigint AS t
            FROM snapshot WHERE fng_value IS NOT NULL
        """))).mappings().first()

    return {
        "series": [{"t": int(r["t"]), "value": int(r["value"]), "label": r["label"]}
                   for r in series if r["value"] is not None],
        "current": {"value": int(cur["value"]), "label": cur["label"]} if cur else None,
        "comparisons": {"yesterday": yesterday, "lastWeek": last_week, "lastMonth": last_month},
        "extremes": {
            "high": {"value": int(high["value"]), "label": high["label"], "t": int(high["t"])} if high else None,
            "low":  {"value": int(low["value"]),  "label": low["label"],  "t": int(low["t"])}  if low  else None,
        },
        "trackingSince": int(since["t"]) if since and since["t"] is not None else None,
    }