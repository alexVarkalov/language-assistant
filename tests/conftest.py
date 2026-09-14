from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _webapp_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """WEBAPP_URL is mandatory for Settings.from_env(); tests that check its absence delenv it explicitly."""
    monkeypatch.setenv("WEBAPP_URL", "https://vocab.example.com")
