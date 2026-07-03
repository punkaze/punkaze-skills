#!/usr/bin/env bash
# free-disk-space scanner — READ-ONLY. Detects OS (macOS/Linux) and emits
# structured TSV rows (label, path, human size, KB). It does NOT classify,
# advise, or delete — SKILL.md maps each label to impact/how-to-clear/safety.
#
# Design notes:
#  - CANDIDATES are leaf, individually-clearable locations and are measured at
#    the exact path the matching cleanup command clears (no parent/child overlap
#    inside this section, and size ~= what the command actually frees).
#  - UMBRELLA totals (whole-cache dirs) are reported separately and are supersets
#    of some candidates — never sum them with candidate rows.
#  - DISCOVER_* sections enumerate big dirs for things NOT already a candidate.
#
# Usage: scan.sh [code_root]
#   code_root = directory to search for project node_modules / git worktrees.
#   Defaults to $HOME. Pass a narrower path (e.g. ~/projects) for a faster scan.
# Uses only $HOME-relative and standard system paths — nothing machine-specific.
set -uo pipefail

CODE_ROOT="${1:-$HOME}"
[ -d "$CODE_ROOT" ] || CODE_ROOT="$HOME"

case "$(uname -s)" in
  Darwin) OS=macos ;;
  Linux)  OS=linux ;;
  *)      OS=unsupported ;;
esac

# KB -> human string (no GNU numfmt dependency; macOS/BSD safe)
human() { awk -v k="$1" 'BEGIN{split("KB MB GB TB PB",u);s=k;i=1;while(s>=1024&&i<5){s/=1024;i++}printf "%.1f%s",s,u[i]}'; }

CAND="$(mktemp)"; trap 'rm -f "$CAND"' EXIT

# Buffer a candidate row if the path exists and is non-empty: label\tpath\thuman\tKB
row() {
  local label="$1" path="$2"
  [ -e "$path" ] || return 0
  local kb; kb=$(du -sk "$path" 2>/dev/null | awk '{print $1}')
  [ -n "${kb:-}" ] && [ "$kb" -gt 0 ] 2>/dev/null || return 0
  printf '%s\t%s\t%s\t%s\n' "$label" "$path" "$(human "$kb")" "$kb" >> "$CAND"
}

# Print an informational umbrella total (superset of some candidates; don't sum)
umbrella() {
  local label="$1" path="$2"
  [ -e "$path" ] || return 0
  local kb; kb=$(du -sk "$path" 2>/dev/null | awk '{print $1}')
  [ -n "${kb:-}" ] && [ "$kb" -gt 0 ] 2>/dev/null || return 0
  printf '%s\t%s\t%s\n' "$label" "$path" "$(human "$kb")"
}

printf '## OS\t%s\n' "$OS"
[ "$OS" = unsupported ] && \
  printf '## UNSUPPORTED\tonly macOS and Linux are supported; OS-specific paths skipped\n'

printf '## FREE\n'
if [ "$OS" = macos ]; then
  df -h /System/Volumes/Data 2>/dev/null | tail -2     # macOS data volume, not the sealed system vol
else
  df -h "$HOME" 2>/dev/null | tail -2                  # filesystem holding $HOME
fi

# --- Cross-platform dev caches (measured at the command's exact target) ---
row "Gradle build cache"        "$HOME/.gradle/caches"
row "npm cache"                 "$HOME/.npm"
row "Bun install cache"         "$HOME/.bun/install/cache"
row "Dart pub cache"            "$HOME/.pub-cache"
row "Dart analysis cache"       "$HOME/.dartServer"
row "Cargo registry cache"      "$HOME/.cargo/registry/cache"
row "Rustup toolchains"         "$HOME/.rustup"               # PARTIAL: frees only unused toolchains
row "nvm node versions"         "$HOME/.nvm/versions"         # PARTIAL: frees only old versions
row "Android AVDs"              "$HOME/.android/avd"          # PARTIAL: frees only deleted emulators
row "pip cache"                 "$HOME/.cache/pip"
row "Puppeteer browsers"        "$HOME/.cache/puppeteer"
row "Playwright browsers"       "$HOME/.cache/ms-playwright"
row "Go module cache"           "$HOME/go/pkg/mod"
row "uv cache"                  "$HOME/.cache/uv"

