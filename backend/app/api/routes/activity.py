from fastapi import APIRouter

from app.api.dependencies import PageParamsDep, SessionDep, WorkspaceMembership
from app.core.pagination import Page
from app.schemas.activity import ActivityOut, StatsOut
from app.services.activity import ActivityService

router = APIRouter(tags=["activity"])


@router.get("/activity")
async def list_activity(
    membership: WorkspaceMembership, session: SessionDep, params: PageParamsDep
) -> Page[ActivityOut]:
    return await ActivityService(session).list(membership.workspace.id, params)


@router.get("/stats")
async def stats(membership: WorkspaceMembership, session: SessionDep) -> StatsOut:
    """Dashboard numbers, computed from the database on each request."""
    return await ActivityService(session).stats(membership.workspace.id)
