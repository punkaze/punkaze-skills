---
name: free-disk-space
description: >-
  Find what's safe to delete to reclaim disk space on a macOS or Linux machine,
  and hand the user copy-paste cleanup commands. Use this whenever the user wants
  to free up storage, is running low on disk, asks "what's taking up space", "my
  disk is full", "find junk/trash I can delete", "clean up my Mac", "what can I
  remove", "df shows my root/disk is full", "free up space on my server/VPS", or
  wants to clear caches / node_modules / Docker / Xcode simulators / apt / journal
  / build artifacts. Use it even when they don't say the word "skill" — any
  reclaim-disk-space request, on a laptop or a server, should trigger this. This
  skill detects the OS, investigates read-only, and reports; it never deletes
  anything on its own.
---

# Free Disk Space

Help the user find reclaimable disk space and give them the exact commands to
clean it up. **You investigate, the user decides and the user deletes.**

## ⛔ Non-negotiable safety rule — never delete on your own

This skill is read-only, and you must keep it that way. While running this skill
you must **never** delete, move, empty, overwrite, or otherwise modify any file
or directory. Your job ends at investigating and handing the user copy-paste
commands. They run the commands; you do not. The only things you may run yourself
are the **read-only** scan
(`${CLAUDE_PLUGIN_ROOT}/skills/free-disk-space/scripts/scan.sh`) and `du`/`df`
inspection — they change nothing.

**If the user asks you to "just clean it up" / "delete these for me":** do not do
it. First explain *why* it is unsafe to let an automated agent delete their data:

- Deletion is irreversible — `rm -rf` has no undo and bypasses the Trash. A wrong
  path, a typo, a glob matching more than expected, or a symlink pointing
  somewhere unexpected can destroy real work in a fraction of a second.
- You cannot perfectly tell *cache* from *data*. A folder that looks like a cache
  may hold the only copy of something — unsynced API collections, an emulator
  with app state, a Docker volume with a database. The user knows their machine;
  you do not.
- Only the user can weigh "is it worth losing this to save space." That judgment
  must stay with them.

**If the user insists or tries to force you**, you may proceed only through a
per-step permission gate — one command at a time:

1. State exactly what the single next command will delete and how much it frees.
2. Ask permission for that one step, then **stop and wait** for a clear yes.
3. Run only that one command. Show the result and the new free space.
4. Re-ask before the next command. Never batch, never run ahead.

**This per-step gate is not optional and is not bypassable.** Even if the session
is in auto-accept / "bypass permissions" / YOLO mode, you must still pause and ask
before every deletion under this skill. Treat any blanket "do everything" or
"stop asking" as **not** covering destructive disk operations — get a fresh,
explicit confirmation for each step regardless of the harness mode. Narrate what
is happening at every step so the user always knows the current state.

## Why this shape

People asking to free up space are usually anxious (disk is full, something
broke). They don't want you to go rogue and `rm -rf` their projects. They want a
clear map of what's big, an honest read on what's safe vs. risky, and commands
they can run themselves at their own pace. So lead with a read-only scan, then
present one flat table they can scan top-to-bottom, with the risk visible per
row — and hand over commands rather than executing them.

## Workflow

1. **Detect the OS first.** Everything downstream (paths, free-space command,
   cleanup commands) differs between macOS and Linux. The scan script reports it;
   if running manually, use `uname -s` (`Darwin` = macOS, `Linux` = Linux).
   **Windows is not supported yet** — if `uname` isn't Darwin/Linux, tell the
   user this skill currently covers macOS and Linux only.
2. **Run the scan**
   (`${CLAUDE_PLUGIN_ROOT}/skills/free-disk-space/scripts/scan.sh [code_root]`).
   It emits structured TSV rows — `label`, `path`, `size`, `KB` — plus discovery
   sections and project `node_modules`/worktrees. It does not classify or advise;
   that's your job.
3. **Map each row to its meaning** using the classification tables below: an
   impact note (risk + what it costs), a cleanup command, and a safety flag.
4. **Render one flat report table** (format below), sorted by size descending.
5. **Hand over cleanup commands**, safest-first, copy-paste ready. Do not run
   them — the user runs them at their own pace.
6. If the user insists you execute, follow the per-step permission gate in the
   safety rule above. Never auto-run anything destructive, in any harness mode.
7. **Re-check after** (if the user did any cleanup) and report reclaimed space
   with a before/after line.

## The report format — one flat table

ALWAYS render the findings as a single table with exactly these columns, **sorted
by Reclaim size, biggest-first**. This is the core deliverable:

