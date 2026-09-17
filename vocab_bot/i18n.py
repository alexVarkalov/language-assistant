from __future__ import annotations

from collections.abc import Mapping

from vocab_bot.persistence import BotUser

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "ru")
DEFAULT_LOCALE = "en"

_MESSAGES: Mapping[str, Mapping[str, str]] = {
    "en": {
        "access_disabled": "Your access to this bot is disabled. Contact the bot administrator if this looks wrong.",
        "admin_only": "This command is only available to bot admins.",
        "start_title": "<b>Vocabulary bot</b>",
        "start_intro": (
            "Send a word in <b>{lang_a}</b> or <b>{lang_b}</b> "
            "and I will detect which one and translate it to the other."
        ),
        "start_review": "After each translation you can save the word to start spaced reviews (SM-2 style intervals).",
        "start_grading": (
            "Reviews happen in the app: flip the card to see the answer, "
            "then grade yourself with <i>Again</i>, <i>Good</i>, or <i>Easy</i>."
        ),
        "start_lang_pair": "<code>Language pair: {lang_pair}</code>",
        "start_set_timezone": "Set your timezone with <code>/timezone Europe/Warsaw</code>.",
        "start_timezone": "<code>Timezone: {timezone}</code>",
        "start_locale": "<code>Locale: {locale_label}</code>",
        "start_set_locale": "Set interface language with <code>/locale en</code> or <code>/locale ru</code>.",
        "start_translator": "<code>Translator: {translator}</code>",
        "timezone_current": "Your timezone is {timezone}.\nSet it with /timezone Europe/Warsaw",
        "timezone_invalid": (
            "I do not recognize that timezone. Use an IANA name like Europe/Warsaw, Europe/Moscow, or UTC."
        ),
        "timezone_updated": "Timezone updated to {timezone}.",
        "locale_current": (
            "Current interface language: {locale_label}\nSupported locales: {supported}\n"
            "Set with /locale <code>, e.g. /locale ru"
        ),
        "locale_unsupported": "Unsupported locale: {locale_label}.\nSupported locales: {supported}",
        "locale_updated": "Interface language updated to {locale_label}.",
        "menu_title": "<b>Settings menu</b>",
        "menu_current_locale": "Interface language: <b>{locale_label}</b>",
        "menu_current_pair": "Language pair: <b>{lang_pair}</b>",
        "menu_hint": "Choose what you want to change:",
        "menu_button_locale": "Change interface language",
        "menu_button_back": "Back",
        "menu_choose_locale": "Choose interface language:",
        "start_reminders": "<code>Reminders: {frequency} at {times} ({timezone})</code>",
        "start_set_reminders": (
            "Choose how often to be reminded about due cards: <code>/reminders 1</code>, "
            "<code>2</code> or <code>3</code> (times a day)."
        ),
        "reminders_per_day_one": "once a day",
        "reminders_per_day_few": "{count} times a day",
        "reminders_per_day_many": "{count} times a day",
        "reminders_current": (
            "Review reminders: {frequency} at {times} ({timezone}).\n"
            "They are sent only when you have cards to review.\n"
            "Change with /reminders 1, /reminders 2 or /reminders 3."
        ),
        "reminders_invalid": "Choose 1, 2 or 3 reminders a day, e.g. /reminders 2",
        "reminders_updated": "Reminders updated: {frequency} at {times} ({timezone}).",
        "menu_current_reminders": "Reminders: <b>{frequency}</b> at {times} ({timezone})",
        "menu_button_reminders": "Change reminder frequency",
        "menu_choose_reminders": (
            "How often should I remind you about cards to review?\n"
            "Times are in your timezone ({timezone}); reminders are sent only when cards are due."
        ),
        "translation_could_not": "Could not translate: {error}",
        "translation_failed_unexpectedly": "Translation failed unexpectedly. Try again later.",
        "translation_choose": "<b>{source}</b> ({pair})\nChoose a translation to save:\n{options}",
        "button_save": "Save: {label}",
        "button_dismiss": "Dismiss",
        "pending_expired": "That suggestion expired. Send the word again.",
        "pending_saved": (
            'Saved "<tg-spoiler>{source}</tg-spoiler>" -> "<tg-spoiler>{target}</tg-spoiler>". '
            "First review around {first_review} ({lang_pair})."
        ),
        "pending_dismissed": "Okay - not saved.",
        "due_summary_one": "<b>Review time</b>\nYou have <b>{count}</b> card to review.",
        "due_summary_few": "<b>Review time</b>\nYou have <b>{count}</b> cards to review.",
        "due_summary_many": "<b>Review time</b>\nYou have <b>{count}</b> cards to review.",
        "due_open_app": "Open in app",
        "menu_button_app": "Reviews",
        "start_app_hint": "Tap the menu button next to the input field to review cards in the app.",
        "wordbank_sections_header": "Choose a topic section:",
        "wordbank_topics_header": "<b>{title}</b>\nChoose a topic:",
        "wordbank_topic_header": "<b>{number}. {title}</b> ({count} words)",
        "wordbank_topic_more": "…and {count} more",
        "wordbank_button_add_all": "➕ Add all {count} words",
        "wordbank_added": "Added {added} new words from «{title}» to your cards. {skipped} were already in your list.",
        "wordbank_topic_missing": "That topic no longer exists.",
    },
    "ru": {
        "access_disabled": "Ваш доступ к боту отключен. Если это ошибка, свяжитесь с администратором.",
        "admin_only": "Эта команда доступна только администраторам бота.",
        "start_title": "<b>Словарный бот</b>",
        "start_intro": (
            "Отправьте слово на <b>{lang_a}</b> или <b>{lang_b}</b> — я определю, какой это язык, и переведу на другой."
        ),
        "start_review": "После каждого перевода вы можете сохранить слово и начать интервальные повторения (SM-2).",
        "start_grading": (
            "Повторения проходят в приложении: переверните карточку, чтобы увидеть ответ, "
            "и оцените себя: <i>Again</i>, <i>Good</i> или <i>Easy</i>."
        ),
        "start_lang_pair": "<code>Языковая пара: {lang_pair}</code>",
        "start_set_timezone": "Установить часовой пояс: <code>/timezone Europe/Moscow</code>.",
        "start_timezone": "<code>Часовой пояс: {timezone}</code>",
        "start_locale": "<code>Язык интерфейса: {locale_label}</code>",
        "start_set_locale": "Изменить язык интерфейса: <code>/locale ru</code> или <code>/locale en</code>.",
        "start_translator": "<code>Переводчик: {translator}</code>",
        "timezone_current": "Ваш часовой пояс: {timezone}.\nИзменить: /timezone Europe/Moscow",
        "timezone_invalid": (
            "Не удалось распознать часовой пояс. Используйте IANA-имя, например Europe/Moscow, Europe/Warsaw или UTC."
        ),
        "timezone_updated": "Часовой пояс обновлен: {timezone}.",
        "locale_current": (
            "Текущий язык интерфейса: {locale_label}\nПоддерживаемые локали: {supported}\n"
            "Изменить: /locale <code>, например /locale ru"
        ),
        "locale_unsupported": "Неподдерживаемая локаль: {locale_label}.\nПоддерживаемые локали: {supported}",
        "locale_updated": "Язык интерфейса обновлен: {locale_label}.",
        "menu_title": "<b>Меню настроек</b>",
        "menu_current_locale": "Язык интерфейса: <b>{locale_label}</b>",
        "menu_current_pair": "Языковая пара: <b>{lang_pair}</b>",
        "menu_hint": "Выберите, что хотите изменить:",
        "menu_button_locale": "Изменить язык интерфейса",
        "menu_button_back": "Назад",
        "menu_choose_locale": "Выберите язык интерфейса:",
        "start_reminders": "<code>Напоминания: {frequency} в {times} ({timezone})</code>",
        "start_set_reminders": (
            "Выберите, как часто напоминать о карточках: <code>/reminders 1</code>, "
            "<code>2</code> или <code>3</code> (раз в день)."
        ),
        "reminders_per_day_one": "раз в день",
        "reminders_per_day_few": "{count} раза в день",
        "reminders_per_day_many": "{count} раз в день",
        "reminders_current": (
            "Напоминания о повторении: {frequency} в {times} ({timezone}).\n"
            "Они приходят только когда есть карточки к повторению.\n"
            "Изменить: /reminders 1, /reminders 2 или /reminders 3."
        ),
        "reminders_invalid": "Выберите 1, 2 или 3 напоминания в день, например /reminders 2",
        "reminders_updated": "Напоминания обновлены: {frequency} в {times} ({timezone}).",
        "menu_current_reminders": "Напоминания: <b>{frequency}</b> в {times} ({timezone})",
        "menu_button_reminders": "Изменить частоту напоминаний",
        "menu_choose_reminders": (
            "Как часто напоминать о карточках к повторению?\n"
            "Время указано в вашем часовом поясе ({timezone}); напоминания приходят только когда есть карточки."
        ),
        "translation_could_not": "Не удалось перевести: {error}",
        "translation_failed_unexpectedly": "Ошибка перевода. Попробуйте еще раз позже.",
        "translation_choose": "<b>{source}</b> ({pair})\nВыберите перевод для сохранения:\n{options}",
        "button_save": "Сохранить: {label}",
        "button_dismiss": "Отмена",
        "pending_expired": "Этот вариант уже устарел. Отправьте слово снова.",
        "pending_saved": (
            'Сохранено: "<tg-spoiler>{source}</tg-spoiler>" -> "<tg-spoiler>{target}</tg-spoiler>". '
            "Первое повторение примерно в {first_review} ({lang_pair})."
        ),
        "pending_dismissed": "Хорошо, не сохраняю.",
        "due_summary_one": "<b>Пора повторять</b>\nУ вас <b>{count}</b> карточка к повторению.",
        "due_summary_few": "<b>Пора повторять</b>\nУ вас <b>{count}</b> карточки к повторению.",
        "due_summary_many": "<b>Пора повторять</b>\nУ вас <b>{count}</b> карточек к повторению.",
        "due_open_app": "Открыть в приложении",
        "menu_button_app": "Повторения",
        "start_app_hint": "Кнопка меню рядом с полем ввода открывает приложение для повторений.",
        "wordbank_sections_header": "Выберите раздел тем:",
        "wordbank_topics_header": "<b>{title}</b>\nВыберите тему:",
        "wordbank_topic_header": "<b>{number}. {title}</b> ({count} слов)",
        "wordbank_topic_more": "…и еще {count}",
        "wordbank_button_add_all": "➕ Добавить все {count} слов",
        "wordbank_added": "Добавлено {added} новых слов из «{title}» в ваши карточки. {skipped} уже были в списке.",
        "wordbank_topic_missing": "Эта тема больше не существует.",
    },
}


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    locale = value.strip().lower()
    return locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE


