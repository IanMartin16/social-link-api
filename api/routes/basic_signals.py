from fastapi import APIRouter, Query
from services.basic_signals_service import get_basic_signals
from models.basic_signals import SocialLinkBasicSignalsResponse
from datetime import datetime, timezone
from clients.coingecko_client import fetch_trending
from clients.alternative_client import fetch_fear_greed
from adapters.coingecko_adapter import map_trending_to_basic_signals
from adapters.alternative_adapter import map_fear_greed_to_backdrop

async def get_basic_signals(window: str = "1h", assets: list[str] | None = None, limit: int = 3):
    trending = await fetch_trending()

    result = map_trending_to_basic_signals(
        trending=trending,
        window=window,
        ts=datetime.now(timezone.utc).isoformat(),
        assets_filter=assets,
        limit=limit,
    )

    try:
        fng = await fetch_fear_greed()
        backdrop = map_fear_greed_to_backdrop(fng)
    except Exception:
        backdrop = None

    result["backdrop"] = backdrop
    return result


router = APIRouter()


@router.get("/v1/basic-signals", response_model=SocialLinkBasicSignalsResponse)
async def basic_signals(
    window: str = Query("1h"),
    assets: str | None = Query(None),
    limit: int = Query(3, ge=1, le=10),
):
    asset_list = [x.strip().upper() for x in assets.split(",")] if assets else None
    return await get_basic_signals(window=window, assets=asset_list, limit=limit)

