"""
The chat save path and the wordbank must land on the same card.

Both write through the same unique key, `(user_id, source_lang, target_lang, source_text)`, but via
different statements: the chat upserts, the wordbank inserts-if-missing. The fake repository here
enforces that key and mirrors both conflict behaviours, so these tests catch the two paths drifting
apart and recreating the mirrored duplicates `canonical_sides()` exists to prevent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from vocab_bot.config import Settings
from vocab_bot.persistence import PendingTranslation
from vocab_bot.services.translation import TranslationService
from vocab_bot.services.wordbank import WordbankService
from vocab_bot.translations import merge_translations
from vocab_bot.wordbank import Section, Topic, WordEntry


class FakeCardRepo:
    """Keyed like the cards table; `upsert` only folds in translations, as the real one does."""

    def __init__(self) -> None:
        self.rows: dict[tuple[int, str, str, str], dict[str, Any]] = {}

    async def upsert(self, *, user_id: int, source_lang: str, target_lang: str, source_text: str, **rest: Any) -> int:
        key = (user_id, source_lang, target_lang, source_text)
        if key in self.rows:
            row = self.rows[key]
            row["target_text"] = merge_translations(row["target_text"], rest["target_text"])
        else:
            self.rows[key] = dict(rest)
        return 1

    async def insert_if_missing(
        self, *, user_id: int, source_lang: str, target_lang: str, source_text: str, **rest: Any
    ) -> bool:
        key = (user_id, source_lang, target_lang, source_text)
        if key in self.rows:
            return False
        self.rows[key] = dict(rest)
        return True


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
        native_lang="RU",
    )


def _sections() -> tuple[Section, ...]:
    return (
        Section(
            title="основные понятия",
            topics=(Topic(number=1, title="Местоимения", words=(WordEntry(ru="я", pl="ja", ipa="[ja]"),)),),
        ),
    )


def _typing_service(settings: Settings, repo: FakeCardRepo, *, typed: str, translated: str) -> TranslationService:
    """A service whose pending translation is what the user typed, detected as the chat would."""
    source_lang = "RU" if typed == "я" else "PL"
    target_lang = "PL" if source_lang == "RU" else "RU"
    pending_repo = AsyncMock()
    pending_repo.get.return_value = PendingTranslation(
        id="p1",
        user_id=1,
        source_lang=source_lang,
        target_lang=target_lang,
        source_text=typed,
        target_text=translated,
        target_options=(translated,),
    )
    return TranslationService(settings, pending_repo, repo)  # type: ignore[arg-type]


@pytest.mark.parametrize(("typed", "translated"), [("ja", "я"), ("я", "ja")])
@pytest.mark.asyncio
async def test_typing_a_topic_word_does_not_add_a_second_card(typed: str, translated: str) -> None:
    settings = _settings()
    repo = FakeCardRepo()
    await WordbankService(_sections(), repo, settings).add_topic_words(user_id=1, topic_number=1)  # type: ignore[arg-type]
    assert list(repo.rows) == [(1, "RU", "PL", "я")]

    await _typing_service(settings, repo, typed=typed, translated=translated).save_pending_as_card(
        pending_id="p1", user_id=1
    )

    assert list(repo.rows) == [(1, "RU", "PL", "я")]


@pytest.mark.asyncio
async def test_typing_a_topic_word_keeps_the_progress_it_already_earned() -> None:
    settings = _settings()
    repo = FakeCardRepo()
    await WordbankService(_sections(), repo, settings).add_topic_words(user_id=1, topic_number=1)  # type: ignore[arg-type]
    repo.rows[(1, "RU", "PL", "я")]["repetition"] = 7  # the user has been reviewing it for a while

    await _typing_service(settings, repo, typed="ja", translated="я").save_pending_as_card(pending_id="p1", user_id=1)

    assert repo.rows[(1, "RU", "PL", "я")]["repetition"] == 7


@pytest.mark.parametrize(("typed", "translated"), [("ja", "я"), ("я", "ja")])
@pytest.mark.asyncio
async def test_a_topic_skips_a_word_the_user_typed_earlier(typed: str, translated: str) -> None:
    settings = _settings()
    repo = FakeCardRepo()
    await _typing_service(settings, repo, typed=typed, translated=translated).save_pending_as_card(
        pending_id="p1", user_id=1
    )
    repo.rows[(1, "RU", "PL", "я")]["repetition"] = 4

    result = await WordbankService(_sections(), repo, settings).add_topic_words(user_id=1, topic_number=1)  # type: ignore[arg-type]

    assert result is not None
    assert (result.added, result.skipped) == (0, 1)
    assert list(repo.rows) == [(1, "RU", "PL", "я")]
    assert repo.rows[(1, "RU", "PL", "я")]["repetition"] == 4


@pytest.mark.asyncio
async def test_a_pl_first_deployment_files_topic_words_the_same_way() -> None:
    settings = _settings(source_lang="PL", target_lang="RU")
    repo = FakeCardRepo()

    await WordbankService(_sections(), repo, settings).add_topic_words(user_id=1, topic_number=1)  # type: ignore[arg-type]
    await _typing_service(settings, repo, typed="ja", translated="я").save_pending_as_card(pending_id="p1", user_id=1)

    assert list(repo.rows) == [(1, "RU", "PL", "я")]


@pytest.mark.asyncio
async def test_wordbank_cards_start_in_the_recognition_direction() -> None:
    from vocab_bot.persistence import Card
    from vocab_bot.services.reviews import build_due_card, direction_for_card

    settings = _settings()
    repo = FakeCardRepo()
    await WordbankService(_sections(), repo, settings).add_topic_words(user_id=1, topic_number=1)  # type: ignore[arg-type]

    (key, row) = next(iter(repo.rows.items()))
    card = Card(1, key[0], key[3], row["target_text"], key[1], key[2], 2.5, 0.0, row["repetition"], datetime.now(UTC))
    due = build_due_card(card, direction_for_card(card, settings.native_lang))

    # A freshly added topic word is asked foreign-first, like any other new card.
    assert (due.prompt_text, due.prompt_lang) == ("ja", "PL")
    assert (due.answer_text, due.answer_lang) == ("я", "RU")


@pytest.mark.asyncio
async def test_a_second_translation_joins_the_topic_word_instead_of_replacing_it() -> None:
    settings = _settings()
    repo = FakeCardRepo()
    await WordbankService(_sections(), repo, settings).add_topic_words(user_id=1, topic_number=1)  # type: ignore[arg-type]
    repo.rows[(1, "RU", "PL", "я")]["target_text"] = "ja (zaimek)"
    repo.rows[(1, "RU", "PL", "я")]["repetition"] = 5

    # The user types a different Polish word that DeepL renders back as the same Russian one.
    await _typing_service(settings, repo, typed="ja", translated="я").save_pending_as_card(pending_id="p1", user_id=1)

    row = repo.rows[(1, "RU", "PL", "я")]
    assert list(repo.rows) == [(1, "RU", "PL", "я")]
    assert row["target_text"] == "ja (zaimek)"  # same word, so the annotated form is kept
    assert row["repetition"] == 5
