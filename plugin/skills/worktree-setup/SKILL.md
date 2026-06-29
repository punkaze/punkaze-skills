---
name: worktree-setup
description: Use when starting an isolated task that needs a git worktree on a NEW branch — any project. Triggers — "set up a worktree for X", "start a worktree for this task", "isolate this work in a worktree", or before a subagent-driven / executing-plans run on a repo not already in a linked worktree. Reads a per-project config (in-repo .worktree.json or a registry under $CLAUDE_PLUGIN_DATA/projects) to decide single vs dual/multi-repo scope (identical branch names on coupled repos), cut from the right base branch, copy env files, and run the right install command. No-op when no config matches and you are not asked to init one.
---

# Worktree Setup

Set up isolated git worktree(s) for a task, deciding **single vs dual/multi repo scope** from the nature of the change, using a per-project **config**. **Setup only** — creates worktree(s) + branch(es), copies env, installs deps, registers the primary worktree, then hands back. It does NOT plan or implement.

> **REQUIRED BACKGROUND:** Read the underlying git-worktree isolation logic for your toolchain. This skill layers per-project config (base branch, install, env-copy, coupling) on top.

> **Paths:** scripts live at `${CLAUDE_PLUGIN_ROOT}/skills/worktree-setup/scripts/`. Persistent per-project configs live at `${CLAUDE_PLUGIN_DATA}/projects/` (survives plugin updates), overridable with `WORKTREE_REGISTRY_DIR`. A bundled `projects/example.json` documents the format.

## When to trigger

- "set up a worktree for <X>" · "start a worktree for this task" · `/skills:worktree-setup <task>`
- "isolate this work in a worktree" (inside a configured repo)
- Before a `subagent-driven-development` / `executing-plans` run on a repo not already in a linked worktree

## When NOT to trigger

- **No config matches** the current repo and the user did not ask to set one up → no-op (offer `init`).
- **Already in a linked worktree** (`GIT_DIR != GIT_COMMON`) → work in the one you're in.
- **Trivial one-file fix** the user wants in place (`git switch -c fix/<slug>`) → no worktree.

## Step 0 — Resolve config (always first)

```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/worktree-setup/scripts/resolve-config.mjs" resolve
```
Returns JSON: `{status}` is one of `in-repo` | `registry` | `none` | `ambiguous`.

- `in-repo` / `registry` → use `configPath`. Continue.
- `none` → the repo isn't configured. If the user asked to set up a worktree, go to **Init** (Step I). Otherwise no-op.
- `ambiguous` → two registry configs match this origin; show `candidates` and ask which (or fix the `remoteMatch` values).

Also confirm you are NOT already in a linked worktree:
```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
[ "$GIT_DIR" = "$GIT_COMMON" ] || { echo "already in a linked worktree — no-op"; }
```

The current repo's **key** = the `repos[].dir` whose value equals `basename` of the current git toplevel.

## Step 1 — Decide scope (single vs dual/multi)

This is the skill's core judgment. Read the config's `coupling[]`, `neverCouple`, and `notes`.

1. **Read the task.** If it clearly belongs to one repo's domain → single (that repo).
2. **Does it touch a declared shared surface?** Compare the task against each `coupling[].sharedSurface`. If yes → **dual/multi**: all repos in that coupling group, identical branch, primary = the repo the task originates in.
3. **Unsure?** Grep the `coupling[].grep` globs (and `contractPath` if set) in the sibling repo for the symbols/files involved before deciding.
4. **`neverCouple` repos are always single.** If a change elsewhere affects a surface they also use, surface it as a **manual follow-up** — never auto-create their worktree.
5. Respect the per-coupling `notes` (e.g. code paths that are live on only one side).

## Step 2 — Confirm before creating

Worktrees are heavy (install takes minutes). Present the plan and get a yes:

> Plan: **dual** worktrees (shared contract change).
> - Primary: `<dir>` → `feature/<slug>` (becomes the working dir)
> - Secondary: `<dir>` → `feature/<slug>` (edit via absolute path)
> - Base: `origin/<base>` · install + env-copy in both
> Create these?

Branch: use the user's, else propose `<prefix>/<kebab-slug>` from `branchPrefixes`. **On dual/multi the branch name is IDENTICAL across repos.**

## Step 3 — Create the worktree(s)

Run the engine once per target repo, **primary first**:
```bash
"${CLAUDE_PLUGIN_ROOT}/skills/worktree-setup/scripts/new-worktree.sh" --config <configPath> --repo <key> --branch <name>
```
Flags: `--no-install`, `--no-env`, `--base <branch>`, `--slug`, `--worktree <path>`, `--parent <dir>`, `--help`.

The engine cuts from `origin/<base>` (never disturbs the main checkout), `--unset-upstream`s, copies configured env files, runs the configured install, prints a report. For **dual/multi**, run it once per repo with the **same `--branch`**.

## Step 4 — Register the primary worktree (agentic sessions)

