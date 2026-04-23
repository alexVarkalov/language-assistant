from __future__ import annotations

import html
import logging
import uuid
from datetime import UTC, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from vocab_bot.config import Settings
from vocab_bot.db import Database, PendingTranslation
from vocab_bot.srs import SrsState, next_review_datetime
from vocab_bot.translate import TranslationError, translate_text

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _format_langs(settings: Settings) -> str:
    return f"{settings.source_lang}→{settings.target_lang}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    await update.effective_message.reply_html(
        "<b>Vocabulary bot</b>\n"
        f"Send a word in <b>{html.escape(settings.source_lang)}</b> and I will translate it to "
        f"<b>{html.escape(settings.target_lang)}</b>.\n\n"
        "After each translation you can save the word to start spaced reviews "
        "(SM-2 style intervals).\n\n"
        "During a review I show the translation; reveal the word you are learning, "
        "then grade yourself with <i>Again</i>, <i>Good</i>, or <i>Easy</i>.\n"
        f"<code>Translator: {html.escape(settings.translator)}</code>"
    )


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    db: Database = context.application.bot_data["db"]
    client = context.application.bot_data["http_client"]

    text = update.effective_message.text or ""
    if not text.strip():
        return

    try:
        translated = await translate_text(
            text=text,
            source_lang=settings.source_lang,
            target_lang=settings.target_lang,
            translator=settings.translator,
            deepl_api_key=settings.deepl_api_key,
            deepl_plan=settings.deepl_plan,
            client=client,
        )
    except TranslationError as exc:
        await update.effective_message.reply_text(f"Could not translate: {exc}")
        return
    except Exception:
        logger.exception("translate failed")
        await update.effective_message.reply_text("Translation failed unexpectedly. Try again later.")
        return

    pending_id = uuid.uuid4().hex
    pending = PendingTranslation(
        id=pending_id,
        user_id=update.effective_user.id,
        source_lang=settings.source_lang,
        target_lang=settings.target_lang,
        source_text=text.strip(),
        target_text=translated,
    )
    await db.insert_pending(pending)

    src = html.escape(pending.source_text)
    tgt = html.escape(translated)
    pair = html.escape(_format_langs(settings))

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Save & learn", callback_data=f"save:{pending_id}"),
                InlineKeyboardButton("Dismiss", callback_data=f"dismiss:{pending_id}"),
            ]
        ]
    )

    await update.effective_message.reply_html(
        f"<b>{src}</b> ({pair})\n<b>{tgt}</b>",
        reply_markup=keyboard,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return

    await query.answer()

    settings: Settings = context.application.bot_data["settings"]
    db: Database = context.application.bot_data["db"]

    data = query.data
    if data.startswith("save:"):
        pending_id = data.removeprefix("save:")
        pending = await db.get_pending(pending_id, update.effective_user.id)
        if pending is None:
            await query.edit_message_text("That suggestion expired. Send the word again.")
            return

        first_review = _now() + timedelta(minutes=10)
        await db.upsert_card(
            user_id=pending.user_id,
            source_lang=pending.source_lang,
            target_lang=pending.target_lang,
            source_text=pending.source_text,
            target_text=pending.target_text,
            ease_factor=2.5,
            interval_days=0.0,
            repetition=0,
            next_review_at=first_review,
        )
        await db.delete_pending(pending_id, pending.user_id)

        await query.edit_message_text(
            f"Saved “{pending.source_text}” → “{pending.target_text}”. "
            f"First review in ~10 minutes ({_format_langs(settings)})."
        )
        return

    if data.startswith("dismiss:"):
        pending_id = data.removeprefix("dismiss:")
        await db.delete_pending(pending_id, update.effective_user.id)
        await query.edit_message_text("Okay — not saved.")
        return

    if data.startswith("reveal:"):
        card_id = int(data.removeprefix("reveal:"))
        card = await db.get_card(card_id, update.effective_user.id)
        if card is None:
            await query.edit_message_text("This review card no longer exists.")
            return

        keyboard = _grade_keyboard(card.id)
        src = html.escape(card.source_text)
        tgt = html.escape(card.target_text)
        await query.edit_message_text(
            f"<b>Review</b> ({html.escape(_format_langs(settings))})\n"
            f"Prompt: <b>{tgt}</b>\n"
            f"Answer: <b>{src}</b>\n\n"
            "How hard was it?",
            reply_markup=keyboard,
        )
        return

    if data.startswith("grade:"):
        _, card_id_raw, quality_raw = data.split(":", maxsplit=2)
        card_id = int(card_id_raw)
        quality = int(quality_raw)
        card = await db.get_card(card_id, update.effective_user.id)
        if card is None:
            await query.edit_message_text("This review card no longer exists.")
            return

        before = SrsState(card.ease_factor, card.interval_days, card.repetition)
        when, after = next_review_datetime(before, quality, _now())

        await db.update_card_srs(
            card_id=card.id,
            user_id=card.user_id,
            ease_factor=after.ease_factor,
            interval_days=after.interval_days,
            repetition=after.repetition,
            next_review_at=when,
        )

        human_when = when.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
        await query.edit_message_text(
            "Updated schedule.\n"
            f"Next review: <b>{html.escape(human_when)}</b>\n"
            f"Repetitions: {after.repetition}, interval: {after.interval_days:.4f} days, EF: {after.ease_factor:.2f}",
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


async def due_poll(context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.application.bot_data["db"]
    settings: Settings = context.application.bot_data["settings"]

    try:
        due = await db.list_due_cards(limit=50)
    except Exception:
        logger.exception("due poll: failed to list cards")
        return

    seen_users: set[int] = set()
    for card in due:
        if card.user_id in seen_users:
            continue
        seen_users.add(card.user_id)

        try:
            await context.bot.send_message(
                chat_id=card.user_id,
                text=(
                    f"<b>Review time</b> ({_format_langs(settings)})\n"
                    f"What is the <b>{settings.source_lang}</b> word for:\n<b>{html.escape(card.target_text)}</b>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"Reveal {settings.source_lang} word",
                                callback_data=f"reveal:{card.id}",
                            )
                        ]
                    ]
                ),
            )
            await db.mark_awaiting(card.id, card.user_id, True)
        except Exception:
            logger.exception("due poll: failed to notify user_id=%s card_id=%s", card.user_id, card.id)


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=r"^(save|dismiss|reveal|grade):"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))
