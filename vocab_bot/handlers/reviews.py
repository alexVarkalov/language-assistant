from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import format_langs
from vocab_bot.i18n import DEFAULT_LOCALE, resolve_user_locale, t
from vocab_bot.services import ReviewService, UserService, build_due_card, pick_direction

logger = logging.getLogger(__name__)


def due_review_keyboard(
    locale: str, card_id: int, direction: str, answer_lang: str, settings: Settings
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                t(locale, "due_reveal", answer_lang=answer_lang),
                callback_data=f"reveal:{card_id}:{direction}",
            )
        ]
    ]
    if settings.webapp_url is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    t(locale, "due_open_app"),
                    web_app=WebAppInfo(url=f"{settings.webapp_url}/?card={card_id}"),
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


async def due_poll(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    review_service: ReviewService = context.application.bot_data["review_service"]
    user_service: UserService = context.application.bot_data["user_service"]
    try:
        due = await review_service.list_due_cards(limit=50)
    except Exception:
        logger.exception("due poll: failed to list cards")
        return

    awaiting_messages: dict[tuple[int, int], int] = context.application.bot_data.setdefault(
        "awaiting_review_messages", {}
    )
    awaiting_directions: dict[tuple[int, int], str] = context.application.bot_data.setdefault(
        "awaiting_review_directions", {}
    )
    seen_users: set[int] = set()
    for card in due:
        if card.user_id in seen_users:
            continue
        seen_users.add(card.user_id)

        if not await user_service.is_allowed(card.user_id):
            continue

        try:
            user = await user_service.get_user(card.user_id)
            locale = DEFAULT_LOCALE if user is None else resolve_user_locale(user)
            due = build_due_card(card, pick_direction())
            sent = await context.bot.send_message(
                chat_id=card.user_id,
                text=t(
                    locale,
                    "due_review_time",
                    lang_pair=format_langs(card.source_lang, card.target_lang),
                    answer_lang=due.answer_lang,
                    prompt_text=html.escape(due.prompt_text),
                ),
                parse_mode="HTML",
                reply_markup=due_review_keyboard(locale, card.id, due.direction, due.answer_lang, settings),
            )
            awaiting_messages[(card.user_id, card.id)] = sent.message_id
            awaiting_directions[(card.user_id, card.id)] = due.direction
            await review_service.mark_awaiting(card_id=card.id, user_id=card.user_id, awaiting=True)
        except Exception:
            logger.exception("due poll: failed to notify user_id=%s card_id=%s", card.user_id, card.id)
