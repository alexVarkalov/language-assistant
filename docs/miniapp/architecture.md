# Mini App architecture

> **Design document (2026-09-13).** Implemented as written on 2026-09-13; the following parts were then
> superseded on 2026-09-14 and are kept only for context (marked *Superseded* below):
> the chat review flow, `awaiting_grade` semantics and the double-grading guard (chat reviews removed),
> the per-card notification with `?card=` (replaced by one consolidated reminder per user, see
> `services/notifications.py`), and everything "conditional on `WEBAPP_URL`" (now mandatory).

## Components

```
┌──────────────── Telegram client ────────────────┐
│  chat with bot          Mini App webview (HTTPS) │
│  [inline buttons]       Svelte SPA + telegram-   │
│                         web-app.js               │
└──────────┬──────────────────────┬────────────────┘
           │ Bot API (polling)    │ HTTPS  Authorization: tma <initData>
           ▼                      ▼
   vocab-bot (existing)     nginx ──► vocab-bot-api (uvicorn)
   handlers/ → services/           webapi/  → services/
           │                              │
           └────────► PostgreSQL ◄────────┘
```

- **Bot process** (`python -m vocab_bot`) — chat handles translation/saving/wordbank; reviews are delegated to
  the app via a persistent Menu Button and a consolidated "N cards to review → Open app" reminder
  (`due_poll` + `DueNotificationService`).
- **API process** (`python -m vocab_bot.webapi`) — FastAPI app. Validates `initData`, calls the same
  `ReviewService`/`UserService` the handlers use, returns JSON. Owns its own `Database` instance.
- **Frontend** (`webapp/`, Svelte + Vite) — built to static files, served by nginx on the same origin as the API.
- **nginx** — TLS termination, serves `webapp/dist` at `/`, proxies `/api/` to `127.0.0.1:8080`.

## Where it sits in the 4-layer stack

`webapi/` is a second **entry-point layer**, a sibling of `handlers/`, not a layer above it:

```
handlers/  (Telegram Update)  ─┐
webapi/    (HTTP request)     ─┼─→  services  →  repositories  →  persistence
                               ─┘
```

Rules carried over from `CLAUDE.md`:

- `webapi/` is thin: parse request → auth → call a service → map result to a pydantic schema. No SQL, no
  SRS math, no business decisions.
- `webapi/` **never imports `handlers/`** (that module tree imports `telegram`). Shared helpers that both need
  move down into `services/` (see "Refactors" below).
- `services/` and `persistence/` still never import `telegram` — and now also never import `fastapi`.
- New capability = touch layers in order: persistence → repository → service → webapi (and/or handler).

## Authentication: Telegram `initData`

Every request from the Mini App carries `Authorization: tma <initData>` where `initData` is the raw
`window.Telegram.WebApp.initData` query string. The API validates it on every request (stateless, no sessions):

1. Parse as a query string (`urllib.parse.parse_qsl`). Pop `hash`.
2. Build the data-check-string: remaining pairs sorted by key, joined as `key=value` with `\n`.
3. `secret_key = HMAC_SHA256(key=b"WebAppData", msg=BOT_TOKEN)`
4. `expected = HMAC_SHA256(key=secret_key, msg=data_check_string).hexdigest()`
5. `hmac.compare_digest(expected, hash)` — reject with **401** on mismatch.
6. Reject with **401** if `now - auth_date > WEBAPP_INITDATA_MAX_AGE` (default 24 h).
7. Parse the `user` JSON field → `telegram_id`, `username`, `first_name`, `last_name`, `language_code`.

The validated user is then run through the same lifecycle as a chat update:

- `UserService.record_seen(...)` — upserts the user row and `last_seen_at`, exactly like `record_user_seen()`.
- access check (`is_allowed` or in `ADMIN_USER_IDS`) — reject with **403** otherwise. Blocked users can open
  the app (Telegram opens any URL) but every API call fails; the frontend shows the `access_disabled` message.

The client-supplied `telegram_id` is **never** trusted from a body/query param — only from validated
`initData`. `BOT_TOKEN` is required by the API process for this reason (same `.env` as the bot).

`auth.py` is a pure module (`parse_and_validate_init_data(raw: str, bot_token: str, *, now, max_age) -> InitData`)
so it can be unit-tested with a fixed token and hand-computed signatures.

## Review flow (MVP)

```
open app ──► GET /api/me ──► GET /api/reviews/queue
                                  │
              ┌───────────────────┘
              ▼
        show prompt side ──tap──► flip: show answer ──tap grade──► POST /api/reviews/{id}/grade
              ▲                                                            │
              └──────────────── next card in local queue ◄─────────────────┘
                                          │ queue empty
                                          ▼
                                    "All done" screen (WebApp.close() or stay)
```

- The queue is fetched **once** on open (up to `limit`, default 50) and drained client-side; each grade is a
  separate `POST`. No polling.
