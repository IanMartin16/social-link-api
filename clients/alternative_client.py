import httpx

ALTERNATIVE_FNG_URL = "https://api.alternative.me/fng/"

async def fetch_fear_greed():
    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.get(
            ALTERNATIVE_FNG_URL,
            params={"limit": 1},
            headers={"accept": "application/json"},
        )
        res.raise_for_status()
        return res.json()