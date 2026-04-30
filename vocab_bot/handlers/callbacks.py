from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import (
    format_langs,
    format_user_datetime,
    record_user_seen,
    user_has_access,
    user_locale,
)
from vocab_bot.handlers.menu import (
    locale_menu_keyboard,
    quick_language_pairs_keyboard,
    settings_menu_keyboard,
    settings_menu_text,
)
from vocab_bot.i18n import t
from vocab_bot.services import ReviewService, TranslationService, UserService


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    user = await record_user_seen(update, context)
    if user is None:
        return
    locale = user_locale(user)
    if not user_has_access(user, settings):
        await query.answer(t(locale, "access_disabled"), show_alert=True)
        return

    await query.answer()

    translation_service: TranslationService = context.application.bot_data["translation_service"]
    review_service: ReviewService = context.application.bot_data["review_service"]
    user_service: UserService = context.application.bot_data["user_service"]

    data = query.data
    awaiting_messages: dict[tuple[int, int], int] = context.application.bot_data.setdefault(
        "awaiting_review_messages", {}
    )
    awaiting_directions: dict[tuple[int, int], str] = context.application.bot_data.setdefault(
        "awaiting_review_directions", {}
    )
    if data.startswith("save:"):
        _, pending_id, option_index_raw, source_message_id_raw = (data.split(":", maxsplit=3) + [None, None])[:4]
        option_index = int(option_index_raw) if option_index_raw and option_index_raw.isdigit() else None
        source_message_id = (
            int(source_message_id_raw) if source_message_id_raw and source_message_id_raw.isdigit() else None
        )
        pending = await translation_service.save_pending_as_card(
            pending_id=pending_id,
            user_id=update.effective_user.id,
            option_index=option_index,
        )
        if pending is None:
            await query.edit_message_text(t(locale, "pending_expired"))
            return

        settings: Settings = context.application.bot_data["settings"]
        first_review = format_user_datetime(
            datetime.now(tz=UTC) + timedelta(minutes=settings.short_review_interval_minutes),
            user,
        )
        await query.edit_message_text(
            t(
                locale,
                "pending_saved",
                source=html.escape(pending.source_text),
                target=html.escape(pending.target_text),
                first_review=first_review,
                lang_pair=html.escape(format_langs(pending.source_lang, pending.target_lang)),
            ),
            parse_mode="HTML",
        )
        if source_message_id is not None:
            try:
                await context.bot.delete_message(chat_id=update.effective_user.id, message_id=source_message_id)
            except Exception:
                pass
        return

    if data.startswith("dismiss:"):
        pending_id = data.removeprefix("dismiss:")
        await translation_service.dismiss_pending(pending_id=pending_id, user_id=update.effective_user.id)
        await query.edit_message_text(t(locale, "pending_dismissed"))
        return

    if data.startswith("reveal:"):
        _, card_id_raw, direction = (data.split(":", maxsplit=2) + ["source"])[:3]
        card_id = int(card_id_raw)
        awaiting_messages.pop((update.effective_user.id, card_id), None)
        direction = awaiting_directions.pop((update.effective_user.id, card_id), direction)
        card = await review_service.get_card_for_user(card_id=card_id, user_id=update.effective_user.id)
        if card is None:
            await query.edit_message_text(t(locale, "review_missing"))
            return

        keyboard = _grade_keyboard(card.id, locale)
        if direction == "target":
            prompt = html.escape(card.source_text)
            answer = html.escape(card.target_text)
        else:
            prompt = html.escape(card.target_text)
            answer = html.escape(card.source_text)
        await query.edit_message_text(
            t(
                locale,
                "review_prompt",
                lang_pair=html.escape(format_langs(card.source_lang, card.target_lang)),
                prompt=prompt,
                answer=answer,
            ),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    if data.startswith("grade:"):
        _, card_id_raw, quality_raw = data.split(":", maxsplit=2)
        card_id = int(card_id_raw)
        awaiting_messages.pop((update.effective_user.id, card_id), None)
        awaiting_directions.pop((update.effective_user.id, card_id), None)
        quality = int(quality_raw)
        result = await review_service.apply_grade(card_id=card_id, user_id=update.effective_user.id, quality=quality)
        if result is None:
            await query.edit_message_text(t(locale, "review_missing"))
            return

        human_when = format_user_datetime(result.next_review_at, user)
        await query.edit_message_text(
            t(
                locale,
                "review_updated",
                next_review=html.escape(human_when),
                repetition=result.repetition,
                interval_days=result.interval_days,
                ease_factor=result.ease_factor,
            ),
            parse_mode="HTML",
        )
        return

    if data == "menu:open":
        await query.edit_message_text(
            settings_menu_text(locale, user, settings),
            reply_markup=settings_menu_keyboard(locale),
            parse_mode="HTML",
        )
        return

    if data == "menu:locale":
        await query.edit_message_text(
            t(locale, "menu_choose_locale"),
            reply_markup=locale_menu_keyboard(locale, user_locale(user)),
        )
        return

    if data == "menu:pair":
        await query.edit_message_text(
            t(locale, "quick_pair_choose"),
            reply_markup=quick_language_pairs_keyboard(locale),
        )
        return

    if data.startswith("menu:set_locale:"):
        requested_locale = data.removeprefix("menu:set_locale:")
        if requested_locale not in {"en", "ru"}:
            await query.answer(
                t(locale, "locale_unsupported", locale_label=requested_locale, supported="en, ru"),
                show_alert=True,
            )
            return
        updated_user = await user_service.set_locale(update.effective_user.id, requested_locale)
        updated_locale = user_locale(updated_user)
        await query.edit_message_text(
            settings_menu_text(
                updated_locale,
                updated_user,
                settings,
                status_line=t(updated_locale, "locale_updated", locale_label=updated_locale),
            ),
            reply_markup=settings_menu_keyboard(updated_locale),
            parse_mode="HTML",
        )
        return

    if data.startswith("menu:set_pair:"):
        pair_data = data.removeprefix("menu:set_pair:")
        source_lang, _, target_lang = pair_data.partition(":")
        source_lang = source_lang.strip().upper()
        target_lang = target_lang.strip().upper()
        invalid = [code for code in (source_lang, target_lang) if code not in settings.available_languages]
        if invalid:
            await query.answer(
                t(
                    locale,
                    "languages_unsupported",
                    invalid=", ".join(invalid),
                    allowed=", ".join(sorted(settings.available_languages)),
                ),
                show_alert=True,
            )
            return
        updated_user = await user_service.set_languages(update.effective_user.id, source_lang, target_lang)
        updated_locale = user_locale(updated_user)
        await query.edit_message_text(
            t(updated_locale, "quick_pair_updated", lang_pair=format_langs(source_lang, target_lang))
        )
        return


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
