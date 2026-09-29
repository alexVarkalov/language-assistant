from __future__ import annotations

import pytest

from vocab_bot.translations import merge_translations, split_translations


def test_adds_a_translation_the_card_does_not_have() -> None:
    assert merge_translations("kapcie", "pantofle") == "kapcie; pantofle"


def test_keeps_the_card_unchanged_when_it_already_has_the_translation() -> None:
    assert merge_translations("kapcie; pantofle", "pantofle") == "kapcie; pantofle"


@pytest.mark.parametrize("addition", ["Pantofle", " pantofle ", "pantofle (l.mn.)"])
def test_spelling_case_and_grammar_notes_do_not_make_a_duplicate(addition: str) -> None:
    assert merge_translations("pantofle", addition) == "pantofle"


def test_a_stored_grammar_note_survives_a_plainer_save() -> None:
    # The wordbank's richer text wins: saving "kapcie" must not strip "(l.mn.)".
    assert merge_translations("kapcie (l.mn.)", "kapcie") == "kapcie (l.mn.)"


def test_stops_growing_at_the_limit() -> None:
    full = "a; b; c; d"
    assert merge_translations(full, "e") == full
    assert merge_translations("a; b", "c", limit=2) == "a; b"


def test_an_empty_card_takes_the_translation_as_is() -> None:
    assert merge_translations("", "kapcie") == "kapcie"


def test_a_blank_addition_changes_nothing() -> None:
    assert merge_translations("kapcie", "   ") == "kapcie"


def test_split_ignores_empty_parts_and_spacing() -> None:
    assert split_translations(" kapcie ;; pantofle ") == ["kapcie", "pantofle"]
