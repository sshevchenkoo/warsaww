# Disaster Recovery

This document outlines the recovery procedures for different failure scenarios in the production environment.

## RPO / RTO

- **RPO (Recovery Point Objective):** minutes, within the last 7 days — DO managed Postgres
  keeps daily backups plus point-in-time recovery (PITR) for 7 days. Beyond that window, or
  without DO, it is the age of the last `make do-db-backup` dump. Catalog data is re-ingested
  from the external sources anyway; what is actually at stake is users, saves, friendships
  and shares.
- **RTO (Recovery Time Objective):** ~15-30 minutes for a full infrastructure recreation using automated scripts.

## Scenarios

### (a) Database Loss
If the managed PostgreSQL database is corrupted or lost:
1. Try using DigitalOcean's Point-In-Time Recovery (PITR) via the DO control panel (7-day window).
   The restore lands in a **new** database cluster: point `DATABASE_URL` in
   `deploy/cloud/k8s/secret.yml` at it, then follow steps 4–8 of (b).
2. Alternatively, restore from a manual local backup:
   ```bash
   make do-db-restore FILE=backup.dump
   ```

### (b) Cluster Loss
If the Kubernetes cluster (DOKS) goes down, rebuild it in the same order as the first
deploy ([deploy/cloud/README.md](../deploy/cloud/README.md#deploy-runbook)):

1. Re-provision the infrastructure: `make do-infra-up`
2. Save the new cluster's kubeconfig: `make do-kubeconfig` — every later step talks to the
   new cluster through it
3. Prepare the database (all idempotent, safe on a surviving DB):
   `make do-db-init`, `make do-db-role`, `make do-db-monitor-role`
4. Create or upgrade the schema: `make do-db-migrate`
5. Install the platform — ingress, cert-manager, monitoring, fluent-bit: `make do-platform`
6. Apply the app secret: `kubectl apply -f deploy/cloud/k8s/secret.yml`
   (`DATABASE_URL` uses the `warsaw_app` role from step 3)
7. Deploy the application: `make do-deploy` (`make do-images` first if the GHCR images are gone)
8. Point DNS (`WARSAW_DOMAIN`) at the new ingress load balancer — its IP changes with the cluster
9. The catalog will be re-seeded automatically by the CronJobs, or you can trigger them manually.
   If the database was lost too, restore users' data first — see (a).

### (c) ELK Droplet Loss
If the ELK droplet goes down or is lost:
1. Re-provision the ELK droplet:
   ```bash
   make do-elk
   ```
This will run the Ansible playbook to configure and start Elasticsearch, Logstash, and Kibana on the droplet.

### (d) Secrets Management and Rotation
Secrets are stored securely in `.env` files locally and deployed as Kubernetes Secrets (`deploy/cloud/k8s/secret.yml`).
To rotate secrets:
1. Update your local `.env` and `deploy/cloud/k8s/secret.yml` with the new values.
2. Re-apply the secrets to the cluster:
   ```bash
   kubectl apply -f deploy/cloud/k8s/secret.yml
   ```
3. Restart the application pods to pick up the new secrets:
   ```bash
   kubectl rollout restart deployment warsaw-api warsaw-web
   ```
