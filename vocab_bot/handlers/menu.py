from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from vocab_bot.config import Settings
from vocab_bot.handlers.common import format_langs, user_lang_pair, user_locale
from vocab_bot.i18n import SUPPORTED_LOCALES, t
from vocab_bot.persistence import BotUser


def settings_menu_text(locale: str, user: BotUser, settings: Settings, status_line: str | None = None) -> str:
    source_lang, target_lang = user_lang_pair(user, settings)
    lines = [
        t(locale, "menu_title"),
        t(locale, "menu_current_locale", locale_label=user_locale(user)),
        t(locale, "menu_current_pair", lang_pair=format_langs(source_lang, target_lang)),
        t(locale, "menu_hint"),
    ]
    if status_line:
        lines.append("")
        lines.append(status_line)
    return "\n".join(lines)


def settings_menu_keyboard(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(locale, "menu_button_locale"), callback_data="menu:locale")],
            [InlineKeyboardButton(t(locale, "menu_button_source"), callback_data="menu:source")],
            [InlineKeyboardButton(t(locale, "menu_button_target"), callback_data="menu:target")],
        ]
    )


def locale_menu_keyboard(locale: str, current_locale: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for candidate in SUPPORTED_LOCALES:
        marker = "✅ " if candidate == current_locale else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{marker}{candidate}",
                    callback_data=f"menu:set_locale:{candidate}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(t(locale, "menu_button_back"), callback_data="menu:open")])
    return InlineKeyboardMarkup(rows)


def language_menu_keyboard(
    locale: str,
    available_languages: frozenset[str],
    selected_lang: str,
    axis: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for code in sorted(available_languages):
        marker = "✅ " if code == selected_lang else ""
        rows.append([InlineKeyboardButton(f"{marker}{code}", callback_data=f"menu:set_{axis}:{code}")])
    rows.append([InlineKeyboardButton(t(locale, "menu_button_back"), callback_data="menu:open")])
    return InlineKeyboardMarkup(rows)
