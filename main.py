from fastapi import FastAPI, Query, APIRouter
from datetime import datetime, timezone
from fastapi.middleware.cors import CORSMiddleware
from services.basic_signals_service import get_basic_signals
from services.symbols_service import get_symbols_360, get_symbols_top
from api.health import router as health_router
from api.routes.attention import router as attention_router
from detector.episodizer import run_episodizer
from detector.tracker import run_tracker
from db.session import get_session

from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from jobs.persistence_job import persist_snapshot

scheduler = AsyncIOScheduler()


# wrappers de los jobs del detector
async def capture_and_episodize():
    # 1) tu captura de siempre (escribe y commitea el batch de trending)
    await persist_snapshot()
    # 2) el episodizador, sobre el batch recién escrito. Aislado: si truena,
    #    NO tumba la persistencia (filosofía Lego).
    try:
        async with get_session() as s:
            summary = await run_episodizer(s)
            print(f"[episodizer] {summary}")
    except Exception as e:
        print(f"[episodizer] error: {e}")

async def tracker_job():
    try:
        async with get_session() as s:
            summary = await run_tracker(s)
            print(f"[tracker] {summary}")
    except Exception as e:
        print(f"[tracker] error: {e}")


@asynccontextmanager
async def lifespan(app):
    # --- startup ---
    # captura + episodizador encadenados (el episodizador ve el batch fresco)
    scheduler.add_job(
        capture_and_episodize,
        trigger=IntervalTrigger(minutes=10),
        id="persist_snapshot",          # reemplaza el job anterior
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    # tracker: seguimiento post-trending, más seguido
    scheduler.add_job(
        tracker_job,
        trigger=IntervalTrigger(minutes=3),
        id="detector_tracker",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )
    scheduler.start()
    print("[scheduler] persist+episodizer every 10 min, tracker every 3 min")

    yield

    # --- shutdown ---
    scheduler.shutdown(wait=False)
    print("[scheduler] stopped")


app = FastAPI(title="social-link", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(attention_router)

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
