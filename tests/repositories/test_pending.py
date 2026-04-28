from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vocab_bot.persistence import PendingTranslation
from vocab_bot.repositories.pending import PendingRepository


@pytest.mark.asyncio
async def test_pending_repository_crud_calls_db() -> None:
    db = AsyncMock()
    repo = PendingRepository(db)
    pending = PendingTranslation(
        id="p1",
        user_id=1,
        source_lang="EN",
        target_lang="RU",
        source_text="hello",
        target_text="privet",
        target_options=("privet",),
    )

    await repo.add(pending)
    await repo.get("p1", 1)
    await repo.delete("p1", 1)

    db.insert_pending.assert_awaited_once_with(pending)
    db.get_pending.assert_awaited_once_with("p1", 1)
    db.delete_pending.assert_awaited_once_with("p1", 1)
