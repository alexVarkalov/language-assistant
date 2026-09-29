"""
Store every existing card native-language-first, merging mirrored duplicates.

Cards are keyed by (user_id, source_lang, target_lang, source_text), and until NATIVE_LANG existed
the side a word landed on was decided by the language the user happened to type. That let the same
word pair exist twice, once per direction. This script rewrites the rows that sit the wrong way
round so that every card matches what `canonical_sides()` now produces at save time.

Per card that is stored foreign-first:

* no card on the canonical side yet -> flip it in place (id, schedule and progress are kept);
* a card already on the canonical key -> merge the two, keeping the better-learned schedule, the
  sooner review date and both translations (`merge_translations`), then delete the mirrored row.

Merging keeps both translations rather than choosing between them, so a native word that has two
translations ends up as one card holding both, and a stored "kapcie (l.mn.)" survives a hand-typed
"kapcie".

Reviews are unaffected either way: `direction_for_card()` reads NATIVE_LANG, not the stored side.

Dry run (prints the plan, changes nothing):

    uv run python -m scripts.canonicalize_card_orientation

Apply it (take a pg_dump first; the bot and API should be stopped):

    uv run python -m scripts.canonicalize_card_orientation --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from vocab_bot.config import load_dotenv_if_present
from vocab_bot.translations import merge_translations


@dataclass(frozen=True)
class Row:
    id: int
    user_id: int
    source_lang: str
    target_lang: str
    source_text: str
    target_text: str
    ease_factor: float
    interval_days: float
    repetition: int
    next_review_at: datetime


@dataclass
class Plan:
    flipped: list[Row]
    merged: list[tuple[Row, Row, str]]


_COLUMNS = (
    "id, user_id, source_lang, target_lang, source_text, target_text, "
    "ease_factor, interval_days, repetition, next_review_at"
)


def _non_canonical(conn: Connection, native: str) -> list[Row]:
    """Cards whose target side is the native language, i.e. the ones stored the wrong way round."""
    result = conn.execute(
        text(
            f"SELECT {_COLUMNS} FROM cards "
            "WHERE upper(target_lang) = :native AND upper(source_lang) <> :native ORDER BY id"
        ),
        {"native": native},
    )
    return [Row(*row) for row in result]


def _canonical_twin(conn: Connection, row: Row) -> Row | None:
    """The card already occupying the key `row` would flip onto, if there is one."""
    result = conn.execute(
        text(
            f"SELECT {_COLUMNS} FROM cards WHERE user_id = :user_id AND source_lang = :source_lang "
            "AND target_lang = :target_lang AND source_text = :source_text"
        ),
        {
            "user_id": row.user_id,
            "source_lang": row.target_lang,
            "target_lang": row.source_lang,
            "source_text": row.target_text,
        },
    ).first()
    return Row(*result) if result is not None else None


def _better_learned(a: Row, b: Row) -> Row:
    """The row whose progress we keep: the longer streak, then the longer interval."""
    return a if (a.repetition, a.interval_days) >= (b.repetition, b.interval_days) else b


def _flip(conn: Connection, row: Row) -> None:
    conn.execute(
        text(
            "UPDATE cards SET source_lang = :source_lang, target_lang = :target_lang, "
            "source_text = :source_text, target_text = :target_text WHERE id = :id"
        ),
        {
            "id": row.id,
            "source_lang": row.target_lang,
            "target_lang": row.source_lang,
            "source_text": row.target_text,
            "target_text": row.source_text,
        },
    )


def merged_target_text(row: Row, twin: Row) -> str:
    """Both translations on one card; `row`'s source word is its translation once flipped."""
    return merge_translations(twin.target_text, row.source_text)


def _merge(conn: Connection, row: Row, twin: Row) -> None:
    """Fold `row` into `twin`: keep the better progress, and never push a due card further out."""
    keep = _better_learned(row, twin)
    conn.execute(
        text(
            "UPDATE cards SET target_text = :target_text, ease_factor = :ease_factor, "
            "interval_days = :interval_days, repetition = :repetition, next_review_at = :next_review_at "
            "WHERE id = :id"
        ),
        {
            "id": twin.id,
            "target_text": merged_target_text(row, twin),
            "ease_factor": keep.ease_factor,
            "interval_days": keep.interval_days,
            "repetition": keep.repetition,
            "next_review_at": min(row.next_review_at, twin.next_review_at),
        },
    )
    conn.execute(text("DELETE FROM cards WHERE id = :id"), {"id": row.id})


def build_plan(conn: Connection, native: str, *, apply: bool) -> Plan:
    plan = Plan(flipped=[], merged=[])
    for row in _non_canonical(conn, native):
        twin = _canonical_twin(conn, row)
        if twin is None:
            plan.flipped.append(row)
            if apply:
                _flip(conn, row)
        else:
            plan.merged.append((row, twin, merged_target_text(row, twin)))
            if apply:
                _merge(conn, row, twin)
    return plan


def _report(plan: Plan, native: str, *, apply: bool) -> None:
    verb = "Rewrote" if apply else "Would rewrite"
    print(f"native language: {native}")
    print(f"{verb} {len(plan.flipped)} card(s) to sit native-side-first:")
    for row in plan.flipped:
        print(f"  #{row.id:<6} {row.source_text} -> {row.target_text}   (rep={row.repetition})")
    print(f"{'Merged' if apply else 'Would merge'} {len(plan.merged)} duplicate(s) into an existing card:")
    for row, twin, target_text in plan.merged:
        keep = _better_learned(row, twin)
        print(f"  #{row.id} {row.source_text} -> {row.target_text}  into  #{twin.id}")
        print(f"          becomes  {twin.source_text} -> {target_text}   (rep={keep.repetition})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    parser.add_argument("--database-url", default=None, help="defaults to DATABASE_URL")
    parser.add_argument("--native-lang", default=None, help="defaults to NATIVE_LANG")
    args = parser.parse_args(argv)

    load_dotenv_if_present()
    database_url = args.database_url or os.environ.get("DATABASE_URL", "").strip()
    native = (args.native_lang or os.environ.get("NATIVE_LANG", "")).strip().upper()
    if not database_url:
        print("DATABASE_URL is not set (and --database-url was not given)", file=sys.stderr)
        return 2
    if not native:
        print("NATIVE_LANG is not set (and --native-lang was not given)", file=sys.stderr)
        return 2

    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        plan = build_plan(conn, native, apply=args.apply)
        _report(plan, native, apply=args.apply)
        if not args.apply:
            print("\nDry run — nothing was written. Re-run with --apply (after a pg_dump) to commit.")
            conn.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
