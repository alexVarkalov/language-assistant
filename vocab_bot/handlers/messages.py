from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import (
    format_langs,
    record_user_seen,
    user_has_access,
    user_lang_pair,
    user_locale,
)
from vocab_bot.i18n import t
from vocab_bot.services import ReviewService, TranslationService
from vocab_bot.translate import TranslationError

logger = logging.getLogger(__name__)


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    user = await record_user_seen(update, context)
    if user is None:
        return
    locale = user_locale(user)
    if not user_has_access(user, settings):
        await update.effective_message.reply_text(t(locale, "access_disabled"))
        return

    source_message_id = update.effective_message.message_id
    text = update.effective_message.text or ""
    if not text.strip():
        return

    review_service: ReviewService = context.application.bot_data["review_service"]
    awaiting_card = await review_service.get_awaiting_card_for_user(user_id=update.effective_user.id)
    if awaiting_card is not None:
        awaiting_messages: dict[tuple[int, int], int] = context.application.bot_data.setdefault(
            "awaiting_review_messages", {}
        )
        previous_prompt_message_id = awaiting_messages.pop((update.effective_user.id, awaiting_card.id), None)
        if previous_prompt_message_id is not None:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_user.id, message_id=previous_prompt_message_id
                )
            except Exception:
                pass
        guess = html.escape(text.strip())
        await update.effective_message.reply_html(
            t(
                locale,
                "review_prompt_with_guess",
                lang_pair=html.escape(format_langs(awaiting_card.source_lang, awaiting_card.target_lang)),
                prompt=html.escape(awaiting_card.target_text),
                guess=guess,
                answer=html.escape(awaiting_card.source_text),
            ),
            reply_markup=_grade_keyboard(awaiting_card.id, locale),
        )
        return

    translation_service: TranslationService = context.application.bot_data["translation_service"]
    client = context.application.bot_data["http_client"]
    source_lang, target_lang = user_lang_pair(user, settings)

    try:
        pending = await translation_service.translate_and_store_pending(
            user_id=update.effective_user.id,
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            client=client,
        )
    except TranslationError as exc:
        await update.effective_message.reply_text(t(locale, "translation_could_not", error=exc))
        return
    except Exception:
        logger.exception("translate failed")
        await update.effective_message.reply_text(t(locale, "translation_failed_unexpectedly"))
        return

    src = html.escape(pending.source_text)
    pair = html.escape(format_langs(pending.source_lang, pending.target_lang))
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    for idx, option in enumerate(pending.target_options):
        label = option if len(option) <= 45 else f"{option[:42]}..."
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    t(locale, "button_save", label=label),
                    callback_data=f"save:{pending.id}:{idx}:{source_message_id}",
                )
            ]
        )
    keyboard_rows.append([InlineKeyboardButton(t(locale, "button_dismiss"), callback_data=f"dismiss:{pending.id}")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    options_lines = "\n".join(
        [f"{idx + 1}. <b>{html.escape(option)}</b>" for idx, option in enumerate(pending.target_options)]
    )

    await update.effective_message.reply_html(
        t(locale, "translation_choose", source=src, pair=pair, options=options_lines),
        reply_markup=keyboard,
    )


def _grade_keyboard(card_id: int, locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(locale, "button_again"), callback_data=f"grade:{card_id}:0"),
                InlineKeyboardButton(t(locale, "button_good"), callback_data=f"grade:{card_id}:3"),
                InlineKeyboardButton(t(locale, "button_easy"), callback_data=f"grade:{card_id}:5"),
            ]
        ]
    )
