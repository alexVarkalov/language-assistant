# Deployment (VPS)

Target: one small Linux VPS (1 vCPU / 1 GB is plenty) running **everything**: PostgreSQL, the bot, the API
and nginx. This is the recommended layout — one host, one database on `localhost`, one `.env`.

The alternative (bot + Postgres stay on the Raspberry Pi, only API + nginx on the VPS) is described at the
end; it works but adds a cross-host database connection to maintain.

Assumptions (adjust to taste):

- OS: Debian 12 / Ubuntu 24.04, user `app`, repo at `/home/app/language-assistant`
- domain `vocab.example.com` pointing (A/AAAA) at the VPS
- service names `language-assistant-bot`, `language-assistant-api`

## 1) Base setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates postgresql postgresql-contrib nginx
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

Firewall: allow only 22, 80, 443 (`ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable`). Postgres and
uvicorn bind to `127.0.0.1` only.

## 2) PostgreSQL

Fresh install:

```bash
sudo -u postgres psql -c "CREATE ROLE langbot WITH LOGIN PASSWORD 'change_me_strong_password';"
sudo -u postgres psql -c "CREATE DATABASE language_assistant OWNER langbot;"
```

Migrating existing data from the Pi (do this once, with the Pi bot **stopped** so no reviews are lost):

```bash
# on the Pi
sudo systemctl stop language-assistant-bot
pg_dump -Fc -U langbot -h localhost language_assistant > language_assistant.dump
scp language_assistant.dump app@vocab.example.com:/home/app/

# on the VPS
pg_restore -U langbot -h localhost -d language_assistant --no-owner --no-privileges /home/app/language_assistant.dump
```

Keep the Pi service disabled afterwards (`sudo systemctl disable language-assistant-bot`) — two bots polling
the same token fight over updates.

## 3) Code and environment

```bash
cd /home/app
git clone <repo-url> language-assistant
cd language-assistant
uv venv .venv --python 3.14
uv sync --frozen --extra api
```

`.env` (same file for both services):

```env
BOT_TOKEN=...
DEEPL_API_KEY=...
DEEPL_PLAN=free
TRANSLATOR=deepl
SOURCE_LANG=PL
TARGET_LANG=RU
DATABASE_URL=postgresql+psycopg://langbot:change_me_strong_password@localhost:5432/language_assistant
DUE_POLL_INTERVAL=45
SHORT_REVIEW_INTERVAL_MINUTES=10
ADMIN_USER_IDS=123456789
WORDBANK_PATH=data/ru_pl_dictionary.json      # optional; scp the JSON out-of-band as before

# Mini App
WEBAPP_URL=https://vocab.example.com
WEBAPP_API_HOST=127.0.0.1
WEBAPP_API_PORT=8080
WEBAPP_INITDATA_MAX_AGE=86400
```

Leave `WEBAPP_URL` **commented out** until nginx + TLS + the frontend are live (step 6); the bot only
advertises the app when this is set.

## 4) systemd units

`/etc/systemd/system/language-assistant-bot.service` — as in the README Raspberry Pi section, with
`User=app` and `/home/app/...` paths.

`/etc/systemd/system/language-assistant-api.service`:

```ini
[Unit]
Description=Language Assistant Mini App API
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=app
WorkingDirectory=/home/app/language-assistant
EnvironmentFile=/home/app/language-assistant/.env
ExecStart=/home/app/language-assistant/.venv/bin/python -m vocab_bot.webapi
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now language-assistant-bot language-assistant-api
curl -s http://127.0.0.1:8080/api/health     # {"status":"ok"}
```

## 5) nginx + TLS

`/etc/nginx/sites-available/vocab`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name vocab.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name vocab.example.com;

    # certbot fills these in
    ssl_certificate     /etc/letsencrypt/live/vocab.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vocab.example.com/privkey.pem;

    root /var/www/vocab;                 # webapp/dist copied here
    index index.html;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    # Telegram opens the app inside its own webview; allow framing only by telegram.org/web.telegram.org
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org" always;

    location = /api/health { proxy_pass http://127.0.0.1:8080; access_log off; }

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    location / {
        try_files $uri /index.html;
        # hashed assets can be cached hard; index.html must not be
        location ~* \.(js|css|woff2?)$ { expires 30d; add_header Cache-Control "public, immutable"; }
        location = /index.html { add_header Cache-Control "no-cache"; }
    }
}
```

Add to `/etc/nginx/nginx.conf` inside `http {}`:

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
```

