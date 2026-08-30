<!-- Known-issue doc template. Copy this file to
     docs/known-issues/YYYY-MM-DD-<slug>.md and fill in every <placeholder>.
     Sections/subsections/rows marked (optional) may be deleted entirely if
     they don't apply — everything else keeps its heading and gets
     "_None yet._" when there's nothing real to put there. See SKILL.md for
     the full workflow and hard rules.

     Status/Severity bracket tokens are machine-parsed — keep them in sync.
     `**Status:**` starts with `[OPEN]`, `[FIXED]`, or `[WONTFIX]` (decided
     not a real issue / closed by decision, not by a code change — tooling
     buckets this with Fixed for filtering, but keep the literal "Won't
     Fix"/"Moot" wording in the prose so a reader can tell the difference).
     `**Severity:**` starts with `[Critical]`, `[High]`, `[Medium]`, or
     `[Low]`. Matching is case-insensitive, but write the exact casing shown
     here. Tooling (this skill's own dashboard, Workflow B) reads these
     tokens directly instead of guessing from prose — flip the token the
     moment reality changes (a fix lands, a re-verification changes the
     severity call), even before a fuller Resolution section gets written.

     Cross-repo doc covering the same bug in both corntrol-api-client and
     corntrol-api (or any two runtime instances)? Keep the top-line token
     `[OPEN]` until EVERY instance is closed — describe a partial fix in
     prose (e.g. "client-side fixed 2026-07-25; corntrol-api copy still
     open") rather than flipping to `[FIXED]` early.

     `**Tracker:**` is the single source of truth for the ticket key — don't
     restate or contradict it in the Status prose; link specific MRs there
     instead of repeating the ticket number.

     Retrofitting an older doc that predates this convention? If you're
     already editing it substantially (resolving it, re-verifying it), take
     the opportunity to add the bracket tokens and Category/Tracker fields
     at the same time — don't leave it half-migrated for the next person. -->

# Known Issue — <Human-readable title>

**Status:** [OPEN] Shelved <YYYY-MM-DD>. <optional extra detail — what's blocked, a branch/MR reference once one exists>.
**Severity:** [<Critical|High|Medium|Low — pick one>] <one sentence — who's blocked, how badly, single-instance vs cross-instance, prod-impact vs local-dev>.
**Category:** <short topic label, 1-3 words, not a sentence — grep sibling docs' `**Category:**` lines in this project's `docs/known-issues/` and reuse one; don't invent a new one-off>.
**Tracker:** <issue key or URL in whatever this project uses — Jira, ClickUp, Linear, GitHub Issues, etc.> (optional — delete this line if the project has no external tracker yet, or none has been filed for this issue)
**Branch at time of shelving:** `<branch>`
**Last verified commit:** `<short-hash>` — `<commit subject>`.

## Re-verification — <YYYY-MM-DD> (optional — add a new one of these, newest first, each time Status or Severity gets rechecked; delete entirely if this doc has never been re-verified)

What changed since the last check (if anything), what was re-confirmed against current code/state, and whether the Status/Severity tokens above needed to move as a result.

## Symptom

What the user observes, in concrete steps. Use bullet points if there's a sequence. Link any screenshot captured in step 4 here.

## What we already know

### <Subsystem 1> (status: <fine | suspect | broken>)

What was investigated, what code was read, what was changed (with file:line citations), what we ruled in/out.

### <Subsystem 2> (status: ...)

...

## Root cause hypothesis (most likely)

One paragraph. State the working theory. If multiple, lead with the most likely and list alternates in priority order.

### Cross-implementation comparison (optional)

Include only if the bug is a contract mismatch between two implementations of the same thing (e.g. two clients talking to one backend, two platforms sharing a protocol). Delete this subsection entirely otherwise. Concrete example of what one side expects vs what the other sends:

| Source | What it does | On wire | Result |
|---|---|---|---|
| Implementation A | … | … | ✓ |
| Implementation B | … | … | ✗ |

## Status of the in-flight fix

What's uncommitted (or committed) at time of shelving. Cite file paths + a one-line description per change. State explicitly whether the change has been verified live, or whether it's a probe waiting for repro.

When you resume:

- <Action 1 — verify, commit, restore, or rethink>
- <Action 2 — diagnostic that would confirm/deny the hypothesis>

## How the system works (optional — reference)

Short paragraph or diagram-as-prose for anyone (or future-you) picking this up cold. If the README/docs already cover this well, either delete this section or replace the paragraph with a one-line link instead of duplicating it.

## Open questions for next investigator

1. **<Question 1>** — Why it matters + how to check.
2. **<Question 2>** — …
3. ...

## Things to try next

In priority order:

1. **<First thing>** — One sentence: what + how to verify it worked.
2. **<Second thing>** — …
3. ...

## Code pointers

| What | Where |
|---|---|
| <Entry point> | `<path/to/file>` |
| <Related file> | `<path/to/file>` (line range) |
| <Sibling-repo reference> (optional) | `{{PLACEHOLDER}}/path` (line range) — only if the project documents a sibling-repo placeholder (see SKILL.md step 5); delete this row otherwise |

## Reproduction

1. Numbered steps to reproduce on a fresh checkout.
2. Expected behavior.
3. Actual behavior.
