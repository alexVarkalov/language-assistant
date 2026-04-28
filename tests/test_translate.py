from __future__ import annotations

import httpx
import pytest

from vocab_bot.translate import (
    TranslationError,
    _deepl_error_detail,
    _normalize_options,
    translate_text_options,
)


def test_normalize_options_deduplicates_and_limits() -> None:
    values = ["  Hello ", "hello", "Hi", "", "Hey", "Yo"]
    assert _normalize_options(values) == ["Hello", "Hi", "Hey"]


def test_deepl_error_detail_uses_json_message() -> None:
    response = httpx.Response(403, json={"message": "Invalid auth key"})
    assert _deepl_error_detail(response) == "Invalid auth key"


@pytest.mark.asyncio
async def test_translate_text_options_rejects_empty_text() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(TranslationError, match="empty text"):
            await translate_text_options(
                text="   ",
                source_lang="EN",
                target_lang="RU",
                translator="deepl",
                deepl_api_key="key",
                client=client,
            )


@pytest.mark.asyncio
async def test_translate_text_options_requires_deepl_key() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(TranslationError, match="must be configured"):
            await translate_text_options(
                text="hello",
                source_lang="EN",
                target_lang="RU",
                translator="deepl",
                deepl_api_key=None,
                client=client,
            )
