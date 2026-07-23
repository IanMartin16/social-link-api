from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from core.runtime import get_uptime_seconds
from models.health import (
    HealthCheck,
    HealthResponse,
    LiveResponse,
    ReadyResponse,
    ServiceInfo,
)
from services.health_service import HealthService


router = APIRouter(tags=["Health"])


@router.get(
    "/api/health",
    response_model=HealthResponse,
)
async def health() -> HealthResponse:
    dependencies = HealthService.dependency_checks()

    checks = [
        HealthCheck(
            name="application",
            status=dependencies["checks"]["application"]["status"],
            details=dependencies["checks"]["application"]["error"],
        ),
        HealthCheck(
            name="runtime",
            status=dependencies["checks"]["runtime"]["status"],
            details=dependencies["checks"]["runtime"]["error"],
        ),
    ]

    return HealthResponse(
        contract_version="health.v1",
        service=ServiceInfo(
            id="social-link",
            name="Social_Link",
            version="0.1.0",
            environment="development",
            stack="fastapi",
        ),
        status=dependencies["status"],
        readiness=(
            "ready"
            if dependencies["status"] == "operational"
            else "degraded"
        ),
        uptime_seconds=get_uptime_seconds(),
        checks=checks,
    )


@router.get(
    "/api/health/live",
    response_model=LiveResponse,
)
async def live() -> LiveResponse:
    return LiveResponse(status="alive")


@router.get(
    "/api/health/ready",
    response_model=ReadyResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadyResponse,
        }
    },
)
async def ready():
    if not HealthService.is_ready():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ReadyResponse(
                status="not_ready",
            ).model_dump(),
        )

    return ReadyResponse(status="ready")


@router.get("/health")
async def legacy_health():
    return {"ok": True}