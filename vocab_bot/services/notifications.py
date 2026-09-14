from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from vocab_bot.persistence import BotUser
from vocab_bot.repositories import CardRepository, UserRepository
from vocab_bot.services.users import user_has_access


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class DueSummary:
    user: BotUser
    due_count: int


def should_notify(user: BotUser, *, now: datetime, cooldown: timedelta) -> bool:
    """A user is reminded when they have never been, or when the last reminder is older than the cool-down."""
    return user.due_notified_at is None or user.due_notified_at <= now - cooldown


class DueNotificationService:
    """Decides who gets the consolidated "N cards due" reminder on each poll.

    Edge-triggered with a periodic fallback: the first due card after an empty queue is announced on the
    next poll; while the queue stays non-empty the reminder repeats once per cool-down.
    """

    def __init__(
        self,
        card_repo: CardRepository,
        user_repo: UserRepository,
        *,
        admin_user_ids: frozenset[int],
        cooldown_minutes: int,
    ) -> None:
        self._card_repo = card_repo
        self._user_repo = user_repo
        self._admin_user_ids = admin_user_ids
        self._cooldown = timedelta(minutes=max(1, cooldown_minutes))

    async def collect(self, *, now: datetime | None = None) -> list[DueSummary]:
        now = now or _now()
        counts = await self._card_repo.count_due_by_user()
        # Users with an empty queue get their reminder state reset so the next due card notifies promptly.
        await self._user_repo.clear_due_notified_except(list(counts))
        summaries: list[DueSummary] = []
        for user_id, due_count in counts.items():
            if due_count <= 0:
                continue
            user = await self._user_repo.get(user_id)
            if user is None or not user_has_access(user, self._admin_user_ids):
                continue
            if not should_notify(user, now=now, cooldown=self._cooldown):
                continue
            summaries.append(DueSummary(user=user, due_count=due_count))
        return summaries

    async def mark_notified(self, user_id: int, *, now: datetime | None = None) -> None:
        await self._user_repo.set_due_notified_at(user_id, now or _now())
