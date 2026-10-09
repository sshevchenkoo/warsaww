# Pre-evaluation checklist — manual test on a campus workstation

Run this the day before the evaluation, on a campus workstation, the way the evaluators will
see it. Budget about 1.5 hours: 20 minutes to bring the stack up from scratch, the rest to
click through. Tick each box; anything that fails gets fixed (or dropped from the module
table in `README.md`) before the evaluation, not during it.

All commands run inside the VM — see [VM_SETUP_42.md](../deploy/local/VM_SETUP_42.md).
`STACK` below is shorthand for `docker compose -f deploy/local/docker-compose.yml`.

---

## 0. Before you start

- [ ] VM is up, `docker compose version` prints v2.24+
- [ ] `backend/.env` holds working keys: `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`,
      `GOOGLE_CLIENT_ID`/`SECRET`, `RESEND_API_KEY` (see [api-keys.md](api-keys.md))
- [ ] The Google OAuth client lists `https://localhost/auth/callback` as a redirect URI
- [ ] You know which address owns the Resend account — with the default sender, codes are
      delivered **only** there, so the 2FA test needs an account on that address

## 1. Fresh start — one command, from a clean clone

The evaluators start from the repository, not from your warm VM. Reproduce that.

```bash
cd ~ && rm -rf warsaww-eval
git clone https://github.com/sshevchenkoo/warsaww.git warsaww-eval && cd warsaww-eval
cp ~/warsaww/backend/.env backend/.env
docker compose -f deploy/local/docker-compose.yml down -v   # ⚠ wipes the stack's volumes (local data only)
make infra-auth AUTH_USER=admin AUTH_PASS=<password>
make stack-init
```

- [ ] `make stack-init` finishes without an error
- [ ] `$STACK ps` — every service `running`, `api` and `db` show `(healthy)`
- [ ] `git ls-files | grep -E '(^|/)\.env$|secrets\.env|\.htpasswd|\.dump$'` prints nothing
- [ ] `.env.example` files exist for the backend and frontend

## 2. Rules that apply to the whole project

- [ ] `https://localhost` opens the site (accept the self-signed certificate once)
- [ ] `http://localhost` redirects to `https://`
- [ ] Browser DevTools → **Console**: no errors and no warnings while clicking through
      the pages below. Check it on every page, not just the home page
- [ ] Footer links open **Privacy Policy** (`/privacy`) and **Terms of Service** (`/terms`),
      and both describe what the app actually does (account deletion, data export)
- [ ] Two users at once: Firefox normal window as `user1@test.com`, private window as
      `user2@test.com` (both password `1234`) — both work in parallel
- [ ] Forms validate on both sides: register with a bad email / short password — the form
      refuses it, and the API answers 4xx too (DevTools → Network)

## 3. Modules from the README table

Search has a quota of 10 per user per day. If you run out while testing:
`$STACK exec redis redis-cli FLUSHDB` (local only — it also resets the auth rate limit).

### Web

- [ ] **#1 Frameworks** — site is Next.js, API is FastAPI: `https://localhost` loads, and
      `$STACK exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"`
      prints `{"status":"ok"}`
- [ ] **#2 ORM** — be ready to show `backend/app/catalog/models.py` and one query in
      `backend/app/api/`
- [ ] **#3 SSR** — open any item, copy its URL, then
      `curl -sk https://localhost/item/<id> | grep -o '<title>[^<]*'` shows the event's
      title (rendered on the server, before JavaScript)
- [ ] **#4 Design system** — icons and spinners are SVG (no text glyphs), the search
      spinner shows while a query runs, colours and type are consistent across pages

### User management

- [ ] **#5 Standard user management**
  - [ ] Register a new account, confirm the code from the email, log in, log out
  - [ ] Profile: edit the name inline; change the email (confirmed by a code)
  - [ ] `/people`: `user1` finds `user2` by name, sends a friend request; `user2` accepts
        it in the other window
  - [ ] Online status: `user2` shows as online while their window is open, offline a while
        after it is closed
  - [ ] Public profile `/u/<id>` shows the user and their saved items
