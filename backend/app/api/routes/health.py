from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_health_service
from app.core.errors import AppError
from app.schemas.health import HealthReport
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    responses={503: {"description": "One or more dependencies are unavailable"}},
)
async def health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthReport:
    """Report Postgres, Redis and Qdrant connectivity separately."""
    report = await service.check()
    if report.status != "ok":
        raise AppError(
            503,
            "service_unavailable",
            "One or more dependencies are unavailable.",
            details=report.model_dump(),
        )
    return report
