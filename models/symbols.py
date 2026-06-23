from pydantic import BaseModel
from typing import Optional


class SymbolMarket(BaseModel):
    """Ficha de mercado por activo (campos de oro de CoinGecko /coins/markets).

    Descartados a propósito: roi (casi siempre null), atl* (anecdótico),
    market_cap_change* (redundante con price change), last_updated.
    """
    symbol: str
    name: Optional[str] = None
    image: Optional[str] = None          # logo oficial CoinGecko
    rank: Optional[int] = None           # market_cap_rank

    price: Optional[float] = None        # current_price
    change24h: Optional[float] = None    # price_change_percentage_24h (el REAL)
    high24h: Optional[float] = None
    low24h: Optional[float] = None

    marketCap: Optional[float] = None
    volume24h: Optional[float] = None
    circulatingSupply: Optional[float] = None
    totalSupply: Optional[float] = None
    maxSupply: Optional[float] = None

    ath: Optional[float] = None
    athChangePct: Optional[float] = None  # ath_change_percentage
    athDate: Optional[str] = None


class SymbolsResponse(BaseModel):
    ok: bool
    source: str
    ts: str
    fiat: str
    symbols: list[SymbolMarket]
    # símbolos pedidos que NO tuvieron datos (no existen en CoinGecko o sin id).
    # El front los puede mostrar como "data unavailable" en vez de hueco.
    missing: list[str] = []
