from typing import Literal

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: Literal["ok", "unavailable"]
    latency_ms: float
    error: Literal["timeout", "unreachable"] | None = None


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, ComponentHealth]
