#!/usr/bin/env bash
# Hermetic smoke test for scan.sh. Points HOME and the scan root at a temp dir
# populated with fake caches / a project / a git repo, so output is deterministic
# and the real machine is never touched. Asserts the report contract and that the
# scan is read-only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SCAN="$SCRIPT_DIR/scan.sh"
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

H="$(mktemp -d -t fds-smoke-XXXXXX)"
trap 'rm -rf "$H"' EXIT

# Fake candidates with clearly distinct sizes (to test the size sort): the
# labels gradle/uv/npm are cross-platform, so this runs on macOS and Linux alike.
mkdir -p "$H/.gradle/caches" "$H/.cache/uv" "$H/.npm"
head -c 600000 /dev/zero > "$H/.gradle/caches/blob"   # ~586 KB
head -c 300000 /dev/zero > "$H/.cache/uv/blob"        # ~293 KB
head -c  40000 /dev/zero > "$H/.npm/blob"             # ~40 KB

# A project with node_modules inside a real git repo (for the NODE_MODULES and
# WORKTREES sections).
mkdir -p "$H/repo/node_modules"
head -c 10000 /dev/zero > "$H/repo/node_modules/blob"
( cd "$H/repo"
  git init -q
  git config user.email t@t; git config user.name t
  echo x > f; git add -A; git commit -q -m init )

# Read-only sentinel.
printf 'keep\n' > "$H/SENTINEL"

OUT="$H/out.txt"
HOME="$H" bash "$SCAN" "$H" > "$OUT" 2>/dev/null || fail "scan exited non-zero"

# --- contract: required section markers ---
for marker in '## OS' '## FREE' '## CANDIDATES' '## UMBRELLA' '## NODE_MODULES' '## WORKTREES' '## DONE'; do
  grep -q "^$marker" "$OUT" || fail "missing section: $marker"
done

# OS detected as one of the known values
grep -Eq '^## OS	(macos|linux|unsupported)$' "$OUT" || fail "bad/missing OS line"

# CANDIDATES header has the exact TSV columns
grep -q "^## CANDIDATES	label	path	human	KB$" "$OUT" || fail "bad CANDIDATES header"

# Our fake candidates show up with their human sizes
grep -q "^Gradle build cache	" "$OUT" || fail "Gradle candidate missing"
grep -q "^uv cache	"           "$OUT" || fail "uv candidate missing"
grep -q "^npm cache	"          "$OUT" || fail "npm candidate missing"

# Candidates are sorted by size (KB, col 4) descending
prev=""
while IFS= read -r kb; do
  [ -n "$kb" ] || continue
  if [ -n "$prev" ] && [ "$kb" -gt "$prev" ]; then
    fail "candidates not sorted descending ($kb after $prev)"
  fi
  prev="$kb"
done < <(awk -F'\t' '/^## CANDIDATES/{f=1;next} /^## /{f=0} f{print $4}' "$OUT")
[ -n "$prev" ] || fail "no candidate rows parsed"

# Project sections picked up our fixtures
grep -q "$H/repo/node_modules" "$OUT" || fail "node_modules not found"
grep -q "	$H/repo$"            "$OUT" || fail "git worktree not found"

# DONE line confirms read-only intent
grep -q '^## DONE	scan was read-only; nothing deleted$' "$OUT" || fail "bad DONE line"

# --- read-only: fixtures untouched ---
[ "$(cat "$H/SENTINEL")" = "keep" ] || fail "sentinel modified"
[ -f "$H/.gradle/caches/blob" ]     || fail "candidate deleted by scan"
[ -f "$H/repo/node_modules/blob" ]  || fail "node_modules deleted by scan"

echo "SMOKE OK"
