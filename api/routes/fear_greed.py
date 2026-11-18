# routers/fear_greed.py  →  app.include_router(router)
from fastapi import APIRouter
from services.fear_greed_service import get_fear_greed

router = APIRouter(prefix="/internal/v1", tags=["fear-greed"])

@router.get("/fear-greed")
async def fear_greed(window: str = "all") -> dict:
    return await get_fear_greed(window)