# Auth & user profiles

Users sign in to keep a list of **saved items** (favorited events and places).
There are two doors into the same account, joined on the email address: Google
OAuth, and email + password (bcrypt, with email verification by code).

> Deep dive: [SECURITY.md](SECURITY.md) — password handling, the account
> pre-hijacking guard on OAuth linking, verification codes, sessions and RLS.

## How it works

```
Browser → /auth/login/google → Google consent
        → /auth/callback (the registered redirect URI)
              → upsert the user, store user_id in a signed session cookie
              → redirect back to the frontend
Browser → /me, /me/saved* (session cookie sent automatically)
```

**Sessions are a signed cookie** (Starlette `SessionMiddleware`), not server-side
state — so the API stays stateless and scales across replicas; every replica
validates the cookie with the shared `SESSION_SECRET`. The cookie holds only the
user id; the `users` row is the source of truth.

Identity is handled by `authlib` against Google's OIDC discovery endpoint
(`app/auth/oauth.py`). The login flow lives in `app/api/auth.py`; the
`current_user` dependency (`app/auth/deps.py`) guards the protected routes.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/auth/login/google` | Redirects to Google consent |
| GET | `/auth/callback` | OAuth redirect URI; sets the session, bounces to the frontend |
| POST | `/auth/logout` | Clears the session |
| GET | `/me` | Current user, or 401 |
| PATCH | `/me` | Edit `name` (applies at once) and/or `email`. An email change needs `current_password`, goes to `pending_email` and is confirmed by a code via `POST /auth/verify`; the old email keeps working until then. 409 if the email is taken, 403 for Google accounts (Google owns their email). Sending the current email cancels a pending change |
| GET | `/me/saved` | The user's saved items (`ItemOut[]`) |
| GET | `/me/saved/ids` | Saved item ids (to mark hearts on the search page) |
| POST | `/me/saved/{item_id}` | Save (idempotent); 404 if the item is unknown |
| DELETE | `/me/saved/{item_id}` | Un-save |

Data model: `users` and `saved_items` (see [data-model.md](data-model.md)).

## Config

Set in `backend/.env` (local) or the `warsaw-secrets` Secret (cluster):

- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — an OAuth 2.0 **Web** client from
  console.cloud.google.com.
- `SESSION_SECRET` — a long random string that signs the session cookie.
- `FRONTEND_URL` — where login redirects back to and the base for the OAuth
  redirect URI (`{FRONTEND_URL}/auth/callback`). Defaults to `http://localhost:3000`.
- `SESSION_HTTPS_ONLY` — `true` in production (Secure cookies), `false` for local http.

**Register these redirect URIs** on the Google client:
`http://localhost:3000/auth/callback` (dev) and `https://<domain>/auth/callback` (prod).

## Same-origin / cookies

In production the ingress serves web + API from one domain, so `/auth` and `/me`
are same-origin and the cookie is first-party. In local dev the web (`:3000`) and
API (`:8000`) are separate origins, so Next.js rewrites (`frontend/next.config.ts`)
proxy `/auth` and `/me` to the API — keeping the cookie first-party to `:3000`.
Search stays a direct cross-origin call (it needs no cookie).