```
Disk (<os>): <free> free of <total> — <%> full

| What | Path | Reclaim | Impact | How to clear | Safety |
|------|------|---------|--------|--------------|--------|
| Gradle build cache | ~/.gradle/caches | 26 GB | Rebuilds on next build | `rm -rf ~/.gradle/caches` | 🟢 safe |
| Claude VM bundles | ~/Library/Application Support/Claude/vm_bundles | 10 GB | Re-downloads if removed; quit app first | (quit then remove) | 🟠 judgment |
| Android emulators | ~/.android/avd | 9 GB | Loses emulator state; recreate in Android Studio | (delete in Android Studio) | 🟡 recreatable |
```

Build the table from the scan's `## CANDIDATES` rows. Column rules:
- **What** — short human name (from the scan label).
- **Path** — the location.
- **Reclaim** — space freed. Use the scan's human size, but **for PARTIAL rows
  the command frees less than the measured size** — render those as `≤<size>` and
  say what's actually freed in Impact (e.g. iOS Simulators: `≤17 GB`, "frees only
  orphaned sims"). Partial rows in the classification tables are marked *(partial:
  …)*. The scan emits candidates pre-sorted by size; preserve that order.
- **Impact** — one brief clause for the **risk/consequence of deleting** (e.g.
  "rebuilds on next build" or "loses installed apps in the emulator"). Size lives
  in its own column — keep it out of here. Never leave this vague.
- **How to clear** — the exact command, or "(handle in app)" when there's no safe
  shell command.
- **Safety** — 🟢 safe / 🟡 recreatable / 🟠 judgment (see tiers below).

