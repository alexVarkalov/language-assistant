from __future__ import annotations

from fastapi import APIRouter

from vocab_bot.i18n import resolve_user_locale
from vocab_bot.webapi.deps import CurrentUser, ReviewServiceDep, SettingsDep
from vocab_bot.webapi.schemas import LangPair, MeResponse

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def get_me(user: CurrentUser, settings: SettingsDep, review_service: ReviewServiceDep) -> MeResponse:
    due_count = await review_service.count_due_for_user(user_id=user.telegram_id)
    return MeResponse(
        telegram_id=user.telegram_id,
        locale=resolve_user_locale(user),
        timezone=user.timezone or "UTC",
        lang_pair=LangPair(source=settings.source_lang, target=settings.target_lang),
        due_count=due_count,
        short_review_interval_minutes=settings.short_review_interval_minutes,
    )
