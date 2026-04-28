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
    user_lang_pair,
    user_locale,
)
from vocab_bot.handlers.menu import (
    language_menu_keyboard,
    locale_menu_keyboard,
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
    if data.startswith("save:"):
        _, pending_id, option_index_raw = (data.split(":", maxsplit=2) + [None])[:3]
        option_index = int(option_index_raw) if option_index_raw and option_index_raw.isdigit() else None
        pending = await translation_service.save_pending_as_card(
            pending_id=pending_id,
            user_id=update.effective_user.id,
            option_index=option_index,
        )
        if pending is None:
            await query.edit_message_text(t(locale, "pending_expired"))
            return

        first_review = format_user_datetime(datetime.now(tz=UTC) + timedelta(minutes=10), user)
        await query.edit_message_text(
            t(
                locale,
                "pending_saved",
                source=pending.source_text,
                target=pending.target_text,
                first_review=first_review,
                lang_pair=format_langs(pending.source_lang, pending.target_lang),
            )
        )
        return

    if data.startswith("dismiss:"):
        pending_id = data.removeprefix("dismiss:")
        await translation_service.dismiss_pending(pending_id=pending_id, user_id=update.effective_user.id)
        await query.edit_message_text(t(locale, "pending_dismissed"))
        return

    if data.startswith("reveal:"):
        card_id = int(data.removeprefix("reveal:"))
        card = await review_service.get_card_for_user(card_id=card_id, user_id=update.effective_user.id)
        if card is None:
            await query.edit_message_text(t(locale, "review_missing"))
            return

        keyboard = _grade_keyboard(card.id, locale)
        src = html.escape(card.source_text)
        tgt = html.escape(card.target_text)
        await query.edit_message_text(
            t(
                locale,
                "review_prompt",
                lang_pair=html.escape(format_langs(card.source_lang, card.target_lang)),
                prompt=tgt,
                answer=src,
            ),
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

    if data == "menu:source":
        source_lang, _ = user_lang_pair(user, settings)
        await query.edit_message_text(
            t(locale, "menu_choose_source"),
            reply_markup=language_menu_keyboard(locale, settings.available_languages, source_lang, "source"),
        )
        return

    if data == "menu:target":
        _, target_lang = user_lang_pair(user, settings)
        await query.edit_message_text(
            t(locale, "menu_choose_target"),
            reply_markup=language_menu_keyboard(locale, settings.available_languages, target_lang, "target"),
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

    if data.startswith("menu:set_source:"):
        source_lang = data.removeprefix("menu:set_source:")
        if source_lang not in settings.available_languages:
            await query.answer(t(locale, "menu_invalid_language", code=source_lang), show_alert=True)
            return
        _, current_target = user_lang_pair(user, settings)
        updated_user = await user_service.set_languages(update.effective_user.id, source_lang, current_target)
        updated_locale = user_locale(updated_user)
        await query.edit_message_text(
            settings_menu_text(
                updated_locale,
                updated_user,
                settings,
                status_line=t(updated_locale, "menu_source_updated", code=source_lang),
            ),
            reply_markup=settings_menu_keyboard(updated_locale),
            parse_mode="HTML",
        )
        return

    if data.startswith("menu:set_target:"):
        target_lang = data.removeprefix("menu:set_target:")
        if target_lang not in settings.available_languages:
            await query.answer(t(locale, "menu_invalid_language", code=target_lang), show_alert=True)
            return
        current_source, _ = user_lang_pair(user, settings)
        updated_user = await user_service.set_languages(update.effective_user.id, current_source, target_lang)
        updated_locale = user_locale(updated_user)
        await query.edit_message_text(
            settings_menu_text(
                updated_locale,
                updated_user,
                settings,
                status_line=t(updated_locale, "menu_target_updated", code=target_lang),
            ),
            reply_markup=settings_menu_keyboard(updated_locale),
            parse_mode="HTML",
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
