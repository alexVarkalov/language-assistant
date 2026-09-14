from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta

from telegram import Update
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
    settings_menu_keyboard,
    settings_menu_text,
)
from vocab_bot.i18n import t
from vocab_bot.services import TranslationService, UserService


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
    user_service: UserService = context.application.bot_data["user_service"]

    data = query.data
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
