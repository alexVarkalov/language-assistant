from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from tests.webapi.conftest import BOT_TOKEN, make_init_data
from vocab_bot.webapi.auth import InitDataError, parse_and_validate_init_data

NOW = datetime.now(tz=UTC)


def _validate(raw: str, *, token: str = BOT_TOKEN, max_age: int = 3600):
    return parse_and_validate_init_data(raw, token, now=NOW, max_age_seconds=max_age)


def test_valid_init_data_is_parsed() -> None:
    init_data = _validate(make_init_data(extra={"start_param": "card_5"}))

    assert init_data.telegram_id == 123
    assert init_data.username == "tester"
    assert init_data.first_name == "Test"
    assert init_data.last_name == "User"
    assert init_data.language_code == "en"
    assert init_data.start_param == "card_5"
    assert init_data.auth_date.tzinfo is UTC


def test_unicode_user_fields_survive_encoding() -> None:
    raw = make_init_data(user={"id": 7, "first_name": "Саша", "language_code": "ru"})

    init_data = _validate(raw)

    assert init_data.telegram_id == 7
    assert init_data.first_name == "Саша"
    assert init_data.username is None


def test_empty_init_data_rejected() -> None:
    with pytest.raises(InitDataError, match="empty"):
        _validate("")


def test_missing_hash_rejected() -> None:
    with pytest.raises(InitDataError, match="missing hash"):
        _validate("auth_date=1&user=%7B%22id%22%3A1%7D")


def test_tampered_hash_rejected() -> None:
    with pytest.raises(InitDataError, match="signature mismatch"):
        _validate(make_init_data(tamper_hash=True))


def test_tampered_field_rejected() -> None:
    raw = make_init_data().replace("%22id%22%3A123", "%22id%22%3A999")

    with pytest.raises(InitDataError, match="signature mismatch"):
        _validate(raw)


def test_wrong_bot_token_rejected() -> None:
    with pytest.raises(InitDataError, match="signature mismatch"):
        _validate(make_init_data(), token="other-token")


def test_expired_auth_date_rejected() -> None:
    raw = make_init_data(auth_date=int(NOW.timestamp()) - 7200)

    with pytest.raises(InitDataError, match="expired"):
        _validate(raw, max_age=3600)


def test_auth_date_within_max_age_accepted() -> None:
    raw = make_init_data(auth_date=int(NOW.timestamp()) - 3599)

    assert _validate(raw, max_age=3600).telegram_id == 123


def test_non_integer_auth_date_rejected() -> None:
    with pytest.raises(InitDataError, match="auth_date"):
        _validate(make_init_data(auth_date=None, extra={"auth_date": "yesterday"}))


def test_missing_user_rejected() -> None:
    fields_without_user = make_init_data(extra={"user": ""})

    with pytest.raises(InitDataError, match="missing user"):
        _validate(fields_without_user)


def test_invalid_user_json_rejected() -> None:
    with pytest.raises(InitDataError, match="invalid user JSON"):
        _validate(make_init_data(extra={"user": "{not json"}))


def test_user_without_integer_id_rejected() -> None:
    with pytest.raises(InitDataError, match="invalid user id"):
        _validate(make_init_data(user={"id": "123", "first_name": "x"}))


def test_auth_date_defaults_to_now_in_fixture() -> None:
    before = int(time.time())
    init_data = _validate(make_init_data())
    assert int(init_data.auth_date.timestamp()) >= before
