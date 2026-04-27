from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from vocab_bot.persistence import BotUser
from vocab_bot.repositories import UserRepository


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def record_seen(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
    ) -> BotUser:
        return await self._user_repo.record_seen(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )

    async def is_allowed(self, telegram_id: int) -> bool:
        user = await self._user_repo.get(telegram_id)
        return False if user is None else user.is_allowed

    async def set_allowed(self, telegram_id: int, allowed: bool) -> BotUser:
        return await self._user_repo.set_allowed(telegram_id, allowed)

    async def set_timezone(self, telegram_id: int, timezone: str) -> BotUser:
        normalized = timezone.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            msg = f"Unknown timezone: {timezone}"
            raise ValueError(msg) from exc
        return await self._user_repo.set_timezone(telegram_id, normalized)

    async def set_languages(self, telegram_id: int, source_lang: str, target_lang: str) -> BotUser:
        return await self._user_repo.set_languages(telegram_id, source_lang, target_lang)

    async def list_recent(self, limit: int = 50) -> list[BotUser]:
        return await self._user_repo.list_recent(limit)
