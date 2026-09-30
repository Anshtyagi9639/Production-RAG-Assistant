from fastapi import APIRouter

from app.api.routes import activity, auth, documents, health, search, workspaces

api_router = APIRouter()
for module in (health, auth, workspaces, documents, search, activity):
    api_router.include_router(module.router)
