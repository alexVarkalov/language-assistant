from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.helpers import make_user
from tests.webapi.conftest import auth_header, make_init_data, make_settings


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_missing_authorization_header_is_401(app: FastAPI) -> None:
    async with _client(app) as client:
        response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["error"] == "missing_auth"
    app.state.user_service.record_seen.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_scheme_is_401(app: FastAPI) -> None:
    async with _client(app) as client:
        response = await client.get("/api/me", headers={"Authorization": f"Bearer {make_init_data()}"})

    assert response.status_code == 401
    assert response.json()["error"] == "missing_auth"


@pytest.mark.asyncio
async def test_invalid_signature_is_401(app: FastAPI) -> None:
    async with _client(app) as client:
        response = await client.get("/api/me", headers=auth_header(make_init_data(tamper_hash=True)))

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_init_data"
    app.state.user_service.record_seen.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocked_user_is_403(app: FastAPI) -> None:
    app.state.user_service.record_seen.return_value = make_user(is_allowed=False)

    async with _client(app) as client:
        response = await client.get("/api/me", headers=auth_header())

    assert response.status_code == 403
    assert response.json()["error"] == "access_disabled"


@pytest.mark.asyncio
async def test_admin_bypasses_block() -> None:
    from unittest.mock import AsyncMock

    from vocab_bot.webapi.app import create_app

    app = create_app(make_settings(admin_user_ids=frozenset({123})), db=object())  # type: ignore[arg-type]
    app.state.user_service = AsyncMock()
    app.state.review_service = AsyncMock()
    app.state.user_service.record_seen.return_value = make_user(telegram_id=123, is_allowed=False)
    app.state.review_service.count_due_for_user.return_value = 0

    async with _client(app) as client:
        response = await client.get("/api/me", headers=auth_header())

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_record_seen_receives_init_data_user_fields(app: FastAPI) -> None:
    app.state.user_service.record_seen.return_value = make_user(is_allowed=True)
    app.state.review_service.count_due_for_user.return_value = 0
    raw = make_init_data(user={"id": 555, "first_name": "Ala", "username": "ala", "language_code": "pl"})

    async with _client(app) as client:
        response = await client.get("/api/me", headers=auth_header(raw))

    assert response.status_code == 200
    app.state.user_service.record_seen.assert_awaited_once_with(
        telegram_id=555,
        username="ala",
        first_name="Ala",
        last_name=None,
        language_code="pl",
    )
