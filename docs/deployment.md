# Deployment (Warsaw-events app)

The app ships as **one Docker image** used by both the API (uvicorn) and the
ingestion CronJobs (`python -m app.ingestion.runner --source=X`); only the
command differs. Manifests live in [`backend/k8s/`](../backend/k8s) and target a
dedicated `warsaw` namespace (separate from the ft_transcendence Django service).
The platform they run on is documented in [infrastructure.md](infrastructure.md).

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

## Build & deploy

Manifests use `${VAR}` substitution via `envsubst`, matching the repo
convention. Full step-by-step in [`backend/k8s/README.md`](../backend/k8s/README.md).

```bash
cd backend
docker build -t ghcr.io/$GITHUB_USER/warsaw-events:$IMAGE_TAG .
docker push ghcr.io/$GITHUB_USER/warsaw-events:$IMAGE_TAG

kubectl apply -f k8s/00-namespace.yml
kubectl apply -f k8s/secret.yml          # from secret.example.yml, filled in
kubectl apply -f k8s/10-postgres.yml -f k8s/20-redis.yml
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < k8s/30-api.yml | kubectl apply -f -
WARSAW_DOMAIN=$WARSAW_DOMAIN envsubst < k8s/40-ingress.yml | kubectl apply -f -
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < k8s/50-cronjobs.yml | kubectl apply -f -
```

## Secrets

A single `warsaw-secrets` Secret holds: `ANTHROPIC_API_KEY` (intent, re-rank,
dedup adjudication), `VOYAGE_API_KEY` (embeddings), `APIFY_TOKEN` (Facebook
adapter), and `DATABASE_URL` + `POSTGRES_USER/PASSWORD/DB`.

## Notes

- **Postgres** runs in-cluster on a PVC for simplicity. For production a managed
  Postgres with pgvector is sturdier — point `DATABASE_URL` at it and drop
  `10-postgres.yml`.
- **Voyage free tier** rate-limits batch embedding; add a payment method for fast
  `ingest-places` runs (the code already retries with backoff).
