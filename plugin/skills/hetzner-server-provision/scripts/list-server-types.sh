#!/usr/bin/env bash
set -euo pipefail

# Lists non-deprecated Hetzner server types with per-location monthly pricing,
# cheapest first. Use this to pick a type/location before provisioning.
#
# Requires: hcloud CLI, HCLOUD_TOKEN env var (or an active `hcloud context`).
# Usage:
#   list-server-types.sh                 # everything, cheapest first
#   list-server-types.sh --location hel1 # only one location
#   list-server-types.sh --arch arm      # only arm (or: x86)

LOCATION=""
ARCH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --location) LOCATION="$2"; shift 2 ;;
    --arch)     ARCH="$2";     shift 2 ;;
    -h|--help)  grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

command -v hcloud >/dev/null || { echo "hcloud not found. Install: brew install hcloud" >&2; exit 1; }
if [[ -z "${HCLOUD_TOKEN:-}" && -z "$(hcloud context active 2>/dev/null)" ]]; then
  echo "No Hetzner credentials. Set HCLOUD_TOKEN or run: hcloud context create <name>" >&2; exit 1
fi

hcloud server-type list -o json \
  | LOCATION="$LOCATION" ARCH="$ARCH" python3 -c '
import sys, json, os
loc_filter  = os.environ.get("LOCATION") or None
arch_filter = os.environ.get("ARCH") or None
data = json.load(sys.stdin)
rows = []
for s in data:
    if s.get("deprecation"):
        continue
    if arch_filter and s.get("architecture") != arch_filter:
        continue
    for p in s.get("prices", []):
        loc = p["location"]
        if loc_filter and loc != loc_filter:
            continue
        price = float(p["price_monthly"]["gross"])
        rows.append((price, s["name"], s["cores"], float(s["memory"]), s["disk"], s["architecture"], loc))
rows.sort()
print("%-10s %5s %7s %7s  %-6s %-6s %9s" % ("TYPE","CPU","RAM","DISK","ARCH","LOC","EUR/mo"))
for price, name, cores, mem, disk, arch, loc in rows:
    print("%-10s %4dc %5.0fGB %5dGB  %-6s %-6s %9.2f" % (name, cores, mem, disk, arch, loc, price))
'