- Direction (which side is the prompt) is chosen **server-side** per card, matching the existing chat
  behaviour (`random.choice(["source", "target"])` in `due_poll`). The queue response carries
  `prompt_text`/`answer_text` already resolved so the client has no language logic.
- Grades reuse `ReviewService.apply_grade(card_id, user_id, quality)` — same SM-2 path as `grade:` callbacks.
  Quality values are the same three the chat uses: `0` Again, `3` Good, `5` Easy.

### Queue semantics vs the chat flow

*Superseded 2026-09-14: the chat flow and `awaiting_grade` handling are gone; the per-user queue is simply
`next_review_at <= now` for that user. The column remains in the DB, always `False`.*

Today `CardStore.list_due_cards()` is **global** (all users, for `due_poll`) and **excludes**
`awaiting_grade=True` cards — those are the ones a chat notification has already been sent for. The Mini App
queue needs the opposite: **one user, including awaiting cards** (the user should be able to review a card in
the app even though the bot already pinged them about it in chat). Hence a new persistence method
`list_due_cards_for_user(user_id, limit)` with `next_review_at <= now` and no `awaiting_grade` filter.

Grading via the API goes through `update_card_srs`, which already sets `awaiting_grade = False`, so a card
graded in the app drops out of the chat's "awaiting" state automatically.

### Preventing double grading

*Superseded 2026-09-14: no chat grading exists any more, so nothing to guard.*

A user can grade a card in the app while the chat notification (with its `reveal:`/`grade:` buttons) is still
on screen. The bot's in-memory `awaiting_review_messages` map lives in a different process, so the API cannot
edit that message. Instead the chat handlers become defensive:

- `reveal:{card_id}:...` and `grade:{card_id}:...` re-read the card and, if `card.awaiting_grade` is `False`,
  edit the message to a new `review_already_graded` string and stop.

This is a small, safe change: in the normal chat flow the flag is `True` from `due_poll` until `grade:` runs.

## Launch points

*Superseded 2026-09-14: (1) is now one consolidated reminder per user opening the app root, not a per-card
`?card=` link; (2) and (3) are unconditional because `WEBAPP_URL` is required.*

1. **Due-review notification** — `due_poll` adds a second row under the existing "Reveal" button:
   `InlineKeyboardButton(t(locale, "due_open_app"), web_app=WebAppInfo(url=f"{WEBAPP_URL}/?card={card.id}"))`.
   The `?card=` hint lets the frontend move that card to the front of the queue; it is a hint only, never
   trusted for access (the queue endpoint already scopes to the authenticated user).
2. **Menu Button** — in `_post_init`, when `WEBAPP_URL` is set:
   `await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text=..., web_app=WebAppInfo(url=WEBAPP_URL)))`.
   `chat_id=None` sets the default for all private chats. (Can also be done once by hand via BotFather
   `/setmenubutton`; doing it in code keeps it in sync with `.env`.)
3. **`/start`** — one extra line pointing at the Menu Button when `WEBAPP_URL` is set.

All three are conditional on `settings.webapp_url`, following the `WORDBANK_PATH` pattern: unset → the bot
behaves exactly as today.

## Frontend

- `webapp/` at the repo root, Svelte 5 + Vite + TypeScript. Build output `webapp/dist/` is gitignored and
  deployed as static files (built locally or on the VPS — the Pi is not involved).
- `index.html` loads `https://telegram.org/js/telegram-web-app.js` before the app bundle.
- On boot: `WebApp.ready()`, `WebApp.expand()`, read `WebApp.initData` (empty string ⇒ opened outside
  Telegram ⇒ show a "open this from Telegram" screen).
- Theme: use Telegram CSS variables (`--tg-theme-bg-color`, `--tg-theme-text-color`,
  `--tg-theme-button-color`, …) so the app follows the user's Telegram theme, light and dark.
- Grade buttons: `WebApp.HapticFeedback.impactOccurred("light")` on tap; optional swipe gestures later.
- UI strings: tiny `i18n.ts` with `en`/`ru` maps; locale from `GET /api/me` (server resolves it with the
  existing `resolve_user_locale`, so app and chat agree).
- Times: API returns ISO-8601 UTC; client formats in the user's IANA timezone from `/api/me`
  (`Intl.DateTimeFormat(undefined, { timeZone })`).

## Configuration

New environment variables (all optional; `.env.example` and README get updated in the implementation):

| Var | Used by | Default | Meaning |
|---|---|---|---|
| `WEBAPP_URL` | bot | unset | Public HTTPS URL of the Mini App. When set, enables the Menu Button, the "Open in app" row on due notifications and the `/start` hint. Must be `https://`; validated at startup. |
| `WEBAPP_API_HOST` | api | `127.0.0.1` | Bind address for uvicorn (nginx sits in front). |
| `WEBAPP_API_PORT` | api | `8080` | Bind port. |
| `WEBAPP_INITDATA_MAX_AGE` | api | `86400` | Max accepted age of `initData.auth_date`, seconds. |

