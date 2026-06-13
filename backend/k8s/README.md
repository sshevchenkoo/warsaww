# Deploy — Warsaw Events backend

Self-contained manifests for the `warsaw` namespace (separate from the
`transcendence` app). One Docker image serves both the API and the
ingestion CronJobs; the command differs.

Manifests are applied with `${VAR}` substitution via `envsubst`, matching
the repo convention. Variables used: `GITHUB_USER`, `IMAGE_TAG`, `WARSAW_DOMAIN`.

## 1. Build & push the image

```bash
cd backend
docker build -t ghcr.io/$GITHUB_USER/warsaw-events:$IMAGE_TAG .
echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin
docker push ghcr.io/$GITHUB_USER/warsaw-events:$IMAGE_TAG
```

## 2. Create the secret

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
kubectl apply -f k8s/00-namespace.yml
kubectl apply -f k8s/10-postgres.yml
kubectl apply -f k8s/20-redis.yml
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < k8s/30-api.yml | kubectl apply -f -
WARSAW_DOMAIN=$WARSAW_DOMAIN envsubst < k8s/40-ingress.yml | kubectl apply -f -
GITHUB_USER=$GITHUB_USER IMAGE_TAG=$IMAGE_TAG envsubst < k8s/50-cronjobs.yml | kubectl apply -f -
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
- **Voyage free tier** rate-limits batch embedding — see the project memory;
  add a payment method for fast `ingest-places` runs.
- **Postgres** runs in-cluster on a 5Gi PVC. For production, a managed
  Postgres with pgvector is the sturdier choice — point `DATABASE_URL` at it
  and drop `10-postgres.yml`.
