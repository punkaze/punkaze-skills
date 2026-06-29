#!/usr/bin/env bash
set -euo pipefail

# Installs Docker CE (+ compose plugin), Nginx, and Certbot on a fresh
# Ubuntu 24.04 server, then hardens it (key-only SSH + automatic security
# updates). Run AS ROOT on the server.
#
# From your machine:
#   scp -i <key> bootstrap-remote.sh root@<ip>:/tmp/
#   ssh -i <key> root@<ip> 'bash /tmp/bootstrap-remote.sh'
#
# SAFETY: SSH password auth is disabled (key-only). This is safe because Hetzner
# injects your SSH key at create time, so key login already works. Confirm you can
# log in with your key BEFORE relying on this — a broken key means no password
# fallback. Root stays reachable by key only (PermitRootLogin prohibit-password).
#
# Why not `apt install docker.io`? Ubuntu's docker.io package omits the
# docker-compose-plugin, so `docker compose` won't exist. Use the official repo.

export DEBIAN_FRONTEND=noninteractive

apt-get update -y -q
apt-get install -y -q ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi

# shellcheck disable=SC1091  # /etc/os-release exists on the target Ubuntu box, not here
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y -q
apt-get install -y -q \
  docker-ce docker-ce-cli containerd.io docker-compose-plugin \
  nginx certbot python3-certbot-nginx

systemctl enable docker
systemctl start docker

# --- Hardening: key-only SSH -------------------------------------------------
# Drop-in overrides the distro defaults without editing the main sshd_config.
apt-get install -y -q openssh-server
install -m 0755 -d /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
# Managed by hetzner-server-provision bootstrap. Key-only access.
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PermitRootLogin prohibit-password
EOF
# Validate config before reloading so a typo can't lock us out.
sshd -t
systemctl reload ssh 2>/dev/null || systemctl reload sshd

# --- Hardening: automatic security updates -----------------------------------
apt-get install -y -q unattended-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
systemctl enable --now unattended-upgrades 2>/dev/null || true

echo "=== Installed versions ==="
docker --version
docker compose version
nginx -v
certbot --version
echo "=== SSH hardening: password auth disabled (key-only) ==="
sshd -T | grep -E '^(passwordauthentication|permitrootlogin|kbdinteractiveauthentication) '