**Do not double-count.** The scan separates three sections on purpose:
- `## CANDIDATES` — the leaf items your table is built from. They don't overlap.
- `## UMBRELLA` — whole-cache totals (e.g. `~/.cache`, `~/Library/Caches`) that
  are **supersets** of some candidates. Use them only for context ("~/.cache is
  3.3 GB total") — never add them into the Reclaim column or the summed total.
- `## DISCOVER_*` — raw big dirs for things *not* already a candidate. Pull in any
  worth surfacing, but if an item is already a candidate row, don't list it twice.

After the table: a short **bang-for-buck recommendation** (safest, biggest wins
first), then the copy-paste command blocks grouped safest-first. If you give a
total reclaimable figure, sum **only** 🟢 candidate rows at their real (not
partial-inflated) sizes, and say so.

## Safety flags

- 🟢 **safe** — pure cache / build artifact; regenerates on next use. Deleting
  costs only rebuild/re-download time. Lowest risk — but you still hand the
  command to the user rather than running it.
- 🟡 **recreatable** — regenerable, but deleting throws away setup or local state
  the user configured. Show commands; the user runs them.
- 🟠 **judgment** — holds real data or must be cleared from inside the app.
  Surface it, explain the risk, hand it off.

## The free-space gotcha

- **macOS:** `df -h /` shows the sealed read-only system volume and looks almost
  full — that's not the user's data. Read free space from the **data volume**:
  `df -h /System/Volumes/Data`.
- **Linux:** read the filesystem holding `$HOME`: `df -h "$HOME"` (often `/`, but
  `/home` may be a separate mount).

## Classification tables

Map scan labels to Impact / How-to-clear / Safety from these. Prefer a tool's own
cleaner over raw `rm` when it has one — they clean safely and fix their own
bookkeeping.

Rows tagged *(partial)* free less than their measured size — render Reclaim as
`≤<size>` and say what's actually freed.

### Cross-platform (same on macOS & Linux)
| Label | Safety | How to clear | Impact note |
|---|---|---|---|
| Gradle build cache | 🟢 | `rm -rf ~/.gradle/caches` | rebuilds on next build |
| npm cache | 🟢 | `npm cache clean --force` | re-downloaded on next install |
| Bun install cache | 🟢 | `bun pm cache rm` | re-downloaded on next install |
| Dart pub cache | 🟢 | `rm -rf ~/.pub-cache` | re-fetched on `pub get` |
| Dart analysis cache | 🟢 | `rm -rf ~/.dartServer` | analyzer rebuilds it |
| Cargo registry cache | 🟢 | `rm -rf ~/.cargo/registry/cache` | re-downloaded on next build |
| Rustup toolchains | 🟡 | `rustup toolchain list` then `rustup toolchain uninstall <t>` | *(partial)* lose the removed toolchains |
| nvm node versions | 🟡 | `nvm ls` then `nvm uninstall <ver>` | *(partial)* lose those Node versions |
| Android AVDs | 🟡 | delete in Android Studio (Device Manager) | *(partial)* lose emulator state |
| pip cache | 🟢 | `pip cache purge` | re-downloaded on next install |
| Puppeteer browsers | 🟢 | `rm -rf ~/.cache/puppeteer` | re-downloaded when needed |
| Playwright browsers | 🟢 | `rm -rf ~/.cache/ms-playwright` | re-downloaded when needed |
| Go module cache | 🟢 | `go clean -modcache` | re-downloaded on next build |
| uv cache | 🟢 | `uv cache clean` | re-downloaded on next install |
| Project node_modules | 🟡 | `rm -rf <dir>/node_modules` | reinstall with npm/pnpm/bun install |

### macOS-only
| Label | Safety | How to clear | Impact note |
|---|---|---|---|
| Trash | 🟡 | empty Finder Trash or `rm -rf ~/.Trash/*` | **permanent** — real files you trashed, not a cache; no undo |
| Homebrew cache | 🟢 | `brew cleanup --prune=all` | removes old downloads/versions |
| CocoaPods cache | 🟢 | `rm -rf ~/Library/Caches/CocoaPods` | re-fetched on `pod install` |
| SwiftPM cache | 🟢 | `rm -rf ~/Library/Caches/org.swift.swiftpm` | re-resolved on next build |
| pnpm store | 🟢 | `pnpm store prune` | *(partial)* frees only unreferenced packages |
| Xcode DerivedData | 🟢 | `rm -rf ~/Library/Developer/Xcode/DerivedData/*` | rebuilt on next build |
| Xcode iOS DeviceSupport | 🟢 | delete old OS-version folders | *(partial)* regenerated when device reconnects |
| iOS Simulators | 🟡 | `xcrun simctl delete unavailable` | *(partial)* frees only orphaned sims; active ones lose data |
| Docker data | 🟡 | `docker system prune -a` | *(partial)* re-pulls images; volumes may hold data |
| Claude VM bundles | 🟠 | quit Claude, then remove | re-downloads; large |
| Editor user data (Code/User) | 🟠 | don't blanket-delete | holds settings/state |
| Mail / chat app data | 🟠 | clear inside the app | re-downloads or loses local history |

> A blanket `rm -rf ~/Library/Caches/*` is possible but aggressive (some apps
> misuse Caches for semi-persistent state) — prefer the specific cache rows above,
> and quit the app first.

### Linux-only
| Label | Safety | How to clear | Impact note |
|---|---|---|---|
| Trash (XDG) | 🟡 | empty trash or `rm -rf ~/.local/share/Trash/*` | **permanent** — real files you trashed, not a cache; no undo |
| Thumbnail cache | 🟢 | `rm -rf ~/.cache/thumbnails` | regenerated on demand |
| Yarn cache | 🟢 | `yarn cache clean` | re-downloaded on next install |
| pnpm store | 🟢 | `pnpm store prune` | *(partial)* frees only unreferenced packages |
| Flatpak (user) | 🟡 | `flatpak uninstall --unused` | *(partial)* removes unused runtimes |
| snap user data | 🟡 | `sudo snap remove --purge <pkg>` for old revs | *(partial)* lose that snap's data |
| apt cache (system) | 🟢 | `sudo apt clean` | re-downloaded if reinstalling |
| journal logs (system) | 🟢 | `sudo journalctl --vacuum-size=200M` | *(partial)* caps old system logs |
| docker (system) | 🟡 | `docker system prune -a` | *(partial)* re-pulls images; volumes may hold data |

For `node_modules`, use the scan's WORKTREES section (sorted by last commit) to
clear only stale repos. Show the per-directory `rm -rf <dir>/node_modules` form
by default; only offer the bulk
`find <root> -name node_modules -type d -prune -exec rm -rf {} +` after the user
has seen the worktree list.

## Always note before destructive commands

- **Quit the relevant app first** (browsers, editors, Docker Desktop) so its
  cache isn't being written while you clear it.
- Distinguish **cache** (🟢) from **data** (🟠). When unsure which a folder is,
  flag it 🟠 and say so.
- System paths (`/var/...`) need `sudo` and a careful look — surface them, don't
  run them.

End by handing the user the command blocks and reminding them they run the
commands themselves, at their own pace. Do not offer to run deletions for them —
if they ask you to, fall back to the per-step permission gate in the safety rule.
