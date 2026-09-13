from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.helpers import make_user
from tests.webapi.conftest import auth_header


@pytest.mark.asyncio
async def test_me_returns_user_and_deployment_facts(app: FastAPI) -> None:
    app.state.user_service.record_seen.return_value = make_user(
        telegram_id=123, preferred_locale="ru", timezone="Europe/Warsaw"
    )
    app.state.review_service.count_due_for_user.return_value = 12

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/me", headers=auth_header())

    assert response.status_code == 200
    assert response.json() == {
        "telegram_id": 123,
        "locale": "ru",
        "timezone": "Europe/Warsaw",
        "lang_pair": {"source": "PL", "target": "RU"},
        "due_count": 12,
        "short_review_interval_minutes": 10,
    }
    app.state.review_service.count_due_for_user.assert_awaited_once_with(user_id=123)


@pytest.mark.asyncio
async def test_me_defaults_timezone_to_utc_and_locale_from_language_code(app: FastAPI) -> None:
    app.state.user_service.record_seen.return_value = make_user(
        timezone=None, preferred_locale=None, language_code="ru"
    )
    app.state.review_service.count_due_for_user.return_value = 0

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.get("/api/me", headers=auth_header())).json()

    assert body["timezone"] == "UTC"
    assert body["locale"] == "ru"
