from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import (
    ACCESS_DISABLED_MESSAGE,
    format_langs,
    record_user_seen,
    user_has_access,
    user_lang_pair,
)
from vocab_bot.services import TranslationService
from vocab_bot.translate import TranslationError

logger = logging.getLogger(__name__)


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    user = await record_user_seen(update, context)
    if user is None:
        return
    if not user_has_access(user, settings):
        await update.effective_message.reply_text(ACCESS_DISABLED_MESSAGE)
        return

    translation_service: TranslationService = context.application.bot_data["translation_service"]
    client = context.application.bot_data["http_client"]
    source_lang, target_lang = user_lang_pair(user, settings)

    text = update.effective_message.text or ""
    if not text.strip():
        return

    try:
        pending = await translation_service.translate_and_store_pending(
            user_id=update.effective_user.id,
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            client=client,
        )
    except TranslationError as exc:
        await update.effective_message.reply_text(f"Could not translate: {exc}")
        return
    except Exception:
        logger.exception("translate failed")
        await update.effective_message.reply_text("Translation failed unexpectedly. Try again later.")
        return

    src = html.escape(pending.source_text)
    pair = html.escape(format_langs(pending.source_lang, pending.target_lang))
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    for idx, option in enumerate(pending.target_options):
        label = option if len(option) <= 45 else f"{option[:42]}..."
        keyboard_rows.append([InlineKeyboardButton(f"Save: {label}", callback_data=f"save:{pending.id}:{idx}")])
    keyboard_rows.append([InlineKeyboardButton("Dismiss", callback_data=f"dismiss:{pending.id}")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    options_lines = "\n".join(
        [f"{idx + 1}. <b>{html.escape(option)}</b>" for idx, option in enumerate(pending.target_options)]
    )

    await update.effective_message.reply_html(
        f"<b>{src}</b> ({pair})\nChoose a translation to save:\n{options_lines}",
        reply_markup=keyboard,
    )
