from __future__ import annotations

import logging
import sys

import httpx
from telegram import MenuButtonWebApp, Update, WebAppInfo
from telegram.ext import Application

from vocab_bot.config import Settings, load_dotenv_if_present
from vocab_bot.db import Database
from vocab_bot.handlers import due_poll, register_handlers
from vocab_bot.i18n import DEFAULT_LOCALE, t
from vocab_bot.repositories import CardRepository, PendingRepository, UserRepository
from vocab_bot.services import DueNotificationService, ReviewService, TranslationService, UserService
from vocab_bot.services.wordbank import WordbankService
from vocab_bot.wordbank import load_wordbank

logger = logging.getLogger(__name__)


async def _configure_menu_button(application: Application, settings: Settings) -> None:
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text=t(DEFAULT_LOCALE, "menu_button_app"),
                web_app=WebAppInfo(url=settings.webapp_url),
            )
        )
    except Exception:
        logger.exception("failed to set Mini App menu button")


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
    application.bot_data["review_service"] = ReviewService(
        card_repo,
        short_interval_minutes=settings.short_review_interval_minutes,
    )
    if settings.wordbank_path is not None:
        sections = load_wordbank(settings.wordbank_path)
        application.bot_data["wordbank_service"] = WordbankService(sections, card_repo, settings)
    application.bot_data["due_notification_service"] = DueNotificationService(
        card_repo,
        user_repo,
        admin_user_ids=settings.admin_user_ids,
        cooldown_minutes=settings.due_notify_cooldown_minutes,
    )
    application.job_queue.run_repeating(
        due_poll,
        interval=settings.due_poll_interval,
        first=10,
        name="due_poll",
    )
    await _configure_menu_button(application, settings)


async def _post_shutdown(application: Application) -> None:
    client: httpx.AsyncClient | None = application.bot_data.pop("http_client", None)
    if client is not None:
        await client.aclose()


def main() -> None:
    load_dotenv_if_present()
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
