# Deployment (Warsaw-events app)

The app ships as **one Docker image** used by both the API (uvicorn) and the
ingestion CronJobs (`python -m app.ingestion.runner --source=X`); only the
command differs. Manifests live in [`backend/k8s/`](../backend/k8s) and target a
dedicated `warsaw` namespace. The platform they run on (DOKS) is documented in
[hosting-digitalocean.md](hosting-digitalocean.md).

Manifests are applied with `${VAR}` substitution via `envsubst`, matching the
repo convention. Variables used: `GITHUB_USER`, `IMAGE_TAG`, `WARSAW_DOMAIN`.

## Manifests

| File | Resource |
|---|---|
| `00-namespace.yml` | `warsaw` namespace |
| `10-postgres.yml` | Postgres + pgvector StatefulSet (5Gi PVC) + init ConfigMap (`CREATE EXTENSION vector`) + Service |
| `20-redis.yml` | Redis Deployment + Service (future query cache) |
| `30-api.yml` | API Deployment (2 replicas) + Service + HPA (2–5, CPU 70%) |
| `40-ingress.yml` | nginx ingress + cert-manager TLS; SSE-safe (`proxy-buffering: off`, long timeouts) |
| `50-cronjobs.yml` | One CronJob per source — places weekly, facebook_events every 6h |
| `secret.example.yml` | Template for the `warsaw-secrets` Secret (real one gitignored) |
| `frontend/k8s/web.yml` | Next.js frontend Deployment (2 replicas) + Service `web` |

The `40-ingress.yml` ingress serves the whole app on one domain: `/` → the
`web` frontend, `/search` and `/health` → the `api`. Same origin, so the
browser uses relative API calls and no CORS is needed in production.

## 1. Build & push the image

Two images: the backend (API + ingestion) and the frontend.

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin

# backend
cd backend
docker build -t ghcr.io/$GITHUB_USER/warsaw-events:$IMAGE_TAG .
docker push ghcr.io/$GITHUB_USER/warsaw-events:$IMAGE_TAG

# frontend (empty NEXT_PUBLIC_API_URL → relative API calls, same origin)
cd ../frontend
docker build -t ghcr.io/$GITHUB_USER/warsaw-web:$IMAGE_TAG .
docker push ghcr.io/$GITHUB_USER/warsaw-web:$IMAGE_TAG
```

## 2. Create the secret

A single `warsaw-secrets` Secret holds: `ANTHROPIC_API_KEY` (intent, re-rank,
dedup adjudication), `VOYAGE_API_KEY` (embeddings), `APIFY_TOKEN` (Facebook
adapter), and `DATABASE_URL` + `POSTGRES_USER/PASSWORD/DB`.

Copy the template, fill it in, apply (the filled file is gitignored):

```bash
cp k8s/secret.example.yml k8s/secret.yml   # then edit k8s/secret.yml
kubectl apply -f k8s/00-namespace.yml
kubectl apply -f k8s/secret.yml
```

Or create it inline without a file:

```bash
kubectl -n warsaw create secret generic warsaw-secrets \
  --from-literal=POSTGRES_USER=app \
  --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" \
  --from-literal=POSTGRES_DB=events \
  --from-literal=DATABASE_URL="postgresql+psycopg://app:$PG_PASSWORD@postgres:5432/events" \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --from-literal=VOYAGE_API_KEY="$VOYAGE_API_KEY" \
  --from-literal=APIFY_TOKEN="$APIFY_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## 3. Deploy

```bash
cd backend
kubectl apply -f k8s/00-namespace.yml
kubectl apply -f k8s/10-postgres.yml
kubectl apply -f k8s/20-redis.yml
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < k8s/30-api.yml | kubectl apply -f -
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < k8s/50-cronjobs.yml | kubectl apply -f -

# frontend (same namespace)
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < ../frontend/k8s/web.yml | kubectl apply -f -

# ingress last — routes the domain to web + api
WARSAW_DOMAIN=$WARSAW_DOMAIN envsubst < k8s/40-ingress.yml | kubectl apply -f -
```

## 4. First data load

CronJobs fill the catalog on schedule; trigger one immediately:

```bash
kubectl -n warsaw create job --from=cronjob/ingest-places first-places
kubectl -n warsaw create job --from=cronjob/ingest-facebook-events first-fb
kubectl -n warsaw logs -f job/first-places
```

## Notes

- **DNS**: point `WARSAW_DOMAIN` at the ingress load balancer; cert-manager
  (`letsencrypt-prod`) issues the TLS cert automatically.
- **SSE**: the ingress disables proxy buffering so `/search` streams.
- **Voyage free tier** rate-limits batch embedding; add a payment method for fast
  `ingest-places` runs (the code already retries with backoff).
- **Postgres** runs in-cluster on a 5Gi PVC. For production a managed Postgres
  with pgvector is sturdier — point `DATABASE_URL` at it and drop `10-postgres.yml`.
