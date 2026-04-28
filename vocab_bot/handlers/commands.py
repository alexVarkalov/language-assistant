from __future__ import annotations

import html

from telegram import Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import (
    format_langs,
    format_user_datetime,
    format_user_display,
    format_user_timezone,
    parse_target_user_id,
    record_user_seen,
    require_admin,
    user_has_access,
    user_lang_pair,
    user_locale,
)
from vocab_bot.handlers.menu import settings_menu_keyboard, settings_menu_text
from vocab_bot.i18n import SUPPORTED_LOCALES, t
from vocab_bot.services import UserService


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    user = await record_user_seen(update, context)
    if user is None:
        return
    locale = user_locale(user)
    if not user_has_access(user, settings):
        await update.effective_message.reply_text(t(locale, "access_disabled"))
        return

    source_lang, target_lang = user_lang_pair(user, settings)
    await update.effective_message.reply_html(
        "\n".join(
            [
                t(locale, "start_title"),
                t(
                    locale,
                    "start_intro",
                    source_lang=html.escape(source_lang),
                    target_lang=html.escape(target_lang),
                ),
                "",
                t(locale, "start_review"),
                "",
                t(locale, "start_grading"),
                t(locale, "start_lang_pair", lang_pair=html.escape(format_langs(source_lang, target_lang))),
                t(locale, "start_set_pair"),
                t(locale, "start_set_timezone"),
                t(locale, "start_timezone", timezone=html.escape(format_user_timezone(user))),
                t(locale, "start_locale", locale_label=html.escape(user_locale(user))),
                t(locale, "start_set_locale"),
                t(locale, "start_translator", translator=html.escape(settings.translator)),
            ]
        )
    )


async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return

    settings: Settings = context.application.bot_data["settings"]
    user_service: UserService = context.application.bot_data["user_service"]
    users = await user_service.list_recent(limit=50)
    if not users:
        await update.effective_message.reply_text("No users recorded yet.")
        return

    lines = ["Recent users:"]
    for user in users:
        status = "allowed" if user.is_allowed else "blocked"
        display = format_user_display(user)
        timezone = format_user_timezone(user)
        last_seen = format_user_datetime(user.last_seen_at, user)
        user_source = user.preferred_source_lang or settings.source_lang
        user_target = user.preferred_target_lang or settings.target_lang
        lines.append(
            f"{user.telegram_id} - {display} - {status} - {timezone} - "
            f"{format_langs(user_source, user_target)} - last seen {last_seen}"
        )

    await update.effective_message.reply_text("\n".join(lines))


async def cmd_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    if not context.args:
        await update.effective_message.reply_text(t(locale, "timezone_current", timezone=format_user_timezone(user)))
        return

    timezone = context.args[0].strip()
    user_service: UserService = context.application.bot_data["user_service"]
    try:
        updated_user = await user_service.set_timezone(update.effective_user.id, timezone)
    except ValueError:
        await update.effective_message.reply_text(t(locale, "timezone_invalid"))
        return

    await update.effective_message.reply_text(
        t(locale, "timezone_updated", timezone=format_user_timezone(updated_user))
    )


async def cmd_languages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    current_source, current_target = user_lang_pair(user, settings)
    allowed = ", ".join(sorted(settings.available_languages))
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            t(
                locale,
                "languages_current",
                lang_pair=format_langs(current_source, current_target),
                allowed=allowed,
            )
        )
        return

    source_lang = context.args[0].strip().upper()
    target_lang = context.args[1].strip().upper()
    invalid = [code for code in (source_lang, target_lang) if code not in settings.available_languages]
    if invalid:
        await update.effective_message.reply_text(
            t(locale, "languages_unsupported", invalid=", ".join(invalid), allowed=allowed)
        )
        return

    user_service: UserService = context.application.bot_data["user_service"]
    await user_service.set_languages(update.effective_user.id, source_lang, target_lang)
    await update.effective_message.reply_text(
        t(locale, "languages_updated", lang_pair=format_langs(source_lang, target_lang))
    )


async def cmd_locale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    supported = ", ".join(SUPPORTED_LOCALES)
    if not context.args:
        await update.effective_message.reply_text(t(locale, "locale_current", locale_label=locale, supported=supported))
        return

    requested = context.args[0].strip().lower()
    if requested not in SUPPORTED_LOCALES:
        await update.effective_message.reply_text(
            t(locale, "locale_unsupported", locale_label=requested, supported=supported)
        )
        return

    user_service: UserService = context.application.bot_data["user_service"]
    updated_user = await user_service.set_locale(update.effective_user.id, requested)
    updated_locale = user_locale(updated_user)
    await update.effective_message.reply_text(t(updated_locale, "locale_updated", locale_label=updated_locale))


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    await update.effective_message.reply_html(
        settings_menu_text(locale, user, settings),
        reply_markup=settings_menu_keyboard(locale),
    )


async def cmd_allow_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_user_access(update, context, allowed=True)


async def cmd_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_user_access(update, context, allowed=False)


async def _set_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE, *, allowed: bool) -> None:
    if not await require_admin(update, context):
        return

    if update.effective_message is None:
        return

    target_id = parse_target_user_id(context.args)
    if target_id is None:
        command = "allow_user" if allowed else "block_user"
        await update.effective_message.reply_text(f"Usage: /{command} <telegram_user_id>")
        return

    settings: Settings = context.application.bot_data["settings"]
    if not allowed and target_id in settings.admin_user_ids:
        await update.effective_message.reply_text(
            "Admin users cannot be blocked while they are listed in ADMIN_USER_IDS."
        )
        return

    user_service: UserService = context.application.bot_data["user_service"]
    user = await user_service.set_allowed(target_id, allowed)
    status = "allowed" if user.is_allowed else "blocked"
    await update.effective_message.reply_text(f"User {user.telegram_id} is now {status}.")
