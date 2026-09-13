# Mini App HTTP API (MVP)

Base path: `/api`. All responses are JSON. All endpoints require authentication unless stated.

## Authentication

```
Authorization: tma <raw window.Telegram.WebApp.initData>
```

See [architecture.md → Authentication](architecture.md#authentication-telegram-initdata) for the validation
algorithm. The API never reads a user id from the body, query or path for authorization purposes.

## Errors

```json
{ "error": "invalid_init_data", "message": "initData signature mismatch" }
```

| Status | `error` | When |
|---|---|---|
| 401 | `missing_auth` | No `Authorization` header or wrong scheme |
| 401 | `invalid_init_data` | Signature mismatch, malformed, or `auth_date` too old |
| 403 | `access_disabled` | Valid user, but `is_allowed = false` and not in `ADMIN_USER_IDS` |
| 404 | `card_not_found` | Card id does not exist **or** belongs to another user (same response — no enumeration) |
| 422 | `validation_error` | Body/query failed schema validation (FastAPI default, reshaped to this envelope) |

The frontend maps `error` codes to localized strings; `message` is for logs/devtools only.

## Endpoints

### `GET /api/me`

Current user and deployment facts the UI needs on boot.

```json
{
  "telegram_id": 123456789,
  "locale": "ru",
  "timezone": "Europe/Warsaw",
  "lang_pair": { "source": "PL", "target": "RU" },
  "due_count": 12,
  "short_review_interval_minutes": 10
}
```

- `locale` — resolved with the existing `resolve_user_locale(user)` (`preferred_locale` → `language_code` →
  default), so the app shows the same language as the chat.
- `timezone` — IANA name or `"UTC"` when unset (mirrors `format_user_timezone`).
- `due_count` — number of cards with `next_review_at <= now` for this user (any `awaiting_grade`).

### `GET /api/reviews/queue?limit=50&first=<card_id>`

Due cards for the current user, oldest due first. `limit` 1–100 (default 50). `first` is optional: if that card
is in the result it is moved to index 0 (used by the `?card=` deep link from a chat notification). Cards with
`awaiting_grade = true` **are** included.

```json
{
  "cards": [
    {
      "id": 42,
      "direction": "target",
      "prompt_text": "dom",
      "prompt_lang": "PL",
      "answer_text": "дом",
      "answer_lang": "RU",
      "repetition": 2,
      "interval_days": 6.0,
      "next_review_at": "2026-09-13T08:00:00Z"
    }
  ],
  "total_due": 12
}
```

- `direction` — `"source"` means the prompt is `target_text` and the user recalls `source_text`;
  `"target"` is the reverse. Chosen server-side per response; the same card may get a different direction
  next time, matching the chat behaviour.
- The answer is sent up-front on purpose: reviews are self-graded, and it avoids a round-trip on flip.
- `total_due` may exceed `len(cards)` when capped by `limit`.

### `POST /api/reviews/{card_id}/grade`

```json
{ "quality": 3 }
```

`quality` ∈ `{0, 3, 5}` (Again / Good / Easy — the only values the chat UI produces; the SRS accepts 0–5 but the
API restricts to these three to keep both UIs identical).

```json
{
  "card_id": 42,
  "next_review_at": "2026-09-19T08:00:00Z",
  "interval_days": 6.0,
  "ease_factor": 2.5,
  "repetition": 3
}
```

Idempotency: not guaranteed — grading twice applies SM-2 twice, exactly as two `grade:` taps would. The client
disables the buttons while the request is in flight and never re-sends on success. (The double-grade guard on
the *chat* side is about the same card being graded from two UIs, see architecture.md.)

## Versioning

None for now; paths are `/api/...` without a version segment. If a breaking change is ever needed, add
`/api/v2/...` rather than mutating responses — an installed Mini App can be cached by the Telegram client.

## Not in MVP (reserved paths)

| Path | Phase |
|---|---|
| `GET /api/stats` | 2 — counts by state, due-per-day histogram, streak |
| `GET /api/cards`, `DELETE /api/cards/{id}` | 3 — browse/search/delete |
| `GET /api/wordbank/...`, `POST /api/wordbank/topics/{n}/add` | 4 — only on deployments with `WORDBANK_PATH` |
| `POST /api/translate`, `POST /api/pending/{id}/save` | later — in-app translation |
