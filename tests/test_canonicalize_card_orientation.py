"""
Tests for the one-off orientation migration.

The script is raw SQL against a live database, so mocks would prove nothing. It is exercised here on
an in-memory SQLite database instead — the statements it runs are plain ANSI SQL. The app itself
still talks only to PostgreSQL (see CLAUDE.md); this is a test-only convenience for a standalone
script, not a fallback backend.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from scripts.canonicalize_card_orientation import build_plan

NATIVE = "RU"

_SCHEMA = """
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    source_text TEXT NOT NULL,
    target_text TEXT NOT NULL,
    ease_factor REAL NOT NULL,
    interval_days REAL NOT NULL,
    repetition INTEGER NOT NULL,
    next_review_at TEXT NOT NULL,
    UNIQUE (user_id, source_lang, target_lang, source_text)
)
"""


@pytest.fixture
def conn() -> Iterator[Connection]:
    engine = create_engine("sqlite://", future=True)
    with engine.begin() as connection:
        connection.execute(text(_SCHEMA))
        yield connection


def add_card(
    conn: Connection,
    *,
    source_lang: str,
    target_lang: str,
    source_text: str,
    target_text: str,
    repetition: int = 0,
    interval_days: float = 1.0,
    next_review_at: str = "2026-09-29T09:00:00",
    user_id: int = 1,
) -> int:
    result = conn.execute(
        text(
            "INSERT INTO cards (user_id, source_lang, target_lang, source_text, target_text, "
            "ease_factor, interval_days, repetition, next_review_at) VALUES "
            "(:user_id, :source_lang, :target_lang, :source_text, :target_text, 2.5, "
            ":interval_days, :repetition, :next_review_at) RETURNING id"
        ),
        {
            "user_id": user_id,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source_text": source_text,
            "target_text": target_text,
            "interval_days": interval_days,
            "repetition": repetition,
            "next_review_at": next_review_at,
        },
    )
    return int(result.scalar_one())


def cards(conn: Connection) -> list[tuple]:
    return [
        tuple(row)
        for row in conn.execute(
            text("SELECT id, source_lang, target_lang, source_text, target_text, repetition FROM cards ORDER BY id")
        )
    ]


def test_flips_a_lone_foreign_first_card_in_place(conn: Connection) -> None:
    card_id = add_card(conn, source_lang="PL", target_lang="RU", source_text="dom", target_text="дом", repetition=4)

    plan = build_plan(conn, NATIVE, apply=True)

    assert [row.id for row in plan.flipped] == [card_id]
    assert plan.merged == []
    # Same row, same progress — only the sides swapped.
    assert cards(conn) == [(card_id, "RU", "PL", "дом", "dom", 4)]


def test_leaves_already_canonical_cards_alone(conn: Connection) -> None:
    add_card(conn, source_lang="RU", target_lang="PL", source_text="дом", target_text="dom", repetition=7)

    plan = build_plan(conn, NATIVE, apply=True)

    assert (plan.flipped, plan.merged) == ([], [])
    assert cards(conn) == [(1, "RU", "PL", "дом", "dom", 7)]


def test_merges_an_exact_mirror_and_keeps_the_better_progress(conn: Connection) -> None:
    mirrored = add_card(
        conn,
        source_lang="PL",
        target_lang="RU",
        source_text="dom",
        target_text="дом",
        repetition=9,
        interval_days=30.0,
        next_review_at="2026-10-20T09:00:00",
    )
    canonical = add_card(
        conn,
        source_lang="RU",
        target_lang="PL",
        source_text="дом",
        target_text="dom",
        repetition=2,
        interval_days=1.0,
        next_review_at="2026-09-29T09:00:00",
    )

    plan = build_plan(conn, NATIVE, apply=True)

    assert [(row.id, twin.id) for row, twin, _ in plan.merged] == [(mirrored, canonical)]
    assert cards(conn) == [(canonical, "RU", "PL", "дом", "dom", 9)]
    # The sooner of the two review dates survives, so nothing already due gets pushed away.
    assert conn.execute(text("SELECT next_review_at FROM cards")).scalar_one() == "2026-09-29T09:00:00"


def test_a_hand_typed_card_does_not_strip_the_wordbanks_grammar_note(conn: Connection) -> None:
    typed = add_card(conn, source_lang="PL", target_lang="RU", source_text="kapcie", target_text="тапочки")
    from_wordbank = add_card(
        conn, source_lang="RU", target_lang="PL", source_text="тапочки", target_text="kapcie (l.mn.)"
    )

    build_plan(conn, NATIVE, apply=True)

    assert [(row[0], row[4]) for row in cards(conn)] == [(from_wordbank, "kapcie (l.mn.)")]
    assert typed


def test_two_foreign_words_for_one_native_word_become_one_card_with_both(conn: Connection) -> None:
    first = add_card(conn, source_lang="PL", target_lang="RU", source_text="dom", target_text="дом")
    add_card(conn, source_lang="PL", target_lang="RU", source_text="budynek", target_text="дом")

    plan = build_plan(conn, NATIVE, apply=True)

    # The first flips onto the free canonical key; the second folds its word into that card.
    assert [row.id for row in plan.flipped] == [first]
    assert [target for _, _, target in plan.merged] == ["dom; budynek"]
    assert cards(conn) == [(first, "RU", "PL", "дом", "dom; budynek", 0)]


def test_dry_run_reports_the_plan_without_writing(conn: Connection) -> None:
    card_id = add_card(conn, source_lang="PL", target_lang="RU", source_text="dom", target_text="дом")

    plan = build_plan(conn, NATIVE, apply=False)

    assert [row.id for row in plan.flipped] == [card_id]
    assert cards(conn) == [(card_id, "PL", "RU", "dom", "дом", 0)]


def test_cards_of_other_users_are_not_treated_as_twins(conn: Connection) -> None:
    mine = add_card(conn, source_lang="PL", target_lang="RU", source_text="dom", target_text="дом", user_id=1)
    theirs = add_card(conn, source_lang="RU", target_lang="PL", source_text="дом", target_text="dom", user_id=2)

    plan = build_plan(conn, NATIVE, apply=True)

    assert [row.id for row in plan.flipped] == [mine]
    assert plan.merged == []
    assert len(cards(conn)) == 2 and theirs
