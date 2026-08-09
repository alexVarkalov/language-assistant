from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from vocab_bot.config import Settings
from vocab_bot.handlers import register_handlers


def _settings(wordbank_path: str | None) -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="RU",
        target_lang="PL",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
        wordbank_path=wordbank_path,
    )


def test_register_handlers_wires_expected_handlers_without_wordbank() -> None:
    app = SimpleNamespace(add_handler=Mock(), bot_data={"settings": _settings(None)})

    register_handlers(app)

    assert app.add_handler.call_count == 12


def test_register_handlers_wires_wordbank_when_configured() -> None:
    app = SimpleNamespace(add_handler=Mock(), bot_data={"settings": _settings("data/ru_pl_dictionary.json")})

    register_handlers(app)

    assert app.add_handler.call_count == 14
