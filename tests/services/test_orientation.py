from __future__ import annotations

import pytest

from vocab_bot.services.orientation import CardSides, canonical_sides


def sides(source_lang: str, target_lang: str, native_lang: str | None) -> CardSides:
    texts = {"PL": "dom", "RU": "дом", "EN": "house"}
    return canonical_sides(
        source_lang=source_lang,
        target_lang=target_lang,
        source_text=texts[source_lang],
        target_text=texts[target_lang],
        native_lang=native_lang,
    )


def test_a_foreign_first_card_is_flipped_native_first() -> None:
    assert sides("PL", "RU", "RU") == CardSides("RU", "PL", "дом", "dom")


def test_a_native_first_card_is_left_alone() -> None:
    assert sides("RU", "PL", "RU") == CardSides("RU", "PL", "дом", "dom")


def test_both_typing_directions_collapse_onto_the_same_sides() -> None:
    assert sides("PL", "RU", "RU") == sides("RU", "PL", "RU")


def test_language_case_does_not_matter() -> None:
    result = canonical_sides(source_lang="pl", target_lang="ru", source_text="dom", target_text="дом", native_lang="ru")
    assert result == CardSides("ru", "pl", "дом", "dom")


@pytest.mark.parametrize("native", [None, "EN"])
def test_sides_are_untouched_without_a_usable_native_language(native: str | None) -> None:
    assert sides("PL", "RU", native) == CardSides("PL", "RU", "dom", "дом")
