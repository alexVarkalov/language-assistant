from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vocab_bot.config import Settings
from vocab_bot.services.wordbank import WordbankService
from vocab_bot.wordbank import Section, Topic, WordEntry


def _settings(source_lang: str = "RU", target_lang: str = "PL") -> Settings:
    return Settings(
        bot_token="token",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang=source_lang,
        target_lang=target_lang,
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
        wordbank_path="data/ru_pl_dictionary.json",
    )


def _sections() -> tuple[Section, ...]:
    return (
        Section(
            title="основные понятия | часть 1",
            topics=(
                Topic(
                    number=1,
                    title="Местоимения",
                    words=(WordEntry(ru="я", pl="ja", ipa="[ja]"), WordEntry(ru="ты", pl="ty", ipa="[tɨ]")),
                ),
            ),
        ),
    )


def test_list_sections_and_get_topic() -> None:
    sections = _sections()
    service = WordbankService(sections, AsyncMock(), _settings())

    assert service.list_sections() == sections
    found = service.get_topic(1)
    assert found is not None
    assert found[1].title == "Местоимения"
    assert service.get_topic(999) is None


@pytest.mark.asyncio
async def test_add_topic_words_missing_topic_returns_none() -> None:
    service = WordbankService(_sections(), AsyncMock(), _settings())

    result = await service.add_topic_words(user_id=1, topic_number=999)

    assert result is None


@pytest.mark.asyncio
async def test_add_topic_words_counts_added_and_skipped() -> None:
    card_repo = AsyncMock()
    card_repo.insert_if_missing.side_effect = [True, False]
    service = WordbankService(_sections(), card_repo, _settings())

    result = await service.add_topic_words(user_id=1, topic_number=1)

    assert result is not None
    assert result.topic_title == "Местоимения"
    assert result.added == 1
    assert result.skipped == 1
    assert card_repo.insert_if_missing.await_count == 2

    first_call_kwargs = card_repo.insert_if_missing.await_args_list[0].kwargs
    assert first_call_kwargs["source_lang"] == "RU"
    assert first_call_kwargs["target_lang"] == "PL"
    assert first_call_kwargs["source_text"] == "я"
    assert first_call_kwargs["target_text"] == "ja"


@pytest.mark.asyncio
async def test_add_topic_words_maps_direction_when_pair_is_reversed() -> None:
    card_repo = AsyncMock()
    card_repo.insert_if_missing.return_value = True
    service = WordbankService(_sections(), card_repo, _settings(source_lang="PL", target_lang="RU"))

    result = await service.add_topic_words(user_id=1, topic_number=1)

    assert result is not None
    assert result.added == 2
    first_call_kwargs = card_repo.insert_if_missing.await_args_list[0].kwargs
    assert first_call_kwargs["source_lang"] == "PL"
    assert first_call_kwargs["target_lang"] == "RU"
    assert first_call_kwargs["source_text"] == "ja"
    assert first_call_kwargs["target_text"] == "я"


@pytest.mark.asyncio
async def test_add_topic_words_skips_all_for_unrelated_pair() -> None:
    card_repo = AsyncMock()
    service = WordbankService(_sections(), card_repo, _settings(source_lang="RU", target_lang="EN"))

    result = await service.add_topic_words(user_id=1, topic_number=1)

    assert result is not None
    assert result.added == 0
    assert result.skipped == 2
    card_repo.insert_if_missing.assert_not_awaited()
