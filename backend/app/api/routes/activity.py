from fastapi import APIRouter

from app.api.dependencies import MongoDep, PageParamsDep, WorkspaceMembership
from app.core.pagination import Page
from app.schemas.activity import ActivityOut, StatsOut
from app.services.activity import ActivityService

router = APIRouter(tags=["activity"])


@router.get("/activity")
async def list_activity(
    membership: WorkspaceMembership, mongo: MongoDep, params: PageParamsDep
) -> Page[ActivityOut]:
    return await ActivityService(mongo.db).list(membership.workspace.id, params)


@router.get("/stats")
async def stats(membership: WorkspaceMembership, mongo: MongoDep) -> StatsOut:
    """Dashboard numbers, computed from the database on each request."""
    return await ActivityService(mongo.db).stats(membership.workspace.id)
