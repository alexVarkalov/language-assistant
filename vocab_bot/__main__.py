from __future__ import annotations

import logging
import os
import sys

import httpx
from telegram import Update
from telegram.ext import Application

from vocab_bot.config import Settings
from vocab_bot.db import Database
from vocab_bot.handlers import due_poll, register_handlers
from vocab_bot.repositories import CardRepository, PendingRepository, UserRepository
from vocab_bot.services import ReviewService, TranslationService, UserService


def _load_dotenv_if_present() -> None:
    """Minimal .env loader to avoid an extra dependency; ignores parse errors."""
    path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


async def _post_init(application: Application) -> None:
    db: Database = application.bot_data["db"]
    await db.init()

    application.bot_data["http_client"] = httpx.AsyncClient()
    application.job_queue.scheduler.configure(timezone="UTC")

    settings: Settings = application.bot_data["settings"]
    user_repo = UserRepository(db)
    pending_repo = PendingRepository(db)
    card_repo = CardRepository(db)
    application.bot_data["user_service"] = UserService(user_repo)
    application.bot_data["translation_service"] = TranslationService(settings, pending_repo, card_repo)
    application.bot_data["review_service"] = ReviewService(card_repo)
    application.job_queue.run_repeating(
        due_poll,
        interval=settings.due_poll_interval,
        first=10,
        name="due_poll",
    )


async def _post_shutdown(application: Application) -> None:
    client: httpx.AsyncClient | None = application.bot_data.pop("http_client", None)
    if client is not None:
        await client.aclose()


def main() -> None:
    _load_dotenv_if_present()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        settings = Settings.from_env()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc

    application = (
        Application.builder().token(settings.bot_token).post_init(_post_init).post_shutdown(_post_shutdown).build()
    )

    application.bot_data["settings"] = settings
    application.bot_data["db"] = Database(settings.database_url)

    register_handlers(application)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
