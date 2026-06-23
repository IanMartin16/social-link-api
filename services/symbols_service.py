# services/symbols_service.py

import logging
from datetime import datetime, timezone

from clients.coingecko_client import fetch_markets
from adapters.coingecko_adapter import map_markets_to_symbols
from utils.symbol_ids import resolve_ids
from utils.symbol_policy import FALLBACK_ASSETS
from models.symbols import SymbolsResponse, SymbolMarket

logger = logging.getLogger("social-link.symbols")


async def get_symbols_360(
    symbols: list[str] | None = None,
    fiat: str = "USD",
) -> SymbolsResponse:
    """Ficha de mercado rica (CoinGecko) para los símbolos seleccionados.

    - symbols: los seleccionados por el usuario (del front). Si vacío -> fallback.
    - Resuelve symbol -> coingecko_id (dict espejo de cryptolink_symbols).
    - Una sola llamada a /coins/markets con ids=.
    - Robusto: símbolos sin id o sin datos en CoinGecko van a `missing`.

    Observabilidad: las dos rutas de degradación (sin ids resueltos / fallo de
    CoinGecko) ahora LOGUEAN antes de degradar. Antes devolvían 200 vacío en
    silencio, lo que ocultaba la causa real (timeout, 429, parsing, etc.).
    """
    requested = symbols if symbols else list(FALLBACK_ASSETS)

    # 1) resolver ids (los que no tienen id ya son "missing")
    resolved, missing = resolve_ids(requested)

    ts = datetime.now(timezone.utc).isoformat()

    if not resolved:
        # nada que pedir: devolvemos vacío honesto, no rompemos
        # LOG: si esto pasa con símbolos comunes (BTC/ETH), el resolver tiene un
        # problema (symbol_ids desincronizado, símbolo nuevo no mapeado, etc.)
        logger.warning(
            "symbols_360: no resolved ids for requested=%s (missing=%s). "
            "Returning empty. Check symbol_ids resolver.",
            requested,
            missing,
        )
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
    except Exception as e:
        # si CoinGecko falla, devolvemos vacío + todos como missing (degradación)
        # LOG: este era el punto ciego. Cualquier fallo (timeout, 429, red,
        # parsing) caía aquí y devolvía 200 vacío SIN rastro. Ahora se registra
        # el error real con stack trace para diagnóstico en Railway logs.
        logger.error(
            "symbols_360: fetch_markets FAILED for ids=%s vs=%s -> %r. "
            "Degrading to empty + all missing.",
            list(resolved.values()),
            vs,
            e,
            exc_info=True,
        )
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

    # LOG suave: si hubo símbolos resueltos que CoinGecko no devolvió, dejar rastro
    if missing:
        logger.info(
            "symbols_360: ok with partial missing=%s (returned=%d)",
            missing,
            len(mapped),
        )

    return SymbolsResponse(
        ok=True,
        source="social-link-coingecko-markets-v1",
        ts=ts,
        fiat=fiat.upper(),
        symbols=mapped,
        missing=missing,
    )
