from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    deepl_api_key: str | None
    deepl_plan: str
    translator: str
    source_lang: str
    target_lang: str
    available_languages: frozenset[str]
    database_url: str
    due_poll_interval: int
    admin_user_ids: frozenset[int]

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
        available_languages = _parse_languages(os.environ.get("AVAILABLE_LANGUAGES", "EN,RU,PL"))
        available_languages = frozenset(set(available_languages) | {source_lang, target_lang})
        admin_user_ids = _parse_user_ids(os.environ.get("ADMIN_USER_IDS", ""))
        database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant",
        ).strip()
        if not database_url:
            msg = "DATABASE_URL is required"
            raise ValueError(msg)

        return cls(
            bot_token=token,
            deepl_api_key=deepl,
            deepl_plan=deepl_plan,
            translator=translator,
            source_lang=source_lang,
            target_lang=target_lang,
            available_languages=available_languages,
            database_url=database_url,
            due_poll_interval=due_poll_interval,
            admin_user_ids=admin_user_ids,
        )


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


def _parse_languages(raw: str) -> frozenset[str]:
    codes: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        code = part.strip().upper()
        if not code:
            continue
        codes.add(code)
    if not codes:
        return frozenset({"EN", "RU", "PL"})
    return frozenset(codes)
