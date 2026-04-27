from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.persistence import BotUser
from vocab_bot.services import UserService

ACCESS_DISABLED_MESSAGE = "Your access to this bot is disabled. Contact the bot administrator if this looks wrong."


def format_langs(source_lang: str, target_lang: str) -> str:
    return f"{source_lang}→{target_lang}"


def user_lang_pair(user: BotUser, settings: Settings) -> tuple[str, str]:
    source = user.preferred_source_lang or settings.source_lang
    target = user.preferred_target_lang or settings.target_lang
    return source, target


def user_timezone(user: BotUser) -> ZoneInfo:
    if user.timezone is None:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(user.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def format_user_datetime(when: datetime, user: BotUser) -> str:
    timezone = user_timezone(user)
    return when.astimezone(timezone).strftime(f"%Y-%m-%d %H:%M {timezone.key}")


def format_user_timezone(user: BotUser) -> str:
    return user.timezone or "UTC"


async def record_user_seen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> BotUser | None:
    telegram_user = update.effective_user
    if telegram_user is None:
        return None

    user_service: UserService = context.application.bot_data["user_service"]
    return await user_service.record_seen(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        language_code=telegram_user.language_code,
    )


def user_has_access(user: BotUser, settings: Settings) -> bool:
    return user.is_allowed or user.telegram_id in settings.admin_user_ids


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user is None or update.effective_message is None:
        return False

    await record_user_seen(update, context)
    settings: Settings = context.application.bot_data["settings"]
    if update.effective_user.id in settings.admin_user_ids:
        return True

    await update.effective_message.reply_text("This command is only available to bot admins.")
    return False


def parse_target_user_id(args: list[str] | tuple[str, ...] | None) -> int | None:
    if not args:
        return None
    try:
        return int(args[0])
    except ValueError:
        return None


def format_user_display(user: BotUser) -> str:
    if user.username:
        return f"@{user.username}"
    full_name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return full_name or "no profile name"
