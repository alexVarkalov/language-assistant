from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI

from vocab_bot.config import Settings
from vocab_bot.webapi.app import create_app
from vocab_bot.webapi.auth import compute_init_data_hash

BOT_TOKEN = "123456:test-bot-token"


def make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "bot_token": BOT_TOKEN,
        "deepl_api_key": "key",
        "deepl_plan": "free",
        "translator": "deepl",
        "source_lang": "PL",
        "target_lang": "RU",
        "database_url": "postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        "due_poll_interval": 45,
        "short_review_interval_minutes": 10,
        "admin_user_ids": frozenset(),
        "wordbank_path": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def make_init_data(
    *,
    bot_token: str = BOT_TOKEN,
    user: dict[str, object] | None = None,
    auth_date: int | None = None,
    extra: dict[str, str] | None = None,
    tamper_hash: bool = False,
) -> str:
    fields: dict[str, str] = {
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(
            user
            if user is not None
            else {"id": 123, "first_name": "Test", "last_name": "User", "username": "tester", "language_code": "en"},
            separators=(",", ":"),
        ),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }
    if extra:
        fields.update(extra)
    digest = compute_init_data_hash(fields, bot_token)
    if tamper_hash:
        digest = "0" * len(digest)
    fields["hash"] = digest
    return urlencode(fields)


def auth_header(init_data: str | None = None) -> dict[str, str]:
    return {"Authorization": f"tma {init_data if init_data is not None else make_init_data()}"}


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    # httpx.ASGITransport does not run lifespan, so services are injected directly on app.state.
    application = create_app(settings, db=object())  # type: ignore[arg-type]
    application.state.user_service = AsyncMock()
    application.state.review_service = AsyncMock()
    return application
