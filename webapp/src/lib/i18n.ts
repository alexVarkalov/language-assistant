import type { Locale } from "./types";

const MESSAGES = {
  en: {
    loading: "Loading…",
    tap_to_reveal: "Tap to reveal",
    again: "Again",
    good: "Good",
    easy: "Easy",
    progress: "{done} / {total}",
    done_title: "All done!",
    done_body: "You reviewed {count} cards.",
    done_next: "Next review: {when}",
    done_none: "Nothing else is due right now.",
    load_more: "Load more",
    close: "Close",
    blocked: "Your access to this bot is disabled. Contact the bot administrator if this looks wrong.",
    not_in_telegram: "Open this page from the bot's menu button in Telegram.",
    error_generic: "Something went wrong.",
    retry: "Retry",
  },
  ru: {
    loading: "Загрузка…",
    tap_to_reveal: "Нажми, чтобы открыть",
    again: "Снова",
    good: "Хорошо",
    easy: "Легко",
    progress: "{done} / {total}",
    done_title: "Готово!",
    done_body: "Повторено карточек: {count}.",
    done_next: "Следующее повторение: {when}",
    done_none: "Больше ничего не требует повторения.",
    load_more: "Загрузить ещё",
    close: "Закрыть",
    blocked: "Доступ к боту отключён. Если это ошибка, напишите администратору бота.",
    not_in_telegram: "Откройте эту страницу через кнопку меню бота в Telegram.",
    error_generic: "Что-то пошло не так.",
    retry: "Повторить",
  },
} as const satisfies Record<Locale, Record<string, string>>;

export type MessageKey = keyof (typeof MESSAGES)["en"];

export function t(locale: Locale, key: MessageKey, params: Record<string, string | number> = {}): string {
  const table = MESSAGES[locale] ?? MESSAGES.en;
  let text: string = table[key] ?? MESSAGES.en[key];
  for (const [name, value] of Object.entries(params)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

export function formatDateTime(iso: string, timeZone: string, locale: Locale): string {
  const date = new Date(iso);
  try {
    return new Intl.DateTimeFormat(locale, { timeZone, dateStyle: "medium", timeStyle: "short" }).format(date);
  } catch {
    return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
  }
}