- [ ] **#6 OAuth** — "Sign in with Google" ends logged in, back on `https://localhost`
      (a `redirect_uri_mismatch` page means the callback URI from section 0 is missing)
- [ ] **#9 File upload** — avatar:
  - [ ] Upload a JPEG/PNG: the progress bar moves, the new avatar appears
  - [ ] A file over 5 MB and a non-image file are both rejected with a message
  - [ ] "Remove photo" brings back the default avatar

### AI

- [ ] **#7 RAG + #8 LLM interface** — on the home page, as a verified user:
  - [ ] `koncert jazzowy w ten weekend` (PL), `выставка в субботу` (RU),
        `cheap techno party friday` (EN): cards stream in one by one, each with a one-line
        pitch **in the language of the query**
  - [ ] Dates, places and prices on the cards match the item pages (grounded, not invented)
  - [ ] An off-topic prompt (`how to bake bread`) returns an empty result quickly, no error
  - [ ] Logged out, search asks you to log in; the upcoming feed still shows
  - [ ] After the 10th search of the day the 11th is refused with a clear message

### Module of choice

- [ ] **#12 Ingestion pipeline** — `make stack-seed` loads `places` (no key needed) and
      `facebook_events` (needs `APIFY_TOKEN`, billed per run; it logs and skips without
      one). Its own output in the terminal shows the pipeline steps (fetch, dedup,
      embed, upsert), and `$STACK exec db psql -U app events -c 'select count(*) from items'`
      grows past the 100 demo items. Be ready to walk through `docs/INGESTION.md`

### DevOps

- [ ] **#10 ELK** — `https://localhost:5601` (infra login). Create the index pattern
      `warsaw-logs-*` (time field `@timestamp`) if it is not there yet; **Discover** shows
      API log lines from the last few minutes, searchable by text
- [ ] **#11 Prometheus + Grafana**
  - [ ] `https://localhost:9090/targets` — every target is **UP**
  - [ ] `https://localhost:3001` — dashboards *App overview*, *Host overview*,
        *Search analytics* and *Traces* all show data (run a few searches first)
  - [ ] Alerting works: `$STACK stop api`, wait a few minutes, `APIDown` turns **firing** on
        `https://localhost:9090/alerts` and appears in Alertmanager (`:9093`).
        Then `$STACK start api`

## 4. Minor modules waiting for their frontend

Backend is merged; claim them only once the UI is merged and the line is added to the
README module table.

- [ ] **2FA** (UI: #16) — as the Resend-owner account: enable two-factor on the profile,
      log out, log in with the password → the app asks for a code, the code arrives by
      email, a wrong code is refused. Until the UI lands, in the DevTools console while
      logged in:
      `await fetch('/me', {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({two_factor_enabled: true})})`
- [ ] **GDPR** (UI: #18) — use a throwaway account, **not** `user1`/`user2`:
  - [ ] Export downloads a JSON with the account, saves, friendships and shares — and
        nothing about other users. Console: `await (await fetch('/me/export')).json()`
  - [ ] Delete asks for the password, logs you out, the account can no longer log in, and
        a confirmation email arrives
- [ ] **Health check + backups + DR** (UI: status page #20)
  - [ ] Ready check passes:
        `$STACK exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/ready').read())"`
  - [ ] `$STACK stop redis` → the same command fails with HTTP 503 and `"redis": false`;
        `$STACK start redis` → back to ok
  - [ ] Be ready to walk through `docs/DISASTER_RECOVERY.md` and `make do-db-backup`

## 5. Wrap-up

- [ ] Anything that failed is either fixed and re-tested, or removed from the README module
      table — the total must stay at 14 or more
- [ ] `make stack-down` (volumes are kept), then take a VM snapshot (`eval-ready`)
