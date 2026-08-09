from __future__ import annotations

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from vocab_bot.config import Settings
from vocab_bot.handlers.common import record_user_seen, user_has_access, user_locale
from vocab_bot.i18n import t
from vocab_bot.services.wordbank import WordbankService
from vocab_bot.wordbank import Section, Topic

PREVIEW_WORD_LIMIT = 15


def sections_keyboard(sections: tuple[Section, ...]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(section.title, callback_data=f"wb:section:{idx}")] for idx, section in enumerate(sections)
    ]
    return InlineKeyboardMarkup(rows)


def topics_keyboard(locale: str, section: Section) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{topic.number}. {topic.title}", callback_data=f"wb:topic:{topic.number}")]
        for topic in section.topics
    ]
    rows.append([InlineKeyboardButton(t(locale, "menu_button_back"), callback_data="wb:sections")])
    return InlineKeyboardMarkup(rows)


def topic_preview_text(locale: str, topic: Topic) -> str:
    header = t(
        locale,
        "wordbank_topic_header",
        number=topic.number,
        title=html.escape(topic.title),
        count=len(topic.words),
    )
    lines = [header]
    preview = topic.words[:PREVIEW_WORD_LIMIT]
    for word in preview:
        lines.append(f"{html.escape(word.ru)} — {html.escape(word.pl)}")
    remaining = len(topic.words) - len(preview)
    if remaining > 0:
        lines.append(t(locale, "wordbank_topic_more", count=remaining))
    return "\n".join(lines)


def topic_action_keyboard(locale: str, section_idx: int, topic: Topic) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(locale, "wordbank_button_add_all", count=len(topic.words)),
                    callback_data=f"wb:add:{topic.number}",
                )
            ],
            [InlineKeyboardButton(t(locale, "menu_button_back"), callback_data=f"wb:section:{section_idx}")],
        ]
    )


async def cmd_wordbank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    wordbank_service: WordbankService = context.application.bot_data["wordbank_service"]
    await update.effective_message.reply_text(
        t(locale, "wordbank_sections_header"),
        reply_markup=sections_keyboard(wordbank_service.list_sections()),
    )


async def on_wordbank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    wordbank_service: WordbankService = context.application.bot_data["wordbank_service"]
    sections = wordbank_service.list_sections()
    data = query.data

    if data == "wb:sections":
        await query.edit_message_text(t(locale, "wordbank_sections_header"), reply_markup=sections_keyboard(sections))
        return

    if data.startswith("wb:section:"):
        idx = int(data.removeprefix("wb:section:"))
        section = sections[idx]
        await query.edit_message_text(
            t(locale, "wordbank_topics_header", title=html.escape(section.title)),
            reply_markup=topics_keyboard(locale, section),
        )
        return

    if data.startswith("wb:topic:"):
        number = int(data.removeprefix("wb:topic:"))
        found = wordbank_service.get_topic(number)
        if found is None:
            await query.edit_message_text(t(locale, "wordbank_topic_missing"))
            return
        section, topic = found
        section_idx = sections.index(section)
        await query.edit_message_text(
            topic_preview_text(locale, topic),
            reply_markup=topic_action_keyboard(locale, section_idx, topic),
            parse_mode="HTML",
        )
        return

    if data.startswith("wb:add:"):
        number = int(data.removeprefix("wb:add:"))
        result = await wordbank_service.add_topic_words(user_id=update.effective_user.id, topic_number=number)
        if result is None:
            await query.edit_message_text(t(locale, "wordbank_topic_missing"))
            return
        await query.edit_message_text(
            t(
                locale,
                "wordbank_added",
                title=html.escape(result.topic_title),
                added=result.added,
                skipped=result.skipped,
            )
        )
        return
