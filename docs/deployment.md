# Deployment (Warsaw-events app)

The app ships as **one Docker image** used by both the API (uvicorn) and the
ingestion CronJobs (`python -m app.ingestion.runner --source=X`); only the
command differs. Manifests live in [`deploy/cloud/k8s/`](../deploy/cloud/k8s) and target a
dedicated `warsaw` namespace. The platform they run on (DOKS) is documented in
[hosting-digitalocean.md](hosting-digitalocean.md).

Manifests are applied with `${VAR}` substitution via `envsubst`, matching the
repo convention. Variables used: `GITHUB_USER`, `IMAGE_TAG`, `WARSAW_DOMAIN`.
`make do-deploy` applies everything in the right order; the manual commands
below are what it runs.

## Manifests

| File | Resource |
|---|---|
| `00-namespace.yml` | `warsaw` namespace |
| `20-redis.yml` | Redis Deployment + Service — backs the per-session search quota and the per-IP auth rate limit (`app/ratelimit.py`) |
| `30-api.yml` | API Deployment (2 replicas, `DB_BOOTSTRAP=false`) + Service + HPA (2–5, CPU 70%) |
| `35-pdb.yml` | PodDisruptionBudgets `api` and `web` (`minAvailable: 1`) so node drains keep one pod of each up |
| `40-ingress.yml` | nginx ingress + cert-manager TLS; SSE-safe (`proxy-buffering: off`, long timeouts) |
| `45-networkpolicies.yml` | Default-deny ingress in the namespace, then explicit allows: ACME solver, api, web, postgres, redis |
| `50-cronjobs.yml` | One CronJob per source — `ingest-places` Mondays 04:00, `ingest-facebook-events` every 6 h, `ingest-ticketmaster` every 12 h |
| `web.yml` | Next.js frontend Deployment (2 replicas) + Service `web` |
| `secret.example.yml` | Template for the `warsaw-secrets` Secret (the filled `secret.yml` is gitignored) |
| `optional/10-postgres.yml` | In-cluster Postgres + pgvector StatefulSet (5Gi PVC), **not applied by `make do-deploy`** — prod uses DigitalOcean managed Postgres |

The `40-ingress.yml` ingress serves the whole app on one domain. API prefixes go
to the `api` Service — `/search`, `/health`, `/auth`, `/me`, `/upcoming`,
`/items`, `/avatars`, `/users`, `/friends`, `/share` — and `/` goes to `web`.
Same origin, so the browser uses relative API calls and no CORS is needed in
production.

## 1. Build & push the images

Two images: the backend (API + ingestion) and the frontend. `make do-images`
builds both for `linux/amd64` (DOKS nodes; also correct from an Apple-Silicon
Mac), tags them with the short git SHA **and** `latest`, and pushes to ghcr.io.
Manifests deploy by SHA, so every commit rolls out a new pod spec.

```bash
make do-images                       # IMAGE_TAG defaults to $(git rev-parse --short HEAD)
```

Manual equivalent:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin
docker buildx build --platform linux/amd64 \
  -t ghcr.io/$GITHUB_USER/warsaw-events:$IMAGE_TAG --push backend
# empty NEXT_PUBLIC_API_URL → relative API calls, same origin
docker buildx build --platform linux/amd64 \
  -t ghcr.io/$GITHUB_USER/warsaw-web:$IMAGE_TAG --push frontend
```

## 2. Create the secret

A single `warsaw-secrets` Secret holds everything the pods read from the
environment (`deploy/cloud/k8s/secret.example.yml` lists each key with a comment):

| Key | Used by |
|---|---|
| `DATABASE_URL` | API + CronJobs. In prod: the managed-Postgres URI from `terraform output`, with the least-privilege `warsaw_app` role (see the runbook) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Only the in-cluster `optional/10-postgres.yml` |
| `ANTHROPIC_API_KEY` | Intent, re-rank, dedup adjudication |
| `VOYAGE_API_KEY` | Embeddings |
| `APIFY_TOKEN`, `TICKETMASTER_API_KEY` | Facebook and Ticketmaster adapters — a missing key fails that adapter with a clear `RuntimeError`; since each source is its own CronJob, only that job fails |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google sign-in |
| `SESSION_SECRET` | Signs the session cookie and the email-verification codes |
| `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO` | Verification email; blank `RESEND_API_KEY` = no-op |

Copy the template, fill it in, apply:

```bash
cp deploy/cloud/k8s/secret.example.yml deploy/cloud/k8s/secret.yml   # then edit secret.yml
kubectl apply -f deploy/cloud/k8s/00-namespace.yml
kubectl apply -f deploy/cloud/k8s/secret.yml
```

## 3. Deploy

```bash
make do-deploy
```

Manual equivalent, from the repo root, in the same order (network policies
before workloads, PDBs after the Deployments they select, ingress last):

```bash
K=deploy/cloud/k8s
kubectl apply -f $K/00-namespace.yml
kubectl apply -f $K/secret.yml
kubectl apply -f $K/45-networkpolicies.yml
kubectl apply -f $K/20-redis.yml
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < $K/30-api.yml      | kubectl apply -f -
kubectl apply -f $K/35-pdb.yml
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < $K/50-cronjobs.yml | kubectl apply -f -
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < $K/web.yml         | kubectl apply -f -
WARSAW_DOMAIN=$WARSAW_DOMAIN envsubst < $K/40-ingress.yml                   | kubectl apply -f -
```

The API runs with `DB_BOOTSTRAP=false`, so it never creates or alters tables.
When a deploy changes the schema, run `make do-db-migrate` first — it executes
the same `_create_schema` as the admin role (see [data-model.md](data-model.md)).

## 4. First data load

CronJobs fill the catalog on schedule; trigger them immediately after the first
deploy:

```bash
kubectl -n warsaw create job --from=cronjob/ingest-places first-places
kubectl -n warsaw create job --from=cronjob/ingest-facebook-events first-fb
kubectl -n warsaw create job --from=cronjob/ingest-ticketmaster first-tm
kubectl -n warsaw logs -f job/first-places
```

## Notes

- **DNS**: point `WARSAW_DOMAIN` at the ingress load balancer; cert-manager
  (`letsencrypt-prod`) issues the TLS cert automatically.
- **SSE**: the ingress disables proxy buffering so `/search` streams.
- **Voyage free tier** rate-limits batch embedding; add a payment method for fast
  `ingest-places` runs (the code already retries with backoff).
- **Postgres**: prod uses DigitalOcean managed Postgres provisioned by Terraform
  (`deploy/cloud/terraform/`); `make do-db-init` enables `vector` + `pg_trgm`.
  `optional/10-postgres.yml` remains for clusters without a managed database — apply it by
  hand, set the `POSTGRES_*` keys, and point `DATABASE_URL` at
  `postgres.warsaw.svc.cluster.local`.
