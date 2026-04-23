from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class SrsState:
    """SM-2-ish scheduling; intervals are expressed in days (fractional allowed)."""

    ease_factor: float
    interval_days: float
    repetition: int


def initial_srs() -> SrsState:
    return SrsState(ease_factor=2.5, interval_days=0.0, repetition=0)


def schedule_after_grade(state: SrsState, quality: int) -> SrsState:
    """
    Update SRS state after a review.

    quality uses SM-2 scale 0..5. We map buttons to:
    - Again -> 0
    - Good -> 3
    - Easy -> 5
    """
    q = max(0, min(5, quality))
    ef = state.ease_factor
    rep = state.repetition
    interval = state.interval_days

    if q < 3:
        return SrsState(ease_factor=max(1.3, ef), interval_days=0.0, repetition=0)

    if rep == 0:
        new_interval = 1.0 / 24.0 / 6.0  # 10 minutes expressed in days
    elif rep == 1:
        new_interval = 1.0
    else:
        new_interval = max(1.0, round(interval * ef, 4))

    new_ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ef = max(1.3, new_ef)
    return SrsState(ease_factor=new_ef, interval_days=new_interval, repetition=rep + 1)


def next_review_datetime(before: SrsState, quality: int, now: datetime) -> tuple[datetime, SrsState]:
    """Return the next review instant and the updated SRS snapshot after a grade."""
    updated = schedule_after_grade(before, quality)
    if updated.interval_days <= 0:
        when = now.astimezone(UTC) + timedelta(minutes=10)
    else:
        when = now.astimezone(UTC) + timedelta(days=updated.interval_days)
    return when, updated
