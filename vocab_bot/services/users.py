from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from vocab_bot.i18n import normalize_locale
from vocab_bot.persistence import REMINDER_OPTIONS, BotUser
from vocab_bot.repositories import UserRepository


def user_has_access(user: BotUser, admin_user_ids: frozenset[int]) -> bool:
    return user.is_allowed or user.telegram_id in admin_user_ids


def user_zone(user: BotUser) -> ZoneInfo:
    """The user's IANA timezone, falling back to UTC when unset or no longer recognised."""
    if user.timezone is None:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(user.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


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

    async def get_user(self, telegram_id: int) -> BotUser | None:
        return await self._user_repo.get(telegram_id)

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

    async def set_locale(self, telegram_id: int, locale: str) -> BotUser:
        normalized = normalize_locale(locale)
        return await self._user_repo.set_locale(telegram_id, normalized)

    async def set_reminders_per_day(self, telegram_id: int, reminders_per_day: int) -> BotUser:
        if reminders_per_day not in REMINDER_OPTIONS:
            msg = f"reminders_per_day must be one of {REMINDER_OPTIONS}, got {reminders_per_day}"
            raise ValueError(msg)
        return await self._user_repo.set_reminders_per_day(telegram_id, reminders_per_day)

    async def list_recent(self, limit: int = 50) -> list[BotUser]:
        return await self._user_repo.list_recent(limit)
