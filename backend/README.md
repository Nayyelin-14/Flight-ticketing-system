# Flight Booking API (FastAPI)

## Stack

- FastAPI + SQLModel + PostgreSQL (Alembic migrations)
- Transactional outbox → polling worker or Kafka (welcome email)
- JWT access tokens + rotating refresh sessions in **HttpOnly cookies**

## Local development

```bash
cd backend
cp .env.example .env   # set DATABASE_URL, JWT_SECRET, SMTP_*, ALLOWED_ORIGINS
uv sync
uv run alembic upgrade head
uv run fastapi run main.py --port 8000
```

Worker (optional email delivery):

```bash
uv run python worker.py
```

Tests / lint:

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

---

## Authentication

### Design

| Credential | Storage | Lifetime | Purpose |
|---|---|---|---|
| Access token (JWT) | `Set-Cookie: access_token` — **HttpOnly**, `Path=/` | 15 minutes (`ACCESS_TOKEN_TTL`) | Authorize API requests |
| Refresh token (opaque) | `Set-Cookie: refresh_token` — **HttpOnly**, `Path=/api/v1/auth` | 7 days absolute (`REFRESH_TOKEN_TTL`) | Rotate access token only via `POST /auth/refresh` |

- Browser never sees raw tokens (no `localStorage` / `sessionStorage` / JS-readable cookies).
- Server stores only **SHA-256 hashes** of refresh tokens (`refresh_sessions.token_hash`).
- Rotation: each refresh inserts a sibling row in the same `family_id`, revokes the presented row (`revoked_at` + `replaced_by`). **Reuse of a rotated token revokes the entire family.**
- Absolute expiry: `expires_at` is copied from the family root and **never extended** on rotation.
- Authorization-header fallback exists for non-browser clients only (`Authorization: Bearer <access>`); the Next.js app relies on cookies.

### Endpoints (`/api/v1`)

| Method | Path | Success | Notes |
|---|---|---|---|
| POST | `/auth/login` | 200 `{user}` + cookies | Rate-limited; generic `INVALID_CREDENTIALS`; `EMAIL_NOT_VERIFIED` / `ACCOUNT_UNAVAILABLE` when applicable |
| POST | `/auth/refresh` | 200 `{user}` + new cookies | Cookie only (not body/header); failure → 401 `REFRESH_TOKEN_INVALID` **and** cookies cleared |
| GET | `/auth/me` | 200 `{user}` | Access cookie or `Authorization: Bearer` |
| POST | `/auth/logout` | 204 | Revokes session family; clears cookies; idempotent |
| POST | `/auth/register` | 201 | Existing flow (now also persists `name`) |
| POST | `/auth/verify-email` | 200 | Existing flow |

Stable error `detail` shape: `{ "code": "...", "message": "..." }`.

Codes: `VALIDATION_ERROR` (422), `INVALID_CREDENTIALS` (401), `EMAIL_NOT_VERIFIED` (403), `ACCOUNT_UNAVAILABLE` (403), `RATE_LIMITED` (429), `REFRESH_TOKEN_INVALID` (401), `UNAUTHORIZED` (401), `ORIGIN_NOT_ALLOWED` (403), `INTERNAL_ERROR` (500).

### Cookies (attributes)

| Attribute | Access | Refresh |
|---|---|---|
| HttpOnly | yes | yes |
| Secure | `COOKIE_SECURE` (default **true**) | same |
| SameSite | `COOKIE_SAMESITE` (default **lax**) | same |
| Path | `/` | `/api/v1/auth` (`API_V1_PREFIX` + `/auth`) |
| Max-Age | `ACCESS_TOKEN_TTL` (900) | `REFRESH_TOKEN_TTL` (604800) |

**Local vs production**

| Env | `COOKIE_SECURE` | `ALLOWED_ORIGINS` | HTTPS |
|---|---|---|---|
| Local (`localhost`) | `true` works in modern browsers on localhost; set `false` only if a tool rejects Secure-on-http | `http://localhost:3000` | not required |
| Staging/Production | **`true` (required)** | exact frontend origin(s), comma-separated | **required** everywhere non-local |

### CORS & CSRF

- CORS: exact origin list from `ALLOWED_ORIGINS`, `allow_credentials=true`, methods/headers narrowed. Never `*` with credentials.
- CSRF: `SameSite=Lax` blocks cross-site POST cookies. Additionally, `POST /auth/login|refresh|logout` reject requests whose `Origin` header is present and not in `ALLOWED_ORIGINS` (403 `ORIGIN_NOT_ALLOWED`).

### Rate limiting

- In-process sliding window: `LOGIN_RATE_MAX_ATTEMPTS` per email and per IP within `LOGIN_RATE_WINDOW_SECONDS`.
- **Limitation:** counters are per process — multi-pod deployments need a shared store (Redis) before relying on this in production.

### Environment variables

```
JWT_SECRET=...            # required long random string outside local dev
JWT_ALGORITHM=HS256
JWT_ISSUER=skyflare
JWT_AUDIENCE=skyflare-api
ACCESS_TOKEN_TTL=900
REFRESH_TOKEN_TTL=604800
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
ALLOWED_ORIGINS=http://localhost:3000
LOGIN_RATE_MAX_ATTEMPTS=5
LOGIN_RATE_WINDOW_SECONDS=300
```

### Security logging

Login/refresh/logout log event names and user/ids/IPs only. **Never** passwords, raw refresh tokens, cookies, or `Authorization` headers.

### Residual risks / follow-ups

- Access JWT remains valid until natural expiry (≤15 min) after logout; refresh session is revoked immediately.
- In-memory rate limit is per instance.
- `EMAIL_NOT_VERIFIED` discloses that an email is registered (accepted for resend UX).
- Password change / account disable should revoke all refresh families (not implemented yet).
- Resend-verification endpoint (can reuse outbox) is a follow-up.

### Frontend contract

- Single API client owns credentials (`credentials: 'include'`), error parsing, and **one** silent refresh + one request retry on 401.
- Login / refresh / logout are excluded from the auto-retry path.
- Concurrent 401s share one in-flight refresh promise (safe with rotation).
- Auth state lives in a single `AuthProvider`: `loading` → `authenticated | unauthenticated` (startup: me → optional refresh → me once).
