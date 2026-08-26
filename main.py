from fastapi import FastAPI, Query
from datetime import datetime, timezone
from fastapi.middleware.cors import CORSMiddleware
from services.basic_signals_service import get_basic_signals
from services.symbols_service import get_symbols_360, get_symbols_top
from api.health import router as health_router

app = FastAPI(title="social-link", version="0.1.0")
app.include_router(health_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://cryptolink.mx",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

    
@app.get("/internal/v1/basic-signals")
async def basic_signals(
    window: str = Query(default="1h"),
    assets: str | None = Query(default=None),
    limit: int = Query(default=20),
):
    asset_list = [s.strip().upper() for s in assets.split(",")] if assets else None
    result = await get_basic_signals(window=window, assets=asset_list, limit=limit)
    return result

@app.get("/internal/v1/symbols")
async def symbols(
    symbols: str | None = Query(default=None),
    fiat: str = Query(default="USD"),
    top: int | None = Query(default=None),   # nuevo
):
    if top:
        return await get_symbols_top(fiat=fiat, top=top)

    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else None
    )
    result = await get_symbols_360(symbols=symbol_list, fiat=fiat)
    return result
