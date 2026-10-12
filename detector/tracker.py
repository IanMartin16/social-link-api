from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TrendingEpisode, EpisodeTrack

log = logging.getLogger("detector.tracker")

EVENT_DROP = 0.80           # drawdown desde el pico que define COLAPSO
CENSOR_DAYS = 14            # sobrevive 14d sin evento -> CENSORED
INTENSIVE_HOURS = 48        # POST_INTENSIVE -> POST_LIGHT
STALE_ENTRY_DROP = 0.50    # red de seguridad: 1er precio fresco >50% bajo el entry
                           # con pico sin confirmar = entry rancio -> re-anclar
BATCH_IDS = 250

PriceMap = dict[str, dict]
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
                        await asyncio.sleep(2 * (attempt + 1))
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

    events = censored = downshift = tracked = missing = reanchored = 0

    for ep in episodes:
        q = prices.get(ep.coingecko_id or "")
        price = float(q["usd"]) if q and q.get("usd") is not None else None
        vol = q.get("usd_24h_vol") if q else None

        # 1) cadencia POST_INTENSIVE -> POST_LIGHT
        if ep.state == "POST_INTENSIVE" and ep.left_trend_at:
            if _hours(ep.left_trend_at, now) >= INTENSIVE_HOURS:
                ep.state = "POST_LIGHT"
                downshift += 1

        if price is None:
            missing += 1
        else:
            # 2) RED DE SEGURIDAD: entry rancio -> re-anclar (NO disparar EVENT)
            #    El pico sigue siendo el de nacimiento (nunca confirmado en vivo) y el
            #    precio fresco está muy por debajo = el trending traía precio stale.
            stale_entry = (
                ep.peak_at is not None
                and ep.peak_at == ep.entered_trend_at
                and ep.peak_price is not None
                and price < float(ep.peak_price) * (1 - STALE_ENTRY_DROP)
            )
            if stale_entry:
                ep.peak_price, ep.peak_at = price, now      # re-ancla al precio fresco real
                ep.trough_price, ep.trough_at = price, now
                ep.max_drawdown = 0
                ep.peak_confidence = "reanchored"
                reanchored += 1
            else:
                # 3) pico/fondo/drawdown (rolling) — dueño único del precio-estado
                if ep.peak_price is None or price > float(ep.peak_price):
                    ep.peak_price, ep.peak_at = price, now
                if ep.trough_price is None or price < float(ep.trough_price):
                    ep.trough_price, ep.trough_at = price, now
                dd = _dd(ep.peak_price, price)
                if dd is not None and (ep.max_drawdown is None or dd > float(ep.max_drawdown)):
                    ep.max_drawdown = dd

                # 4) EVENT — solo si el pico fue confirmado en vivo (peak_at > entry)
                #    Doble candado: si el pico sigue siendo el del nacimiento, NO se
                #    emite EVENT (no observamos el descenso = no es etiqueta confiable).
                peak_confirmed = ep.peak_at is not None and ep.peak_at > ep.entered_trend_at
                if dd is not None and dd >= EVENT_DROP and peak_confirmed:
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

        # 5) CENSORED (sobrevivió 14d sin evento)
        if ep.state != "CLOSED" and _hours(ep.entered_trend_at, now) >= CENSOR_DAYS * 24:
            ep.state = "CLOSED"
            ep.label = "CENSORED"
            ep.closed_at = now
            censored += 1

    await session.commit()
    summary = {
        "open_before": len(episodes), "tracked": tracked, "events": events,
        "censored": censored, "downshift": downshift, "reanchored": reanchored,
        "missing_price": missing,
    }
    log.info("tracker: %s", summary)
    return summary
