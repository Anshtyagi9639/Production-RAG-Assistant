import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import CurrentUser, WorkspaceMembership, get_agent_service, rate_limited
from app.schemas.chat import AgentRunOut, AgentRunRequest
from app.services.agent import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])
AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


@router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limited("agent"))],
)
async def run_agent(
    request: AgentRunRequest,
    user: CurrentUser,
    membership: WorkspaceMembership,
    service: AgentServiceDep,
) -> AgentRunOut:
    """Queue a multi-step agent run over this workspace's documents. Poll
    `GET /api/agent/runs/{id}` for its step trace and answer."""
    return await service.start(user, membership.workspace.id, request.request)


@router.get("/runs/{run_id}")
async def get_agent_run(
    run_id: uuid.UUID, user: CurrentUser, membership: WorkspaceMembership, service: AgentServiceDep
) -> AgentRunOut:
    return await service.get(user, membership.workspace.id, run_id)
