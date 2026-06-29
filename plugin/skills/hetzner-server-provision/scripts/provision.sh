#!/usr/bin/env bash
set -euo pipefail

# Provisions a Hetzner Cloud server end-to-end using the hcloud CLI:
#   - uploads the SSH key (idempotent)
#   - creates a firewall: SSH locked to your IP, public 80/443/ICMP (idempotent)
#   - creates the server, falling back across locations on capacity errors
#   - waits for it to be running (hcloud does this natively) and prints a JSON summary
#
# Requires: hcloud CLI, HCLOUD_TOKEN env var (or an active `hcloud context`), curl.
# Usage:
#   provision.sh --name my-app-dev --type cx23 --ssh-key-file ~/.ssh/id_ed25519.pub
#
# Options:
#   --name NAME             server name; lowercase letters/digits/hyphens (required)
#   --type TYPE             server type, e.g. cx23 / cax11 (required)
#   --ssh-key-file PATH     path to the PUBLIC key, e.g. ~/.ssh/id_ed25519.pub (required)
#   --location LOC          pin to one location; default tries: hel1 nbg1 fsn1
#   --ssh-key-name NAME     name to register the key under; default: basename of key file
#   --firewall-name NAME    firewall name; default: <server-name>-fw
#   --image IMAGE           OS image; default: ubuntu-24.04
#   --ssh-source CIDR[,..]  who may reach port 22; default: your detected public IP /32.
#                           Pass 0.0.0.0/0,::/0 to open it to the world (not recommended).
#
# Security note: SSH (22) is restricted to your current public IP by default. Ports
# 80/443 are public (web traffic). After you run the tailscale-server-setup skill you
# can drop the public SSH rule entirely and reach the box over Tailscale only.

NAME="" TYPE="" KEY_FILE="" LOCATION="" KEY_NAME="" FW_NAME="" IMAGE="ubuntu-24.04" SSH_SOURCE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)          NAME="$2";       shift 2 ;;
    --type)          TYPE="$2";       shift 2 ;;
    --ssh-key-file)  KEY_FILE="$2";   shift 2 ;;
    --location)      LOCATION="$2";   shift 2 ;;
    --ssh-key-name)  KEY_NAME="$2";   shift 2 ;;
    --firewall-name) FW_NAME="$2";    shift 2 ;;
    --image)         IMAGE="$2";      shift 2 ;;
    --ssh-source)    SSH_SOURCE="$2"; shift 2 ;;
    -h|--help)       grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

command -v hcloud     >/dev/null || { echo "hcloud not found. Install: brew install hcloud" >&2; exit 1; }
command -v curl       >/dev/null || { echo "curl not found (needed to detect your public IP)" >&2; exit 1; }
command -v ssh-keygen >/dev/null || { echo "ssh-keygen not found (needed to fingerprint the SSH key)" >&2; exit 1; }
if [[ -z "${HCLOUD_TOKEN:-}" && -z "$(hcloud context active 2>/dev/null)" ]]; then
  echo "No Hetzner credentials. Set HCLOUD_TOKEN or run: hcloud context create <name>" >&2; exit 1
fi
[[ -n "$NAME"     ]] || { echo "--name is required" >&2; exit 1; }
[[ -n "$TYPE"     ]] || { echo "--type is required" >&2; exit 1; }
[[ -n "$KEY_FILE" ]] || { echo "--ssh-key-file is required" >&2; exit 1; }
[[ "$NAME" =~ ^[a-z0-9-]+$ ]] || { echo "--name must be lowercase letters, digits and hyphens only" >&2; exit 1; }
KEY_FILE="${KEY_FILE/#\~/$HOME}"
[[ -f "$KEY_FILE" ]] || { echo "SSH public key not found: $KEY_FILE" >&2; exit 1; }
case "$KEY_FILE" in
  *.pub) ;;
  *) echo "Refusing to upload '$KEY_FILE': not a .pub file. Pass the PUBLIC key, never a private key." >&2; exit 1 ;;
esac
grep -qE '^(ssh-(rsa|ed25519)|ecdsa-)' "$KEY_FILE" || { echo "'$KEY_FILE' doesn't look like an OpenSSH public key" >&2; exit 1; }

KEY_NAME="${KEY_NAME:-$(basename "$KEY_FILE" .pub)}"
FW_NAME="${FW_NAME:-${NAME}-fw}"
LOCATIONS=("$LOCATION"); [[ -z "$LOCATION" ]] && LOCATIONS=(hel1 nbg1 fsn1)

log() { echo ">> $*" >&2; }

