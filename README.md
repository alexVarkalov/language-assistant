# Language Assistant Bot

Telegram bot for vocabulary learning with translation and spaced repetition.

Each deployment is fixed to one language pair (default: Polish <-> Russian). It auto-detects which of the two
languages you typed (by script — Cyrillic vs Latin) and translates to the other, lets you save the word, and
schedules reviews using an SM-2 style algorithm.

## Features

- Auto-detect which of the deployment's two languages you typed (by script) and translate to the other
- Translate text with DeepL (`DEEPL_API_KEY` required)
- Show multiple translation options and save the chosen one
- Background due-card polling with one consolidated "N cards to review" reminder per user (edge-triggered,
  repeated at most once per cool-down while the queue stays non-empty); reviews happen in the Mini App
- Self-grading flow (`Again`, `Good`, `Easy`) in the Telegram Mini App
- PostgreSQL persistence via SQLAlchemy ORM

## Tech stack

- Python 3.14+
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
TRANSLATOR=deepl
SOURCE_LANG=PL
TARGET_LANG=RU
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant
DUE_POLL_INTERVAL=45
SHORT_REVIEW_INTERVAL_MINUTES=10
ADMIN_USER_IDS=123456789
```

3. Run the bot:

```bash
uv run vocab-bot
```

## Configuration

Environment variables:

- `BOT_TOKEN` (required): Telegram bot token.
- `TRANSLATOR` (optional): currently only `deepl` is supported. Default: `deepl`.
- `DEEPL_API_KEY` (required): DeepL API key.
- `DEEPL_PLAN` (optional): `auto`, `free`, or `pro`. Default: `free`.
- `SOURCE_LANG` / `TARGET_LANG` (optional): this deployment's fixed language pair. Defaults: `PL` / `RU`.
  Direction is auto-detected per message by script (Cyrillic vs Latin), so one of the two must be a
  Cyrillic-script language (e.g. `RU`) and the other Latin-script (e.g. `PL`) — the order between them
  doesn't matter. To support a different pair, run a separate deployment (new bot token, `.env`, database)
  rather than reconfiguring this one.
- `DATABASE_URL` (optional): PostgreSQL SQLAlchemy URL. Default: `postgresql+psycopg://postgres:postgres@localhost:5432/language_assistant`.
- `DUE_POLL_INTERVAL` (optional): polling interval in seconds (minimum 15). Default: `45`.
- `DUE_NOTIFY_COOLDOWN_MINUTES` (optional): minimum gap between two "cards to review" reminders for the same
  user while their due queue stays non-empty (minimum 1). The first due card after an empty queue is always
  announced on the next poll. Default: `240`.
- `SHORT_REVIEW_INTERVAL_MINUTES` (optional): short review delay in minutes used for first review and resets after `Again` (minimum 1). Default: `10`.
- `ADMIN_USER_IDS` (optional): comma-separated Telegram user IDs allowed to manage user access.
- `WORDBANK_PATH` (optional): path to a parsed topic-dictionary JSON file (see "Wordbank" below). Unset by
  default — the `/wordbank` command only exists on deployments where this is set.
- `WEBAPP_URL` (**required**): public `https://` URL of the Telegram Mini App (see "Mini App" below). The bot
  sets it as the Menu Button and puts an "Open in app" button on review reminders; reviews happen only there,
  so the bot refuses to start without it.
- `WEBAPP_API_HOST` / `WEBAPP_API_PORT` (optional): bind address/port of the Mini App API process
  (`python -m vocab_bot.webapi`). Defaults: `127.0.0.1` / `8080`.
- `WEBAPP_INITDATA_MAX_AGE` (optional): max accepted age of Telegram `initData` in seconds (minimum 60).
  Default: `86400`.

## Bot usage

- Send `/start` to see instructions.
- Send `/menu` (or `/settings`) to open an interactive settings menu (interface language).
- Send `/locale ru` (or `/localization ru`) to switch bot interface language to Russian.
- Send `/timezone Europe/Warsaw` to set your local timezone for review times.
- Send a word/phrase in either of the deployment's two languages — the bot detects which one and translates
  to the other.
- Click `Save & learn` to create/update a card.
- When cards are due, the bot sends one "N cards to review" reminder with an **Open in app** button (also
  reachable any time via the Menu Button next to the input field). Reviews happen only in the Mini App.
- Flip the card, then grade yourself:
  - `Again` -> reset progress for that card
  - `Good` -> standard interval growth
  - `Easy` -> larger ease factor / spacing

