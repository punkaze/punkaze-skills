#!/usr/bin/env bash
# Real end-to-end check: build a temp bare origin + a clone whose dir/origin
# match a temp config, then run the engine and assert the worktree is correct.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

WORK="$(mktemp -d -t wt-smoke-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
PARENT="$WORK/wt-smoke-origin-root"   # 'wt-smoke-origin' is the remoteMatch token
mkdir -p "$PARENT"

# bare origin with a develop branch
git init -q --bare "$PARENT/demo.git"
SEED="$WORK/seed"
git clone -q "$PARENT/demo.git" "$SEED"
( cd "$SEED"
  git config user.email t@t; git config user.name t
  git checkout -q -b develop
  echo hello > file.txt; git add -A; git commit -q -m init
  git push -q origin develop )

# main checkout whose dir name == config repos[].dir, origin == bare path
git clone -q "$PARENT/demo.git" "$PARENT/demo"
( cd "$PARENT/demo" && git checkout -q develop )
printf 'SECRET=1\n' > "$PARENT/demo/.env"   # to test env copy

CFG="$WORK/cfg.json"
cat > "$CFG" <<JSON
{ "project":"smoke","remoteMatch":"wt-smoke-origin","baseBranch":"develop",
  "repos":[{"key":"demo","dir":"demo","install":"true","envFiles":[".env"]}] }
JSON

# run the engine from inside the main checkout
( cd "$PARENT/demo" && "$SCRIPT_DIR/new-worktree.sh" --config "$CFG" --repo demo --branch feature/smoke )

WT="$PARENT/demo-smoke"
[ -d "$WT" ] || fail "worktree dir missing: $WT"
[ "$(git -C "$WT" branch --show-current)" = "feature/smoke" ] || fail "wrong branch"
git -C "$WT" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null && fail "should have no upstream"
[ "$(git -C "$PARENT/demo" branch --show-current)" = "develop" ] || fail "main checkout branch changed"
[ -f "$WT/.env" ] || fail "env file not copied"

echo "SMOKE OK"
