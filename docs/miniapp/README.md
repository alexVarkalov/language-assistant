# Telegram Mini App — planning docs

A Telegram Mini App (Web App) that opens full-screen inside Telegram and gives the bot a real UI for
spaced-repetition reviews (and, later, stats and card management). The chat-based flow keeps working
unchanged; the Mini App is an additional entry point on top of the same services and database.

| Doc | What it covers |
|---|---|
| [architecture.md](architecture.md) | Components, how the Mini App fits the 4-layer stack, auth, data flow, config, code layout |
| [api.md](api.md) | HTTP API contract between the Svelte frontend and the `webapi` backend |
| [implementation-plan.md](implementation-plan.md) | MVP task breakdown by layer (persistence → repository → service → webapi → bot → frontend), tests, acceptance criteria, later phases |
| [deployment.md](deployment.md) | VPS deployment: nginx + TLS, systemd units, Postgres, BotFather setup, migrating off the Raspberry Pi |

## Status (2026-09-13)

| Phase 1 step | State |
|---|---|
| 1–5 backend (`persistence` → `webapi/`, bot integration behind `WEBAPP_URL`) | **Done.** 215 pytest tests + `pre-commit` green; live smoke test over real uvicorn/HTTP (auth 401/403, queue, grade, 404, 422) passed with an in-memory `Database` stand-in. |
| 6 frontend (`webapp/`, Svelte 5 + Vite) | **Done.** `npm test` (14 vitest), `npm run check` (0 errors/warnings), `npm run build` (≈40 kB JS, 15 kB gzip). |
| 7 deployment | **Not started** — follow [deployment.md](deployment.md). |

Not yet verified: the app running *inside the Telegram client* (needs the public HTTPS deployment) and the
API against a real PostgreSQL (no local instance in the dev environment). Both are covered by the MVP
acceptance checklist in [implementation-plan.md](implementation-plan.md).

## Decisions (2026-09-13)

| Decision | Choice | Why / alternatives considered |
|---|---|---|
| Frontend stack | **Svelte 5 + Vite**, TypeScript | Small bundle, no boilerplate, good for card flip/swipe animations. Vanilla JS rejected as too verbose for 3–4 screens; React rejected as overkill. |
| Backend API | **FastAPI + uvicorn**, new package `vocab_bot/webapi/` | Async, pydantic schemas map 1:1 onto the frozen dataclasses in `persistence/types.py`. Same repo, same `Settings`, same services. |
| Process model | **Separate process** (`vocab-bot-api` entry point), not embedded in the bot's asyncio loop | Avoids fighting `Application.run_polling()`; bot and API can be restarted independently. Both connect to the same Postgres. |
| Hosting | **Dedicated VPS** | Telegram requires a public HTTPS URL for `web_app` buttons. The home Raspberry Pi has no public HTTPS; a tunnel was rejected in favour of a VPS. Recommended: move the whole stack (bot + Postgres + API + nginx) to the VPS — see [deployment.md](deployment.md) for the split-host alternative. |
| Auth | Telegram `initData` HMAC validation on every request | No passwords/tokens to manage; the trusted `telegram_id` comes from Telegram's signature, never from the client. |
| MVP scope | **Due-card review only** (flip + Again/Good/Easy) | Biggest UX win for least code. Stats, card management, wordbank search and in-app translation are later phases. |
| Frontend/API origin | Same origin: nginx serves `webapp/dist` at `/` and proxies `/api/` to uvicorn | No CORS, one TLS cert, one domain. |

## Non-goals (for now)

- ~~Replacing the chat flow.~~ Reversed on 2026-09-14: chat reviews were removed, the app is the only review UI
  and `WEBAPP_URL` is mandatory. Translation/saving/wordbank stay in chat.
- Per-user language pair selection — still one deployment per pair.
- Real-time sync between an open Mini App and chat messages (see "Known limitations" in
  [architecture.md](architecture.md)).
