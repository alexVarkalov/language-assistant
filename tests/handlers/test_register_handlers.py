from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from vocab_bot.handlers import register_handlers


def test_register_handlers_wires_expected_handlers() -> None:
    app = SimpleNamespace(add_handler=Mock())

    register_handlers(app)

    assert app.add_handler.call_count == 15
