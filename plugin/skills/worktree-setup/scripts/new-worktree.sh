#!/usr/bin/env bash
#
# new-worktree.sh — create ONE isolated worktree for a repo described in a
# worktree config. Cuts a branch from origin/<base> (never touches the main
# checkout's current branch), drops it in a sibling dir, copies the configured
# env files, runs the configured install command, and prints a report block.
# Call once per repo; the worktree SKILL.md loops it for dual/multi tasks.
#
# Usage:
#   new-worktree.sh --config <path> --repo <key> --branch <name> [opts]
#
# Options:
#   --config <path>   Required. Resolved worktree config JSON.
#   --repo <key>      Required. A repos[].key in the config.
#   --branch <name>   Required. Identical across coupled repos on dual/multi.
#   --parent <dir>    Sibling-checkouts dir. Default: parentHint or parent of toplevel.
#   --base <branch>   Override base. Default: repo/project base from config.
#   --slug <slug>     Worktree dir suffix. Default: branch's last path segment.
#   --worktree <path> Full worktree path override.
#   --no-install      Skip install.
#   --no-env          Skip env-file copy.
#   -h, --help        Show this help.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="" REPO_KEY="" BRANCH="" PARENT="" BASE="" SLUG="" WT_PATH="" DO_INSTALL=1 DO_ENV=1
die() { echo "ERROR: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --config)   CONFIG="${2:-}"; shift 2 ;;
    --repo)     REPO_KEY="${2:-}"; shift 2 ;;
    --branch)   BRANCH="${2:-}"; shift 2 ;;
    --parent)   PARENT="${2:-}"; shift 2 ;;
    --base)     BASE="${2:-}"; shift 2 ;;
    --slug)     SLUG="${2:-}"; shift 2 ;;
    --worktree) WT_PATH="${2:-}"; shift 2 ;;
    --no-install) DO_INSTALL=0; shift ;;
    --no-env)     DO_ENV=0; shift ;;
    -h|--help)  awk 'NR>1 && /^#/{sub(/^# ?/,"");print;next} NR>1{exit}' "$0"; exit 0 ;;
    *) die "unknown arg: $1" ;;
  esac
done

[ -n "$CONFIG" ] || die "--config is required"
[ -f "$CONFIG" ] || die "config not found: $CONFIG"
[ -n "$REPO_KEY" ] || die "--repo is required"
[ -n "$BRANCH" ]   || die "--branch is required"

# Pull repo fields from config via the node helper (no bash JSON parsing).
eval "$(node "$SCRIPT_DIR/resolve-config.mjs" repo --config "$CONFIG" --repo "$REPO_KEY")" \
  || die "repo '$REPO_KEY' not found in config $CONFIG"
[ -n "${REPO_DIR:-}" ] || die "repo '$REPO_KEY' has no dir in config"
[ -n "$BASE" ] || BASE="${REPO_BASE:-}"
[ -n "$BASE" ] || die "no base branch (config baseBranch missing and --base not given)"

# Parent dir.
if [ -z "$PARENT" ]; then
  if [ -n "${CONFIG_PARENT_HINT:-}" ]; then
    PARENT="$CONFIG_PARENT_HINT"
  else
    CUR_TOP="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    [ -n "$CUR_TOP" ] || die "not in a git repo and --parent not given"
    PARENT="$(cd "$(dirname "$CUR_TOP")" && pwd -P)"
  fi
fi
[ -d "$PARENT" ] || die "parent dir not found: $PARENT"

TARGET="$PARENT/$REPO_DIR"
[ -d "$TARGET/.git" ] || [ -f "$TARGET/.git" ] || die "target checkout not a git repo: $TARGET"

# Guard: target origin must match the config's remoteMatch.
REMOTE_URL="$(git -C "$TARGET" remote get-url origin 2>/dev/null || true)"
node "$SCRIPT_DIR/resolve-config.mjs" guard --config "$CONFIG" --origin "$REMOTE_URL" \
  || die "refusing: $TARGET origin ('$REMOTE_URL') does not match config remoteMatch"

# Slug + worktree path.
[ -n "$SLUG" ] || SLUG="${BRANCH##*/}"
[ -n "$SLUG" ] || die "could not derive slug from branch '$BRANCH'"
[ -n "$WT_PATH" ] || WT_PATH="$PARENT/$REPO_DIR-$SLUG"

# Collisions.
[ ! -e "$WT_PATH" ] || die "worktree path already exists: $WT_PATH"
if git -C "$TARGET" rev-parse --verify --quiet "refs/heads/$BRANCH" >/dev/null; then
  die "branch already exists in $REPO_DIR: $BRANCH"
fi

echo ">> $REPO_DIR : creating worktree for '$BRANCH'"
echo "   target checkout : $TARGET"
echo "   worktree path   : $WT_PATH"
echo "   base            : origin/$BASE"

# Cut from origin/<base> so the main checkout's branch is never touched.
git -C "$TARGET" fetch origin "$BASE"
git -C "$TARGET" rev-parse --verify --quiet "refs/remotes/origin/$BASE" >/dev/null \
  || die "origin/$BASE not found after fetch — does $REPO_DIR have a '$BASE' branch?"

git -C "$TARGET" worktree add "$WT_PATH" -b "$BRANCH" "origin/$BASE"
git -C "$WT_PATH" branch --unset-upstream 2>/dev/null || true
BASE_SHA="$(git -C "$WT_PATH" rev-parse --short HEAD)"

# Copy configured env files: literal name | glob | "dir/". Skip-if-absent.
ENV_STATUS="skipped (--no-env)"
if [ "$DO_ENV" -eq 1 ]; then
  copied=""
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    case "$entry" in
      */)
        d="${entry%/}"
        if [ -d "$TARGET/$d" ]; then cp -R "$TARGET/$d" "$WT_PATH/"; copied="$copied $entry"; fi
        ;;
      *)
        for f in "$TARGET"/$entry; do
          [ -e "$f" ] || continue
          cp "$f" "$WT_PATH/"; copied="$copied $(basename "$f")"
        done
        ;;
    esac
  done <<< "${REPO_ENVFILES:-}"
  ENV_STATUS="${copied:- (none found to copy)}"
fi

# Install.
INSTALL_STATUS="skipped (--no-install)"
if [ "$DO_INSTALL" -eq 1 ] && [ -n "${REPO_INSTALL:-}" ]; then
  echo ">> $REPO_DIR : $REPO_INSTALL …"
  if ( cd "$WT_PATH" && sh -c "$REPO_INSTALL" ); then
    INSTALL_STATUS="ok ($REPO_INSTALL)"
  else
    die "install failed in $WT_PATH — worktree created but unusable until deps install"
  fi
fi

cat <<EOF

=== worktree: $REPO_DIR ===
repo:      $REPO_DIR
worktree:  $WT_PATH
branch:    $BRANCH  (no upstream; first push: git push -u origin $BRANCH)
base:      origin/$BASE @ $BASE_SHA
env:       $ENV_STATUS
install:   $INSTALL_STATUS
EOF
