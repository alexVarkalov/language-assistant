from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.i18n import resolve_user_locale, t, t_count
from vocab_bot.services import DueNotificationService

logger = logging.getLogger(__name__)


def due_summary_keyboard(locale: str, settings: Settings) -> InlineKeyboardMarkup | None:
    if settings.webapp_url is None:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(locale, "due_open_app"), web_app=WebAppInfo(url=settings.webapp_url))]]
    )


async def due_poll(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send one consolidated "N cards due" reminder per user, subject to the service's cool-down."""
    settings: Settings = context.application.bot_data["settings"]
    notifier: DueNotificationService = context.application.bot_data["due_notification_service"]
    try:
        summaries = await notifier.collect()
    except Exception:
        logger.exception("due poll: failed to collect due summaries")
        return

    for summary in summaries:
        user_id = summary.user.telegram_id
        locale = resolve_user_locale(summary.user)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=t_count(locale, "due_summary", summary.due_count),
                parse_mode="HTML",
                reply_markup=due_summary_keyboard(locale, settings),
            )
            await notifier.mark_notified(user_id)
        except Exception:
            logger.exception("due poll: failed to notify user_id=%s", user_id)
