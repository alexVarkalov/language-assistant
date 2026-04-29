from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from vocab_bot.handlers.common import format_langs
from vocab_bot.i18n import DEFAULT_LOCALE, resolve_user_locale, t
from vocab_bot.services import ReviewService, UserService

logger = logging.getLogger(__name__)


async def due_poll(context: ContextTypes.DEFAULT_TYPE) -> None:
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
            sent = await context.bot.send_message(
                chat_id=card.user_id,
                text=t(
                    locale,
                    "due_review_time",
                    lang_pair=format_langs(card.source_lang, card.target_lang),
                    source_lang=card.source_lang,
                    target_text=html.escape(card.target_text),
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                t(locale, "due_reveal", source_lang=card.source_lang),
                                callback_data=f"reveal:{card.id}",
                            )
                        ]
                    ]
                ),
            )
            awaiting_messages[(card.user_id, card.id)] = sent.message_id
            await review_service.mark_awaiting(card_id=card.id, user_id=card.user_id, awaiting=True)
        except Exception:
            logger.exception("due poll: failed to notify user_id=%s card_id=%s", card.user_id, card.id)
