from __future__ import annotations

from tests.helpers import make_user
from vocab_bot.i18n import _MESSAGES, DEFAULT_LOCALE, SUPPORTED_LOCALES, normalize_locale, resolve_user_locale, t


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
