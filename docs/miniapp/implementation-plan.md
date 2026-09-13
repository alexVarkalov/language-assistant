# Implementation plan

Ordered so that every step leaves `main` green (`ruff` + `pytest`) and deployable. Steps 1–5 are pure backend
and can ship before any frontend exists; the bot keeps behaving exactly as today until `WEBAPP_URL` is set.

Conventions apply throughout (see `CLAUDE.md`): layers in order persistence → repository → service →
entry point; i18n keys added for `en` **and** `ru` in the same change; tests mirror source layout; no
`telegram` import outside `handlers/`, no `fastapi` import outside `webapi/`.

---

## Phase 1 — MVP: due-card review

### Step 1 — Persistence + repository: per-user due queue

**`vocab_bot/persistence/cards.py`**

- `async def list_due_cards_for_user(self, user_id: int, limit: int) -> list[Card]` +
  `_list_due_cards_for_user_sync`: `where user_id == :user_id and next_review_at <= utc_now()`, ordered by
  `next_review_at asc`, **no** `awaiting_grade` filter. Uses the existing `idx_cards_due` index.
- `async def count_due_cards_for_user(self, user_id: int) -> int` + sync twin (for `/api/me.due_count` and
  `queue.total_due`).

**`vocab_bot/repositories/cards.py`**

- `list_due_for_user(user_id, limit=50)`, `count_due_for_user(user_id)`.

**Tests**

- `tests/persistence/test_cards_store.py`: fake-session tests for both sync methods — includes awaiting
  cards, excludes other users, excludes future cards, respects limit/order.
- `tests/repositories/test_cards.py`: delegation tests.

### Step 2 — Services: `DueCard`, direction selection, access helper

**`vocab_bot/services/reviews.py`**

- `@dataclass(frozen=True) class DueCard`: `card: Card`, `direction: Literal["source","target"]`,
  `prompt_text`, `prompt_lang`, `answer_text`, `answer_lang`.
- `def build_due_card(card: Card, direction: str) -> DueCard` (pure) and
  `def pick_direction(rng: random.Random | None = None) -> str`.
- `async def list_due_cards_for_user(self, *, user_id, limit=50, first_card_id: int | None = None) -> list[DueCard]`
  — fetches via repo, picks a direction per card, moves `first_card_id` to the front if present.
- `async def count_due_for_user(self, *, user_id) -> int`.
- Constructor gains optional `rng: random.Random | None` for deterministic tests.

**`vocab_bot/services/users.py`**

- Module-level `def user_has_access(user: BotUser, admin_user_ids: frozenset[int]) -> bool`.

**`vocab_bot/handlers/common.py`**

- `user_has_access(user, settings)` becomes `return users.user_has_access(user, settings.admin_user_ids)`.

**`vocab_bot/handlers/reviews.py`**

- `due_poll` builds prompt/answer via `build_due_card(card, pick_direction())` instead of the inline
  `random.choice` block (behaviour unchanged; keeps one source of truth).

**Tests**

- `tests/services/test_reviews.py`: `build_due_card` both directions; `list_due_cards_for_user` ordering and
  `first_card_id` promotion (present / absent); seeded `rng`.
- `tests/services/test_users_service.py`: `user_has_access` allowed / admin / blocked.
- `tests/handlers/test_reviews_handler.py`: still passes (direction now comes from the service).

### Step 3 — Config

**`vocab_bot/config.py`**

- `webapp_url: str | None` — `WEBAPP_URL`, stripped, trailing `/` removed; must start with `https://` else
  `ValueError("WEBAPP_URL must be an https:// URL")`.
- `webapp_api_host: str` (`WEBAPP_API_HOST`, default `127.0.0.1`), `webapp_api_port: int`
  (`WEBAPP_API_PORT`, default `8080`, invalid → default), `webapp_initdata_max_age: int`
  (`WEBAPP_INITDATA_MAX_AGE`, default `86400`, min `60`).

**`.env.example`**, **`README.md` → Configuration** — document the four vars.

