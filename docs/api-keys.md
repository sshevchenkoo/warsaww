# API keys — how to get each one

Every external credential the project uses, where it goes, and how to obtain it.
Secrets never get committed: `backend/.env` and the root `.env` are gitignored.

## Which file, which key

| Variable | File | Needed for | Required? |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | `backend/.env` | `/search`: intent parse + re-rank | yes, for search |
| `VOYAGE_API_KEY` | `backend/.env` | embeddings (ingestion + search) | yes, for search |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | `backend/.env` | "Sign in with Google" | only for Google login |
| `RESEND_API_KEY` | `backend/.env` | verification + 2FA code emails | no (without it, emails are only logged) |
| `TICKETMASTER_API_KEY` | `backend/.env` | Ticketmaster ingestion adapter | only for that source |
| `APIFY_TOKEN` | `backend/.env` | `facebook_events` ingestion adapter | only for that source |
| `SESSION_SECRET` | `backend/.env` | signs the session cookie | generate, don't obtain |
| `DIGITALOCEAN_TOKEN` | root `.env` | `make do-infra-*` (Terraform) | prod only |
| `GITHUB_TOKEN` | root `.env` | `make do-images` (push to GHCR) | prod only |

After editing `backend/.env`, restart the backend — settings are read once at startup
(`backend/app/config.py`). In `backend/.env.example` the optional keys are commented
out: remove the leading `# ` when you fill them in.

---

## Anthropic — `ANTHROPIC_API_KEY`

1. Sign in at <https://console.anthropic.com>.
2. **Settings → API Keys → Create Key.** Copy it now; it is shown only once.
3. Add credits under **Billing** — a key with no balance returns errors.

The key starts with `sk-ant-`. The app uses `claude-haiku-4-5` (intent) and
`claude-sonnet-4-6` (re-rank); see `intent_model` / `rerank_model` in `config.py`.
Ask the team for a shared key before paying from a personal account.

## Voyage AI — `VOYAGE_API_KEY`

1. Sign up at <https://dash.voyageai.com>.
2. **API Keys → Create new secret key.** Copy it.
3. Add a payment method. New accounts get a free token allowance, but without a
   payment method the rate limits are very low and a full ingestion run gets throttled.

The model is `voyage-3.5` (`embedding_model`). Without this key ingestion skips
embeddings and search returns nothing — after setting it, re-seed the catalog.

## Google OAuth — `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

1. Open <https://console.cloud.google.com> and create (or pick) a project.
2. **APIs & Services → OAuth consent screen:** user type *External*, fill the app name
   and support email. While the app is in *Testing*, add your Google account under
   **Test users** — nobody else can sign in.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**, type
   **Web application**.
4. Under **Authorized redirect URIs** add every place you run the app. The URI is
   `{FRONTEND_URL}/auth/callback`:
   - `https://localhost/auth/callback` — local docker compose (nginx front, `FRONTEND_URL=https://localhost`)
   - `http://localhost:3000/auth/callback` — frontend run directly, without nginx
   - `https://<WARSAW_DOMAIN>/auth/callback` — production
5. Copy the **Client ID** and **Client secret**.

A mismatch between the redirect URI and `FRONTEND_URL` ends in Google's
`redirect_uri_mismatch` error page.

## Resend — `RESEND_API_KEY`

1. Sign up at <https://resend.com>.
2. **API Keys → Create API Key**, permission *Sending access*. Copy it (starts with `re_`).
3. Local dev: the default sender `onboarding@resend.dev` works, but Resend delivers it
   **only to the email address of the Resend account owner**. Register test users with
   that address.
4. Production: **Domains → Add Domain**, add the DNS records Resend shows, wait for
   *Verified*, then set `EMAIL_FROM` to an address on that domain
   (e.g. `Warsaw Events <no-reply@your-domain>`). Optional `EMAIL_REPLY_TO` routes replies
   to a personal inbox.

## Ticketmaster — `TICKETMASTER_API_KEY`

1. Register at <https://developer.ticketmaster.com>.
2. **My Apps** — a default app is created on sign-up; open it (or add one).
3. Copy the **Consumer Key**. The Consumer Secret is not needed.

Free tier: 5 000 calls/day, 5 requests/second — enough for development.

## Apify — `APIFY_TOKEN`

1. Sign up at <https://console.apify.com>.
2. **Settings → API & Integrations → Personal API tokens.** Copy the token
   (starts with `apify_api_`).

The `facebook_events` adapter runs the *Facebook Events Scraper* actor, which is billed
per usage against your Apify credits. The free plan includes a small monthly credit;
check the cost of a run in [INGESTION.md](INGESTION.md) §6 before scheduling it.

## `SESSION_SECRET` — generate it

```bash
openssl rand -hex 32
```

Locally any value works. With `SESSION_HTTPS_ONLY=true` (production) the backend refuses
to start if the secret is the dev default or shorter than 32 characters.

---

## Production only (root `.env`)

### DigitalOcean — `DIGITALOCEAN_TOKEN`

1. <https://cloud.digitalocean.com> → **API → Tokens → Generate New Token**.
2. Scope: **read and write** (Full Access). Copy it (starts with `dop_v1_`).

### GitHub Container Registry — `GITHUB_TOKEN`

1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)
   → Generate new token (classic)**.
2. Scope: **`write:packages`** (it pulls in `read:packages`). Fine-grained tokens do not
   cover GHCR, so use a classic one.
3. Set `GITHUB_USER` to your GitHub username.

The remaining values in the root `.env` (`GRAFANA_PASSWORD`, `KIBANA_PASSWORD`,
`WARSAW_APP_DB_PASSWORD`) are passwords you choose — generate them with
`openssl rand -base64 24`.
