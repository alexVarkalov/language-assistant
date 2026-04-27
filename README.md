# Language Assistant Bot

Telegram bot for vocabulary learning with translation and spaced repetition.

It translates incoming words (default: Polish -> Russian), lets you save them, and schedules reviews using an SM-2 style algorithm.

## Features

- Translate text with either:
  - `mymemory` (default, no API key required)
  - `deepl` (optional, via `DEEPL_API_KEY`)
- Show multiple translation options and save the chosen one
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
AVAILABLE_LANGUAGES=EN,RU,PL
DATABASE_PATH=./data/vocab.sqlite
DUE_POLL_INTERVAL=45
ADMIN_USER_IDS=123456789
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
- `AVAILABLE_LANGUAGES` (optional): comma-separated language codes users can choose from. Default: `EN,RU,PL`.
- `DATABASE_PATH` (optional): SQLite DB file path. Default: `./data/vocab.sqlite`.
- `DUE_POLL_INTERVAL` (optional): polling interval in seconds (minimum 15). Default: `45`.
- `ADMIN_USER_IDS` (optional): comma-separated Telegram user IDs allowed to manage user access.

## Bot usage

- Send `/start` to see instructions.
- Send `/languages EN RU` (or `/langs EN RU`) to set your source/target languages.
- Send `/timezone Europe/Warsaw` to set your local timezone for review times.
- Send a word/phrase in the source language.
- Click `Save & learn` to create/update a card.
- When review time comes, the bot sends a prompt.
- Click reveal, then grade yourself:
  - `Again` -> reset progress for that card
  - `Good` -> standard interval growth
  - `Easy` -> larger ease factor / spacing

## User access management

The bot stores each Telegram user it sees in the SQLite database. New users are allowed by default, and admins can switch access on or off with:

- `/users`: show recently seen users and their Telegram IDs.
- `/block_user <telegram_user_id>`: disable a user's access to translations, saves, reviews, and review reminders.
- `/allow_user <telegram_user_id>`: enable access again.

Users can set their timezone with `/timezone <iana_timezone>`, for example `/timezone Europe/Warsaw`.
The bot stores this on the user record and uses it when showing review dates and times.

Set `ADMIN_USER_IDS` to your Telegram user ID before using these commands.

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
- `vocab_bot/handlers/`: Telegram command/message/callback handlers
- `vocab_bot/services/`: bot business logic services
- `vocab_bot/repositories/`: repository layer over DB methods
- `vocab_bot/persistence/`: ORM models, datatypes, and DB store mixins
- `vocab_bot/translate.py`: translation providers (MyMemory, DeepL)
- `vocab_bot/srs.py`: SM-2 style scheduling logic
- `vocab_bot/db.py`: database facade and lifecycle
