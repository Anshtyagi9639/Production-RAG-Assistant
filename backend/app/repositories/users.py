import uuid
from collections.abc import Iterable

from app.db.mongo import Database, Session
from app.models import User


class UserRepository:
    def __init__(self, db: Database) -> None:
        self._users = db["users"]

    async def get(self, user_id: uuid.UUID) -> User | None:
        document = await self._users.find_one({"_id": user_id})
        return User.from_document(document) if document else None

    async def get_by_email(self, email: str, session: Session | None = None) -> User | None:
        document = await self._users.find_one({"email": email}, session=session)
        return User.from_document(document) if document else None

    async def insert(self, user: User, session: Session | None = None) -> None:
        await self._users.insert_one(user.to_document(), session=session)

    async def names(self, user_ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, str]:
        """Full names for a set of ids, in one query (the replacement for a JOIN on users)."""
        ids = {user_id for user_id in user_ids if user_id is not None}
        if not ids:
            return {}
        cursor = self._users.find({"_id": {"$in": list(ids)}}, {"full_name": 1})
        return {document["_id"]: document["full_name"] async for document in cursor}
