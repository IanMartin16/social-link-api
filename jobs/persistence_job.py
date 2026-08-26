"""
jobs/persistence_job.py — el job de persistencia de social_link.

Cada 10 min (APScheduler in-process):
  1. Obtiene markets(top 100) + trending + fear&greed VÍA EL CACHÉ (get_or_fetch).
     → NO agrega llamadas a CoinGecko: si el portal ya pidió datos recientes,
       lee del caché; si no, hace 1 llamada que TAMBIÉN sirve al portal.
  2. Crea un snapshot (cabezal) con captured_at común.
  3. Puebla asset_snapshot (markets) y trending_snapshot (trending) con el mismo
     snapshot_id/captured_at.

Diseño clave: markets y trending son flujos SEPARADOS en social_link, pero el job
los une bajo un mismo snapshot para que el ML pueda cruzarlos por tiempo.
"""

from datetime import datetime, timezone

from db.session import get_session
from db.models import Snapshot, AssetSnapshot, TrendingSnapshot
from utils.cache import cache

# los fetch crudos existentes (sin caché); el caché los envuelve aquí
from clients.coingecko_client import fetch_top_markets, fetch_trending
from clients.alternative_client import fetch_fear_greed
from adapters.coingecko_adapter import map_markets_to_symbols
from adapters.alternative_adapter import map_fear_greed_to_backdrop

# TTL del caché: alineado a la ventana. El portal y el job comparten estas claves.
CACHE_TTL = 300  # 5 min
TOP_N = 100      # top por market cap a persistir


def _money_str_to_float(v):
    """CoinGecko trending manda market_cap/volume como '$40,179,689'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = v.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


async def _cached_top_markets():
    return await cache.get_or_fetch(
        key=f"markets:top:{TOP_N}:usd",
        fetch_fn=lambda: fetch_top_markets(vs_currency="usd", per_page=TOP_N),
        ttl_seconds=CACHE_TTL,
    )


async def _cached_trending():
    return await cache.get_or_fetch(
        key="trending:usd",
        fetch_fn=fetch_trending,
        ttl_seconds=CACHE_TTL,
    )


async def _cached_fng():
    raw = await cache.get_or_fetch(
        key="fng",
        fetch_fn=fetch_fear_greed,
        ttl_seconds=CACHE_TTL,
    )
    return map_fear_greed_to_backdrop(raw)


async def persist_snapshot() -> None:
    """Una captura completa: markets + trending + fng en un snapshot."""
    captured_at = datetime.now(timezone.utc)

    # --- 1. obtener datos (vía caché, sin llamadas extra) ---
    try:
        raw_markets = await _cached_top_markets()
    except Exception as e:
        print(f"[persist] markets fetch failed: {e}")
        raw_markets = []

    try:
        raw_trending = await _cached_trending()
    except Exception as e:
        print(f"[persist] trending fetch failed: {e}")
        raw_trending = {}

    fng_value = None
    fng_label = None
    try:
        backdrop = await _cached_fng()
        if backdrop:
            fng_value = backdrop.get("fearGreedValue")
            fng_label = backdrop.get("fearGreedLabel")
    except Exception as e:
        print(f"[persist] fng fetch failed: {e}")

    # si no hay NI markets NI trending, no tiene sentido escribir un snapshot vacío
    if not raw_markets and not (raw_trending or {}).get("coins"):
        print("[persist] nothing to persist this cycle (cache cold, no data)")
        return

    # --- 2. mapear markets a objetos Pydantic (reusa el adapter existente) ---
    symbols = map_markets_to_symbols(raw_markets)  # list[SymbolMarket]

    # --- 3. escribir todo en una transacción ---
    async with get_session() as session:
        snap = Snapshot(
            captured_at=captured_at,
            fng_value=fng_value,
            fng_label=fng_label,
            coverage=None,           # el basic-signals no está en este flujo; opcional
            market_tags=None,
            source_markets="social-link-coingecko-markets-v1",
            source_signals="social-link-coingecko-trending-v1",
        )
        session.add(snap)
        await session.flush()  # obtiene snap.id sin cerrar la transacción

        # asset_snapshot desde markets (la señal REAL)
        for s in symbols:
            session.add(AssetSnapshot(
                snapshot_id=snap.id,
                captured_at=captured_at,
                symbol=s.symbol,
                price=s.price,
                change_24h=s.change24h,
                high_24h=s.high24h,
                low_24h=s.low24h,
                market_cap=s.marketCap,
                volume_24h=s.volume24h,
                rank=s.rank,
                ath=s.ath,
                ath_change_pct=s.athChangePct,
                circulating_supply=s.circulatingSupply,
                total_supply=s.totalSupply,
                max_supply=s.maxSupply,
            ))

        # trending_snapshot desde trending (ATENCIÓN real)
        coins = (raw_trending or {}).get("coins", [])
        for position, entry in enumerate(coins):
            item = entry.get("item", {}) or {}
            data = item.get("data", {}) or {}
            pcp = data.get("price_change_percentage_24h") or {}
            symbol = (item.get("symbol") or "").strip().upper()
            if not symbol:
                continue

            session.add(TrendingSnapshot(
                snapshot_id=snap.id,
                captured_at=captured_at,
                position=position,
                symbol=symbol,
                name=item.get("name"),
                coin_id=item.get("id"),
                market_cap_rank=item.get("market_cap_rank"),
                score=item.get("score"),
                price_usd=data.get("price"),
                price_change_24h_usd=pcp.get("usd") if isinstance(pcp, dict) else None,
                market_cap_usd=_money_str_to_float(data.get("market_cap")),
                total_volume_usd=_money_str_to_float(data.get("total_volume")),
            ))

        await session.commit()

    n_assets = len(symbols)
    n_trending = len((raw_trending or {}).get("coins", []))
    print(f"[persist] snapshot {snap.id} @ {captured_at.isoformat()} "
          f"— {n_assets} assets, {n_trending} trending")
