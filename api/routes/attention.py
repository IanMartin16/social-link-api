from fastapi import APIRouter, Query
from services.attention_service import get_attention

router = APIRouter()

@router.get("/internal/v1/attention")
async def attention(limit: int = Query(15, ge=1, le=30)):
    return await get_attention(limit=limit)