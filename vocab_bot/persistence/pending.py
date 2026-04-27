from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from vocab_bot.persistence.models import PendingRecord
from vocab_bot.persistence.types import PendingTranslation
from vocab_bot.persistence.utils import utc_now


class PendingStore:
    async def insert_pending(self, pending: PendingTranslation) -> None:
        await asyncio.to_thread(self._insert_pending_sync, pending)

    def _insert_pending_sync(self, pending: PendingTranslation) -> None:
        with self._session_factory() as session:
            session.add(
                PendingRecord(
                    id=pending.id,
                    user_id=pending.user_id,
                    source_lang=pending.source_lang,
                    target_lang=pending.target_lang,
                    source_text=pending.source_text,
                    target_text=pending.target_text,
                    target_options=json.dumps(list(pending.target_options), ensure_ascii=False),
                    created_at=utc_now(),
                )
            )
            session.commit()

    async def get_pending(self, pending_id: str, user_id: int) -> PendingTranslation | None:
        return await asyncio.to_thread(self._get_pending_sync, pending_id, user_id)

    def _get_pending_sync(self, pending_id: str, user_id: int) -> PendingTranslation | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(PendingRecord).where(PendingRecord.id == pending_id, PendingRecord.user_id == user_id)
            )
            if record is None:
                return None
            return PendingTranslation(
                id=record.id,
                user_id=record.user_id,
                source_lang=record.source_lang,
                target_lang=record.target_lang,
                source_text=record.source_text,
                target_text=record.target_text,
                target_options=_load_options(record.target_options, record.target_text),
            )

    async def delete_pending(self, pending_id: str, user_id: int) -> None:
        await asyncio.to_thread(self._delete_pending_sync, pending_id, user_id)

    def _delete_pending_sync(self, pending_id: str, user_id: int) -> None:
        with self._session_factory() as session:
            record = session.scalar(
                select(PendingRecord).where(PendingRecord.id == pending_id, PendingRecord.user_id == user_id)
            )
            if record is not None:
                session.delete(record)
            session.commit()


def _load_options(raw: str, fallback: str) -> tuple[str, ...]:
    if not raw.strip():
        return (fallback,)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return (fallback,)
    if not isinstance(parsed, list):
        return (fallback,)

    options: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        options.append(value)
    if not options:
        return (fallback,)
    return tuple(options)
