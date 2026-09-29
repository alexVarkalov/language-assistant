from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CardSides:
    """The four card columns that decide which language sits on which side."""

    source_lang: str
    target_lang: str
    source_text: str
    target_text: str


def canonical_sides(
    *,
    source_lang: str,
    target_lang: str,
    source_text: str,
    target_text: str,
    native_lang: str | None,
) -> CardSides:
    """
    Put the user's own language on the source side of a card.

    Cards are keyed by (user, source_lang, target_lang, source_text), and which side a word lands on
    is decided by the language the user happened to type in. Storing every card the same way round is
    what makes "dom" and "дом" the same card instead of two mirrored ones.

    Without a native language, or on a card where neither side is it, the sides are left alone —
    those cards keep working, they just aren't deduplicated across directions.
    """
    sides = CardSides(source_lang, target_lang, source_text, target_text)
    if native_lang is None:
        return sides
    native = native_lang.upper()
    if source_lang.upper() == native or target_lang.upper() != native:
        return sides
    return CardSides(target_lang, source_lang, target_text, source_text)
