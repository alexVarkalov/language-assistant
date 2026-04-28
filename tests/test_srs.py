from __future__ import annotations

from datetime import UTC, datetime

from vocab_bot.srs import SrsState, initial_srs, next_review_datetime, schedule_after_grade


def test_initial_srs_defaults() -> None:
    state = initial_srs()
    assert state == SrsState(ease_factor=2.5, interval_days=0.0, repetition=0)


def test_schedule_after_grade_again_resets_repetition() -> None:
    state = SrsState(ease_factor=2.2, interval_days=4.0, repetition=3)
    updated = schedule_after_grade(state, 0)
    assert updated.repetition == 0
    assert updated.interval_days == 0.0
    assert updated.ease_factor >= 1.3


def test_schedule_after_grade_good_progresses_intervals() -> None:
    first = schedule_after_grade(initial_srs(), 3)
    second = schedule_after_grade(first, 3)
    assert first.repetition == 1
    assert second.repetition == 2
    assert second.interval_days >= 1.0


def test_next_review_datetime_uses_interval() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    before = SrsState(ease_factor=2.5, interval_days=1.0, repetition=2)
    when, _ = next_review_datetime(before, 5, now)
    assert when > now
