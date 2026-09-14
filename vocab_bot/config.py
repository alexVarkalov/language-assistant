from __future__ import annotations

import os
from dataclasses import dataclass

from vocab_bot.lang_detect import validate_language_pair


def load_dotenv_if_present() -> None:
    """Minimal .env loader to avoid an extra dependency; ignores parse errors."""
    path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


@dataclass(frozen=True)
class Settings:
    bot_token: str
    deepl_api_key: str | None
    deepl_plan: str
    translator: str
    source_lang: str
    target_lang: str
    database_url: str
    due_poll_interval: int
    short_review_interval_minutes: int
    admin_user_ids: frozenset[int]
    wordbank_path: str | None
    webapp_url: str | None = None
    webapp_api_host: str = "127.0.0.1"
    webapp_api_port: int = 8080
    webapp_initdata_max_age: int = 86400
    due_notify_cooldown_minutes: int = 240

    @classmethod
    def from_env(cls) -> Settings:
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            msg = "BOT_TOKEN is required"
            raise ValueError(msg)

        interval_raw = os.environ.get("DUE_POLL_INTERVAL", "45").strip()
        try:
            due_poll_interval = max(15, int(interval_raw))
        except ValueError:
            due_poll_interval = 45

        short_interval_raw = os.environ.get("SHORT_REVIEW_INTERVAL_MINUTES", "10").strip()
        try:
            short_review_interval_minutes = max(1, int(short_interval_raw))
        except ValueError:
            short_review_interval_minutes = 10

        deepl = os.environ.get("DEEPL_API_KEY", "").strip() or None
        # Default free: most keys from deepl.com/pro-api are Free-plan keys (api-free.deepl.com only).
        deepl_plan = os.environ.get("DEEPL_PLAN", "free").strip().lower()
        if deepl_plan not in {"auto", "free", "pro"}:
            deepl_plan = "free"

        translator = os.environ.get("TRANSLATOR", "deepl").strip().lower()
        if translator != "deepl":
            translator = "deepl"
        if not deepl:
            msg = "DEEPL_API_KEY is required (MyMemory is disabled)"
            raise ValueError(msg)

        source_lang = os.environ.get("SOURCE_LANG", "PL").strip().upper()
        target_lang = os.environ.get("TARGET_LANG", "RU").strip().upper()
        validate_language_pair(source_lang, target_lang)
        admin_user_ids = _parse_user_ids(os.environ.get("ADMIN_USER_IDS", ""))
        database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        ).strip()
        if not database_url:
            msg = "DATABASE_URL is required"
            raise ValueError(msg)

        wordbank_path = os.environ.get("WORDBANK_PATH", "").strip() or None

        webapp_url = os.environ.get("WEBAPP_URL", "").strip().rstrip("/") or None
        if webapp_url is None:
            msg = "WEBAPP_URL is required (reviews and reminders live in the Mini App)"
            raise ValueError(msg)
        if not webapp_url.startswith("https://"):
            msg = "WEBAPP_URL must be an https:// URL (Telegram refuses plain http for Mini Apps)"
            raise ValueError(msg)
        webapp_api_host = os.environ.get("WEBAPP_API_HOST", "").strip() or "127.0.0.1"
        webapp_api_port = _int_env("WEBAPP_API_PORT", default=8080, minimum=1)
        webapp_initdata_max_age = _int_env("WEBAPP_INITDATA_MAX_AGE", default=86400, minimum=60)
        due_notify_cooldown_minutes = _int_env("DUE_NOTIFY_COOLDOWN_MINUTES", default=240, minimum=1)

        return cls(
            bot_token=token,
            deepl_api_key=deepl,
            deepl_plan=deepl_plan,
            translator=translator,
            source_lang=source_lang,
            target_lang=target_lang,
            database_url=database_url,
            due_poll_interval=due_poll_interval,
            short_review_interval_minutes=short_review_interval_minutes,
            admin_user_ids=admin_user_ids,
            wordbank_path=wordbank_path,
            webapp_url=webapp_url,
            webapp_api_host=webapp_api_host,
            webapp_api_port=webapp_api_port,
            webapp_initdata_max_age=webapp_initdata_max_age,
            due_notify_cooldown_minutes=due_notify_cooldown_minutes,
        )


def _int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def _parse_user_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        value = part.strip()
        if not value:
            continue
        try:
            ids.add(int(value))
        except ValueError:
            continue
    return frozenset(ids)