## Wordbank (topic-dictionary batch-add)

On deployments with `WORDBANK_PATH` set, `/wordbank` lets a user browse a pre-parsed topic dictionary
(section → topic) and add every word in a topic as a card in one tap, skipping any word they've already
saved. Currently this only exists for the RU↔PL deployment, built from a commercial print dictionary.

**The parsed dictionary JSON (and its source PDF) are intentionally never committed to this repo** — this
repo is public, and that content is copyrighted. `scripts/parse_ru_pl_dictionary.py` (requires `pdftotext`
from poppler) regenerates the JSON locally from the source PDF; deploy the resulting file directly to the
target host outside of git (e.g. `scp`), the same way `.env` is deployed:

```bash
uv run python scripts/parse_ru_pl_dictionary.py "path/to/source.pdf" data/ru_pl_dictionary.json
scp data/ru_pl_dictionary.json <host>:/home/app/language-assistant/data/ru_pl_dictionary.json
```

Then set `WORDBANK_PATH=data/ru_pl_dictionary.json` in that deployment's `.env` and restart the service.

## Mini App (Telegram Web App)

The full-screen review UI that opens inside Telegram — the only place cards are reviewed. It consists of a
Svelte frontend (`webapp/`)
and a FastAPI backend (`vocab_bot/webapi/`) that runs as a **separate process** next to the bot and talks to
the same PostgreSQL database:

```bash
uv sync --extra api
uv run vocab-bot-api        # or: python -m vocab_bot.webapi  (binds WEBAPP_API_HOST:WEBAPP_API_PORT)
```

Requests are authenticated with Telegram `initData` (HMAC-signed by Telegram with your bot token), so there
are no passwords or sessions; access follows the same allow/block list as the chat. `WEBAPP_URL` (required)
is the public `https://` URL where the frontend is served; the bot uses it for the Menu Button and the "Open
in app" button on review reminders. Design, API contract, implementation plan and VPS deployment guide:
[`docs/miniapp/`](docs/miniapp/README.md).

## User access management

The bot stores each Telegram user it sees in the PostgreSQL database. New users are blocked by default, and admins can switch access on or off with:

- `/users`: show recently seen users and their Telegram IDs.
- `/block_user <telegram_user_id>`: disable a user's access to translations, saves, reviews, and review reminders.
- `/allow_user <telegram_user_id>`: enable access again.

Users can set their timezone with `/timezone <iana_timezone>`, for example `/timezone Europe/Warsaw`.
The bot stores this on the user record and uses it when showing review dates and times.

Set `ADMIN_USER_IDS` to your Telegram user ID before using these commands.

## Deploy

**Production runs on a VPS** — bot, Mini App API, Postgres and nginx on one host, two language pairs side by
side. The maintained guide is [`docs/miniapp/deployment.md`](docs/miniapp/deployment.md) (provisioning, base
setup, Postgres, systemd units, nginx + TLS, frontend publish, updating, backups, second language pair).

### Legacy: Raspberry Pi (chat-only era)

The section below predates the Mini App and is kept for the Postgres/systemd/`uv` steps, which are still
accurate. Note that `WEBAPP_URL` is now **required** and the Mini App needs a public `https://` origin, so a
Pi on a home network alone is no longer a complete deployment — pair it with a VPS or a tunnel for the
frontend + API (see the "Alternative" section at the end of `deployment.md`).

This section describes a deployment on Raspberry Pi OS with:

- `systemd` service for auto-start/restart
- local PostgreSQL
- project managed with `uv`

The commands below assume:

- user: `pi`
- app dir: `/home/pi/language-assistant`
- service name: `language-assistant-bot`

Adjust paths/usernames if your setup differs.

### 1) Prepare the Pi

Update OS and install required packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates postgresql postgresql-contrib
```

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Reload shell so `uv` is available:

```bash
source "$HOME/.local/bin/env"
```

### 2) Clone project and create a dedicated environment

```bash
cd /home/pi
git clone <your-repo-url> language-assistant
cd language-assistant
uv venv .venv --python 3.14
uv sync --frozen
```

This creates an isolated virtual environment for this project at `/home/pi/language-assistant/.venv`.

### 3) Configure PostgreSQL

Create DB user and DB for the bot:

```bash
sudo -u postgres psql -c "CREATE ROLE langbot WITH LOGIN PASSWORD 'change_me_strong_password';"
sudo -u postgres psql -c "CREATE DATABASE language_assistant OWNER langbot;"
```

Optional: test connectivity:

```bash
psql "postgresql://langbot:change_me_strong_password@localhost:5432/language_assistant" -c "SELECT 1;"
```

### 4) Configure environment

Create `.env` in repo root:

```env
BOT_TOKEN=your_telegram_bot_token
TRANSLATOR=deepl
DEEPL_API_KEY=your_deepl_key
DEEPL_PLAN=free

