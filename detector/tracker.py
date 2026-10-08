from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TrendingEpisode, EpisodeTrack

log = logging.getLogger("detector.tracker")

EVENT_DROP = 0.80           # drawdown desde el pico que define COLAPSO
CENSOR_DAYS = 14            # sobrevive 14d sin evento -> CENSORED
INTENSIVE_HOURS = 48        # POST_INTENSIVE -> POST_LIGHT
BATCH_IDS = 250             # /simple/price aguanta muchos ids por llamada

# NOTA DE CUOTA — por qué el tracker es KEYLESS y NO usa la demo key:
# corre seguido (cada ~3 min) y casi siempre hay episodios abiertos → ~1 call/3min
# ≈ 14,000 calls/mes. La Demo key tiene tope de 10,000/mes → la reventaría.
# Keyless NO tiene tope mensual, y su límite por-minuto (1 call cada 3 min) sobra.
# El gate (market_chart, por-coin, solo en nacimientos) sí puede usar la demo; el
# tracker (simple/price, batch, alta frecuencia) debe quedarse keyless. Cada uno
# en su carril.

PriceMap = dict[str, dict]                       # coingecko_id -> {"usd":..., "usd_24h_vol":...}
FetchPrices = Callable[[list[str]], Awaitable[PriceMap]]


async def _default_fetch_prices(ids: list[str]) -> PriceMap:
    """Precio + volumen de MUCHOS ids en una sola llamada (/simple/price). Keyless."""
    out: PriceMap = {}
    for i in range(0, len(ids), BATCH_IDS):
        chunk = ids[i:i + BATCH_IDS]
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": ",".join(chunk), "vs_currencies": "usd", "include_24hr_vol": "true"}
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get(url, params=params)
                    if r.status_code == 429:
                        await asyncio.sleep(2 * (attempt + 1))   # backoff
                        continue
                    r.raise_for_status()
                    out.update(r.json())
                    break
            except Exception as e:  # noqa: BLE001
                log.warning("fetch_prices falló (chunk %d): %s", i, e)
                break
    return out


def _dd(peak, price) -> Optional[float]:
    if peak and price and float(peak) > 0:
        return max(0.0, (float(peak) - float(price)) / float(peak))
    return None


def _hours(a: datetime, b: datetime) -> float:
    return round((b - a).total_seconds() / 3600.0, 3)


async def run_tracker(
    session: AsyncSession,
    *,
    fetch_prices: FetchPrices = _default_fetch_prices,
) -> dict:
    now = datetime.now(timezone.utc)

    episodes = (await session.scalars(
        select(TrendingEpisode).where(TrendingEpisode.state != "CLOSED")
    )).all()
    if not episodes:
        return {"status": "no_open_episodes"}

    ids = sorted({ep.coingecko_id for ep in episodes if ep.coingecko_id})
    prices = await fetch_prices(ids) if ids else {}

    events = censored = downshift = tracked = missing = 0

    for ep in episodes:
        q = prices.get(ep.coingecko_id or "")
        price = float(q["usd"]) if q and q.get("usd") is not None else None
        vol = q.get("usd_24h_vol") if q else None

        # 1) cadencia POST_INTENSIVE -> POST_LIGHT (48h fuera del trending)
        if ep.state == "POST_INTENSIVE" and ep.left_trend_at:
            if _hours(ep.left_trend_at, now) >= INTENSIVE_HOURS:
                ep.state = "POST_LIGHT"
                downshift += 1

        if price is None:
            missing += 1   # el id no volvió en /simple/price (raro: delisted/typo)
        else:
            # 2) pico/fondo/drawdown (rolling)
            if ep.peak_price is None or price > float(ep.peak_price):
                ep.peak_price, ep.peak_at = price, now
            if ep.trough_price is None or price < float(ep.trough_price):
                ep.trough_price, ep.trough_at = price, now
            dd = _dd(ep.peak_price, price)
            if dd is not None and (ep.max_drawdown is None or dd > float(ep.max_drawdown)):
                ep.max_drawdown = dd

            # 3) EVENT (colapso)
            if dd is not None and dd >= EVENT_DROP:
                ep.state = "CLOSED"
                ep.label = "EVENT"
                ep.event_at = now
                ep.closed_at = now
                ep.time_to_event_h = _hours(ep.entered_trend_at, now)
                if ep.peak_at:
                    ep.dump_speed_h = _hours(ep.peak_at, now)
                events += 1

            # track row (idempotente por (episode_id, ts))
            await session.execute(
                pg_insert(EpisodeTrack).values(
                    episode_id=ep.episode_id, ts=now, price=price,
                    source="coingecko",
                    in_trending=(ep.state == "ACTIVE_TRENDING"),
                    rank=None, vol24h=vol,
                    drawdown_from_peak=_dd(ep.peak_price, price),
                    time_in_trend_h=_hours(ep.entered_trend_at, now),
                    raw={"from": "tracker"}, live_features={},
                ).on_conflict_do_nothing(index_elements=["episode_id", "ts"])
            )
            tracked += 1

        # 4) CENSORED (sobrevivió 14d sin evento = excepción genuina)
        if ep.state != "CLOSED" and _hours(ep.entered_trend_at, now) >= CENSOR_DAYS * 24:
            ep.state = "CLOSED"
            ep.label = "CENSORED"
            ep.closed_at = now
            censored += 1

    await session.commit()
    summary = {
        "open_before": len(episodes), "tracked": tracked, "events": events,
        "censored": censored, "downshift": downshift, "missing_price": missing,
    }
    log.info("tracker: %s", summary)
    return summary
