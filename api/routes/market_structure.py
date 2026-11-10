"""
routers/market_structure.py

Expone Market Structure bajo /internal/v1 (igual que attention/insights).
Monta en tu app:  app.include_router(router)
"""
from fastapi import APIRouter

from services.market_structure_service import get_market_structure

router = APIRouter(prefix="/internal/v1", tags=["market-structure"])

_WINDOWS = {"7d": 168, "14d": 336, "30d": 720, "90d": 2160}


@router.get("/market-structure")
async def market_structure(window: str = "30d") -> dict:
    hours = _WINDOWS.get(window, 720)
    return await get_market_structure(hours)