# Determine who may reach SSH. Default: this machine's public IPv4 only (fail closed).
if [[ -z "$SSH_SOURCE" ]]; then
  MYIP="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)"
  [[ -z "$MYIP" ]] && MYIP="$(curl -fsS --max-time 10 https://ifconfig.me 2>/dev/null || true)"
  [[ "$MYIP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "Could not detect your public IPv4 to lock down SSH. Re-run with --ssh-source <CIDR> (e.g. 203.0.113.4/32)." >&2
    exit 1
  }
  SSH_SOURCE="${MYIP}/32"
  log "Restricting SSH (port 22) to your detected IP: $SSH_SOURCE"
else
  log "Restricting SSH (port 22) to: $SSH_SOURCE"
fi

# 1. SSH key (idempotent by fingerprint, then name) ---------------------------
# Hetzner rejects a duplicate fingerprint even under a new name, so match on
# fingerprint first and reuse whatever name the key is already registered under.
FP="$(ssh-keygen -E md5 -lf "$KEY_FILE" | grep -oE 'MD5:[0-9a-f:]+' | cut -d: -f2-)"
EXISTING_NAME="$(hcloud ssh-key list -o json | FP="$FP" python3 -c '
import sys, json, os
fp = os.environ["FP"]
for k in json.load(sys.stdin):
    if k.get("fingerprint") == fp:
        print(k["name"]); break
')"
if [[ -n "$EXISTING_NAME" ]]; then
  log "SSH key already registered as '$EXISTING_NAME' (fingerprint match) — reusing"
  KEY_NAME="$EXISTING_NAME"
elif hcloud ssh-key list -o noheader -o columns=name | grep -qx "$KEY_NAME"; then
  echo "An SSH key named '$KEY_NAME' exists but with a DIFFERENT fingerprint." >&2
  echo "Refusing to clash. Re-run with --ssh-key-name <other-name>." >&2
  exit 1
else
  log "Uploading SSH key '$KEY_NAME'"
  hcloud ssh-key create --name "$KEY_NAME" --public-key-from-file "$KEY_FILE" >&2
fi

# 2. Firewall ------------------------------------------------------------------
# Create if missing, then ALWAYS apply the full desired ruleset via replace-rules.
# This makes re-running idempotent AND lets it update the SSH source if your IP
# changed. SSH is restricted to $SSH_SOURCE; 80/443/ICMP are public.
if ! hcloud firewall list -o noheader -o columns=name | grep -qx "$FW_NAME"; then
  log "Creating firewall '$FW_NAME'"
  hcloud firewall create --name "$FW_NAME" >&2
fi
log "Applying firewall rules (SSH: $SSH_SOURCE; public 80/443/ICMP)"
SSH_SOURCE="$SSH_SOURCE" python3 -c '
import os, json
ssh = [s.strip() for s in os.environ["SSH_SOURCE"].split(",") if s.strip()]
print(json.dumps([
  {"direction":"in","protocol":"tcp","port":"22","source_ips":ssh,"description":"SSH"},
  {"direction":"in","protocol":"tcp","port":"80","source_ips":["0.0.0.0/0","::/0"],"description":"HTTP"},
  {"direction":"in","protocol":"tcp","port":"443","source_ips":["0.0.0.0/0","::/0"],"description":"HTTPS"},
  {"direction":"in","protocol":"icmp","source_ips":["0.0.0.0/0","::/0"],"description":"ICMP"},
]))
' | hcloud firewall replace-rules "$FW_NAME" --rules-file - >&2

# 3. Create server, falling back across locations on capacity errors ----------
if hcloud server describe "$NAME" >/dev/null 2>&1; then
  log "Server '$NAME' already exists — skipping create"
else
  created=""
  for loc in "${LOCATIONS[@]}"; do
    log "Creating server '$NAME' ($TYPE, $IMAGE) in $loc ..."
    if hcloud server create \
        --name "$NAME" --type "$TYPE" --image "$IMAGE" --location "$loc" \
        --ssh-key "$KEY_NAME" --firewall "$FW_NAME" >&2; then
      created="$loc"; break
    fi
    log "Location $loc failed (likely no capacity) — trying next"
  done
  [[ -n "$created" ]] || { echo "Could not create server in any of: ${LOCATIONS[*]}" >&2; exit 1; }
fi

# 4. Summarize ----------------------------------------------------------------
# Parse the server's JSON (stable REST schema) rather than Go-template field
# paths, so this doesn't break if hcloud's struct field names differ.
IP="$(hcloud server ip "$NAME")"
INFO="$(hcloud server describe "$NAME" -o json)"
ID="$(printf '%s' "$INFO"  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
LOC="$(printf '%s' "$INFO" | python3 -c 'import sys,json; print(json.load(sys.stdin)["datacenter"]["location"]["name"])')"
log "Server is running. Wait ~15s before SSH so sshd is up."
printf '{"name":"%s","id":%s,"ip":"%s","location":"%s","type":"%s","ssh_key":"%s","ssh_source":"%s"}\n' \
  "$NAME" "$ID" "$IP" "$LOC" "$TYPE" "$KEY_NAME" "$SSH_SOURCE"
