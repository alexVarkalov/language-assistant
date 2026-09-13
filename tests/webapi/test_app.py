from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.webapi.conftest import make_settings
from vocab_bot.webapi.app import create_app


@pytest.mark.asyncio
async def test_health_needs_no_auth(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_unknown_route_uses_error_envelope(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/nope")

    assert response.status_code == 404
    assert response.json()["error"] == "http_404"


@pytest.mark.asyncio
async def test_lifespan_builds_services_from_injected_db() -> None:
    db = AsyncMock()
    app = create_app(make_settings(), db=db)

    async with app.router.lifespan_context(app):
        assert app.state.db is db
        assert app.state.user_service is not None
        assert app.state.review_service is not None

    db.init.assert_awaited_once()


def test_docs_are_disabled() -> None:
    app = create_app(make_settings(), db=object())  # type: ignore[arg-type]
    assert app.docs_url is None
    assert app.openapi_url is None
