# Disaster Recovery

This document outlines the recovery procedures for different failure scenarios in the production environment.

## RPO / RTO

- **RPO (Recovery Point Objective):** 24 hours (based on daily DO managed database backups). Data loss is minimal since catalog data is mostly re-ingested from external sources.
- **RTO (Recovery Time Objective):** ~15-30 minutes for a full infrastructure recreation using automated scripts.

## Scenarios

### (a) Database Loss
If the managed PostgreSQL database is corrupted or lost:
1. Try using DigitalOcean's Point-In-Time Recovery (PITR) via the DO control panel (7-day window).
2. Alternatively, restore from a manual local backup:
   ```bash
   make do-db-restore FILE=backup.dump
   ```

### (b) Cluster Loss
If the Kubernetes cluster (DOKS) goes down:
1. Re-provision the infrastructure: `make do-infra-up`
2. Initialize the database: `make do-db-init`
3. Run migrations: `make do-db-migrate`
4. Deploy the application: `make do-deploy`
5. The catalog will be re-seeded automatically by the CronJobs, or you can trigger them manually.

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
