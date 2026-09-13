"""Telegram Mini App initData validation. Pure module: no FastAPI, no I/O."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    pass


@dataclass(frozen=True)
class InitData:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    auth_date: datetime
    start_param: str | None


def compute_init_data_hash(pairs: Mapping[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()) if key != "hash")
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


def parse_and_validate_init_data(
    raw: str,
    bot_token: str,
    *,
    now: datetime,
    max_age_seconds: int,
) -> InitData:
    if not raw:
        raise InitDataError("empty initData")

    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    received_hash = pairs.get("hash")
    if not received_hash:
        raise InitDataError("missing hash")

    expected_hash = compute_init_data_hash(pairs, bot_token)
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError("signature mismatch")

    try:
        auth_timestamp = int(pairs.get("auth_date", ""))
    except ValueError as exc:
        raise InitDataError("missing or invalid auth_date") from exc
    auth_date = datetime.fromtimestamp(auth_timestamp, tz=UTC)
    if (now - auth_date).total_seconds() > max_age_seconds:
        raise InitDataError("initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InitDataError("missing user")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise InitDataError("invalid user JSON") from exc
    if not isinstance(user, dict) or not isinstance(user.get("id"), int) or isinstance(user.get("id"), bool):
        raise InitDataError("invalid user id")

    return InitData(
        telegram_id=user["id"],
        username=_optional_str(user.get("username")),
        first_name=_optional_str(user.get("first_name")),
        last_name=_optional_str(user.get("last_name")),
        language_code=_optional_str(user.get("language_code")),
        auth_date=auth_date,
        start_param=_optional_str(pairs.get("start_param")),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
