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
        "start_intro": "Send a word in <b>{source_lang}</b> and I will translate it to <b>{target_lang}</b>.",
        "start_review": "After each translation you can save the word to start spaced reviews (SM-2 style intervals).",
        "start_grading": (
            "During a review I show the translation; reveal the word you are learning, "
            "then grade yourself with <i>Again</i>, <i>Good</i>, or <i>Easy</i>."
        ),
        "start_lang_pair": "<code>Language pair: {lang_pair}</code>",
        "start_set_pair": "Set your pair with <code>/languages EN RU</code>.",
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
        "languages_current": (
            "Current pair: {lang_pair}\nAllowed languages: {allowed}\n"
            "Set with /languages <SOURCE> <TARGET>, e.g. /languages EN RU"
        ),
        "languages_unsupported": "Unsupported language code(s): {invalid}.\nAllowed languages: {allowed}",
        "languages_updated": "Language pair updated to {lang_pair}.",
        "locale_current": (
            "Current interface language: {locale_label}\nSupported locales: {supported}\n"
            "Set with /locale <code>, e.g. /locale ru"
        ),
        "locale_unsupported": "Unsupported locale: {locale_label}.\nSupported locales: {supported}",
        "locale_updated": "Interface language updated to {locale_label}.",
        "translation_could_not": "Could not translate: {error}",
        "translation_failed_unexpectedly": "Translation failed unexpectedly. Try again later.",
        "translation_choose": "<b>{source}</b> ({pair})\nChoose a translation to save:\n{options}",
        "button_save": "Save: {label}",
        "button_dismiss": "Dismiss",
        "pending_expired": "That suggestion expired. Send the word again.",
        "pending_saved": 'Saved "{source}" -> "{target}". First review around {first_review} ({lang_pair}).',
        "pending_dismissed": "Okay - not saved.",
        "review_missing": "This review card no longer exists.",
        "review_prompt": (
            "<b>Review</b> ({lang_pair})\nPrompt: <b>{prompt}</b>\nAnswer: <b>{answer}</b>\n\nHow hard was it?"
        ),
        "review_updated": (
            "Updated schedule.\nNext review: <b>{next_review}</b>\nRepetitions: {repetition}, "
            "interval: {interval_days:.4f} days, EF: {ease_factor:.2f}"
        ),
        "button_again": "Again",
        "button_good": "Good",
        "button_easy": "Easy",
        "due_review_time": (
            "<b>Review time</b> ({lang_pair})\nWhat is the <b>{source_lang}</b> word for:\n<b>{target_text}</b>"
        ),
        "due_reveal": "Reveal {source_lang} word",
    },
    "ru": {
        "access_disabled": "Ваш доступ к боту отключен. Если это ошибка, свяжитесь с администратором.",
        "admin_only": "Эта команда доступна только администраторам бота.",
        "start_title": "<b>Словарный бот</b>",
        "start_intro": "Отправьте слово на <b>{source_lang}</b>, и я переведу его на <b>{target_lang}</b>.",
        "start_review": "После каждого перевода вы можете сохранить слово и начать интервальные повторения (SM-2).",
        "start_grading": (
            "Во время повторения я показываю перевод; раскройте изучаемое слово "
            "и оцените себя: <i>Again</i>, <i>Good</i> или <i>Easy</i>."
        ),
        "start_lang_pair": "<code>Языковая пара: {lang_pair}</code>",
        "start_set_pair": "Изменить пару: <code>/languages EN RU</code>.",
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
        "languages_current": (
            "Текущая пара: {lang_pair}\nДоступные языки: {allowed}\n"
            "Изменить: /languages <SOURCE> <TARGET>, например /languages EN RU"
        ),
        "languages_unsupported": "Неподдерживаемые коды языка: {invalid}.\nДоступные языки: {allowed}",
        "languages_updated": "Языковая пара обновлена: {lang_pair}.",
        "locale_current": (
            "Текущий язык интерфейса: {locale_label}\nПоддерживаемые локали: {supported}\n"
            "Изменить: /locale <code>, например /locale ru"
        ),
        "locale_unsupported": "Неподдерживаемая локаль: {locale_label}.\nПоддерживаемые локали: {supported}",
        "locale_updated": "Язык интерфейса обновлен: {locale_label}.",
        "translation_could_not": "Не удалось перевести: {error}",
        "translation_failed_unexpectedly": "Ошибка перевода. Попробуйте еще раз позже.",
        "translation_choose": "<b>{source}</b> ({pair})\nВыберите перевод для сохранения:\n{options}",
        "button_save": "Сохранить: {label}",
        "button_dismiss": "Отмена",
        "pending_expired": "Этот вариант уже устарел. Отправьте слово снова.",
        "pending_saved": (
            'Сохранено: "{source}" -> "{target}". Первое повторение примерно в {first_review} ({lang_pair}).'
        ),
        "pending_dismissed": "Хорошо, не сохраняю.",
        "review_missing": "Карточка повторения больше не существует.",
        "review_prompt": (
            "<b>Повторение</b> ({lang_pair})\nПодсказка: <b>{prompt}</b>\nОтвет: <b>{answer}</b>\n\n"
            "Насколько это было сложно?"
        ),
        "review_updated": (
            "Расписание обновлено.\nСледующее повторение: <b>{next_review}</b>\n"
            "Повторений: {repetition}, интервал: {interval_days:.4f} дн., EF: {ease_factor:.2f}"
        ),
        "button_again": "Again",
        "button_good": "Good",
        "button_easy": "Easy",
        "due_review_time": (
            "<b>Пора повторять</b> ({lang_pair})\nКакое слово на <b>{source_lang}</b> соответствует:\n"
            "<b>{target_text}</b>"
        ),
        "due_reveal": "Показать слово на {source_lang}",
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