Both processes read the same `.env` via the same `Settings.from_env()`. `BOT_TOKEN` (for HMAC) and
`DATABASE_URL` are the only ones the API strictly needs; `DEEPL_API_KEY` remains required by `Settings`
validation, which is fine since it is the same file.

## Code layout (new/changed files)

```
vocab_bot/
  config.py                      + webapp_url, webapp_api_host, webapp_api_port, webapp_initdata_max_age
  persistence/cards.py           + list_due_cards_for_user / _list_due_cards_for_user_sync
  repositories/cards.py          + list_due_for_user
  services/reviews.py            + list_due_cards_for_user, DueCard DTO with resolved prompt/answer/direction
  services/users.py              + user_has_access(user, admin_user_ids)  (moved from handlers/common.py)
  handlers/common.py             user_has_access delegates to services.users
  handlers/reviews.py            due_poll: consolidated reminder (superseded the per-card row on 2026-09-14)
  services/notifications.py      DueNotificationService (added 2026-09-14)
  handlers/callbacks.py          (reveal:/grade: removed 2026-09-14)
  handlers/commands.py           /start hint
  i18n.py                        + due_open_app, menu_button_app, start_app_hint, review_already_graded (en + ru)
  __main__.py                    _post_init: set_chat_menu_button when webapp_url set
  webapi/
    __init__.py
    __main__.py                  main(): Settings.from_env(), uvicorn.run(create_app(settings), host, port)
    app.py                       create_app(settings) -> FastAPI; lifespan builds Database + repos + services on app.state
    auth.py                      pure initData parsing/validation (no FastAPI imports)
    deps.py                      get_current_user(): reads Authorization header, validates, record_seen, access check
    schemas.py                   pydantic models: MeResponse, QueueCard, GradeRequest, GradeResponse, ErrorResponse
    routes/
      __init__.py
      me.py                      GET /api/me
      reviews.py                 GET /api/reviews/queue, POST /api/reviews/{card_id}/grade
webapp/                          Svelte + Vite project (see implementation-plan.md)
tests/
  webapi/test_auth.py            pure HMAC tests
  webapi/test_routes_reviews.py  httpx.AsyncClient + ASGITransport, AsyncMock services on app.state
  webapi/test_routes_me.py
  webapi/test_deps.py            401/403 paths
  (+ updates in tests/persistence, tests/repositories, tests/services, tests/handlers for the new methods/guards)
pyproject.toml                   optional extra `api = ["fastapi", "uvicorn"]`; script `vocab-bot-api`
.gitignore                       + webapp/node_modules/, webapp/dist/
docs/miniapp/                    these docs
```

### Refactors needed so `webapi/` does not import `handlers/`

- `user_has_access(user, settings)` currently lives in `handlers/common.py`. Move the logic to
  `services/users.py` as `user_has_access(user: BotUser, admin_user_ids: frozenset[int]) -> bool`; keep the
  `handlers/common.py` function as a one-line wrapper so existing handler code and tests are untouched.
- Direction selection (`random.choice(["source", "target"])`) moves from `due_poll` into
  `ReviewService` (a `DueCard` DTO with `direction`, `prompt_text`, `answer_text`, `prompt_lang`,
  `answer_lang`). `due_poll` and the queue route both consume it.

## Security notes

- HTTPS only (Telegram refuses `http://` for `web_app`). nginx redirects 80 → 443.
- `initData` validated on **every** request; no session cookies, nothing to steal or fixate.
- `auth_date` max age bounds replay of a leaked `initData` string.
- All card queries are scoped by `user_id` from `initData` (`CardStore.get_card(card_id, user_id)` already
  enforces ownership; the queue method takes `user_id`).
- Same origin for frontend and API — no CORS middleware needed; do not add a permissive one "just in case".
- nginx: `limit_req` on `/api/` (e.g. 10 r/s per IP) is cheap insurance; the bot token is never sent to the
  browser.
- Log validation failures at `WARNING` with the reason but never log the raw `initData` (it contains the hash
  and user data).

## Known limitations (MVP) → later phases

- ~~**Chat notifications keep coming while reviewing in the app.**~~ Done (2026-09-14): `due_poll` now sends one
  consolidated "N cards to review → [Open app]" message per user. `DueNotificationService` decides who: the
  first due card after an empty queue is announced on the next poll, then at most once per
  `DUE_NOTIFY_COOLDOWN_MINUTES` while the queue stays non-empty (`users.due_notified_at`, reset when the
  user's queue is empty). Per-card chat notifications are gone; the job only runs when `WEBAPP_URL` is set.
- ~~**Stale chat messages.**~~ Gone with the chat review flow (2026-09-14): `reveal:`/`grade:` callbacks, the
  typed-guess path and `awaiting_grade` handling were removed; the column stays in the DB, always `False`.
- **No offline support.** Grades are sent immediately; a failed `POST` is retried once, then surfaced.