```bash
sudo ln -s /etc/nginx/sites-available/vocab /etc/nginx/sites-enabled/vocab
sudo mkdir -p /var/www/vocab && sudo chown app:app /var/www/vocab
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d vocab.example.com          # obtains cert, enables auto-renew timer
sudo nginx -t && sudo systemctl reload nginx
curl -s https://vocab.example.com/api/health      # {"status":"ok"}
```

If `'unsafe-inline'` for styles bothers you: Svelte/Vite emit a CSS file by default, so it can be dropped
after verifying the built `index.html` has no inline `<style>`.

## 6) Frontend build and publish

Node is only needed where you build (your laptop is fine; the VPS does not need Node at all):

```bash
cd webapp
npm ci
npm run build                                       # → webapp/dist
rsync -av --delete dist/ app@vocab.example.com:/var/www/vocab/
```

Then on the VPS: uncomment `WEBAPP_URL` in `.env` and `sudo systemctl restart language-assistant-bot`. The bot
sets the Menu Button on startup; if it does not show up in Telegram within a minute, fully close and reopen
the Telegram client (menu buttons are cached).

## 7) BotFather

Nothing mandatory — the Menu Button is set by the bot. Optional:

- `/setmenubutton` — set it by hand instead of (or before) the code path.
- `/newapp` — register a named Mini App to get a shareable direct link `https://t.me/<bot>/<app>`; point
  it at `https://vocab.example.com`. The app reads `start_param` from `initData` if you ever pass
  `?startapp=...`.
- `/setdomain` is **not** needed (that is for the Login Widget, not Mini Apps).

## 8) Updating

```bash
cd /home/app/language-assistant
git pull origin main
uv sync --frozen --extra api
sudo systemctl restart language-assistant-api language-assistant-bot
# frontend, when webapp/ changed: build locally, rsync dist/ (step 6)
```

Additive DB migrations run in `Database._init_sync` on both processes' startup; restarting either applies them.

## 9) Monitoring / troubleshooting

```bash
journalctl -u language-assistant-api -f
journalctl -u language-assistant-bot -f
sudo tail -f /var/log/nginx/error.log
```

| Symptom | Check |
|---|---|
| Telegram shows a blank/white app | Open `https://vocab.example.com` in a normal browser: you should see the "open from Telegram" screen. If not, nginx root/`index.html`. |
| App loads, every call is 401 | `BOT_TOKEN` in `.env` on the VPS differs from the bot the app was opened from; or clock skew making `auth_date` look old (`timedatectl`). |
| 403 access disabled | User is blocked — `/allow_user <id>` in chat. |
| Menu Button missing | `WEBAPP_URL` unset or not `https://`; bot logs show `set_chat_menu_button` error; restart Telegram client. |
| Bot works, API 502 | `systemctl status language-assistant-api`; port mismatch between `.env` and nginx. |
| Reviews graded in app still notify in chat | Expected in MVP (see architecture.md → Known limitations); phase 2. |

## Alternative: keep bot + Postgres on the Pi, API on the VPS

Only the API needs to be public; the bot can stay where it is. Then the VPS API must reach the Pi's
Postgres:

1. Put both hosts on a private network — Tailscale (simplest) or a WireGuard tunnel.
2. On the Pi: `listen_addresses = 'localhost,<tailscale-ip>'` in `postgresql.conf`, a `pg_hba.conf` line
   `hostssl language_assistant langbot <vps-tailscale-ip>/32 scram-sha-256`, and `ssl = on`.
3. VPS `.env`: `DATABASE_URL=postgresql+psycopg://langbot:...@<pi-tailscale-ip>:5432/language_assistant?sslmode=require`.
4. Steps 3–6 above apply to the VPS for the API/nginx only (`uv sync --frozen --extra api`, no bot unit); the
   Pi `.env` gets `WEBAPP_URL` and the bot is restarted there.

Trade-offs: every API request crosses your home uplink (latency, and the app is down when the Pi or home
internet is), and you now operate a VPN. Prefer the single-host layout unless there is a reason to keep the
database at home.