**Tests** — `tests/test_config.py`: unset → `None`/defaults; `http://` rejected; trailing slash stripped.

### Step 4 — `webapi/` package

**`pyproject.toml`**

```toml
[project.optional-dependencies]
api = ["fastapi>=0.115,<1", "uvicorn[standard]>=0.30,<1"]
dev = ["pre-commit", "pytest", "pytest-asyncio", "ruff", "fastapi>=0.115,<1", "httpx>=0.27,<1"]

[project.scripts]
vocab-bot-api = "vocab_bot.webapi.__main__:main"
```

(`httpx` is already a runtime dep; it is what the route tests use via `ASGITransport`.)

**`vocab_bot/webapi/auth.py`** (pure, no FastAPI)

- `@dataclass(frozen=True) class InitData`: `telegram_id`, `username`, `first_name`, `last_name`,
  `language_code`, `auth_date: datetime`, `start_param: str | None`.
- `class InitDataError(ValueError)`.
- `def parse_and_validate_init_data(raw: str, bot_token: str, *, now: datetime, max_age_seconds: int) -> InitData`
  implementing the algorithm in architecture.md. Rejects: empty, missing `hash`, signature mismatch, missing or
  non-integer `auth_date`, expired, missing/invalid `user` JSON.
- `def compute_init_data_hash(pairs: Mapping[str, str], bot_token: str) -> str` exposed so tests can build
  valid fixtures.

**`vocab_bot/webapi/schemas.py`** — pydantic v2 models exactly as in `api.md`. Datetimes serialized as
ISO-8601 with `Z`.

**`vocab_bot/webapi/deps.py`**

- `get_settings(request) -> Settings`, `get_review_service(request)`, `get_user_service(request)` read
  from `request.app.state`.
- `async def get_current_user(request, ...) -> BotUser`: header parse (`tma` scheme, case-insensitive) → 401
  `missing_auth`; validate → 401 `invalid_init_data`; `user_service.record_seen(...)`; access check → 403.

**`vocab_bot/webapi/app.py`**

- `def create_app(settings: Settings, *, db: Database | None = None) -> FastAPI` with a `lifespan` that builds
  `Database(settings.database_url)` (unless injected — tests inject a stub), calls `db.init()`, constructs
  repos and services, stores everything on `app.state`. Registers routers under `/api`, an exception handler
  that reshapes `HTTPException`/validation errors into the `{error, message}` envelope, and
  `GET /api/health` (unauthenticated, `{"status":"ok"}`) for nginx/systemd checks.

**`vocab_bot/webapi/routes/me.py`**, **`routes/reviews.py`** — per `api.md`. Each route: dependency-inject
user + services, call one service method, return schema. `grade` returns 404 `card_not_found` when
`apply_grade` returns `None`.

**`vocab_bot/webapi/__main__.py`**

- `main()`: `_load_dotenv_if_present()` (move this helper from `vocab_bot/__main__.py` to
  `vocab_bot/config.py` as `load_dotenv_if_present()` so both entry points share it), logging setup,
  `Settings.from_env()`, `uvicorn.run(create_app(settings), host=..., port=..., proxy_headers=True)`.

**Tests** (`tests/webapi/`)

- `test_auth.py`: golden-path with a fixture built via `compute_init_data_hash`; tampered field; wrong token;
  missing hash; expired `auth_date`; `max_age` boundary; malformed `user` JSON; `start_param` passthrough.
- `test_deps.py`: via a minimal app — no header → 401 `missing_auth`; bad scheme → 401; blocked user →
  403 `access_disabled`; admin bypass; `record_seen` called with the initData user fields.
- `test_routes_me.py`, `test_routes_reviews.py`: `httpx.AsyncClient(transport=ASGITransport(app=app))`
  with `AsyncMock` services set on `app.state` (pattern mirrors `tests/handlers/*` using `AsyncMock`
  services). Cover: queue shape/direction resolution, `limit` bounds (0, 101 → 422), `first` promotion,
  grade happy path, invalid `quality` (1, 4, 7 → 422), unknown card → 404, `total_due`.
