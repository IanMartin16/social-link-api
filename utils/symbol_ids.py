# utils/symbol_ids.py

COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "BNB": "binancecoin",
    "DOGE": "dogecoin",
    "POL": "polygon-ecosystem-token",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "DOT": "polkadot",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "LTC": "litecoin",
    "USDT": "tether",
    "USDC": "usd-coin",
    "SHIB": "shiba-inu",
    "DAI": "dai",
    "BCH": "bitcoin-cash",
    "XLM": "stellar",
    "NEAR": "near",
    "VET": "vechain",
    "TRX": "tron",
    "ATOM": "cosmos",
    "SUI": "sui",
    "ARB": "arbitrum",
    "FTM": "fantom",
    "OP": "optimism",
    "TON": "the-open-network",
    "HYPE": "hyperliquid",
    "OKB": "okb",
    "PYUSD": "paypal-usd",
    "PI": "pi-network",
    "LEO": "leo-token",
    "XMR": "monero",
    "USDE": "ethena-usde",
    "CC": "canton-network",
    "WLFI": "world-liberty-financial",
    "HBAR": "hedera-hashgraph",
    "MNT": "mantle",
    "PAXG": "pax-gold",
    "PEPE": "pepe",
    "FLOKI": "floki",
    "AAVE": "aave",
    "MKR": "maker",
    "CRO": "crypto-com-chain",
    "TAO": "bittensor",
    "USDG": "global-dollar",
    "INJ": "injective-protocol",
    "SKY": "sky",
    "ICP": "internet-computer",
    "APT": "aptos",
    "ALGO": "algorand",
    "XTZ": "tezos",
    "EGLD": "elrond-erd-2",
    "FET": "fetch-ai",
    "RENDER": "render-token",
    "ETHFI": "ether-fi",
    "GRT": "the-graph",
    "JUP": "jupiter-exchange-solana",
    "PYTH": "pyth-network",
}


def resolve_ids(symbols: list[str]) -> tuple[dict[str, str], list[str]]:
    """Mapea símbolos del portal a coingecko_ids.

    Devuelve:
      - resolved: { "BTC": "bitcoin", ... } solo de los que tienen id
      - missing:  ["XYZ", ...] los que no están en el dict (sin datos posibles)
    """
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for raw in symbols:
        sym = (raw or "").strip().upper()
        if not sym:
            continue
        cg_id = COINGECKO_IDS.get(sym)
        if cg_id:
            resolved[sym] = cg_id
        else:
            missing.append(sym)

    return resolved, missing
