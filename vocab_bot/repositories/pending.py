from __future__ import annotations

from vocab_bot.db import Database
from vocab_bot.persistence import PendingTranslation


class PendingRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def add(self, pending: PendingTranslation) -> None:
        await self._db.insert_pending(pending)

    async def get(self, pending_id: str, user_id: int) -> PendingTranslation | None:
        return await self._db.get_pending(pending_id, user_id)

    async def delete(self, pending_id: str, user_id: int) -> None:
        await self._db.delete_pending(pending_id, user_id)
