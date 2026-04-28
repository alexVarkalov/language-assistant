from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from vocab_bot.config import Settings
from vocab_bot.persistence import PendingTranslation
from vocab_bot.services import translation as translation_module
from vocab_bot.services.translation import TranslationService, _select_target


def _settings() -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="EN",
        target_lang="RU",
        available_languages=frozenset({"EN", "RU"}),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        admin_user_ids=frozenset(),
    )


@pytest.mark.asyncio
async def test_translate_and_store_pending_uses_translator_and_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_translate_text_options(**_: object) -> list[str]:
        return ["privet", "zdravstvuyte"]

    monkeypatch.setattr(translation_module, "translate_text_options", fake_translate_text_options)

    pending_repo = AsyncMock()
    card_repo = AsyncMock()
    service = TranslationService(_settings(), pending_repo, card_repo)

    async with httpx.AsyncClient() as client:
        pending = await service.translate_and_store_pending(
            user_id=1,
            text=" hello ",
            source_lang="EN",
            target_lang="RU",
            client=client,
        )

    assert pending.source_text == "hello"
    assert pending.target_text == "privet"
    pending_repo.add.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_pending_as_card_returns_none_when_pending_missing() -> None:
    pending_repo = AsyncMock()
    pending_repo.get.return_value = None
    card_repo = AsyncMock()
    service = TranslationService(_settings(), pending_repo, card_repo)

    result = await service.save_pending_as_card(pending_id="x", user_id=1, option_index=0)

    assert result is None
    card_repo.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_pending_as_card_persists_card_and_deletes_pending() -> None:
    pending = PendingTranslation(
        id="p1",
        user_id=1,
        source_lang="EN",
        target_lang="RU",
        source_text="hello",
        target_text="privet",
        target_options=("privet", "zdravstvuyte"),
    )
    pending_repo = AsyncMock()
    pending_repo.get.return_value = pending
    card_repo = AsyncMock()
    service = TranslationService(_settings(), pending_repo, card_repo)

    saved = await service.save_pending_as_card(pending_id="p1", user_id=1, option_index=1)

    assert saved is not None
    assert saved.target_text == "zdravstvuyte"
    card_repo.upsert.assert_awaited_once()
    pending_repo.delete.assert_awaited_once_with("p1", 1)


def test_select_target_fallbacks() -> None:
    pending = PendingTranslation(
        id="p1",
        user_id=1,
        source_lang="EN",
        target_lang="RU",
        source_text="hello",
        target_text="privet",
        target_options=("privet", "zdravstvuyte"),
    )
    assert _select_target(pending, None) == "privet"
    assert _select_target(pending, -1) == "privet"
    assert _select_target(pending, 100) == "privet"
