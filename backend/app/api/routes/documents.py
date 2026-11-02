import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.api.dependencies import (
    CurrentUser,
    OwnerMembership,
    PageParamsDep,
    SettingsDep,
    WorkspaceMembership,
    get_document_service,
)
from app.core.errors import AppError
from app.core.pagination import Page
from app.models.enums import DocumentStatus
from app.schemas.documents import (
    CompleteUploadRequest,
    DirectUploadOut,
    DirectUploadRequest,
    DocumentOut,
)
from app.services.documents import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
# Multipart framing (boundaries, headers) on top of the file itself.
_MULTIPART_OVERHEAD_BYTES = 64 * 1024


def reject_oversized_body(request: Request, settings: SettingsDep) -> None:
    """Refuse clearly oversized uploads from Content-Length before the body is parsed."""
    length = request.headers.get("content-length")
    limit = settings.max_upload_bytes + _MULTIPART_OVERHEAD_BYTES
    if length and length.isdigit() and int(length) > limit:
        raise AppError(
            413, "file_too_large", f"The file is larger than the {settings.max_upload_mb} MB limit."
        )


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(reject_oversized_body)],
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    user: CurrentUser,
    membership: OwnerMembership,
    service: DocumentServiceDep,
    settings: SettingsDep,
) -> DocumentOut:
    """Owner only. Stores the file and queues processing; the response is the UPLOADED document."""
    data = await file.read(settings.max_upload_bytes + 1)
    return await service.upload(user, membership.workspace.id, file.filename, data)


@router.post("/upload/direct")
async def create_direct_upload(
    request: DirectUploadRequest,
    user: CurrentUser,
    membership: OwnerMembership,
    service: DocumentServiceDep,
) -> DirectUploadOut:
    """Owner only. A short-lived URL to upload the file straight to the bucket, so large files
    never pass through the API. 409 `direct_upload_unavailable` when storage is a local
    directory: use /documents/upload instead."""
    return await service.create_direct_upload(
        user, membership.workspace.id, request.filename, request.size_bytes
    )


@router.post("/upload/complete", status_code=status.HTTP_202_ACCEPTED)
async def complete_direct_upload(
    request: CompleteUploadRequest,
    user: CurrentUser,
    membership: OwnerMembership,
    service: DocumentServiceDep,
) -> DocumentOut:
    """Owner only. Checks the uploaded file, records it as UPLOADED and queues processing."""
    return await service.complete_direct_upload(user, membership.workspace.id, request.upload_token)


@router.get("")
async def list_documents(
    membership: WorkspaceMembership,
    service: DocumentServiceDep,
    params: PageParamsDep,
    sort: Annotated[str, Query(description="Field, prefixed with - for descending")] = (
        "-created_at"
    ),
    document_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
) -> Page[DocumentOut]:
    return await service.list(membership.workspace.id, params, sort, document_status)


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID, membership: WorkspaceMembership, service: DocumentServiceDep
) -> DocumentOut:
    return await service.get(membership.workspace.id, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    membership: OwnerMembership,
    service: DocumentServiceDep,
) -> Response:
    """Owner only. Removes the Qdrant points, the row (and its chunks), then the stored file."""
    await service.delete(user, membership.workspace.id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
