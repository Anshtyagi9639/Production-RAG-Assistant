from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import WorkspaceMembership, get_search_service
from app.schemas.documents import SearchRequest, SearchResponse
from app.services.search import SearchService

router = APIRouter(tags=["search"])


@router.post("/search")
async def search(
    request: SearchRequest,
    membership: WorkspaceMembership,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    """Semantic search over the current workspace's indexed passages."""
    return await service.search(membership.workspace.id, request)
