# Running the stack in a VM on a 42 workstation

The workstations run Ubuntu with no sudo for the student account, and the full stack needs
things only root can do (Docker, `vm.max_map_count` for Elasticsearch). So the project runs
inside a Debian 12 guest in VirtualBox, which is already installed on the workstation.

Budget about an hour: 40 minutes for the VM, 15–20 for the first `make stack-init`
(it pulls several images, Elasticsearch among them).

Every command below uses your 42 login through one variable. Set it first, in every new
terminal on the workstation:

```bash
export LOGIN=$USER        # your 42 login, e.g. jdoe
```

## 1. Check the workstation

```bash
df -h /sgoinfre /goinfre  # need ~40 GB free on one of them
```

The workstations have 16 GB of RAM: 8 GB go to the guest (the full stack wants 4–6 GB
free inside it) and 8 GB stay for the host. Close other heavy apps on the workstation
while the stack runs.

## 2. Download the ISO to scratch storage

The home directory is quota-limited, so the ISO and the disk image go to scratch storage.
Use `/goinfre` if `/sgoinfre` does not exist; on some campuses `goinfre` is wiped on
logout, so check before relying on it.

```bash
mkdir -p /sgoinfre/$LOGIN/VMs && cd /sgoinfre/$LOGIN
wget https://cdimage.debian.org/cdimage/archive/latest-oldstable/amd64/iso-cd/ -r -l1 -nd -A 'debian-12*-netinst.iso'
```

## 3. Create the guest in VirtualBox

1. *File → Preferences → General → Default Machine Folder* → `/sgoinfre/$LOGIN/VMs`
   (type the expanded path, e.g. `/sgoinfre/jdoe/VMs`)
2. *New* → **Name** `warsaww`, **ISO** the netinst downloaded above,
   **tick "Skip Unattended Installation"**
3. **Hardware:** 8192 MB RAM, 4 CPUs
4. **Hard disk:** 40 GB, VDI, dynamically allocated
5. *Settings → Network → Adapter 1 → NAT → Advanced → Port Forwarding*, add one rule:
   host port `2222` → guest port `22` (SSH, to copy `backend/.env` in)

The site itself is browsed from inside the guest, so no other ports need forwarding.

## 4. Install Debian

Follow the text installer with the defaults, except:

- **Root password:** leave empty (the first user then gets sudo automatically)
- **Username:** your 42 login
- **Software selection:** deselect GNOME, select **Xfce** and **SSH server**
  (a desktop is needed for the browser; Xfce is the light one)

After the first login, `sudo whoami` has to print `root`.

## 5. Install the tooling in the guest

Run the commands from a terminal on the workstation over SSH rather than in the VM
window — without VirtualBox Guest Additions the clipboard is not shared, so nothing can
be pasted into the VM window:

```bash
ssh -p 2222 $LOGIN@localhost
```

Docker CE from Docker's own repository — the stack needs Compose v2.24+, which the
Debian `docker.io` / `docker-compose-v2` packages do not ship.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git make openssl firefox-esr
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER

# Elasticsearch refuses to start without this
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-elasticsearch.conf
```

Log out and back in so the `docker` group applies, then check `docker compose version`.

## 6. Clone, add keys, start

In the guest:

```bash
git clone https://github.com/sshevchenkoo/warsaww.git ~/warsaww
```

On the workstation, copy your filled `backend/.env` in (see [API keys](../../docs/api-keys.md)):

```bash
scp -P 2222 backend/.env $LOGIN@localhost:~/warsaww/backend/.env
```

Without it the stack still starts and the demo data still loads, but `/search` does not
answer (it needs `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY`).

In the guest:

```bash
cd ~/warsaww
make infra-auth AUTH_USER=admin AUTH_PASS=<password>   # one login for Grafana/Kibana/Prometheus
make stack-init                                        # build, start, demo events + test users
```

`stack-init` polls `http://localhost:8000/health` before seeding, but the API no longer
publishes a host port, so that wait always runs its full ~2 minutes. It is slow, not stuck.

Most images come from Docker Hub, which rate-limits anonymous pulls per IP address — and
the whole campus shares one. If the first run fails with `toomanyrequests`, sign in with
a free Docker Hub account (the limit then counts per account) and run it again:

```bash
docker login
make stack-init
```

This only matters on the first run: afterwards the images are on the VM's disk.

## 7. Test it

Open Firefox **inside the guest** (`FRONTEND_URL` is `https://localhost`, so a browser on
the workstation through a forwarded port would break the login redirects):

| What | Where | Login |
|---|---|---|
| Site | `https://localhost` | `user1@test.com` / `1234` (pre-verified) |
| Grafana | `https://localhost:3001` | the `infra-auth` login |
| Kibana | `https://localhost:5601` | the `infra-auth` login |
| Prometheus | `https://localhost:9090` | the `infra-auth` login |

Accept the self-signed certificate warning once per port.

- **Search returns nothing:** `VOYAGE_API_KEY` was missing when the demo data loaded —
  set it, restart (`make stack-down && make stack-up`), then `make seed-fixtures`.
- **Google sign-in:** the OAuth client needs `https://localhost/auth/callback` as a
  redirect URI.
- **Light variant** (the guest runs out of memory, or you only need the app): skip the
  stack and run `make dev` — API, Postgres
  and Redis in Docker plus the frontend on `http://localhost:3000`, no monitoring, no
  HTTPS. Needs Node.js 20.9+ in the guest; Debian 12 ships Node 18, so install it from
  NodeSource:
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
  node --version          # v22.x
  ```

Stop with `make stack-down` (data is kept in named volumes).

## 8. Take a snapshot

Once `make stack-init` has worked, *Machine → Take Snapshot* (e.g. `stack-ready`).
Rolling back then takes seconds instead of another hour.
