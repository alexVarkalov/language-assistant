from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from tests.persistence.fakes import FakeInsert, FakeSession, FakeSessionFactory
from vocab_bot.persistence.cards import CardStore


class CardsDb(CardStore):
    def __init__(self, session: FakeSession):
        self._session_factory = FakeSessionFactory(session)


def test_upsert_card_sync_raises_when_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(scalar_results=[None])
    db = CardsDb(session)
    monkeypatch.setattr("vocab_bot.persistence.cards.pg_insert", lambda _model: FakeInsert())
    monkeypatch.setattr(
        "vocab_bot.persistence.cards.select",
        lambda *_a, **_k: SimpleNamespace(where=lambda *_a2, **_k2: object()),
    )

    when = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    with pytest.raises(RuntimeError, match="failed to read card id after upsert"):
        db._upsert_card_sync(1, "EN", "RU", "hello", "privet", 2.5, 1.0, 1, when)


def test_upsert_card_sync_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(scalar_results=[99])
    db = CardsDb(session)
    monkeypatch.setattr("vocab_bot.persistence.cards.pg_insert", lambda _model: FakeInsert())
    monkeypatch.setattr(
        "vocab_bot.persistence.cards.select",
        lambda *_a, **_k: SimpleNamespace(where=lambda *_a2, **_k2: object()),
    )

    when = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    card_id = db._upsert_card_sync(1, "EN", "RU", "hello", "privet", 2.5, 1.0, 1, when)

    assert card_id == 99
    assert session.executed
    assert session.committed == 1


def test_get_card_sync_none(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(scalar_results=[None])
    db = CardsDb(session)
    monkeypatch.setattr("vocab_bot.persistence.cards.to_card", lambda r: r)

    assert db._get_card_sync(1, 2) is None


def test_get_card_sync_some(monkeypatch: pytest.MonkeyPatch) -> None:
    record = SimpleNamespace(id=1)
    session = FakeSession(scalar_results=[record])
    db = CardsDb(session)
    monkeypatch.setattr("vocab_bot.persistence.cards.to_card", lambda r: r)

    assert db._get_card_sync(1, 2) == record


def test_get_awaiting_card_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    record = SimpleNamespace(id=1)
    session = FakeSession(scalar_results=[record])
    db = CardsDb(session)
    monkeypatch.setattr(
        "vocab_bot.persistence.cards.select",
        lambda *_a, **_k: SimpleNamespace(
            where=lambda *_a2, **_k2: SimpleNamespace(
                order_by=lambda *_a3, **_k3: SimpleNamespace(limit=lambda *_a4, **_k4: object())
            )
        ),
    )
    monkeypatch.setattr("vocab_bot.persistence.cards.to_card", lambda r: r)

    assert db._get_awaiting_card_sync(2) == record


def test_list_due_cards_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    r1 = SimpleNamespace(id=1)
    r2 = SimpleNamespace(id=2)
    session = FakeSession(scalars_results=[[r1, r2]])
    db = CardsDb(session)
    monkeypatch.setattr(
        "vocab_bot.persistence.cards.select",
        lambda *_a, **_k: SimpleNamespace(
            where=lambda *_a2, **_k2: SimpleNamespace(
                order_by=lambda *_a3, **_k3: SimpleNamespace(limit=lambda *_a4, **_k4: object())
            )
        ),
    )
    monkeypatch.setattr("vocab_bot.persistence.cards.to_card", lambda r: r)
    monkeypatch.setattr("vocab_bot.persistence.cards.utc_now", lambda: datetime(2026, 1, 1, tzinfo=UTC))

    assert db._list_due_cards_sync(limit=10) == [r1, r2]


def test_mark_awaiting_sync_updates_when_found() -> None:
    record = SimpleNamespace(awaiting_grade=False)
    session = FakeSession(scalar_results=[record])
    db = CardsDb(session)

    db._mark_awaiting_sync(1, 2, True)

    assert record.awaiting_grade is True
    assert session.committed == 1


def test_update_card_srs_sync_updates_fields() -> None:
    record = SimpleNamespace(
        ease_factor=2.5,
        interval_days=1.0,
        repetition=1,
        next_review_at=datetime(2026, 1, 1, tzinfo=UTC),
        awaiting_grade=True,
    )
    session = FakeSession(scalar_results=[record])
    db = CardsDb(session)

    when = datetime(2026, 1, 2, 12, 0, tzinfo=UTC) + timedelta(seconds=1)
    db._update_card_srs_sync(1, 2, 2.7, 3.0, 2, when)

    assert record.ease_factor == 2.7
    assert record.interval_days == 3.0
    assert record.repetition == 2
    assert record.awaiting_grade is False
    assert session.committed == 1
