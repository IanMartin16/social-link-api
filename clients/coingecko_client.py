import httpx
from utils.cache import cache

COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

# TTLs por endpoint (segundos). Ajustables:
#  - markets/top: el portal los muestra "en vivo"; 60s equilibra frescura y carga.
#  - trending: cambia lento (ventana de horas); 300s sobra.
TTL_MARKETS = 60
TTL_TOP = 60
TTL_TRENDING = 300


# ----------------- llamadas REALES (sin caché) -----------------

async def _fetch_trending_raw():
    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.get(
            COINGECKO_TRENDING_URL,
            headers={"accept": "application/json"},
        )
        res.raise_for_status()
        return res.json()


async def _fetch_markets_raw(ids: list[str], vs_currency: str = "usd") -> list[dict]:
    if not ids:
        return []
    params = {
        "vs_currency": vs_currency,
        "ids": ",".join(ids),
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.get(COINGECKO_MARKETS_URL, params=params,
                               headers={"accept": "application/json"})
        res.raise_for_status()
        return res.json()


async def _fetch_top_markets_raw(vs_currency: str = "usd", per_page: int = 50) -> list[dict]:
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.get(COINGECKO_MARKETS_URL, params=params,
                               headers={"accept": "application/json"})
        res.raise_for_status()
        return res.json()


# ----------------- API PÚBLICA (cacheada) -----------------

async def fetch_trending():
    return await cache.get_or_fetch(
        key="trending:usd",
        fetch_fn=_fetch_trending_raw,
        ttl_seconds=TTL_TRENDING,
    )


async def fetch_markets(ids: list[str], vs_currency: str = "usd") -> list[dict]:
    if not ids:
        return []
    # clave estable: mismos ids en cualquier orden -> misma clave (evita
    # cachés separados por reordenamiento). El vs_currency entra en la clave.
    ids_key = ",".join(sorted(i.lower() for i in ids))
    key = f"markets:ids:{vs_currency.lower()}:{ids_key}"
    return await cache.get_or_fetch(
        key=key,
        fetch_fn=lambda: _fetch_markets_raw(ids, vs_currency),
        ttl_seconds=TTL_MARKETS,
    )


async def fetch_top_markets(vs_currency: str = "usd", per_page: int = 50) -> list[dict]:
    key = f"markets:top:{per_page}:{vs_currency.lower()}"
    return await cache.get_or_fetch(
        key=key,
        fetch_fn=lambda: _fetch_top_markets_raw(vs_currency, per_page),
        ttl_seconds=TTL_TOP,
    )
