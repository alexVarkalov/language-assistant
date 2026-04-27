from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import (
    ACCESS_DISABLED_MESSAGE,
    format_langs,
    format_user_datetime,
    record_user_seen,
    user_has_access,
)
from vocab_bot.services import ReviewService, TranslationService


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    user = await record_user_seen(update, context)
    if user is None:
        return
    if not user_has_access(user, settings):
        await query.answer(ACCESS_DISABLED_MESSAGE, show_alert=True)
        return

    await query.answer()

    translation_service: TranslationService = context.application.bot_data["translation_service"]
    review_service: ReviewService = context.application.bot_data["review_service"]

    data = query.data
    if data.startswith("save:"):
        _, pending_id, option_index_raw = (data.split(":", maxsplit=2) + [None])[:3]
        option_index = int(option_index_raw) if option_index_raw and option_index_raw.isdigit() else None
        pending = await translation_service.save_pending_as_card(
            pending_id=pending_id,
            user_id=update.effective_user.id,
            option_index=option_index,
        )
        if pending is None:
            await query.edit_message_text("That suggestion expired. Send the word again.")
            return

        first_review = format_user_datetime(datetime.now(tz=UTC) + timedelta(minutes=10), user)
        await query.edit_message_text(
            f"Saved “{pending.source_text}” → “{pending.target_text}”. "
            f"First review around {first_review} ({format_langs(pending.source_lang, pending.target_lang)})."
        )
        return

    if data.startswith("dismiss:"):
        pending_id = data.removeprefix("dismiss:")
        await translation_service.dismiss_pending(pending_id=pending_id, user_id=update.effective_user.id)
        await query.edit_message_text("Okay — not saved.")
        return

    if data.startswith("reveal:"):
        card_id = int(data.removeprefix("reveal:"))
        card = await review_service.get_card_for_user(card_id=card_id, user_id=update.effective_user.id)
        if card is None:
            await query.edit_message_text("This review card no longer exists.")
            return

        keyboard = _grade_keyboard(card.id)
        src = html.escape(card.source_text)
        tgt = html.escape(card.target_text)
        await query.edit_message_text(
            f"<b>Review</b> ({html.escape(format_langs(card.source_lang, card.target_lang))})\n"
            f"Prompt: <b>{tgt}</b>\n"
            f"Answer: <b>{src}</b>\n\n"
            "How hard was it?",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    if data.startswith("grade:"):
        _, card_id_raw, quality_raw = data.split(":", maxsplit=2)
        card_id = int(card_id_raw)
        quality = int(quality_raw)
        result = await review_service.apply_grade(card_id=card_id, user_id=update.effective_user.id, quality=quality)
        if result is None:
            await query.edit_message_text("This review card no longer exists.")
            return

        human_when = format_user_datetime(result.next_review_at, user)
        await query.edit_message_text(
            "Updated schedule.\n"
            f"Next review: <b>{html.escape(human_when)}</b>\n"
            "Repetitions: "
            f"{result.repetition}, interval: {result.interval_days:.4f} days, EF: {result.ease_factor:.2f}",
            parse_mode="HTML",
        )
        return


def _grade_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Again", callback_data=f"grade:{card_id}:0"),
                InlineKeyboardButton("Good", callback_data=f"grade:{card_id}:3"),
                InlineKeyboardButton("Easy", callback_data=f"grade:{card_id}:5"),
            ]
        ]
    )
