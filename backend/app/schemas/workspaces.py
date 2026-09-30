import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import WorkspaceRole


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.MEMBER


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: WorkspaceRole
