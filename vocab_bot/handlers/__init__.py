from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from vocab_bot.handlers.callbacks import on_callback
from vocab_bot.handlers.commands import (
    cmd_allow_user,
    cmd_block_user,
    cmd_languages,
    cmd_locale,
    cmd_start,
    cmd_timezone,
    cmd_users,
)
from vocab_bot.handlers.messages import on_text_message
from vocab_bot.handlers.reviews import due_poll

__all__ = ["due_poll", "register_handlers"]


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("languages", cmd_languages))
    application.add_handler(CommandHandler("langs", cmd_languages))
    application.add_handler(CommandHandler("locale", cmd_locale))
    application.add_handler(CommandHandler("localization", cmd_locale))
    application.add_handler(CommandHandler("timezone", cmd_timezone))
    application.add_handler(CommandHandler("tz", cmd_timezone))
    application.add_handler(CommandHandler("users", cmd_users))
    application.add_handler(CommandHandler("allow_user", cmd_allow_user))
    application.add_handler(CommandHandler("block_user", cmd_block_user))
    application.add_handler(CallbackQueryHandler(on_callback, pattern=r"^(save|dismiss|reveal|grade):"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))
