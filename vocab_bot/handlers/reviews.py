from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from vocab_bot.handlers.common import format_langs
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

    seen_users: set[int] = set()
    for card in due:
        if card.user_id in seen_users:
            continue
        seen_users.add(card.user_id)

        if not await user_service.is_allowed(card.user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=card.user_id,
                text=(
                    f"<b>Review time</b> ({format_langs(card.source_lang, card.target_lang)})\n"
                    f"What is the <b>{card.source_lang}</b> word for:\n<b>{html.escape(card.target_text)}</b>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"Reveal {card.source_lang} word",
                                callback_data=f"reveal:{card.id}",
                            )
                        ]
                    ]
                ),
            )
            await review_service.mark_awaiting(card_id=card.id, user_id=card.user_id, awaiting=True)
        except Exception:
            logger.exception("due poll: failed to notify user_id=%s card_id=%s", card.user_id, card.id)
