import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import WorkspaceRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (a scheme name, not a secret)
    expires_in: int


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    created_at: datetime


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    role: WorkspaceRole
    created_at: datetime


class RegisterResponse(BaseModel):
    user: UserOut
    workspace: WorkspaceOut


class MeResponse(BaseModel):
    user: UserOut
    workspaces: list[WorkspaceOut]
