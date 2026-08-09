from __future__ import annotations

import pytest

from vocab_bot.lang_detect import (
    UnsupportedLanguagePairError,
    detect_source_lang,
    resolve_direction,
    validate_language_pair,
)


def test_validate_language_pair_accepts_cyrillic_latin_pair() -> None:
    validate_language_pair("PL", "RU")
    validate_language_pair("RU", "PL")


def test_validate_language_pair_rejects_same_script() -> None:
    with pytest.raises(UnsupportedLanguagePairError):
        validate_language_pair("EN", "PL")
    with pytest.raises(UnsupportedLanguagePairError):
        validate_language_pair("RU", "UK")


def test_detect_source_lang_picks_cyrillic_for_cyrillic_text() -> None:
    assert detect_source_lang("Привет, как дела?", "PL", "RU") == "RU"
    assert detect_source_lang("Привет", "RU", "PL") == "RU"


def test_detect_source_lang_defaults_to_latin_language() -> None:
    assert detect_source_lang("Dzień dobry", "PL", "RU") == "PL"
    assert detect_source_lang("", "PL", "RU") == "PL"
    assert detect_source_lang("123", "PL", "RU") == "PL"


def test_resolve_direction_returns_source_and_target() -> None:
    assert resolve_direction("kot", "PL", "RU") == ("PL", "RU")
    assert resolve_direction("кот", "PL", "RU") == ("RU", "PL")
    assert resolve_direction("кот", "RU", "PL") == ("RU", "PL")
