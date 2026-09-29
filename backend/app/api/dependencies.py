from fastapi import Request

from app.services.health import HealthService, postgres_check, qdrant_check, redis_check


def get_health_service(request: Request) -> HealthService:
    state = request.app.state
    return HealthService(
        {
            "postgres": postgres_check(state.engine),
            "redis": redis_check(state.redis),
            "qdrant": qdrant_check(state.qdrant),
        },
        timeout_seconds=state.settings.health_check_timeout_seconds,
    )