def resolve_user_locale(user: BotUser) -> str:
    if user.preferred_locale:
        return normalize_locale(user.preferred_locale)
    if user.language_code:
        return normalize_locale(user.language_code.split("-", maxsplit=1)[0])
    return DEFAULT_LOCALE


def t(locale: str, key: str, **kwargs: object) -> str:
    normalized = normalize_locale(locale)
    template = _MESSAGES[normalized].get(key) or _MESSAGES[DEFAULT_LOCALE][key]
    return template.format(**kwargs)


def plural_form(locale: str, count: int) -> str:
    """CLDR-style category used as a key suffix: en has one/many, ru has one/few/many."""
    n = abs(count)
    if normalize_locale(locale) == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            return "few"
        return "many"
    return "one" if n == 1 else "many"


def t_count(locale: str, key: str, count: int, **kwargs: object) -> str:
    """Translate `{key}_{plural form}` for `count`, falling back to `{key}_many` when a form is missing."""
    normalized = normalize_locale(locale)
    form = plural_form(normalized, count)
    template = _MESSAGES[normalized].get(f"{key}_{form}") or _MESSAGES[normalized].get(f"{key}_many")
    if template is None:
        return t(DEFAULT_LOCALE, f"{key}_{plural_form(DEFAULT_LOCALE, count)}", count=count, **kwargs)
    return template.format(count=count, **kwargs)
