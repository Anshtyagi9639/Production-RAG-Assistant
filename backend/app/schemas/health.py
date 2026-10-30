from typing import Literal

from pydantic import BaseModel

HealthError = Literal["timeout", "unreachable", "authentication_failed"]


class ComponentHealth(BaseModel):
    status: Literal["ok", "unavailable"]
    latency_ms: float
    error: HealthError | None = None


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, ComponentHealth]
