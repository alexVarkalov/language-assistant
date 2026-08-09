# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`vocab_bot` — a Telegram bot for vocabulary learning. Each deployment is fixed to one language pair (default:
Polish ↔ Russian via `SOURCE_LANG`/`TARGET_LANG`) and auto-detects, per message, which of the two languages the
user typed (script-based: Cyrillic vs Latin — see `lang_detect.py`) before translating to the other via DeepL.
There is no per-user language-pair selection; a different pair means a separate deployment (new bot token,
`.env`, database). Users save translations as cards and get spaced-repetition reviews with an SM-2-style
algorithm. Async, built on `python-telegram-bot` v22, with PostgreSQL/SQLAlchemy persistence.

This project was scaffolded in Cursor. `CURSOR_BOT_INSTRUCTIONS.md` in the repo root is the original
Cursor-rules doc this codebase follows (and is also a reusable template for spinning up sibling bots) — read it
for the full architecture/convention rationale; the essentials are captured below.

## Commands

```bash
# Install deps (dev extras include pytest, ruff, pre-commit)
uv sync --extra dev

# Run the bot
uv run vocab-bot            # or: python -m vocab_bot

# Lint / format
uv run --extra dev ruff check .
uv run --extra dev ruff check . --fix
uv run --extra dev ruff format .

# Tests
uv run --extra dev pytest
uv run --extra dev pytest tests/handlers/test_commands.py
uv run --extra dev pytest tests/handlers/test_commands.py::test_cmd_start_access_disabled
uv run --extra dev pytest -k "review"

# Pre-commit (runs ruff-check --fix, ruff-format, pytest on every commit)
uv run --extra dev pre-commit install       # once per clone
uv run --extra dev pre-commit run --all-files
```

Requires Python 3.14+. `DEEPL_API_KEY` is required at startup — `TRANSLATOR` only supports `deepl` (MyMemory is
disabled in `config.py`). `DATABASE_URL` defaults to a local Postgres instance; there is no SQLite fallback.
`.env.example` mirrors these current defaults.

## Architecture

Strict 4-layer stack, dependencies flow one way only:

```
handlers  →  services  →  repositories  →  persistence (store mixins + ORM)
                ↓
        config, i18n, translate.py (external APIs)
```

- **`handlers/`** — Telegram `Update`/`ContextTypes` entry points. Thin: guard on missing
  `effective_user`/`effective_message`, call `record_user_seen()`, check `user_has_access()`, delegate everything
  else to services. No SQL, no business logic here. All handlers register in `handlers/__init__.py` via
  `register_handlers(application)` — that's the single source of truth for commands/callbacks wired up.
- **`services/`** — business logic/orchestration (`UserService`, `TranslationService`, `ReviewService`). Take
  repositories + `Settings` via constructor injection. Never import `telegram`.
- **`repositories/`** — thin async facades over `Database` store methods, one per aggregate (users, cards,
  pending). Domain-oriented method names, not SQL-oriented.
- **`persistence/`** — `models.py` (SQLAlchemy ORM, `*Record` suffix), `types.py` (frozen dataclasses returned
  upward, e.g. `BotUser`, `Card`), store mixins (`UserStore`, `CardStore`, `PendingStore`) each exposing a sync
  `_x_sync` method wrapped by an async `def x` via `asyncio.to_thread`, and `utils.py` for ORM→domain mappers
  (`to_user()`, `to_card()`, `utc_now()`). `db.py`'s `Database` class inherits all store mixins; `init()` runs
  `create_all` plus additive raw-SQL migrations (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) — no Alembic yet.

Dependencies are wired in `__main__.py::_post_init` and stashed on `application.bot_data` (`settings`, `db`,
`http_client`, `user_service`, `translation_service`, `review_service`) — no global singletons. The due-card
reminder job (`due_poll`, in `handlers/reviews.py`) is registered there via `job_queue.run_repeating`.

### Conventions worth knowing before editing

- **i18n**: all user-facing strings go through `t(locale, key, **kwargs)` in `i18n.py`. When adding a string, add
  the key for every supported locale in the same change — never hardcode English/Russian in handlers.
- **Access control**: new users default to blocked (`is_allowed=False`); `ADMIN_USER_IDS` always bypass. Use
  `user_has_access()` / `require_admin()`, don't reimplement checks.
- **Callback data**: namespaced prefixes (`save:`, `dismiss:`, `reveal:`, `grade:`, `menu:`), routed through one
  `CallbackQueryHandler` regex in `handlers/__init__.py`; parse with `data.split(":", maxsplit=N)` and validate
  before `int()`.
- **HTML replies**: `reply_html`/`edit_message_text(parse_mode=HTML)`; escape dynamic content with `html.escape()`.
- **Timestamps**: always UTC-aware (`datetime.now(tz=UTC)`); user timezone stored as IANA string, converted for
  display with `zoneinfo.ZoneInfo`.
- **New feature = touch layers in order**: persistence → repository → service → handler. Never import `telegram`
  in `services/` or `persistence/`.

### Testing

Layout mirrors source (`tests/handlers/test_commands.py` ↔ `vocab_bot/handlers/commands.py`). Layer-specific
approach:

| Layer | Approach |
|---|---|
| `config.py` | `monkeypatch.setenv`/`delenv` |
| `persistence/*Store` | `tests/persistence/fakes.py` (`FakeSession`, `FakeSessionFactory`) against `_sync` methods |
| `repositories/` | mock `Database` or fake-backed store |
| `services/` | mock repositories |
| `handlers/` | `AsyncMock` services, `SimpleNamespace` fake `Update`/`Context` |
| `srs.py`, `lang_detect.py` and other pure logic | plain unit tests, no mocks |

Async tests use `@pytest.mark.asyncio`. Shared fixtures/factories live in `tests/helpers.py` (`make_user()`).
