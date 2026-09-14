# Deployment (VPS)

Target: one small Linux VPS (1 vCPU / 1 GB is plenty) running **everything**: PostgreSQL, the bot, the API
and nginx. This is the recommended layout — one host, one database on `localhost`, one `.env`.

The alternative (bot + Postgres stay on the Raspberry Pi, only API + nginx on the VPS) is described at the
end; it works but adds a cross-host database connection to maintain.

Assumptions (adjust to taste):

- OS: Debian 12 / Ubuntu 24.04, user `app`, repo at `/home/app/language-assistant`
- domain `vocab.example.com` pointing (A/AAAA) at the VPS
- service names `language-assistant-bot`, `language-assistant-api`

## 0) Provisioning on DigitalOcean

Recommended provider: DigitalOcean, region **`ams3` (Amsterdam)** — Telegram's Bot API servers are in
Amsterdam, so latency is single-digit ms; `fra1` (Frankfurt) is the fallback if `ams3` has no capacity.
Not the absolute cheapest EU VPS, but orderable, familiar, and fully scriptable via `doctl`, which matters
when the server is managed through Claude rather than by hand.

What it costs (September 2026):

| Item | Monthly |
|---|---|
| Basic Droplet `s-1vcpu-1gb` (1 vCPU / 1 GB / 25 GB SSD / 1 TB transfer, IPv4 included) | $6.00 |
| Weekly backups (20 % of the Droplet; daily is 30 %) | $1.20 |
| **Total** | **≈ $7.20** |

Do not take the $4 512 MB Droplet: Postgres + bot + API + nginx fit in 1 GB, not in 512 MB, and 10 GB of
disk leaves no room for dumps. Billing is per second, so a throwaway test Droplet costs cents.

### Via `doctl` (preferred)

Install `doctl` locally (`brew install doctl` / `snap install doctl` / GitHub release), create a
**read+write API token** in the control panel (API → Tokens), then:

```bash
doctl auth init                                   # paste the token once; stored in ~/.config/doctl
doctl compute ssh-key import laptop --public-key-file ~/.ssh/id_ed25519.pub
doctl compute ssh-key list                        # note the numeric ID

doctl compute droplet create vocab \
  --region ams3 --size s-1vcpu-1gb --image debian-12-x64 \
  --ssh-keys <ssh-key-id> --enable-backups --enable-ipv6 --wait
doctl compute droplet list --format ID,Name,PublicIPv4,PublicIPv6   # note the ID and IPs

# Cloud firewall (separate from ufw): inbound 22/80/443 only, all outbound.
doctl compute firewall create --name vocab-web \
  --inbound-rules "protocol:tcp,ports:22,address:0.0.0.0/0,address:::/0 protocol:tcp,ports:80,address:0.0.0.0/0,address:::/0 protocol:tcp,ports:443,address:0.0.0.0/0,address:::/0" \
  --outbound-rules "protocol:tcp,ports:all,address:0.0.0.0/0,address:::/0 protocol:udp,ports:all,address:0.0.0.0/0,address:::/0 protocol:icmp,address:0.0.0.0/0,address:::/0" \
  --droplet-ids <droplet-id>
```

Keep `ufw` on the host too (section 1) — two layers, no cost. Root login is key-only from first boot
because the key was passed at creation; never set a root password. Create the `A`/`AAAA` records for
`vocab.example.com` now (DigitalOcean DNS via `doctl compute domain records create`, or wherever the
zone lives) so they have propagated by the time certbot runs.

### Via the control panel

Same thing clicked through: **Create → Droplets**, region Amsterdam, image Debian 12, Basic / Regular
$6 plan, authentication *SSH key*, tick *Enable backups* and *IPv6*; then **Networking → Firewalls →
Create**, inbound TCP 22/80/443, attach to the Droplet.

### Alternatives

Everything from "First login" onward is provider-agnostic (Debian 12 + `ufw`), so any of these works
unchanged:

