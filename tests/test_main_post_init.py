"""
`_post_init` wires the bot up: it is the bot's half of the dependency graph, and it is also where the
scheduler is easy to break.

python-telegram-bot registers its own executor on the JobQueue's APScheduler instance, and
`scheduler.configure()` replaces the whole configuration rather than merging into it. Calling it
here therefore silently detaches that executor: jobs still run, on a default executor APScheduler
creates for itself, but `JobQueue.stop()` reaches into the detached one and the bot dies with an
AttributeError on every shutdown. These tests pin the wiring down by actually starting and stopping
the job queue.

The rest of the module covers the `bot_data` contract the handlers depend on. Handlers reach into
`bot_data` by string key and services are constructed here by hand, so a renamed key or a constructor
argument that is passed in one entry point and forgotten in the other type-checks, passes every
handler test (they inject their own mocks) and only fails in production. `native_lang` is the live
example: it has to be threaded through both `_post_init` and `webapi.app.create_app`.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from telegram.ext import Application

from vocab_bot import __main__ as main_module
from vocab_bot.config import Settings
from vocab_bot.services import DueNotificationService, ReviewService, TranslationService, UserService
from vocab_bot.services.wordbank import WordbankService
from vocab_bot.webapi.app import create_app


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


async def _build_application(settings: Settings) -> Application:
    """An application taken through `_post_init`, exactly as `main()` assembles it."""
    app = Application.builder().token(settings.bot_token).build()
    app.bot_data["settings"] = settings
    app.bot_data["db"] = AsyncMock()
    await main_module._post_init(app)
    return app


@pytest_asyncio.fixture(autouse=True)
def _no_menu_button(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_post_init` ends by calling Telegram; nothing here should touch the network."""
    monkeypatch.setattr(main_module, "_configure_menu_button", AsyncMock())


@pytest_asyncio.fixture
async def application() -> Application:
    app = await _build_application(_settings())
    try:
        yield app
    finally:
        client = app.bot_data.get("http_client")
        if client is not None:
            await client.aclose()


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


# The keys every handler reaches for. `bot_data` is a plain dict addressed by string, so nothing but a
# test notices when one is renamed or quietly dropped -- see vocab_bot/handlers/ for the consumers.
EXPECTED_BOT_DATA = {
    "settings": Settings,
    "db": AsyncMock,
    "http_client": httpx.AsyncClient,
    "user_service": UserService,
    "translation_service": TranslationService,
    "review_service": ReviewService,
    "due_notification_service": DueNotificationService,
}


@pytest.mark.asyncio
async def test_post_init_stashes_every_dependency_the_handlers_read(application: Application) -> None:
    assert set(application.bot_data) == set(EXPECTED_BOT_DATA)
    for key, expected_type in EXPECTED_BOT_DATA.items():
        assert isinstance(application.bot_data[key], expected_type), key


@pytest.mark.asyncio
async def test_post_init_skips_the_wordbank_service_when_no_wordbank_is_configured(
    application: Application,
) -> None:
    # /wordbank is the one conditional feature; its handler is only registered alongside the service.
    assert "wordbank_service" not in application.bot_data


@pytest.mark.asyncio
async def test_post_init_adds_the_wordbank_service_when_a_wordbank_is_configured(tmp_path: Path) -> None:
    words = [{"ru": "я", "pl": "ja", "ipa": "[ja]"}]
    sections = [{"title": "s", "topics": [{"number": 1, "title": "t", "words": words}]}]
    wordbank = tmp_path / "dict.json"
    wordbank.write_text(json.dumps(sections), encoding="utf-8")
    settings = dataclasses.replace(_settings(), wordbank_path=str(wordbank))

    app = await _build_application(settings)
    try:
        assert isinstance(app.bot_data["wordbank_service"], WordbankService)
    finally:
        await app.bot_data["http_client"].aclose()


@pytest.mark.asyncio
async def test_post_init_configures_the_review_service_from_settings(application: Application) -> None:
    review_service = application.bot_data["review_service"]

    # Private attributes, but a constructor argument that never arrives is invisible from the outside:
    # the service keeps working and simply reviews every card in a random direction.
    assert review_service._native_lang == _settings().native_lang
    assert review_service._short_interval_minutes == _settings().short_review_interval_minutes


@pytest.mark.asyncio
async def test_both_entry_points_configure_the_review_service_identically(application: Application) -> None:
    """The bot and the Mini App API build their own ReviewService from the same Settings.

    Nothing links the two constructions, so a new argument added to one is silently missing from the
    other and the same card is then asked in different directions depending on where it is reviewed.
    """
    api = create_app(_settings(), db=AsyncMock())
    async with api.router.lifespan_context(api):
        from_api = api.state.review_service

    from_bot = application.bot_data["review_service"]
    assert from_api._native_lang == from_bot._native_lang
    assert from_api._short_interval_minutes == from_bot._short_interval_minutes


@pytest.mark.asyncio
async def test_post_shutdown_closes_the_http_client(application: Application) -> None:
    client = application.bot_data["http_client"]

    await main_module._post_shutdown(application)

    assert client.is_closed
    # Popped as well as closed, so a second shutdown cannot double-close it.
    assert "http_client" not in application.bot_data
