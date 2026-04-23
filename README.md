# Language Assistant Bot

Telegram bot for vocabulary learning with translation and spaced repetition.

It translates incoming words (default: Polish -> Russian), lets you save them, and schedules reviews using an SM-2 style algorithm.

## Features

- Translate text with either:
  - `mymemory` (default, no API key required)
  - `deepl` (optional, via `DEEPL_API_KEY`)
- Save translated pairs as cards
- Background due-card polling and review prompts
- Self-grading flow (`Again`, `Good`, `Easy`)
- SQLite persistence via SQLAlchemy ORM

## Tech stack

- Python 3.11+
- [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot)
- [`httpx`](https://www.python-httpx.org/)
- [`SQLAlchemy`](https://www.sqlalchemy.org/)
- [`uv`](https://docs.astral.sh/uv/) for dependency and task execution

## Quick start

1. Install dependencies:

```bash
uv sync --extra dev
```

2. Create a `.env` file in the repo root:

```env
BOT_TOKEN=your_telegram_bot_token
TRANSLATOR=mymemory
SOURCE_LANG=PL
TARGET_LANG=RU
DATABASE_PATH=./data/vocab.sqlite
DUE_POLL_INTERVAL=45
```

3. Run the bot:

```bash
uv run vocab-bot
```

## Configuration

Environment variables:

- `BOT_TOKEN` (required): Telegram bot token.
- `TRANSLATOR` (optional): `mymemory` or `deepl`. Default: `mymemory`.
- `DEEPL_API_KEY` (optional): required if `TRANSLATOR=deepl`.
- `DEEPL_PLAN` (optional): `auto`, `free`, or `pro`. Default: `free`.
- `SOURCE_LANG` (optional): source language code. Default: `PL`.
- `TARGET_LANG` (optional): target language code. Default: `RU`.
- `DATABASE_PATH` (optional): SQLite DB file path. Default: `./data/vocab.sqlite`.
- `DUE_POLL_INTERVAL` (optional): polling interval in seconds (minimum 15). Default: `45`.

## Bot usage

- Send `/start` to see instructions.
- Send a word/phrase in the source language.
- Click `Save & learn` to create/update a card.
- When review time comes, the bot sends a prompt.
- Click reveal, then grade yourself:
  - `Again` -> reset progress for that card
  - `Good` -> standard interval growth
  - `Easy` -> larger ease factor / spacing

## Development

### Run Ruff

Check lint issues:

```bash
uv run --extra dev ruff check .
```

Auto-fix safe lint issues:

```bash
uv run --extra dev ruff check . --fix
```

Format code:

```bash
uv run --extra dev ruff format .
```

### Pre-commit setup

Install hooks once per clone:

```bash
uv run --extra dev pre-commit install
```

After this, hooks run automatically on every `git commit`.

### Pre-commit commands

Run all hooks on all files:

```bash
uv run --extra dev pre-commit run --all-files
```

Run hooks only on currently staged files:

```bash
uv run --extra dev pre-commit run
```

Update hook versions in `.pre-commit-config.yaml`:

```bash
uv run --extra dev pre-commit autoupdate
```

If hooks modified files (for example `ruff --fix` or `ruff format`), re-stage and commit again:

```bash
git add -A
git commit
```

## Project layout

- `vocab_bot/__main__.py`: app bootstrap and scheduler setup
- `vocab_bot/config.py`: environment-driven settings
- `vocab_bot/handlers.py`: Telegram command/message/callback handlers
- `vocab_bot/translate.py`: translation providers (MyMemory, DeepL)
- `vocab_bot/srs.py`: SM-2 style scheduling logic
- `vocab_bot/db.py`: SQLAlchemy ORM models and DB operations
