from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request

from vocab_bot.config import Settings
from vocab_bot.persistence import BotUser
from vocab_bot.services import ReviewService, UserService, user_has_access
from vocab_bot.webapi.auth import InitDataError, parse_and_validate_init_data

logger = logging.getLogger(__name__)

AUTH_SCHEME = "tma"


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_user_service(request: Request) -> UserService:
    return request.app.state.user_service


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> BotUser:
    scheme, _, raw = request.headers.get("authorization", "").partition(" ")
    raw = raw.strip()
    if scheme.lower() != AUTH_SCHEME or not raw:
        raise ApiError(401, "missing_auth", "expected 'Authorization: tma <initData>'")

    try:
        init_data = parse_and_validate_init_data(
            raw,
            settings.bot_token,
            now=datetime.now(tz=UTC),
            max_age_seconds=settings.webapp_initdata_max_age,
        )
    except InitDataError as exc:
        logger.warning("rejected initData: %s", exc)
        raise ApiError(401, "invalid_init_data", str(exc)) from exc

    user = await user_service.record_seen(
        telegram_id=init_data.telegram_id,
        username=init_data.username,
        first_name=init_data.first_name,
        last_name=init_data.last_name,
        language_code=init_data.language_code,
    )
    if not user_has_access(user, settings.admin_user_ids):
        raise ApiError(403, "access_disabled", "access to this bot is disabled for this user")
    return user


CurrentUser = Annotated[BotUser, Depends(get_current_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]
