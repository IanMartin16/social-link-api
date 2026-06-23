from fastapi import FastAPI, Query
from datetime import datetime, timezone
from fastapi.middleware.cors import CORSMiddleware
from services.basic_signals_service import get_basic_signals
from services.symbols_service import get_symbols_360

app = FastAPI(title="social-link", version="0.1.0")

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

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/internal/v1/trends")
def trends(symbols: str = Query(default="BTC,ETH")):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    now = datetime.now(timezone.utc).isoformat()
    data = [{"symbol": s, "trend": "up", "score": 0.72, "reason": "mvp: placeholder"} for s in syms]
    return {"ts": now, "data": data}
    
@app.get("/internal/v1/basic-signals")
async def basic_signals(
    window: str = Query(default="1h"),
    assets: str | None = Query(default=None),
    limit: int = Query(default=10),
):
    asset_list = [s.strip().upper() for s in assets.split(",")] if assets else None
    result = await get_basic_signals(window=window, assets=asset_list, limit=limit)
    return result

@app.get("/internal/v1/symbols")
async def symbols(
    symbols: str | None = Query(default=None),
    fiat: str = Query(default="USD"),
):
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else None
    )
    result = await get_symbols_360(symbols=symbol_list, fiat=fiat)
    return result
