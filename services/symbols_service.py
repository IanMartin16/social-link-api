# services/symbols_service.py

from datetime import datetime, timezone

from clients.coingecko_client import fetch_markets
from adapters.coingecko_adapter import map_markets_to_symbols
from utils.symbol_ids import resolve_ids
from utils.symbol_policy import FALLBACK_ASSETS
from models.symbols import SymbolsResponse, SymbolMarket


async def get_symbols_360(
    symbols: list[str] | None = None,
    fiat: str = "USD",
) -> SymbolsResponse:
    """Ficha de mercado rica (CoinGecko) para los símbolos seleccionados.

    - symbols: los seleccionados por el usuario (del front). Si vacío -> fallback.
    - Resuelve symbol -> coingecko_id (dict espejo de cryptolink_symbols).
    - Una sola llamada a /coins/markets con ids=.
    - Robusto: símbolos sin id o sin datos en CoinGecko van a `missing`.
    """
    requested = symbols if symbols else list(FALLBACK_ASSETS)

    # 1) resolver ids (los que no tienen id ya son "missing")
    resolved, missing = resolve_ids(requested)

    ts = datetime.now(timezone.utc).isoformat()

    if not resolved:
        # nada que pedir: devolvemos vacío honesto, no rompemos
        return SymbolsResponse(
            ok=True,
            source="social-link-coingecko-markets-v1",
            ts=ts,
            fiat=fiat.upper(),
            symbols=[],
            missing=missing,
        )

    # 2) una sola llamada a CoinGecko
    vs = fiat.lower()
    try:
        raw = await fetch_markets(ids=list(resolved.values()), vs_currency=vs)
    except Exception:
        # si CoinGecko falla, devolvemos vacío + todos como missing (degradación)
        return SymbolsResponse(
            ok=True,
            source="social-link-coingecko-markets-v1",
            ts=ts,
            fiat=fiat.upper(),
            symbols=[],
            missing=list(resolved.keys()) + missing,
        )

    # 3) mapear a campos de oro
    mapped: list[SymbolMarket] = map_markets_to_symbols(raw)

    # 4) detectar símbolos pedidos que CoinGecko no devolvió (existen en dict
    #    pero sin datos) y sumarlos a missing
    returned_syms = {s.symbol for s in mapped}
    for sym in resolved.keys():
        if sym not in returned_syms:
            missing.append(sym)

    return SymbolsResponse(
        ok=True,
        source="social-link-coingecko-markets-v1",
        ts=ts,
        fiat=fiat.upper(),
        symbols=mapped,
        missing=missing,
    )
