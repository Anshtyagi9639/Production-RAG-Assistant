from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, SessionDep, SettingsDep
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest, session: SessionDep, settings: SettingsDep
) -> RegisterResponse:
    """Create an account, a default workspace and the owner membership (one transaction)."""
    return await AuthService(session, settings).register(request)


@router.post("/login")
async def login(request: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    return await AuthService(session, settings).login(request)


@router.get("/me")
async def me(user: CurrentUser, session: SessionDep, settings: SettingsDep) -> MeResponse:
    return await AuthService(session, settings).me(user)