- `test_app.py`: `/api/health` without auth; error envelope shape for a 422.

### Step 5 — Bot integration (behind `WEBAPP_URL`)

**`vocab_bot/i18n.py`** (en + ru)

| key | en | ru |
|---|---|---|
| `due_open_app` | `Open in app` | `Открыть в приложении` |
| `menu_button_app` | `Reviews` | `Повторения` |
| `start_app_hint` | `Tap the menu button next to the input field to review cards in the app.` | `Кнопка меню рядом с полем ввода открывает приложение для повторений.` |
| `review_already_graded` | `This card was already reviewed (probably in the app).` | `Эта карточка уже оценена (вероятно, в приложении).` |

**`vocab_bot/handlers/reviews.py`** — when `settings.webapp_url` is set, append a row
`[InlineKeyboardButton(t(locale, "due_open_app"), web_app=WebAppInfo(url=f"{settings.webapp_url}/?card={card.id}"))]`.

**`vocab_bot/handlers/callbacks.py`** — in `reveal:` and `grade:`: after fetching the card, if
`not card.awaiting_grade` → `edit_message_text(t(locale, "review_already_graded"))` and return. For `grade:`
this means fetching the card before `apply_grade` (one extra `get_card_for_user`), keep `review_missing` for
`None`.

**`vocab_bot/handlers/commands.py`** — `/start` appends `start_app_hint` when `webapp_url` is set.

**`vocab_bot/__main__.py`** — in `_post_init`, when `settings.webapp_url`:
`await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text=t(DEFAULT_LOCALE, "menu_button_app"), web_app=WebAppInfo(url=settings.webapp_url)))`
wrapped in `try/except Exception: logger.exception(...)` so a Telegram hiccup does not stop the bot.
(Menu button text is not per-user; use the default locale.)

**`CLAUDE.md`** — add `webapi/` to the architecture section and the new conventions (second entry point,
no `fastapi` outside `webapi/`, `tests/webapi/` approach). **`README.md`** — new "Mini App" section pointing
to `docs/miniapp/`.

**Tests**

- `tests/handlers/test_reviews_handler.py`: with/without `webapp_url` → keyboard has 1 or 2 rows; URL carries
  `?card=<id>`.
- `tests/handlers/test_callbacks.py`: `reveal:`/`grade:` on a card with `awaiting_grade=False` → edits to
  `review_already_graded` and does **not** call `apply_grade`.
- `tests/handlers/test_commands.py`: `/start` hint present only with `webapp_url`.
- `tests/test_i18n.py`: existing "all keys present in every locale" check covers the new keys.

### Step 6 — Frontend (`webapp/`)

Scaffold: `npm create vite@latest webapp -- --template svelte-ts` (Svelte 5, TypeScript, Vite). Add
`.gitignore` entries `webapp/node_modules/`, `webapp/dist/`. Commit `package-lock.json`.

```
webapp/
  index.html                 <script src="https://telegram.org/js/telegram-web-app.js"></script> before the bundle
  src/
    main.ts
    App.svelte               boot: ready/expand → initData check → /api/me → route to Review or Blocked/NotInTelegram
    lib/
      telegram.ts            typed accessor for window.Telegram.WebApp (initData, themeParams, HapticFeedback, close)
      api.ts                 fetch wrapper: adds Authorization: tma <initData>, parses error envelope, one retry on network error
      i18n.ts                en/ru string maps + t(locale, key)
      types.ts               mirrors api.md schemas
    screens/
      Review.svelte          queue state, current card, flip, grade buttons (disabled while POST in flight), progress "3 / 12"
      Done.svelte            "All done" + next due time (if any) + Close button
      Blocked.svelte         access_disabled message
      NotInTelegram.svelte   shown when initData is empty
    components/
      Card.svelte            two-sided card with flip transition (Svelte transition/animate), lang badges
      GradeBar.svelte        Again / Good / Easy, colours from --tg-theme-* vars
  vite.config.ts             base: "/", build.outDir: "dist"
```

Behavioural spec:

