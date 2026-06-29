---
name: hetzner-server-provision
description: Use this skill whenever the user wants to create, provision, or spin up a new Hetzner Cloud server. Triggers on phrases like "create a server on Hetzner", "spin up a Hetzner VPS", "set up a new Hetzner instance", "deploy to Hetzner", or any mention of Hetzner server creation. Also use when the user wants to migrate to a different Hetzner location or server type. Always invoke this skill before manually running Hetzner API calls — it handles all the edge cases automatically.
metadata:
  author: piyawat
  version: "1.0.0"
  tags: ["hetzner", "cloud", "vps", "provisioning", "hcloud", "docker", "devops"]
---

# Hetzner Server Provision

Provision a production-ready Hetzner Cloud server end-to-end: choose type/location, create the firewall, boot the server, and install Docker + Nginx + Certbot. The mechanics live in `scripts/`; this file covers *when* to run each one and the judgment calls.

**Announce at start:** "I'm using the hetzner-server-provision skill to set up your Hetzner server."

## Prerequisites

This skill uses Hetzner's official `hcloud` CLI (cleaner and more robust than raw API curl — it waits for the server natively and gives readable errors).

- **hcloud CLI** — `command -v hcloud || brew install hcloud`
- **API token** — export it so every script picks it up:
  ```bash
  export HCLOUD_TOKEN="<your-hetzner-api-token>"
  ```
  (or `hcloud context create <name>` once, interactively). Ask the user for the token if it isn't set.

## Step 0: Gather Requirements

Before provisioning, collect:
- **SSH public key** — check `~/.ssh/*.pub`, ask which to use if multiple found
- **Server purpose** — dev or production? (affects size recommendation)
- **Location preference** — or let the skill fall back across EU locations
- **Server name** — e.g. `my-app-dev`

## Step 1: Pick Type & Location

```bash
scripts/list-server-types.sh                 # all types, cheapest first
scripts/list-server-types.sh --location hel1 # filter to one location
scripts/list-server-types.sh --arch arm      # arm only (or: --arch x86)
```

**Recommendation guide** (specs only — prices drift, so read live figures from `list-server-types.sh`):
| Use case | Recommended | Specs |
|----------|-------------|-------|
| Dev server (budget) | `cx23` | 2vCPU / 4GB / 40GB, AMD64 |
| Dev server (ARM) | `cax11` | 2vCPU / 4GB / 40GB, ARM64 |
| Production small | `cx33` | 4vCPU / 8GB / 80GB, AMD64 |

> **Architecture matters for deploys:** an `arm` server (`cax*`) can only run `arm64` images; an `x86` server (`cx*`) runs `amd64`. Match the image you'll deploy later.

> Not all types exist in all locations. `cx*` are EU-only (fsn1, nbg1, hel1). Singapore (`sin`) only has pricier `cpx*` types. `list-server-types.sh` shows exactly what's bookable where.

## Step 2: Provision the Server

One script handles SSH key upload, firewall, server creation, and waiting — all idempotent, so it's safe to re-run.

```bash
scripts/provision.sh \
  --name my-app-dev \
  --type cx23 \
  --ssh-key-file ~/.ssh/id_ed25519.pub
```

It tries `hel1 → nbg1 → fsn1` and automatically moves on if a location has no capacity. Pin one with `--location hel1` if needed.

**Firewall posture (secure by default):** port 22 is opened **only to your detected public IP**, while 80/443/ICMP are public. Override with `--ssh-source <CIDR[,CIDR]>` (e.g. `--ssh-source 0.0.0.0/0,::/0` to open SSH to the world — not recommended). Database/storage ports stay closed and are later bound to the Tailscale subnet by the tailscale-server-setup skill.

On success it prints a JSON line with the IP and ID, e.g.:
```json
{"name":"my-app-dev","id":12345,"ip":"203.0.113.10","location":"hel1","type":"cx23","ssh_key":"id_ed25519","ssh_source":"203.0.113.5/32"}
```
Wait ~15s after this before the next step so `sshd` is fully up.

## Step 3: Install Docker + Nginx + Certbot (and harden)

Copy the bootstrap script to the server and run it as root:

```bash
IP=203.0.113.10           # from Step 2 JSON
KEY=~/.ssh/id_ed25519

scp -o StrictHostKeyChecking=accept-new -i "$KEY" scripts/bootstrap-remote.sh root@"$IP":/tmp/
ssh -o StrictHostKeyChecking=accept-new -i "$KEY" root@"$IP" 'bash /tmp/bootstrap-remote.sh'
```

> Uses `accept-new` (trust-on-first-use), not `StrictHostKeyChecking=no` — it pins the host key on first connect and refuses a silently-changed key afterward, which closes the MITM hole.

It installs Docker CE from the official repo (so `docker compose` works), plus Nginx and Certbot, then **hardens the box**: disables SSH password auth (key-only) and enables automatic security updates. The script runs `sshd -t` to validate the SSH config before reloading, so a typo can't lock you out, and prints the effective SSH settings at the end.

## Step 4: Report

```
✅ Server provisioned successfully

| | |
|--|--|
| Server ID | <id> |
| Public IP | <ip> |
| Location | <location> |
| Type | <type> (xvCPU, xGB RAM) |
| Cost | €x.xx/mo |
| SSH | ssh -i <key-path> root@<ip> |

Next steps:
- Deploy your application (docker-compose-deploy skill)
- Set up domain + SSL (nginx-ssl-setup skill)
- Secure with Tailscale (tailscale-server-setup skill)
```

## Security Posture

Defaults are chosen to fail closed:

- **Secrets stay out of the repo and argv.** The Hetzner token is read only from `HCLOUD_TOKEN` (or an `hcloud context`) — never a flag, never echoed. Never commit it. `provision.sh` takes a **public** key path and refuses anything that isn't a `.pub`/valid OpenSSH public key, so a private key can't be uploaded by mistake.
- **SSH is locked to your IP** at the firewall by default (`--ssh-source` to change), and the box is then made **key-only** (password auth off, root by key only).
- **Host keys are pinned** on first connect (`accept-new`), not blindly trusted.
- **Automatic security updates** are enabled on the server.
- **Input is validated** (`--name` is restricted to `[a-z0-9-]`) and all scripts use `set -euo pipefail`.

Two things this skill intentionally does *not* do, by design: it leaves 80/443 public (web traffic needs them) and keeps a public SSH rule alive (you need SSH before Tailscale exists). Run the **tailscale-server-setup** skill next to drop public SSH entirely and reach the box over the tailnet.

## Common Pitfalls

- **No capacity in a location** — `provision.sh` already falls back across EU locations; if all fail, try a different type or wait.
- **SSH timeout right after provision** — wait ~15s more for `sshd` to start.
- **Locked out after your IP changed** — SSH is pinned to the IP detected at provision time. If your IP rotates before Tailscale is up, re-run `provision.sh` (idempotent) or temporarily widen with `--ssh-source`; the firewall rule updates.
- **`docker compose` not found** — only happens with `apt install docker.io`. `bootstrap-remote.sh` uses the official Docker repo and avoids this.
- **Architecture mismatch** — deploying an `amd64` image to a `cax*` (ARM) server (or vice-versa) fails to run. Pick the server arch to match your image in Step 1.
- **`HCLOUD_TOKEN` not set** — every script exits early with a clear message; export the token (or set an `hcloud context`).
