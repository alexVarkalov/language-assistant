from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from vocab_bot.persistence import DEFAULT_REMINDERS_PER_DAY, BotUser
from vocab_bot.repositories import CardRepository, UserRepository
from vocab_bot.services.users import user_has_access, user_zone

# Local-time hours (in the user's timezone) at which a reminder may go out, per reminders-per-day option.
_REMINDER_HOURS: Mapping[int, tuple[int, ...]] = {
    1: (9,),
    2: (9, 19),
    3: (9, 14, 19),
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class DueSummary:
    user: BotUser
    due_count: int


def reminder_hours(reminders_per_day: int) -> tuple[int, ...]:
    """The daily reminder slots (local hours) for a reminders-per-day option; unknown values use the default."""
    return _REMINDER_HOURS.get(reminders_per_day, _REMINDER_HOURS[DEFAULT_REMINDERS_PER_DAY])


def latest_slot_passed(user: BotUser, *, now: datetime) -> datetime | None:
    """The most recent of today's reminder slots (user's local day) that is not in the future, if any."""
    local_now = now.astimezone(user_zone(user))
    slots = [
        local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
        for hour in reminder_hours(user.reminders_per_day)
    ]
    passed = [slot for slot in slots if slot <= local_now]
    return max(passed) if passed else None


def should_notify(user: BotUser, *, now: datetime) -> bool:
    """A user is reminded once per slot: when a slot has passed today and no reminder went out since it."""
    slot = latest_slot_passed(user, now=now)
    if slot is None:
        return False
    return user.due_notified_at is None or user.due_notified_at < slot


class DueNotificationService:
    """Decides who gets the consolidated "N cards due" reminder on each poll.

    Each user picks 1, 2 or 3 reminders a day; those map to fixed local-time slots (see `_REMINDER_HOURS`).
    A reminder goes out at the first poll after a slot, only if the user has due cards and has not been
    reminded since that slot, so the queue filling up between slots waits for the next one.
    """

    def __init__(
        self,
        card_repo: CardRepository,
        user_repo: UserRepository,
        *,
        admin_user_ids: frozenset[int],
    ) -> None:
        self._card_repo = card_repo
        self._user_repo = user_repo
        self._admin_user_ids = admin_user_ids

    async def collect(self, *, now: datetime | None = None) -> list[DueSummary]:
        now = now or _now()
        counts = await self._card_repo.count_due_by_user()
        summaries: list[DueSummary] = []
        for user_id, due_count in counts.items():
            if due_count <= 0:
                continue
            user = await self._user_repo.get(user_id)
            if user is None or not user_has_access(user, self._admin_user_ids):
                continue
            if not should_notify(user, now=now):
                continue
            summaries.append(DueSummary(user=user, due_count=due_count))
        return summaries

    async def mark_notified(self, user_id: int, *, now: datetime | None = None) -> None:
        await self._user_repo.set_due_notified_at(user_id, now or _now())