# --- OS-specific candidate paths ---
if [ "$OS" = macos ]; then
  row "Trash"                   "$HOME/.Trash"                # PERMANENT delete (not a cache)
  row "Homebrew cache"          "$HOME/Library/Caches/Homebrew"
  row "CocoaPods cache"         "$HOME/Library/Caches/CocoaPods"
  row "SwiftPM cache"           "$HOME/Library/Caches/org.swift.swiftpm"
  row "pnpm store"              "$HOME/Library/pnpm/store"    # PARTIAL: prune frees only unreferenced
  row "pnpm store (legacy)"     "$HOME/.pnpm-store"
  row "Xcode DerivedData"       "$HOME/Library/Developer/Xcode/DerivedData"
  row "Xcode iOS DeviceSupport" "$HOME/Library/Developer/Xcode/iOS DeviceSupport"  # PARTIAL: per OS version
  row "iOS Simulators"          "$HOME/Library/Developer/CoreSimulator/Devices"    # PARTIAL: orphans only
  row "Docker data"             "$HOME/Library/Containers/com.docker.docker/Data"  # PARTIAL: prune
elif [ "$OS" = linux ]; then
  row "Trash (XDG)"             "$HOME/.local/share/Trash"    # PERMANENT delete (not a cache)
  row "Thumbnail cache"         "$HOME/.cache/thumbnails"
  row "Yarn cache"              "$HOME/.cache/yarn"
  row "pnpm store"              "$HOME/.local/share/pnpm"     # PARTIAL: prune frees only unreferenced
  row "pnpm store (legacy)"     "$HOME/.pnpm-store"
  row "Flatpak (user)"          "$HOME/.var/app"              # PARTIAL: uninstall --unused
  row "snap user data"          "$HOME/snap"                  # PARTIAL: old revisions
fi

# Emit candidates sorted biggest-first (by KB, column 4)
printf '## CANDIDATES\tlabel\tpath\thuman\tKB\n'
sort -t"$(printf '\t')" -k4 -rn "$CAND"

# --- Umbrella totals: supersets of some candidates above; DO NOT SUM with them ---
printf '## UMBRELLA\tlabel\tpath\thuman\n'
umbrella "~/.cache (whole)"     "$HOME/.cache"
[ "$OS" = macos ] && umbrella "~/Library/Caches (whole)" "$HOME/Library/Caches"

# --- Discovery of big items NOT already a curated candidate above ---
printf '## DISCOVER_DOTCACHE\thuman\tpath\n'
du -sh "$HOME"/.cache/* 2>/dev/null | sort -rh | head -10
if [ "$OS" = macos ]; then
  printf '## DISCOVER_LIBCACHES\thuman\tpath\n'
  du -sh "$HOME"/Library/Caches/* 2>/dev/null | sort -rh | head -10
  printf '## DISCOVER_APPSUPPORT\thuman\tpath\n'
  du -sh "$HOME"/Library/Application\ Support/* 2>/dev/null | sort -rh | head -10
elif [ "$OS" = linux ]; then
  printf '## DISCOVER_LOCAL\thuman\tpath\n'
  du -sh "$HOME"/.local/share/* 2>/dev/null | sort -rh | head -10
  printf '## SYSTEM_NOTE\tneeds sudo; surface, do not run\n'
  printf 'apt cache\t/var/cache/apt\n'
  printf 'journal logs\t/var/log/journal\n'
  printf 'docker (system)\t/var/lib/docker\n'
fi

# --- Project build artifacts (both OSes). -xdev: don't cross into mounted
#     volumes / cloud drives; -maxdepth before -name to avoid GNU find warnings. ---
printf '## NODE_MODULES\thuman\tpath\n'
find "$CODE_ROOT" -xdev -name node_modules -type d -prune 2>/dev/null \
  -exec du -sh {} \; | sort -rh | head -15

printf '## WORKTREES\tlast_commit\tpath\n'
find "$CODE_ROOT" -xdev -maxdepth 4 -name .git -prune 2>/dev/null | while read -r g; do
  d=$(dirname "$g")
  printf '%s\t%s\n' "$(git -C "$d" log -1 --format=%cd --date=short 2>/dev/null)" "$d"
done | sort | head -20

printf '## DONE\tscan was read-only; nothing deleted\n'
