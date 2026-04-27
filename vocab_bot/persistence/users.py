from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from vocab_bot.persistence.models import UserRecord
from vocab_bot.persistence.types import BotUser
from vocab_bot.persistence.utils import to_user, utc_now


class UserStore:
    async def upsert_user_seen(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
    ) -> BotUser:
        return await asyncio.to_thread(
            self._upsert_user_seen_sync,
            telegram_id,
            username,
            first_name,
            last_name,
            language_code,
        )

    def _upsert_user_seen_sync(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
    ) -> BotUser:
        now = utc_now()
        with self._session_factory() as session:
            stmt = sqlite_insert(UserRecord).values(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                is_allowed=True,
                created_at=now,
                updated_at=now,
                last_seen_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["telegram_id"],
                set_={
                    "username": stmt.excluded.username,
                    "first_name": stmt.excluded.first_name,
                    "last_name": stmt.excluded.last_name,
                    "language_code": stmt.excluded.language_code,
                    "updated_at": now,
                    "last_seen_at": now,
                },
            )
            session.execute(stmt)
            record = session.scalar(select(UserRecord).where(UserRecord.telegram_id == telegram_id))
            session.commit()
            if record is None:
                msg = "failed to read user after upsert"
                raise RuntimeError(msg)
            return to_user(record)

    async def get_user(self, telegram_id: int) -> BotUser | None:
        return await asyncio.to_thread(self._get_user_sync, telegram_id)

    def _get_user_sync(self, telegram_id: int) -> BotUser | None:
        with self._session_factory() as session:
            record = session.scalar(select(UserRecord).where(UserRecord.telegram_id == telegram_id))
            return to_user(record) if record is not None else None

    async def set_user_allowed(self, telegram_id: int, allowed: bool) -> BotUser:
        return await asyncio.to_thread(self._set_user_allowed_sync, telegram_id, allowed)

    def _set_user_allowed_sync(self, telegram_id: int, allowed: bool) -> BotUser:
        now = utc_now()
        with self._session_factory() as session:
            record = session.scalar(select(UserRecord).where(UserRecord.telegram_id == telegram_id))
            if record is None:
                record = UserRecord(
                    telegram_id=telegram_id,
                    is_allowed=allowed,
                    created_at=now,
                    updated_at=now,
                    last_seen_at=now,
                )
                session.add(record)
            else:
                record.is_allowed = allowed
                record.updated_at = now
            session.commit()
            return to_user(record)

    async def set_user_timezone(self, telegram_id: int, timezone: str) -> BotUser:
        return await asyncio.to_thread(self._set_user_timezone_sync, telegram_id, timezone)

    def _set_user_timezone_sync(self, telegram_id: int, timezone: str) -> BotUser:
        now = utc_now()
        with self._session_factory() as session:
            record = session.scalar(select(UserRecord).where(UserRecord.telegram_id == telegram_id))
            if record is None:
                record = UserRecord(
                    telegram_id=telegram_id,
                    timezone=timezone,
                    is_allowed=True,
                    created_at=now,
                    updated_at=now,
                    last_seen_at=now,
                )
                session.add(record)
            else:
                record.timezone = timezone
                record.updated_at = now
            session.commit()
            return to_user(record)

    async def set_user_languages(self, telegram_id: int, source_lang: str, target_lang: str) -> BotUser:
        return await asyncio.to_thread(self._set_user_languages_sync, telegram_id, source_lang, target_lang)

    def _set_user_languages_sync(self, telegram_id: int, source_lang: str, target_lang: str) -> BotUser:
        now = utc_now()
        with self._session_factory() as session:
            record = session.scalar(select(UserRecord).where(UserRecord.telegram_id == telegram_id))
            if record is None:
                record = UserRecord(
                    telegram_id=telegram_id,
                    preferred_source_lang=source_lang,
                    preferred_target_lang=target_lang,
                    is_allowed=True,
                    created_at=now,
                    updated_at=now,
                    last_seen_at=now,
                )
                session.add(record)
            else:
                record.preferred_source_lang = source_lang
                record.preferred_target_lang = target_lang
                record.updated_at = now
            session.commit()
            return to_user(record)

    async def list_users(self, limit: int = 50) -> list[BotUser]:
        return await asyncio.to_thread(self._list_users_sync, limit)

    def _list_users_sync(self, limit: int) -> list[BotUser]:
        with self._session_factory() as session:
            rows = session.scalars(select(UserRecord).order_by(UserRecord.last_seen_at.desc()).limit(limit)).all()
            return [to_user(record) for record in rows]
