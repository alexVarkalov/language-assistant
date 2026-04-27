from __future__ import annotations

import html

from telegram import Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import (
    ACCESS_DISABLED_MESSAGE,
    format_langs,
    format_user_datetime,
    format_user_display,
    format_user_timezone,
    parse_target_user_id,
    record_user_seen,
    require_admin,
    user_has_access,
    user_lang_pair,
)
from vocab_bot.services import UserService


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    user = await record_user_seen(update, context)
    if user is None:
        return
    if not user_has_access(user, settings):
        await update.effective_message.reply_text(ACCESS_DISABLED_MESSAGE)
        return

    await update.effective_message.reply_html(
        "<b>Vocabulary bot</b>\n"
        f"Send a word in <b>{html.escape(settings.source_lang)}</b> and I will translate it to "
        f"<b>{html.escape(settings.target_lang)}</b>.\n\n"
        "After each translation you can save the word to start spaced reviews "
        "(SM-2 style intervals).\n\n"
        "During a review I show the translation; reveal the word you are learning, "
        "then grade yourself with <i>Again</i>, <i>Good</i>, or <i>Easy</i>.\n"
        f"<code>Language pair: {html.escape(format_langs(*user_lang_pair(user, settings)))}</code>\n"
        "Set your pair with <code>/languages EN RU</code>.\n"
        f"Set your timezone with <code>/timezone Europe/Warsaw</code>.\n"
        f"<code>Timezone: {html.escape(format_user_timezone(user))}</code>\n"
        f"<code>Translator: {html.escape(settings.translator)}</code>"
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
    if not user_has_access(user, settings):
        await update.effective_message.reply_text(ACCESS_DISABLED_MESSAGE)
        return

    if not context.args:
        await update.effective_message.reply_text(
            f"Your timezone is {format_user_timezone(user)}.\nSet it with /timezone Europe/Warsaw"
        )
        return

    timezone = context.args[0].strip()
    user_service: UserService = context.application.bot_data["user_service"]
    try:
        updated_user = await user_service.set_timezone(update.effective_user.id, timezone)
    except ValueError:
        await update.effective_message.reply_text(
            "I do not recognize that timezone. Use an IANA name like Europe/Warsaw, Europe/Moscow, or UTC."
        )
        return

    await update.effective_message.reply_text(f"Timezone updated to {format_user_timezone(updated_user)}.")


async def cmd_languages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.effective_message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    user = await record_user_seen(update, context)
    if user is None:
        return
    if not user_has_access(user, settings):
        await update.effective_message.reply_text(ACCESS_DISABLED_MESSAGE)
        return

    current_source, current_target = user_lang_pair(user, settings)
    allowed = ", ".join(sorted(settings.available_languages))
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            f"Current pair: {format_langs(current_source, current_target)}\n"
            f"Allowed languages: {allowed}\n"
            "Set with /languages <SOURCE> <TARGET>, e.g. /languages EN RU"
        )
        return

    source_lang = context.args[0].strip().upper()
    target_lang = context.args[1].strip().upper()
    invalid = [code for code in (source_lang, target_lang) if code not in settings.available_languages]
    if invalid:
        await update.effective_message.reply_text(
            f"Unsupported language code(s): {', '.join(invalid)}.\nAllowed languages: {allowed}"
        )
        return

    user_service: UserService = context.application.bot_data["user_service"]
    await user_service.set_languages(update.effective_user.id, source_lang, target_lang)
    await update.effective_message.reply_text(f"Language pair updated to {format_langs(source_lang, target_lang)}.")


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
