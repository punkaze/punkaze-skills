#!/usr/bin/env python3
"""Resolve repo/branch identity and the correct base branch for the current
git checkout. Prints one JSON object to stdout. Stdlib + git on PATH only,
no side effects.

Usage: python3 base_branch.py
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

STORAGE_ROOT = Path.home() / ".claude" / "test-tracking"


def worktree_registry_dir():
    # Same resolution order as the worktree-setup skill's own registry lookup
    # (WORKTREE_REGISTRY_DIR override, else $CLAUDE_PLUGIN_DATA/projects) —
    # only meaningful when that skill is also installed.
    override = os.environ.get("WORKTREE_REGISTRY_DIR")
    if override:
        return Path(override)
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data) / "projects"
    return None


def run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def slugify(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")


def parse_remote(url):
    """Return 'org/name' from an SSH or HTTPS git remote URL, or None."""
    if not url:
        return None
    m = re.match(r"^[\w.-]+@[\w.-]+:(.+?)(\.git)?$", url)  # SSH: git@host:org/name.git
    if m:
        return m.group(1)
    m = re.match(r"^https?://[^/]+/(.+?)(\.git)?$", url)  # HTTPS
    if m:
        return m.group(1)
    return None


def resolve_base_branch(repo_url):
    registry_dir = worktree_registry_dir()
    if repo_url and registry_dir and registry_dir.is_dir():
        for f in sorted(registry_dir.glob("*.json")):
            try:
                cfg = json.loads(f.read_text())
            except (ValueError, OSError):
                continue
            match = cfg.get("remoteMatch")
            if match and match in repo_url:
                base = cfg.get("baseBranch")
                if base:
                    return base, "worktree-setup-registry"
    for candidate in ("develop", "main", "master"):
        if run(["git", "merge-base", "HEAD", candidate]) is not None:
            return candidate, f"merge-base-{candidate}"
    return None, "unresolved"


def main():
    if run(["git", "rev-parse", "--is-inside-work-tree"]) != "true":
        print(json.dumps({"error": "not inside a git repository"}))
        sys.exit(1)

    remote_url = run(["git", "remote", "get-url", "origin"])
    repo = parse_remote(remote_url)
    if repo:
        repo_slug = slugify(repo.replace("/", "__"))
    else:
        root = run(["git", "rev-parse", "--show-toplevel"])
        repo_slug = slugify(Path(root).name if root else Path.cwd().name)

    branch = run(["git", "branch", "--show-current"]) or ""
    if not branch:
        print(json.dumps({"error": "detached HEAD — tracking-test-cases needs a named branch"}))
        sys.exit(1)
    branch_slug = slugify(branch)

    base_branch, base_source = resolve_base_branch(remote_url)

    storage_dir = STORAGE_ROOT / repo_slug / branch_slug

    print(json.dumps({
        "repo": repo,
        "repoSlug": repo_slug,
        "branch": branch,
        "branchSlug": branch_slug,
        "baseBranch": base_branch,
        "baseBranchSource": base_source,
        "storageDir": str(storage_dir),
    }, indent=2))


if __name__ == "__main__":
    main()