| Provider | Plan | Spec | Price | Notes |
|---|---|---|---|---|
| netcup (DE) | VPS 500 G12 | 2 vCPU / 4 GB / 128 GB NVMe | ≈ €5.91/month incl. VAT | Cheapest all-in; Nuremberg/Vienna; IPv4 + snapshots included; no CLI, panel only. Pick this if you want to run Claude Code *on* the server (1 GB is too tight for that). |
| Hetzner Cloud (DE/FI) | CAX11 / CX23 | 2 vCPU / 4 GB / 40 GB | ≈ €5.49–5.99 + €0.50 IPv4 + 20 % backups | Great `hcloud` CLI, but after the June 2026 price rise the cheap CX/CAX line is usually **"not available"**; the orderable floor is CPX12 (≈ €12) / CPX22 (≈ €19.49, ≈ $23) — not worth it for this workload. |
| OVHcloud (FR) | VPS-1 | 2 vCPU / 4 GB / 40 GB NVMe | from ≈ $4.54/month | Headline price needs a 12–24 month commitment; month-to-month is netcup territory. IPv4 + daily backup included. |

First login, then create the unprivileged `app` user the rest of this doc assumes:

```bash
ssh root@<server-ip>
adduser --disabled-password --gecos "" app
usermod -aG sudo app
echo "app ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/app
mkdir -p /home/app/.ssh && cp /root/.ssh/authorized_keys /home/app/.ssh/ && chown -R app:app /home/app/.ssh
# harden sshd: key-only, no root
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/; s/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
exit
ssh app@<server-ip>          # everything below runs as app
```

Optional but worth it on a box you touch rarely: `sudo apt install -y unattended-upgrades` (security updates
apply themselves; reboots for kernel updates are manual — check `/var/run/reboot-required`).

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

## 10) Postgres backups (cron)

DigitalOcean's Droplet backups restore the whole disk; a nightly `pg_dump` is what you actually reach for when a
bad migration or a mistaken `DELETE` needs undoing. Everything valuable lives in one database, so one dump
file per day is enough.

```bash
sudo -u postgres psql -c "ALTER ROLE langbot WITH PASSWORD 'change_me_strong_password';"   # if not set yet
mkdir -p /home/app/backups /home/app/bin
cat > /home/app/.pgpass <<'EOF'
localhost:5432:language_assistant:langbot:change_me_strong_password
EOF
chmod 600 /home/app/.pgpass
```

`/home/app/bin/backup-db.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
dir=/home/app/backups
stamp=$(date -u +%Y-%m-%dT%H%M)
tmp="$dir/language_assistant-$stamp.dump.tmp"
out="$dir/language_assistant-$stamp.dump"
pg_dump -Fc -h localhost -U langbot language_assistant > "$tmp"
mv "$tmp" "$out"                                   # only complete dumps get the final name
find "$dir" -name 'language_assistant-*.dump' -mtime +30 -delete
```

```bash
chmod +x /home/app/bin/backup-db.sh
/home/app/bin/backup-db.sh && ls -la /home/app/backups      # run once by hand
crontab -e
```

Cron line (03:15 UTC daily; the server clock is UTC, and review load is lowest then for a European user
base). Output goes to a log file so a failure is visible in the next `ls`:

```cron
15 3 * * * /home/app/bin/backup-db.sh >> /home/app/backups/backup.log 2>&1
```

Get the dumps **off the box** too — a backup on the same disk does not survive the disk. The dumps are
tiny (kilobytes to a few MB), so the cheapest option is simply pulling the directory to your laptop or the
Pi every so often (or from the Pi's own cron):

```bash
rsync -a app@vocab.example.com:/home/app/backups/ ~/backups/language-assistant/
```

If you want it pushed from the server instead: **DigitalOcean Spaces** ($5/month for 250 GiB,
S3-compatible, `rclone copy /home/app/backups spaces:language-assistant` appended to the script) is overkill
at that size; a Hetzner **Storage Box** (BX11, ~€3/month, 1 TB, `rsync` over SSH) works from any provider
and is cheaper.

Restore path is the one used for the Pi migration: `pg_restore -U langbot -h localhost -d language_assistant --no-owner --no-privileges <file>`
(into an empty database: `dropdb`/`createdb` first, with both services stopped).

Test the restore once after setting this up — a backup that has never been restored is a hope, not a
backup.

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
