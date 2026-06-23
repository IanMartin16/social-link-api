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
        result.backdrop = map_fear_greed_to_backdrop(fng)
    except Exception:
        result.backdrop = None

    return result