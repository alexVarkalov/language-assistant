from __future__ import annotations

import pytest

from tests.helpers import make_user
from vocab_bot.i18n import (
    _MESSAGES,
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    normalize_locale,
    plural_form,
    resolve_user_locale,
    t,
    t_count,
)


def test_every_locale_has_the_same_keys() -> None:
    reference = set(_MESSAGES[DEFAULT_LOCALE])
    for locale in SUPPORTED_LOCALES:
        assert set(_MESSAGES[locale]) == reference, locale


def test_normalize_locale() -> None:
    assert normalize_locale("ru") == "ru"
    assert normalize_locale("EN") == "en"
    assert normalize_locale("de") == DEFAULT_LOCALE
    assert normalize_locale(None) == DEFAULT_LOCALE


def test_resolve_user_locale_preferred_wins() -> None:
    user = make_user(preferred_locale="ru", language_code="en-US")
    assert resolve_user_locale(user) == "ru"


def test_resolve_user_locale_uses_language_code_fallback() -> None:
    user = make_user(preferred_locale=None, language_code="ru-RU")
    assert resolve_user_locale(user) == "ru"


def test_translation_fallback_to_default_locale() -> None:
    text = t("de", "locale_updated", locale_label="en")
    assert "updated" in text


@pytest.mark.parametrize(
    ("count", "form"),
    [
        (1, "one"),
        (2, "few"),
        (4, "few"),
        (5, "many"),
        (11, "many"),
        (12, "many"),
        (21, "one"),
        (22, "few"),
        (111, "many"),
    ],
)
def test_plural_form_ru(count: int, form: str) -> None:
    assert plural_form("ru", count) == form


def test_plural_form_en() -> None:
    assert plural_form("en", 1) == "one"
    assert plural_form("en", 0) == "many"
    assert plural_form("en", 2) == "many"


def test_t_count_picks_form_and_falls_back_to_many() -> None:
    assert "<b>1</b> card to review" in t_count("en", "due_summary", 1)
    assert "<b>3</b> cards to review" in t_count("en", "due_summary", 3)
    assert "карточка" in t_count("ru", "due_summary", 21)
    assert "карточки" in t_count("ru", "due_summary", 3)
    assert "карточек" in t_count("ru", "due_summary", 12)
