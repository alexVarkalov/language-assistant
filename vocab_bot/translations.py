"""
How a card holds more than one translation of the same word.

A word often has several valid translations ("тапочки" → "kapcie", "pantofle"), and the same word can
reach a card from several places: typed into the chat, picked from DeepL's options, or added in bulk
from the wordbank. They all land on one card — cards are keyed by the source word — so the card's
target side is a short list rather than a single string.

Nothing here ever replaces what a card already holds: a translation is added only when the card does
not have it yet, and a stored "kapcie (l.mn.)" is kept in preference to a bare "kapcie", so the
wordbank's grammatical notes survive a later hand-typed save.
"""

from __future__ import annotations

import re

SEPARATOR = "; "
MAX_TRANSLATIONS = 4

_PARENTHETICAL = re.compile(r"\([^)]*\)")
_WHITESPACE = re.compile(r"\s+")


def _comparable(translation: str) -> str:
    """The form two translations are judged equal by: no case, no notes, no stray spacing."""
    return _WHITESPACE.sub(" ", _PARENTHETICAL.sub(" ", translation)).strip().lower()


def split_translations(stored: str) -> list[str]:
    return [part.strip() for part in stored.split(";") if part.strip()]


def merge_translations(stored: str, addition: str, *, limit: int = MAX_TRANSLATIONS) -> str:
    """
    Fold `addition` into what a card already stores, and return the new target side.

    Returns `stored` unchanged when the translation is already there (in any spelling), when it is
    blank, or when the card is already holding `limit` of them.
    """
    addition = addition.strip()
    if not addition:
        return stored
    existing = split_translations(stored)
    if not existing:
        return addition
    if _comparable(addition) in {_comparable(part) for part in existing}:
        return stored
    if len(existing) >= limit:
        return stored
    return SEPARATOR.join([*existing, addition])