SOURCE_LANG=PL
TARGET_LANG=RU

DATABASE_URL=postgresql+psycopg://langbot:change_me_strong_password@localhost:5432/language_assistant
DUE_POLL_INTERVAL=45
SHORT_REVIEW_INTERVAL_MINUTES=10
ADMIN_USER_IDS=123456789
```

Find your Telegram user ID (for `ADMIN_USER_IDS`) via bots like `@userinfobot`.

### 5) First run (manual check)

Before creating a service, verify the bot starts from the dedicated environment:

```bash
cd /home/pi/language-assistant
source .venv/bin/activate
python -m vocab_bot
```

Stop it with `Ctrl+C` after confirming no startup errors.

### 6) Create systemd service

Create service file:

```bash
sudo tee /etc/systemd/system/language-assistant-bot.service >/dev/null <<'EOF'
[Unit]
Description=Language Assistant Telegram Bot
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/language-assistant
EnvironmentFile=/home/pi/language-assistant/.env
ExecStart=/home/pi/language-assistant/.venv/bin/python -m vocab_bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now language-assistant-bot
```

### 7) Operate and monitor

Check status:

```bash
sudo systemctl status language-assistant-bot
```

Follow logs:

```bash
journalctl -u language-assistant-bot -f
```

Restart service:

```bash
sudo systemctl restart language-assistant-bot
```

### 8) Update deployment

When you push new code:

```bash
cd /home/pi/language-assistant
git pull origin main
uv sync --frozen
sudo systemctl restart language-assistant-bot
```

### 9) Common issues

- **`FATAL: role ... does not exist`**
  - `DATABASE_URL` points to a PostgreSQL user that is not created.
- **`password authentication failed`**
  - user/password in `DATABASE_URL` does not match Postgres role credentials.
- **Bot starts but does nothing**
  - check `BOT_TOKEN`, then inspect logs with `journalctl -u language-assistant-bot -f`.
- **`DEEPL_API_KEY is required`**
  - add `DEEPL_API_KEY` in `.env` and restart service.
- **`psycopg-binary ... doesn't have a source distribution or wheel for ... armv7l`**
  - use `psycopg` (not `psycopg[binary]`) in project dependencies, then run `uv lock` and redeploy.

### 10) Supporting another language pair

Each deployment handles exactly one fixed pair (`SOURCE_LANG`/`TARGET_LANG`). To support a different pair,
don't reconfigure this deployment — run a second one next to it: new Telegram bot from `@BotFather` (new
`BOT_TOKEN`), its own checkout, `.env`, database, service pair, API port and hostname. The exact convention
is in `docs/miniapp/deployment.md`, "Second language pair on the same host".

## Development

Backend: `uv sync --extra dev --extra api`, then `uv run --extra dev pytest`. Frontend (`webapp/`, Node ≥ 20):
`npm ci`, `npm test`, `npm run check`, `npm run build`. Pre-commit runs ruff + pytest on every commit.

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
- `vocab_bot/translate.py`: translation provider (DeepL)
- `vocab_bot/lang_detect.py`: script-based (Cyrillic vs Latin) direction auto-detection
- `vocab_bot/wordbank.py`: topic-dictionary data model and loader (see "Wordbank" above)
- `vocab_bot/srs.py`: SM-2 style scheduling logic
- `vocab_bot/db.py`: database facade and lifecycle
- `vocab_bot/services/notifications.py`: who gets the consolidated "cards to review" reminder and when
- `vocab_bot/webapi/`: FastAPI backend of the Mini App (separate process, `initData` auth)
- `webapp/`: Svelte frontend of the Mini App (built locally, deployed as static files)
- `docs/miniapp/`: Mini App design, API contract, implementation plan and the VPS deployment guide
- `docs/new-bot-playbook.md`: reusable recipe (stack, layer rules, conventions, testing, deployment, bootstrap checklist)
  for starting another Telegram bot from this project
- `scripts/parse_ru_pl_dictionary.py`: dev-only tool that regenerates the wordbank JSON from the source PDF
