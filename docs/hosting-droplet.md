# Hosting on a single droplet (DigitalOcean) — temporary/dev

A quick way to put the whole app on the public internet without the k8s setup.
Runs everything with `docker-compose.host.yml`: db + redis + api + web, with only
the web service exposed (port 80). For a dev preview, not hardened production.

## 1. Create the droplet

- DigitalOcean → Create Droplet → Ubuntu 24.04.
- Size: **2 GB RAM** (`s-1vcpu-2gb`) — building the Next image on 1 GB can OOM.
  (Or take 1 GB and add 2 GB swap; see step 2.)
- Add your SSH key. New accounts have ~$200/60-day credit, so this is free for
  the month.

## 2. Install Docker on the droplet

```bash
ssh root@<DROPLET_IP>
curl -fsSL https://get.docker.com | sh
# (optional, if on 1 GB) add swap so the build doesn't OOM:
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
```

## 3. Get the code + secrets

```bash
git clone https://github.com/sshevchenkoo/ft_transcendence.git
cd ft_transcendence

# API keys (same as local): create backend/.env
cat > backend/.env <<'EOF'
ANTHROPIC_API_KEY=...
VOYAGE_API_KEY=...
APIFY_TOKEN=...
TICKETMASTER_API_KEY=...
SESSION_SECRET=<long-random-string>
# GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET — only if using Google login (needs HTTPS, see below)
EOF

# Public URL of the site (used for cookies / OAuth). For plain HTTP on the IP:
echo "FRONTEND_URL=http://<DROPLET_IP>" > .env
```

## 4. Run it

```bash
docker compose -f docker-compose.host.yml up -d --build
```

Open `http://<DROPLET_IP>` — the site is live. To load data:

```bash
docker compose -f docker-compose.host.yml exec api python -m app.ingestion.runner --source=places
docker compose -f docker-compose.host.yml exec api python -m app.ingestion.runner --source=facebook_events
docker compose -f docker-compose.host.yml exec api python -m app.ingestion.runner --source=ticketmaster
```

Stop: `docker compose -f docker-compose.host.yml down` (data kept in the `pgdata`
volume). The stack has `restart: unless-stopped`, so it survives reboots.

## Auth over plain HTTP

- **Email/password login works** over `http://<ip>` out of the box.
- **Google login does NOT** — Google only allows an `http` redirect URI for
  `localhost`, not a public IP. For Google sign-in you need a **domain + HTTPS**.
  Easiest: point a domain at the droplet and put a TLS reverse proxy (e.g. Caddy)
  in front, then set `FRONTEND_URL=https://<domain>`, `SESSION_HTTPS_ONLY=true`,
  and add `https://<domain>/auth/callback` to the Google OAuth client. (Ask and
  this can be added to the compose.)

## Firewall (optional but recommended)

Only port 80 (and 22 for SSH) needs to be open; db/redis/api are not published.
```bash
ufw allow 22 && ufw allow 80 && ufw --force enable
```
