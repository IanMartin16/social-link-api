import httpx

COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"


async def fetch_trending():
    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.get(
            COINGECKO_TRENDING_URL,
            headers={"accept": "application/json"},
        )
        res.raise_for_status()
        return res.json()
    
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


async def fetch_markets(ids: list[str], vs_currency: str = "usd") -> list[dict]:
    """Trae datos ricos de mercado para los ids dados, en UNA sola llamada.

    ids: lista de coingecko_id ya resueltos (ej. ["bitcoin", "ether-fi"]).
    Devuelve la lista cruda de CoinGecko (un dict por moneda).
    """
    if not ids:
        return []

    params = {
        "vs_currency": vs_currency,
        "ids": ",".join(ids),
        # orden estable; el front reordena si quiere
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.get(
            COINGECKO_MARKETS_URL,
            params=params,
            headers={"accept": "application/json"},
        )
        res.raise_for_status()
        return res.json()
