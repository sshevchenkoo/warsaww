# Auth & user profiles

There are two doors into the same account, joined on the email address: Google
OAuth, and email + password (bcrypt, with email verification by code and opt-in
two-factor sign-in). An account keeps saved items, friends, shares and an avatar.

> Deep dive: [SECURITY.md](SECURITY.md) — password handling, the account
> pre-hijacking guard on OAuth linking, verification codes, sessions and RLS.

## How it works

```
Google:   /auth/login/google → Google consent → /auth/callback
              → upsert the user by email, store user_id in a signed session cookie
              → redirect back to the frontend
Password: /auth/register → 6-digit code emailed → /auth/verify
          /auth/login → session cookie (or, with 2FA on, a code → /auth/login/2fa)
Then:     /me, /me/saved*, /friends*, … (session cookie sent automatically)
```

**Sessions are a signed cookie** (Starlette `SessionMiddleware`), not server-side
state — so the API stays stateless and scales across replicas; every replica
validates the cookie with the shared `SESSION_SECRET`. The cookie holds only the
user id; the `users` row is the source of truth.

Identity is handled by `authlib` against Google's OIDC discovery endpoint
(`app/auth/oauth.py`). The login flows live in `app/api/auth.py`; the
`current_user` dependency (`app/auth/deps.py`) guards the protected routes.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/auth/login/google` | Redirects to Google consent |
| GET | `/auth/callback` | OAuth redirect URI; sets the session, bounces to the frontend |
| POST | `/auth/register` | Email + password (8–72 bytes); emails a verification code. 409 if the email is taken |
| POST | `/auth/login` | Password login. With 2FA on, returns `{"pending_2fa": true}` and emails a code instead of a session |
| POST | `/auth/login/2fa` | Finishes a 2FA login with the emailed code |
| POST | `/auth/verify` | Confirms the registration code, or a pending email change |
| POST | `/auth/resend` | Sends a new verification code (rate-limited) |
| POST | `/auth/logout` | Clears the session |
| GET | `/me` | Current user, or 401. Includes `pending_email` and `has_password` |
| PATCH | `/me` | Edit `name`, `email` (needs `current_password`, confirmed via `/auth/verify`; 403 for Google accounts) and `two_factor_enabled` (password accounts with a verified email) |
| GET | `/me/export` | GDPR export: profile, saves, friendships, shares as JSON |
| DELETE | `/me` | Deletes the account (password accounts confirm with `current_password`); cascades to everything the user owns |
| POST / DELETE | `/me/avatar` | Upload / remove the avatar; bytes served by `GET /avatars/{user_id}` |
| GET | `/me/saved`, `/me/saved/ids` | The user's saved items / their ids (hearts on the search page) |
| POST / DELETE | `/me/saved/{item_id}` | Save (idempotent; 404 for an unknown item) / un-save |

Social routes (`/users/*`, `/friends*`, `/share`, `/me/shared*`, `/me/ping`) live in
`app/api/social.py`. Data model: [data-model.md](data-model.md).

## Config

Set in `backend/.env` (local) or the `warsaw-secrets` Secret (cluster). How to obtain
each key: [api-keys.md](api-keys.md).

- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — an OAuth 2.0 **Web** client.
- `SESSION_SECRET` — signs the session cookie and the emailed codes. With
  `SESSION_HTTPS_ONLY=true` the API refuses to boot on a key shorter than 32
  characters; generate one with `openssl rand -hex 32`.
- `FRONTEND_URL` — where login redirects back to and the base for the OAuth
  redirect URI (`{FRONTEND_URL}/auth/callback`). Defaults to `http://localhost:3000`.
- `SESSION_HTTPS_ONLY` — `true` in production (Secure cookies), `false` for local http.
- `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO` — code emails; without the key
  sending is a logged no-op.
- `REQUIRE_VERIFIED_EMAIL_TO_SEARCH` (default `true`) — `/search` needs a signed-in,
  verified user. `REQUIRE_EMAIL_VERIFICATION` (default `false`) also refuses password
  login until the email is verified.

## Same-origin / cookies

In production the ingress serves web + API from one domain, so every API call is
same-origin and the cookie is first-party. In local dev the web (`:3000`) and API
(`:8000`) are separate origins, so Next.js rewrites (`frontend/next.config.ts`)
proxy the API paths — `/auth`, `/me`, `/search`, `/friends`, … — keeping the cookie
first-party to `:3000`.
