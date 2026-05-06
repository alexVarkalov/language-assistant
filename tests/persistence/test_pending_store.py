from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from tests.persistence.fakes import FakeSession, FakeSessionFactory
from vocab_bot.persistence.pending import PendingStore, _load_options
from vocab_bot.persistence.types import PendingTranslation


class PendingDb(PendingStore):
    def __init__(self, session: FakeSession):
        self._session_factory = FakeSessionFactory(session)


def test_load_options_fallbacks() -> None:
    assert _load_options("", "x") == ("x",)
    assert _load_options("   ", "x") == ("x",)
    assert _load_options("{", "x") == ("x",)
    assert _load_options('{"a": 1}', "x") == ("x",)
    assert _load_options("[]", "x") == ("x",)
    assert _load_options('["  ", 1, null]', "x") == ("x",)


def test_load_options_dedup_and_strip() -> None:
    assert _load_options('[" a ", "A", "b", ""]', "x") == ("a", "b")


def test_insert_pending_sync_adds_record(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    db = PendingDb(session)

    class FakePendingRecord:
        def __init__(self, **kwargs: object):
            self.kwargs = kwargs

    monkeypatch.setattr("vocab_bot.persistence.pending.PendingRecord", FakePendingRecord)
    monkeypatch.setattr("vocab_bot.persistence.pending.utc_now", lambda: datetime(2026, 1, 1, tzinfo=UTC))

    pending = PendingTranslation(
        id="p1",
        user_id=1,
        source_lang="EN",
        target_lang="RU",
        source_text="hello",
        target_text="privet",
        target_options=("privet", "z"),
    )
    db._insert_pending_sync(pending)

    assert session.committed == 1
    assert session.added


def test_get_pending_sync_none() -> None:
    session = FakeSession(scalar_results=[None])
    db = PendingDb(session)

    assert db._get_pending_sync("p1", 1) is None


def test_get_pending_sync_builds_pending() -> None:
    session = FakeSession(
        scalar_results=[
            SimpleNamespace(
                id="p1",
                user_id=1,
                source_lang="EN",
                target_lang="RU",
                source_text="hello",
                target_text="privet",
                target_options='["a", "b"]',
            )
        ]
    )
    db = PendingDb(session)

    pending = db._get_pending_sync("p1", 1)

    assert pending is not None
    assert pending.target_options == ("a", "b")


def test_delete_pending_sync_deletes_when_found() -> None:
    record = SimpleNamespace(id="p1")
    session = FakeSession(scalar_results=[record])
    db = PendingDb(session)

    db._delete_pending_sync("p1", 1)

    assert session.deleted == [record]
    assert session.committed == 1


def test_delete_pending_sync_commits_even_when_missing() -> None:
    session = FakeSession(scalar_results=[None])
    db = PendingDb(session)

    db._delete_pending_sync("p1", 1)

    assert session.deleted == []
    assert session.committed == 1