- Read `?card=` from `location.search` and pass as `first` to the queue call.
- Queue drained client-side; after the last grade show `Done.svelte`. If `total_due > cards.length`, offer
  "Load more" (re-fetch queue).
- On a `POST /grade` 404 (card deleted meanwhile) skip the card silently.
- `WebApp.BackButton` hidden on Review (single screen); `WebApp.MainButton` unused in MVP (grade bar is
  in-page for three-way choice).
- No `localStorage` persistence of the queue; a reload re-fetches. Keep the app stateless.

Local development: `vite` dev server on `http://localhost:5173` with `server.proxy` for `/api` →
`http://127.0.0.1:8080`. To test inside Telegram locally you still need HTTPS — use the deployed staging URL,
or a temporary tunnel for dev only (not for production).

Frontend tests: `vitest` + `@testing-library/svelte` for `api.ts` (header, error envelope, retry) and the
Review reducer logic (extract queue/grade state into `lib/reviewState.ts` so it is testable without DOM).
Keep it modest — the backend tests are the safety net.

### Step 7 — Deployment

Follow [deployment.md](deployment.md). Order: Postgres migration → API service → nginx + TLS → build & copy
`webapp/dist` → set `WEBAPP_URL` in `.env` → restart bot → verify Menu Button appears and a due notification
shows "Open in app".

### MVP acceptance criteria

- [x] `uv run --extra dev pytest` and `ruff` green; `pre-commit run --all-files` green.
- [x] Bot with `WEBAPP_URL` unset behaves byte-for-byte as before (existing tests unchanged, only extended).
- [x] `/api/health` → `{"status":"ok"}`; `/api/me` without auth → 401 `missing_auth` (verified locally over
  uvicorn; re-check on the deployed host).
- [ ] Opening the Menu Button in Telegram loads the app in the user's theme, shows the due queue, flip works,
  grading updates `next_review_at` in Postgres (check with `psql`) and the chat notification's buttons for that
  card now answer `review_already_graded`.
- [ ] A blocked user opening the app sees the localized "access disabled" screen.
- [ ] Tapping "Open in app" on a due notification opens the app with that card first.

---

## Phase 2 — Stats and smarter notifications

- `GET /api/stats`: totals (cards, due now, learned = `repetition >= N`), reviews-per-day for the last 30 days
  (needs a `review_log` table: `card_id`, `user_id`, `quality`, `graded_at` — written by `apply_grade`; additive
  migration in `Database._init_sync`), current streak.
- Consolidated chat notification: `due_poll` sends one "N cards due" message per user with
  `[Open app] [Review here]` instead of one per card; `[Review here]` starts the existing per-card chat flow.
  Add a per-user cool-down (`users.last_due_notified_at`) so the poll does not re-ping every 45 s.
- Optional: persist `notification_message_id` on `cards` so the API can edit/delete the stale chat message
  after an in-app grade (API process gets a `telegram.Bot` instance — still no `telegram` import in
  `services/`, the call lives in `webapi/`).

## Phase 3 — Card management

- `list_cards_for_user(user_id, *, query, offset, limit)` + `delete_card(card_id, user_id)` in persistence →
  repo → `CardService` (new) → `GET /api/cards`, `DELETE /api/cards/{id}`.
- Screens: searchable list, card detail (SRS state, next review), delete with confirm
  (`WebApp.showConfirm`).
- Optional: reset progress, edit `target_text`.

## Phase 4 — Wordbank in the app

- Only registered when `settings.wordbank_path` is set (same conditional pattern as the bot).
- `GET /api/wordbank/sections`, `GET /api/wordbank/topics/{n}`, `POST /api/wordbank/topics/{n}/add` → reuse
  `WordbankService`.
- Screen: section → topic with full word list and search, "Add all" with the added/skipped result.

## Later / ideas

- In-app translation (`TranslationService.translate` + save) — duplicates the chat flow, low priority.
- Swipe-to-grade gestures; keyboard shortcuts on desktop Telegram.
- Direct-link Mini App via BotFather `/newapp` (`https://t.me/<bot>/<app>`) for sharing.
