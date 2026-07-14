#!/usr/bin/env python3
"""Hermetic self-check for base_branch.py's pure helpers — remote-URL
parsing, slugging, and the worktree-setup registry-dir resolution order.
No git repo or network needed."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import base_branch as bb  # noqa: E402


def check(cond, msg):
    if not cond:
        print(f"SMOKE FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


check(bb.parse_remote("git@github.com:punkaze/skills.git") == "punkaze/skills", "ssh remote")
check(bb.parse_remote("https://github.com/punkaze/skills.git") == "punkaze/skills", "https remote")
check(bb.parse_remote("https://github.com/punkaze/skills") == "punkaze/skills", "https remote, no .git suffix")
check(bb.parse_remote(None) is None, "no remote")

check(bb.slugify("feature/item-note") == "feature-item-note", "slugify slash")
check(bb.slugify("punkaze/skills") == "punkaze-skills", "slugify org/repo")

for var in ("WORKTREE_REGISTRY_DIR", "CLAUDE_PLUGIN_DATA"):
    os.environ.pop(var, None)
check(bb.worktree_registry_dir() is None, "no env set -> None")

os.environ["CLAUDE_PLUGIN_DATA"] = "/data"
check(str(bb.worktree_registry_dir()) == "/data/projects", "CLAUDE_PLUGIN_DATA -> <dir>/projects")

os.environ["WORKTREE_REGISTRY_DIR"] = "/explicit"
check(str(bb.worktree_registry_dir()) == "/explicit", "WORKTREE_REGISTRY_DIR overrides CLAUDE_PLUGIN_DATA")
del os.environ["WORKTREE_REGISTRY_DIR"]
del os.environ["CLAUDE_PLUGIN_DATA"]

print("SMOKE OK")
