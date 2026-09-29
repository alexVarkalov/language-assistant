"""
`_post_init` wires the bot up, and it is also where the scheduler is easy to break.

python-telegram-bot registers its own executor on the JobQueue's APScheduler instance, and
`scheduler.configure()` replaces the whole configuration rather than merging into it. Calling it
here therefore silently detaches that executor: jobs still run, on a default executor APScheduler
creates for itself, but `JobQueue.stop()` reaches into the detached one and the bot dies with an
AttributeError on every shutdown. These tests pin the wiring down by actually starting and stopping
the job queue.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from telegram.ext import Application

from vocab_bot import __main__ as main_module
from vocab_bot.config import Settings


def _settings() -> Settings:
    return Settings(
        bot_token="123456:TEST",
        deepl_api_key="key",
        deepl_plan="free",
        translator="deepl",
        source_lang="RU",
        target_lang="PL",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        due_poll_interval=45,
        short_review_interval_minutes=10,
        admin_user_ids=frozenset(),
        wordbank_path=None,
        native_lang="RU",
        webapp_url="https://vocab.example.com",
    )


@pytest_asyncio.fixture
async def application(monkeypatch: pytest.MonkeyPatch) -> Application:
    """An application taken through `_post_init`, with the network calls stubbed out."""
    monkeypatch.setattr(main_module, "_configure_menu_button", AsyncMock())
    app = Application.builder().token(_settings().bot_token).build()
    app.bot_data["settings"] = _settings()
    app.bot_data["db"] = AsyncMock()
    await main_module._post_init(app)
    try:
        yield app
    finally:
        await app.bot_data["http_client"].aclose()


@pytest.mark.asyncio
async def test_the_job_queue_can_be_stopped_after_post_init(application: Application) -> None:
    await application.job_queue.start()

    # Used to raise AttributeError: 'AsyncIOExecutor' object has no attribute '_pending_futures'.
    await application.job_queue.stop(wait=True)

    assert not application.job_queue.scheduler.running


@pytest.mark.asyncio
async def test_post_init_leaves_the_schedulers_executor_attached(application: Application) -> None:
    job_queue = application.job_queue
    await job_queue.start()
    try:
        # Private attributes, but this identity is exactly what JobQueue.stop() depends on.
        assert job_queue.scheduler._executors["default"] is job_queue._executor
    finally:
        await job_queue.stop(wait=True)


@pytest.mark.asyncio
async def test_post_init_schedules_the_due_poll_job_in_utc(application: Application) -> None:
    assert str(application.job_queue.scheduler.timezone) == "UTC"
    assert [job.name for job in application.job_queue.jobs()] == ["due_poll"]
