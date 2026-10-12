from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TrendingSnapshot, TrendingEpisode, EpisodeTrack
from detector.resolver import resolve_cl_id

log = logging.getLogger("detector.episodizer")

# --- parámetros ---
AFTERMATH_DROP = 0.40     # si entró >40% bajo el máximo reciente -> EXCLUDED
RECENT_HIGH_DAYS = 7
COOLDOWN_HOURS = 24       # tras un EVENT, no re-abrir el mismo coin por 24h (anti-eco)

FetchRecentHigh = Callable[[str], Awaitable[Optional[float]]]


async def _default_recent_high(coingecko_id: str) -> Optional[float]:
    """Máximo de precio de los últimos RECENT_HIGH_DAYS días (CoinGecko keyless + backoff)."""
    import asyncio
    import os
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart"
    params = {"vs_currency": "usd", "days": str(RECENT_HIGH_DAYS)}
    demo = os.environ.get("COINGECKO_DEMO_KEY", "")
    headers = {"x-cg-demo-api-key": demo} if demo else {}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(url, params=params, headers=headers)
                if r.status_code == 429:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                r.raise_for_status()
                vals = [p[1] for p in r.json().get("prices", []) if p and p[1] is not None]
                return max(vals) if vals else None
        except Exception as e:  # noqa: BLE001
            log.warning("recent_high fetch falló para %s: %s", coingecko_id, e)
            return None
    return None


def _hours(a: datetime, b: datetime) -> float:
    return round((b - a).total_seconds() / 3600.0, 3)


def _drawdown(peak, price) -> Optional[float]:
    if peak and price and float(peak) > 0:
        return max(0.0, (float(peak) - float(price)) / float(peak))
    return None


async def run_episodizer(
    session: AsyncSession,
    *,
    fetch_recent_high: FetchRecentHigh = _default_recent_high,
) -> dict:
    latest_ts = await session.scalar(select(func.max(TrendingSnapshot.captured_at)))
    if latest_ts is None:
        return {"status": "no_trending_data"}

    rows = (await session.scalars(
        select(TrendingSnapshot).where(TrendingSnapshot.captured_at == latest_ts)
    )).all()

    seen_cl_ids: set[int] = set()
    born = cont = excluded = cooled = 0

    for row in rows:
        cl_id = await resolve_cl_id(
            session, coingecko_id=row.coin_id, symbol=row.symbol, name=row.name,
        )
        if cl_id is None:
            log.info("skip (sin coingecko_id): symbol=%s", row.symbol)
            continue
        seen_cl_ids.add(cl_id)

        price = float(row.price_usd) if row.price_usd is not None else None

        ep = await session.scalar(
            select(TrendingEpisode).where(
                and_(TrendingEpisode.cl_id == cl_id, TrendingEpisode.state != "CLOSED")
            )
        )

        if ep is None:
            # ---- COOLDOWN: ¿este coin cerró un EVENT hace < COOLDOWN_HOURS? ----
            recent_evt = await session.scalar(
                select(TrendingEpisode.episode_id).where(
                    TrendingEpisode.cl_id == cl_id,
                    TrendingEpisode.label == "EVENT",
                    TrendingEpisode.closed_at >= latest_ts - timedelta(hours=COOLDOWN_HOURS),
                ).limit(1)
            )
            if recent_evt is not None:
                # reaparece en trending justo tras colapsar = ECO del mismo evento, no re-abrir
                cooled += 1
                continue

            # ---- NACIMIENTO + gate de aftermath ----
            recent_high = await fetch_recent_high(row.coin_id) if row.coin_id else None
            peak_conf, label, state = "observed", None, "ACTIVE_TRENDING"
            if recent_high is None:
                peak_conf = "unknown"
            elif price is not None and price < recent_high * (1 - AFTERMATH_DROP):
                label, state = "EXCLUDED", "CLOSED"
                excluded += 1

            ep = TrendingEpisode(
                cl_id=cl_id, coingecko_id=row.coin_id, symbol=row.symbol, name=row.name,
                entered_trend_at=latest_ts,
                entry_price=row.price_usd, entry_rank=row.market_cap_rank,
                entry_mcap=row.market_cap_usd, entry_vol24h=row.total_volume_usd,
                entry_features={},
                recent_high=recent_high, recent_high_win_d=RECENT_HIGH_DAYS,
                peak_confidence=peak_conf,
                peak_price=row.price_usd, peak_at=latest_ts,   # el tracker re-ancla si venía rancio
                trough_price=row.price_usd, trough_at=latest_ts,
                max_drawdown=0,
                state=state, label=label,
                closed_at=(latest_ts if state == "CLOSED" else None),
            )
            session.add(ep)
            await session.flush()
            if label == "EXCLUDED":
                continue
            born += 1
        else:
            # ---- CONTINÚA: solo reactivar si reapareció en trending ----
            # (el episodizador YA NO toca pico/drawdown/EVENT — eso es del tracker)
            if ep.state in ("POST_INTENSIVE", "POST_LIGHT"):
                ep.state, ep.left_trend_at = "ACTIVE_TRENDING", None
            cont += 1

        # ---- track 'in_trending' (informativo; idempotente por (episode_id, ts)) ----
        await session.execute(
            pg_insert(EpisodeTrack).values(
                episode_id=ep.episode_id, ts=latest_ts, price=row.price_usd,
                source="trending", in_trending=True, trend_position=row.position,
                rank=row.market_cap_rank, vol24h=row.total_volume_usd,
                drawdown_from_peak=_drawdown(ep.peak_price, price),
                time_in_trend_h=_hours(ep.entered_trend_at, latest_ts),
                raw={"from": "trending_snapshot", "score": row.score},
                live_features={},
            ).on_conflict_do_nothing(index_elements=["episode_id", "ts"])
        )

    # salidas de trending: ACTIVE_TRENDING que ya NO están en el batch
    actives = (await session.scalars(
        select(TrendingEpisode).where(TrendingEpisode.state == "ACTIVE_TRENDING")
    )).all()
    left = 0
    for ep in actives:
        if ep.cl_id not in seen_cl_ids:
            ep.state, ep.left_trend_at = "POST_INTENSIVE", latest_ts
            left += 1

    await session.commit()
    summary = {
        "batch": latest_ts.isoformat(), "born": born, "continued": cont,
        "excluded": excluded, "cooled_down": cooled, "left_trending": left,
    }
    log.info("episodizer: %s", summary)
    return summary
