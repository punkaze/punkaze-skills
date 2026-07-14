---
name: tracking-test-cases
description: Open a persistent, branch-scoped QA checklist before opening a PR — a local interactive console for manually verifying a feature, with results that survive across re-runs (e.g. after addressing review feedback) even though the branch's worktree gets deleted after merge. Use when the user wants a pre-PR test pass, asks to "track test cases for this branch/feature/PR", or before finishing a development branch if no QA pass has been recorded yet for it. NOT for automated test suites, NOT for post-merge or ongoing mid-development checklists, NOT for tracking review-comment threads.
metadata:
  author: piyawat
  version: "1.0.0"
  tags: ["qa", "testing", "test-tracking", "manual-qa", "pre-pr", "checklist"]
---

# tracking-test-cases

A pre-PR manual QA checklist, scoped to the current git branch, persisted globally (survives worktree deletion after merge), diffing each run against the last one so you can see what changed after a fix.

## Run loop

1. **Resolve identity.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/tracking-test-cases/scripts/base_branch.py"` from inside the target repo. It prints JSON: `repo`, `repoSlug`, `branch`, `branchSlug`, `baseBranch`, `baseBranchSource`, `storageDir`. If it errors (`detached HEAD` or `not inside a git repository`), stop and tell the user why — this skill needs a real checked-out branch.
2. **Load or create the case list** at `<storageDir>/cases.json`.
   - If it already exists: don't overwrite it. Ask whether to just re-run the existing cases, or add more first.
   - If it doesn't exist: ask the user — manual authoring, or auto-derive a draft?
     - **Auto-derive:** run `git diff <baseBranch>...HEAD` (using the `baseBranch` from step 1 — never guess a different one). If a plan doc matching this branch exists under `docs/superpowers/plans/`, read it too. Draft candidate cases from what you find. **Always show the draft to the user to edit/add/remove before writing `cases.json` — never write auto-derived cases straight through unreviewed.** If the diff is empty, say so plainly and fall back to manual entry for this invocation.
     - **Manual:** ask the user for cases directly.
   - Write `<storageDir>/cases.json` as `{"branch", "repo", "createdAt", "cases": [{"id","title","context"?,"steps"?,"expected"?,"source"}]}`. `context` is a short sentence of prose (what/why), `steps` is an array of strings rendered as a numbered, monospaced list (use this for literal commands/checks — don't cram them into `context` as prose), `expected` is a short sentence rendered as its own callout. All three are optional but include at least one alongside `title` — don't fall back to a single wall-of-text field.
   *Done when:* `cases.json` exists with at least one case, every case has a stable `id`.
3. **Launch (background).** Run, as a background process: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/tracking-test-cases/scripts/tracker_server.py" <storageDir>`. *Done when:* the printed `url` opened in the browser.
4. **Hand off and wait.** Tell the user the console is open. There are two footer buttons, both of which record the round (write a `runs/` snapshot, blank the checklist) and exit the server: **Submit** (highlighted) means "capture this round, I'm going to keep testing" — no confirm dialog. **Done & close** (secondary, confirm dialog) means this QA pass is over. Do NOT poll. *Done when:* the background process **exits** — that's the read-results signal, from either button.
5. **Read and report — exhaustive, and call out flips.** Read the newest file in `<storageDir>/runs/`. Report every case's result (not just failures). If this wasn't the first run for this branch, explicitly state which cases flipped since the previous run (the UI only shows each case's own last-run status inline, not a cross-case summary) — don't make the user re-derive that from the raw JSON. Check the run's `action` field:
   - `"submit"` → the user wants another round. After reporting, immediately relaunch a fresh console (step 3 again) without waiting to be asked — that's what Submit signals.
   - `"done"` → this QA pass is complete. Don't auto-relaunch.
6. **Clean up.** If the server is still running (user read early without submitting), stop it.

## Facts

- **Storage:** `~/.claude/test-tracking/<repoSlug>/<branchSlug>/` — global, outside any repo checkout, so it survives this project's post-merge worktree deletion. `cases.json` is mutable; `runs/<timestamp>.json` files are immutable snapshots, one per completed run.
- **Base-branch resolution** (used for auto-derive's diff) checks the `worktree-setup` skill's own project registry first — `$WORKTREE_REGISTRY_DIR` if set, else `$CLAUDE_PLUGIN_DATA/projects` when `worktree-setup` is also installed (matches the repo's `origin` URL against each entry's `remoteMatch`, uses its `baseBranch`) — before falling back to `git merge-base` against `develop`, then `main`, then `master`. Do not shortcut this by trying `main`/`master` first — a repo's platform-default branch and its actual integration branch can differ, and guessing wrong silently produces a valid-but-meaningless diff.
- **Notify:** same pattern as `live-console` — the server exits on either footer button (Submit or Done & close), no polling. The run file's `action` field tells you which: `"submit"` means relaunch for another round, `"done"` means this QA pass is finished.
- **Scope:** pre-PR QA only. Not for automated tests, not for tracking things after a PR is already open.
