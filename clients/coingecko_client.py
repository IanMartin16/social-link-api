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

async def fetch_top_markets(vs_currency: str = "usd", per_page: int = 50) -> list[dict]:
    """Trae el TOP N del mercado por market cap, en UNA sola llamada.

    A diferencia de fetch_markets(ids=...), aquí NO se pasan ids: se le pide a
    CoinGecko su top por market cap directamente. Consecuencias:
      - No hay que resolver symbol -> coingecko_id (no usa symbol_ids).
      - No hay `missing` posible: nunca pedimos algo que no exista.
      - Se actualiza solo: si una moneda entra o sale del top, se refleja.
      - Sigue siendo 1 sola llamada (mismo costo que pedir 2 símbolos).

    Devuelve la lista cruda de CoinGecko (un dict por moneda), mismo shape que
    fetch_markets -> el adapter map_markets_to_symbols NO cambia.
    """
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,   # top N por market cap
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