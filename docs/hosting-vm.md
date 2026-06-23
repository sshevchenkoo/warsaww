# Hosting on a single VM (Azure / any cloud) — temporary/dev

A quick way to put the whole app on the public internet without the k8s setup.
Runs everything with `docker-compose.host.yml`: db + redis + api + web, with only
the web service exposed (port 80). For a dev preview, not hardened production.
The VM steps are the same on any provider; only provisioning differs.

## 1. Create the VM

### Hetzner Cloud (console)
- Cloud Console → project → **Add Server**.
- **Location**: Falkenstein / Nuremberg (EU, close to Poland).
- **Image**: Ubuntu 24.04.
- **Type**: **CX22** (x86, 2 vCPU / 4 GB, ~€4/mo) — or **CAX11** (ARM, cheaper;
  all our images are multi-arch, so ARM works too).
- **SSH key**: add yours.
- **Firewall** (optional, recommended): allow inbound **22, 80, 443**.
- Create → note the server's public IP. Default SSH user is **root** (so skip
  `sudo` in the steps below).

Or with the CLI: `hcloud server create --name warsaw-vm --type cx22 --image ubuntu-24.04 --ssh-key <key> --location fsn1`

### Azure (CLI)
```bash
az login
az group create -n warsaw-rg -l westeurope
az vm create -g warsaw-rg -n warsaw-vm \
  --image Ubuntu2404 --size Standard_B2s \
  --admin-username azureuser --generate-ssh-keys
az vm open-port -g warsaw-rg -n warsaw-vm --port 80
az vm show -g warsaw-rg -n warsaw-vm -d --query publicIps -o tsv   # -> public IP
```
- **Size `Standard_B2s`** (2 vCPU / 4 GB): building the Next image on the
  free-tier `B1s` (1 GB) can OOM — use B2s, or B1s + 2 GB swap (step 2). A new
  account's ~$200 / 30-day credit covers a month of B2s.
- Portal alternative: Create VM → Ubuntu 24.04 → size B2s → allow SSH; then add an
  inbound rule for port **80** in the VM's Network Security Group.

(DigitalOcean / AWS / Oracle: create an Ubuntu VM, open ports 22 + 80, then the
steps below are identical.)

## 2. Install Docker on the VM

```bash
ssh azureuser@<PUBLIC_IP>
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && exec newgrp docker   # run docker without sudo
# (optional, only on a 1 GB VM) add swap so the build doesn't OOM:
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
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
# GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET — only with Google login (needs HTTPS, see below)
EOF

# Public URL of the site (cookies / OAuth). For plain HTTP on the IP:
echo "FRONTEND_URL=http://<PUBLIC_IP>" > .env
```

## 4. Run it

```bash
docker compose -f docker-compose.host.yml up -d --build
```

Open `http://<PUBLIC_IP>` — the site is live. Load data:

```bash
docker compose -f docker-compose.host.yml exec api python -m app.ingestion.runner --source=places
docker compose -f docker-compose.host.yml exec api python -m app.ingestion.runner --source=facebook_events
docker compose -f docker-compose.host.yml exec api python -m app.ingestion.runner --source=ticketmaster
```

Stop: `docker compose -f docker-compose.host.yml down` (data kept in the `pgdata`
volume). The services use `restart: unless-stopped`, so they survive reboots.

## Auth over plain HTTP

- **Email/password login works** over `http://<ip>` out of the box.
- **Google login does NOT** — Google only allows an `http` redirect URI for
  `localhost`, not a public IP. For Google sign-in you need a **domain + HTTPS**:
  point a domain at the VM, put a TLS reverse proxy (e.g. Caddy) in front, set
  `FRONTEND_URL=https://<domain>` + `SESSION_HTTPS_ONLY=true`, and add
  `https://<domain>/auth/callback` to the Google OAuth client.

## HTTPS with a domain (Caddy)

For a real URL + TLS (and Google login), use `docker-compose.https.yml`, which adds
a Caddy reverse proxy that auto-fetches a Let's Encrypt cert. Same project/volume
as the http compose, so seeded data carries over.

1. DNS: add an **A record** `your-domain -> <server IP>` at your registrar; wait
   for it to resolve (`dig +short your-domain`).
2. On the server, set the domain + URL:
   ```bash
   printf 'DOMAIN=your-domain\nFRONTEND_URL=https://your-domain\nSESSION_HTTPS_ONLY=true\n' > .env
   docker compose -f docker-compose.host.yml down            # free port 80
   docker compose -f docker-compose.https.yml up -d --build  # Caddy gets the cert
   ```
3. Open `https://your-domain`. For Google login, add `https://your-domain/auth/callback`
   to the Google OAuth client and put GOOGLE_CLIENT_ID/SECRET in `backend/.env`.

## Teardown (stop the Azure bill)

```bash
az group delete -n warsaw-rg --yes --no-wait   # removes the VM and everything in the group
```
