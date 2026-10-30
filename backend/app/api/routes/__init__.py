from fastapi import APIRouter

from app.api.routes import activity, agent, auth, chat, documents, health, search, workspaces

api_router = APIRouter()
for module in (health, auth, workspaces, documents, search, chat, agent, activity):
    api_router.include_router(module.router)
