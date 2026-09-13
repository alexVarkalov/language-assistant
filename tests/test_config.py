from __future__ import annotations

import pytest

from vocab_bot.config import Settings, _parse_user_ids
from vocab_bot.lang_detect import UnsupportedLanguagePairError


def test_settings_from_env_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("DUE_POLL_INTERVAL", "10")
    monkeypatch.setenv("SOURCE_LANG", "pl")
    monkeypatch.setenv("TARGET_LANG", "ru")
    monkeypatch.setenv("ADMIN_USER_IDS", "1, 2, bad")
    monkeypatch.setenv("SHORT_REVIEW_INTERVAL_MINUTES", "2")

    settings = Settings.from_env()

    assert settings.bot_token == "token"
    assert settings.deepl_api_key == "deepl-key"
    assert settings.due_poll_interval == 15
    assert settings.short_review_interval_minutes == 2
    assert settings.source_lang == "PL"
    assert settings.target_lang == "RU"
    assert settings.admin_user_ids == frozenset({1, 2})
    assert settings.wordbank_path is None
    assert settings.webapp_url is None
    assert settings.webapp_api_host == "127.0.0.1"
    assert settings.webapp_api_port == 8080
    assert settings.webapp_initdata_max_age == 86400


def test_settings_from_env_reads_webapp_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("WEBAPP_URL", " https://vocab.example.com/ ")
    monkeypatch.setenv("WEBAPP_API_HOST", "0.0.0.0")
    monkeypatch.setenv("WEBAPP_API_PORT", "9000")
    monkeypatch.setenv("WEBAPP_INITDATA_MAX_AGE", "30")

    settings = Settings.from_env()

    assert settings.webapp_url == "https://vocab.example.com"
    assert settings.webapp_api_host == "0.0.0.0"
    assert settings.webapp_api_port == 9000
    assert settings.webapp_initdata_max_age == 60


def test_settings_from_env_rejects_http_webapp_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("WEBAPP_URL", "http://vocab.example.com")

    with pytest.raises(ValueError, match="WEBAPP_URL must be an https"):
        Settings.from_env()


def test_settings_from_env_invalid_webapp_port_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("WEBAPP_API_PORT", "not-a-port")

    assert Settings.from_env().webapp_api_port == 8080


def test_settings_from_env_reads_wordbank_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("WORDBANK_PATH", " data/ru_pl_dictionary.json ")

    settings = Settings.from_env()

    assert settings.wordbank_path == "data/ru_pl_dictionary.json"


def test_settings_from_env_rejects_same_script_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")
    monkeypatch.setenv("SOURCE_LANG", "en")
    monkeypatch.setenv("TARGET_LANG", "pl")

    with pytest.raises(UnsupportedLanguagePairError):
        Settings.from_env()


def test_settings_missing_required_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("DEEPL_API_KEY", "deepl-key")

    with pytest.raises(ValueError, match="BOT_TOKEN is required"):
        Settings.from_env()


def test_settings_missing_deepl_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPL_API_KEY is required"):
        Settings.from_env()


def test_parse_user_ids_helper() -> None:
    assert _parse_user_ids("1;2,abc, 3") == frozenset({1, 2, 3})