```
EnterWorktree(path="<absolute path to PRIMARY worktree>")
```
Binds the session to the primary worktree. Secondaries are NOT entered — operate on them via **absolute paths** so coupled contracts stay in sync. If `EnterWorktree` isn't available, the user can `cd` in from a terminal.

## Step 5 — Verify & report

| Check | Command | Expected |
|---|---|---|
| Worktree(s) exist | `git -C <main-checkout> worktree list` | a row per new worktree |
| HEAD is new branch | `git -C <wt> branch --show-current` | the branch name |
| No upstream | `git -C <wt> rev-parse --abbrev-ref --symbolic-full-name '@{u}'` | `fatal: no upstream` (intended) |
| Main checkout untouched | main checkout's `branch --show-current` | unchanged |
| Deps installed | `ls <wt>/node_modules` (or stack equivalent) | present (unless `--no-install`) |
| Session cwd (agentic) | `pwd` after `EnterWorktree` | the primary worktree |

Report each worktree path, branch + base SHA, env/install status, which is primary/cwd, and (dual) the absolute-path reminder. Then surface the config's `caveats`. Hand back.

## Step I — Init a new project's config

When `resolve` returns `none` and the user wants a worktree here:

1. **Detect** sibling repos under the parent dir and their `origin` URLs.
2. **Base branch**: `git symbolic-ref refs/remotes/origin/HEAD` (fallback: `develop` if it exists, else `main`).
3. **Install command** from lockfile: `bun.lock`/`bun.lockb`→`bun install`; `pnpm-lock.yaml`→`pnpm install`; `yarn.lock`→`yarn`; `package-lock.json`→`npm install`; `pubspec.yaml` (+`.fvmrc`)→`fvm install && fvm flutter pub get`; `Cargo.toml`→`cargo fetch`; `go.mod`→`go mod download`.
4. **Coupling**: read the repo's `CLAUDE.md`/docs for cross-repo agreements; ask the user what shared surface couples which repos (and where the contract lives).
5. **All detections are suggestions — confirm with the user.**
6. **Write the config** against `${CLAUDE_PLUGIN_ROOT}/skills/worktree-setup/references/worktree.schema.json` (see `projects/example.json` for a worked sample):
   - **single-repo project** → in-repo `<toplevel>/.worktree.json` (recommended where committing is fine).
   - **multi-repo project** → `${CLAUDE_PLUGIN_DATA}/projects/<name>.json` (persists across plugin updates; do NOT write into the plugin's own dir, which is wiped on update). `WORKTREE_REGISTRY_DIR` overrides the location.

## Red flags — never do these

- **Switch the main checkout's branch.** The engine cuts from `origin/<base>` precisely to avoid this.
- **Cut from `main`** when the project's base is `develop`. Use the config's base.
- **Auto-create a second worktree** for a change that doesn't touch a declared shared surface.
- **Auto-create a `neverCouple` repo's worktree** as a "sync" — surface overlap as a manual note.
- **Place a worktree inside an existing checkout** — always a sibling dir.
- **Skip `--unset-upstream`** (the engine does it) — otherwise a later `git pull` merges base into the feature branch.
- **Write configs into `${CLAUDE_PLUGIN_ROOT}`** — that dir is ephemeral across updates; use `${CLAUDE_PLUGIN_DATA}` or an in-repo `.worktree.json`.

## Worked examples

Assume a registry config at `${CLAUDE_PLUGIN_DATA}/projects/myapp.json` describing two coupled repos (`api`, `web`) — see `projects/example.json` for the full shape.

**Single (backend-internal):** "worktree for the pricing-rounding refactor" (no response-shape change) →
```bash
"${CLAUDE_PLUGIN_ROOT}/skills/worktree-setup/scripts/new-worktree.sh" --config "${CLAUDE_PLUGIN_DATA}/projects/myapp.json" --repo api --branch fix/pricing-rounding
```
then `EnterWorktree(path=".../myapp-api-pricing-rounding")`.

**Dual (API contract change):** "add a `note` field to items and show it in the web app" (request + response shape changes → web reads it) →
```bash
"${CLAUDE_PLUGIN_ROOT}/skills/worktree-setup/scripts/new-worktree.sh" --config "${CLAUDE_PLUGIN_DATA}/projects/myapp.json" --repo api --branch feature/item-note
"${CLAUDE_PLUGIN_ROOT}/skills/worktree-setup/scripts/new-worktree.sh" --config "${CLAUDE_PLUGIN_DATA}/projects/myapp.json" --repo web --branch feature/item-note
```
primary = `myapp-api`; edit `myapp-web` via absolute paths; update the API contract source of truth.

**Init (new project):** "set up a worktree here" in an unconfigured repo → run Step I, detect repos/base/install, confirm, write `.worktree.json` (single) or `${CLAUDE_PLUGIN_DATA}/projects/<name>.json` (multi), then proceed from Step 1.
