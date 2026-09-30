import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        user: User | None = await self._session.get(User, user_id)
        return user

    async def get_by_email(self, email: str) -> User | None:
        user: User | None = await self._session.scalar(select(User).where(User.email == email))
        return user

    def add(self, user: User) -> None:
        self._session.add(user)
