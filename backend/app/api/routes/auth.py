from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, MongoDep, SettingsDep
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
    request: RegisterRequest, mongo: MongoDep, settings: SettingsDep
) -> RegisterResponse:
    """Create an account, a default workspace and the owner membership (one transaction)."""
    return await AuthService(mongo, settings).register(request)


@router.post("/login")
async def login(request: LoginRequest, mongo: MongoDep, settings: SettingsDep) -> TokenResponse:
    return await AuthService(mongo, settings).login(request)


@router.get("/me")
async def me(user: CurrentUser, mongo: MongoDep, settings: SettingsDep) -> MeResponse:
    return await AuthService(mongo, settings).me(user)
