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
    database_path: str
    due_poll_interval: int

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

        translator = os.environ.get("TRANSLATOR", "mymemory").strip().lower()
        if translator not in {"deepl", "mymemory"}:
            translator = "mymemory"
        if translator == "deepl" and not deepl:
            translator = "mymemory"

        return cls(
            bot_token=token,
            deepl_api_key=deepl,
            deepl_plan=deepl_plan,
            translator=translator,
            source_lang=os.environ.get("SOURCE_LANG", "PL").strip().upper(),
            target_lang=os.environ.get("TARGET_LANG", "RU").strip().upper(),
            database_path=os.environ.get("DATABASE_PATH", "./data/vocab.sqlite").strip(),
            due_poll_interval=due_poll_interval,
        )
