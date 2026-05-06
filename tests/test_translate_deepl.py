from __future__ import annotations

import httpx
import pytest

from vocab_bot.translate import (
    DEEPL_FREE_URL,
    DEEPL_PRO_URL,
    TranslationError,
    _deepl_error_detail,
    _deepl_options,
)


def test_deepl_error_detail_empty_body() -> None:
    response = httpx.Response(500, text="")
    assert _deepl_error_detail(response) == "empty response body"


def test_deepl_error_detail_falls_back_to_raw_text_when_not_json() -> None:
    response = httpx.Response(400, content=b"not json")
    assert _deepl_error_detail(response) == "not json"


@pytest.mark.asyncio
async def test_deepl_options_auto_includes_free_detail_when_pro_says_api_free() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if str(request.url) == DEEPL_FREE_URL:
            return httpx.Response(403, json={"message": "Invalid auth key"})
        if str(request.url) == DEEPL_PRO_URL:
            return httpx.Response(403, json={"message": "Please use api-free.deepl.com"})
        return httpx.Response(500, text="unexpected url")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(TranslationError, match="only works on the Free API host"):
            await _deepl_options(
                "hello",
                "EN",
                "RU",
                "key",
                client,
                plan="auto",
            )

    assert calls == [DEEPL_FREE_URL, DEEPL_PRO_URL]


@pytest.mark.asyncio
async def test_deepl_options_pro_plan_rejects_free_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DEEPL_PRO_URL:
            return httpx.Response(403, json={"message": "Please use api-free.deepl.com"})
        return httpx.Response(500, text="unexpected url")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(TranslationError, match="Free API only"):
            await _deepl_options(
                "hello",
                "EN",
                "RU",
                "key",
                client,
                plan="pro",
            )


@pytest.mark.asyncio
async def test_deepl_options_free_endpoint_can_request_paid_host() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DEEPL_FREE_URL:
            return httpx.Response(403, json={"message": "Please use api.deepl.com for your plan"})
        return httpx.Response(500, text="unexpected url")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(TranslationError, match="use the paid API host"):
            await _deepl_options(
                "hello",
                "EN",
                "RU",
                "key",
                client,
                plan="free",
            )


@pytest.mark.asyncio
async def test_deepl_options_success_normalizes_and_limits() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == DEEPL_FREE_URL
        return httpx.Response(
            200,
            json={
                "translations": [
                    {"text": "  Hello  "},
                    {"text": "hello"},
                    {"text": "Hi"},
                    {"text": " "},
                    {"text": "Hey"},
                    {"text": "Yo"},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        options = await _deepl_options(
            "hello",
            "EN",
            "RU",
            "key",
            client,
            plan="free",
        )

    assert options == ["Hello", "Hi", "Hey"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "error_match"),
    [
        ({"translations": []}, "no translations"),
        ({"translations": [{"text": "   "}]}, "empty translation options"),
    ],
)
async def test_deepl_options_invalid_payload_raises(payload: dict[str, object], error_match: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == DEEPL_FREE_URL
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(TranslationError, match=error_match):
            await _deepl_options(
                "hello",
                "EN",
                "RU",
                "key",
                client,
                plan="free",
            )
