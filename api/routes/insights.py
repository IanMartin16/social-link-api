"""
routers/insights.py

Expone el insight bajo /internal/v1/insights/... igual que attention va en
/internal/v1/attention. Monta en tu app:  app.include_router(router)
"""
from fastapi import APIRouter

from services.collapse_risk_service import get_collapse_risk

router = APIRouter(prefix="/internal/v1/insights", tags=["insights"])


@router.get("/collapse-risk")
async def collapse_risk() -> dict:
    return await get_collapse_risk()
