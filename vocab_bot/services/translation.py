from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx

from vocab_bot.config import Settings
from vocab_bot.persistence import PendingTranslation
from vocab_bot.repositories import CardRepository, PendingRepository
from vocab_bot.translate import translate_text_options


def _now() -> datetime:
    return datetime.now(tz=UTC)


class TranslationService:
    def __init__(self, settings: Settings, pending_repo: PendingRepository, card_repo: CardRepository) -> None:
        self._settings = settings
        self._pending_repo = pending_repo
        self._card_repo = card_repo

    async def translate_and_store_pending(
        self, *, user_id: int, text: str, source_lang: str, target_lang: str, client: httpx.AsyncClient
    ) -> PendingTranslation:
        options = await translate_text_options(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            translator=self._settings.translator,
            deepl_api_key=self._settings.deepl_api_key,
            deepl_plan=self._settings.deepl_plan,
            client=client,
        )
        pending = PendingTranslation(
            id=uuid.uuid4().hex,
            user_id=user_id,
            source_lang=source_lang,
            target_lang=target_lang,
            source_text=text.strip(),
            target_text=options[0],
            target_options=tuple(options),
        )
        await self._pending_repo.add(pending)
        return pending

    async def save_pending_as_card(
        self, *, pending_id: str, user_id: int, option_index: int | None = None
    ) -> PendingTranslation | None:
        pending = await self._pending_repo.get(pending_id, user_id)
        if pending is None:
            return None
        selected_target = _select_target(pending, option_index)
        first_review = _now() + timedelta(minutes=self._settings.short_review_interval_minutes)
        await self._card_repo.upsert(
            user_id=pending.user_id,
            source_lang=pending.source_lang,
            target_lang=pending.target_lang,
            source_text=pending.source_text,
            target_text=selected_target,
            ease_factor=2.5,
            interval_days=0.0,
            repetition=0,
            next_review_at=first_review,
        )
        await self._pending_repo.delete(pending_id, pending.user_id)
        return PendingTranslation(
            id=pending.id,
            user_id=pending.user_id,
            source_lang=pending.source_lang,
            target_lang=pending.target_lang,
            source_text=pending.source_text,
            target_text=selected_target,
            target_options=pending.target_options,
        )

    async def dismiss_pending(self, *, pending_id: str, user_id: int) -> None:
        await self._pending_repo.delete(pending_id, user_id)


def _select_target(pending: PendingTranslation, option_index: int | None) -> str:
    if option_index is None:
        return pending.target_text
    if option_index < 0 or option_index >= len(pending.target_options):
        return pending.target_text
    return pending.target_options[option_index]
