from models.symbols import SymbolMarket
from models.basic_signals import (
    SocialAttentionItem,
    BasicSignalsMarket,
    SocialLinkBasicSignalsResponse,
)
from utils.symbol_policy import (
    ALLOWED_SOCIAL_ASSETS,
    FALLBACK_ASSETS,
    NARRATIVE_TAGS,
)


def normalize_symbol(symbol: str | None) -> str:
    return (symbol or "").strip().upper()


def attention_score_from_rank(rank: int | None, index: int = 0) -> float:
    safe_rank = rank if isinstance(rank, int) and rank > 0 else 9999

    if safe_rank <= 2:
        rank_component = 92
    elif safe_rank <= 5:
        rank_component = 84
    elif safe_rank <= 10:
        rank_component = 74
    elif safe_rank <= 25:
        rank_component = 60
    elif safe_rank <= 50:
        rank_component = 48
    else:
        rank_component = 34

    position_penalty = index * 10
    return max(18, min(100, rank_component - position_penalty))


def attention_delta_from_price_change(change, index: int = 0) -> float:
    if isinstance(change, (int, float)):
        return round(float(change), 2)

    fallback = 8 - index * 1.5
    return round(max(1, fallback), 2)


def direction_from_delta(delta: float) -> str:
    if delta > 0.1:
        return "up"
    if delta < -0.1:
        return "down"
    return "flat"


def infer_tags(symbol: str, name: str | None = None) -> list[str]:
    s = symbol.upper()
    n = (name or "").lower()
    tags: list[str] = []

    if s in {"BTC", "ETH"}:
        tags.append("majors-led")
    if s in {"SOL", "ADA", "AVAX", "ATOM", "NEAR"}:
        tags.append("layer1")
    if s in {"DOGE", "SHIB", "PEPE", "FLOKI"}:
        tags.append("meme")
    if s in {"LINK", "UNI", "AAVE", "MKR"}:
        tags.append("defi")
    if "bitcoin" in n:
        tags.append("store-of-value")
    if "ethereum" in n:
        tags.append("smart-contracts")

    return list(dict.fromkeys(tags))


def derive_coverage(top_assets: list[str], tags: list[str]) -> str:
    if len(top_assets) >= 4 and len(tags) >= 4:
        return "broad"
    if len(top_assets) >= 2 and len(tags) >= 2:
        return "moderate"
    return "low"


def ensure_minimum_leaders(leaders: list[SocialAttentionItem]) -> list[SocialAttentionItem]:
    existing = {x.asset for x in leaders}
    fillers: list[SocialAttentionItem] = []

    for index, asset in enumerate(FALLBACK_ASSETS):
        if asset in existing:
            continue
        fillers.append(
            SocialAttentionItem(
                asset=asset,
                attentionScore=45 - index * 5,
                attentionDeltaPct=0,
                direction="flat",
                tags=infer_tags(asset, asset),
            )
        )

    return (leaders + fillers)[:10]


def map_trending_to_basic_signals(trending: dict, window: str = "1h", ts: str = "", assets_filter: list[str] | None = None, limit: int = 3):
    raw_coins = trending.get("coins", [])

    leaders: list[SocialAttentionItem] = []
    allowed = set(assets_filter) if assets_filter else ALLOWED_SOCIAL_ASSETS

    for index, entry in enumerate(raw_coins):
        item = entry.get("item", {})
        asset = normalize_symbol(item.get("symbol"))
        if not asset or asset not in allowed:
            continue

        change = (((item.get("data") or {}).get("price_change_percentage_24h") or {}).get("usd"))
        delta = attention_delta_from_price_change(change, index)

        leaders.append(
            SocialAttentionItem(
                asset=asset,
                attentionScore=attention_score_from_rank(item.get("market_cap_rank"), index),
                attentionDeltaPct=delta,
                direction=direction_from_delta(delta),
                tags=infer_tags(asset, item.get("name")),
            )
        )

    leaders = ensure_minimum_leaders(leaders)[: max(limit, 3)]
    top_assets = [x.asset for x in leaders[:10]]

    raw_tags = []
    for leader in leaders:
        raw_tags.extend(leader.tags)

    raw_tags = list(dict.fromkeys(raw_tags))
    narrative_tags = [tag for tag in raw_tags if tag in NARRATIVE_TAGS]
    tags = narrative_tags[:4] if narrative_tags else raw_tags[:4]

    coverage = derive_coverage(top_assets, tags)

    return SocialLinkBasicSignalsResponse(
        ok=True,
        source="social-link-coingecko-v1",
        ts=ts,
        window=window,
        market=BasicSignalsMarket(
            topAssets=top_assets,
            attentionLeaders=leaders,
            attentionLosers=[],
            tags=tags,
            coverage=coverage,
        ),
    )


def _f(v) -> float | None:
    """float seguro: None si no es numérico."""
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _i(v) -> int | None:
    if isinstance(v, int):
        return v
    return None


def map_markets_to_symbols(markets: list[dict]) -> list[SymbolMarket]:
    """Reduce la respuesta cruda de /coins/markets a los campos de oro.

    Descarta: roi, atl*, market_cap_change*, last_updated, fully_diluted_valuation.
    Mapea por símbolo (uppercase) para que calce con el portal.
    """
    out: list[SymbolMarket] = []

    for m in markets or []:
        sym = (m.get("symbol") or "").strip().upper()
        if not sym:
            continue

        out.append(
            SymbolMarket(
                symbol=sym,
                name=m.get("name"),
                image=m.get("image"),
                rank=_i(m.get("market_cap_rank")),
                price=_f(m.get("current_price")),
                change24h=_f(m.get("price_change_percentage_24h")),
                high24h=_f(m.get("high_24h")),
                low24h=_f(m.get("low_24h")),
                marketCap=_f(m.get("market_cap")),
                volume24h=_f(m.get("total_volume")),
                circulatingSupply=_f(m.get("circulating_supply")),
                totalSupply=_f(m.get("total_supply")),
                maxSupply=_f(m.get("max_supply")),
                ath=_f(m.get("ath")),
                athChangePct=_f(m.get("ath_change_percentage")),
                athDate=m.get("ath_date"),
            )
        )

    return out
