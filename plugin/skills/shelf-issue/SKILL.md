---
name: shelf-issue
description: >-
  Use when the user defers a bug or in-flight investigation — "shelve this",
  "park it as a known issue", "come back to this later" — to capture it as a
  resumable known-issue doc in the current project so it can be picked back
  up later without losing context. Also use when the user wants to preview,
  browse, or review existing known-issue docs — "show me the known issues",
  "preview the known issues", "spin up the known-issues dashboard" — to build
  an interactive HTML summary (sortable table with severity/status/category,
  click-through detail) served on a local server. Also use when the user
  wants to retrofit or bulk-edit many known-issue docs at once — "migrate
  all the known-issue docs to the new template", "rename this field across
  every known-issue doc".
---

# Shelf an Issue

Capture an in-flight bug or investigation as a known-issue doc so it can be
picked back up later without losing context. Also builds an interactive local
HTML dashboard for browsing existing known-issue docs.

Three independent workflows — pick the one matching the request:

- **Workflow A** — capture a *new* issue (the original, default behavior).
- **Workflow B** — *preview* existing issues as an interactive dashboard.
- **Workflow C** — retrofit or bulk-edit many existing docs at once (a
  template migration, a field rename across the whole corpus, etc.).

## Workflow A — Shelve a new issue

An optional kebab-case slug may be given (e.g. `socket-no-inbound-events`,
`http-init-sync-missing-oa`). It may instead arrive as prose, or be empty.

### Workflow

1. **Settle the slug.** If given a clean kebab-case slug, use it. If it's
   prose or empty, derive a short kebab-case slug from the issue and show it
   for confirmation. Then show the proposed filename
   `docs/known-issues/YYYY-MM-DD-<slug>.md` (today's date) — adjust the
   directory if this project already has a different known-issues
   convention, or (in a monorepo) use the `docs/known-issues/` nearest the
   affected package's root, falling back to the repo root if that's unclear.
   If the file already exists, ask whether to overwrite, append, or pick a
   new slug.

2. **Gather context.** Pull from the current conversation, not from a fresh
   investigation:
   - What was the user trying to do?
   - What symptom did they observe?
   - What did we already try / rule out?
   - What's the current best hypothesis?
   - Is there an uncommitted in-flight fix in the working tree?
   - What files / line ranges were load-bearing in the investigation?

   If the conversation doesn't have enough to fill at least the **Symptom** +
   **What we already know** sections, stop and ask the user (Hard rule 1).

3. **Capture the working-tree state.** Run `git status --short`,
   `git diff --stat`, `git rev-parse --short HEAD`, and
   `git branch --show-current`. If there are uncommitted changes related to
   the issue, reference them by file path + a one-line description of what
   each change tries. Not a git repo, or no commits yet? Skip this step and
   write `_None yet._ (no git repo)` for the branch/commit fields instead of
   guessing.

4. **Capture attachments.** If the conversation includes a screenshot or a
   referenced file that belongs with the issue, copy it into
   `docs/known-issues/assets/YYYY-MM-DD-<slug>.<ext>` — the source is often a
   session-ephemeral path (e.g. an image cache) that won't survive — and link
   it from the doc's **Symptom** or **Reproduction** section with a relative
   path. No attachment → skip this step.

5. **Write the doc.** Copy [`template.md`](template.md) to
   `docs/known-issues/YYYY-MM-DD-<slug>.md` and fill in every `<placeholder>`
   (empty sections vs. `(optional)` content: Hard rule 1). For **Code
   pointers**, use this project's own sibling-repo path placeholders if
   `CLAUDE.md`/`CLAUDE.local.md` documents any (don't expand them) — otherwise
   just cite in-repo paths.

6. **Confirm and end.** Print the file path, how many of the template's
   sections got real content vs. `_None yet._` (e.g. "6/8 filled"), and a
   one-line summary. The doc is the next step (Hard rules 2 & 4).

### Hard rules

1. **Don't fabricate.** No real content for a section? Write `_None yet._` —
   never invent symptoms, hypotheses, or "what we tried" entries. Can't fill
   Symptom + What we already know? Stop and ask.
   Exception: content `template.md` marks `(optional)` (cross-implementation
   comparison, "How the system works", the sibling-repo code-pointer row, the
   `**Tracker:**` line) is deleted entirely — heading and all — when it
   doesn't apply. That's the one case where dropping content isn't
   fabrication-by-omission; everything else keeps its heading and gets
   `_None yet._` instead of being cut.
2. **No fixes in the doc.** This is a knowledge-capture artifact, not a fix
   plan. Hypotheses and probes belong in "Status of the in-flight fix" /
   "Things to try next" — actual code changes do not.
3. **Paths are repo-root-relative**, except documented sibling-repo
   placeholders (step 5) — never expand those.
4. **Don't commit, don't open a PR, don't propose next steps.** The doc is
   the deliverable. If the user wants it committed, they'll ask.
5. **Attachments** follow step 4's path convention — always copy from
   ephemeral sources so the link survives.
6. **One issue per file.** If the investigation surfaced two distinct bugs,
   write two files unless the user requests otherwise.
7. **Date format `YYYY-MM-DD`** in the filename. Use today's actual date —
   don't reuse the date of the bug's first observation. Applies to every
   known-issue doc regardless of how it's created — including a batch of
   docs filed from an external report/review, not just interactive shelving
   through this workflow. A bulk-filing process that skips the date prefix
   is non-compliant; fix filenames as part of that filing pass, don't file
   first and rename later.
8. **Keep the `Status`/`Severity` bracket tokens in sync with the prose that
   follows them.** `**Status:**` starts with `[OPEN]`, `[FIXED]`, or
   `[WONTFIX]` (decided not a real issue / closed by decision rather than a
   code change — bucketed with Fixed for filtering, but keep the literal
   "Won't Fix"/"Moot" wording in the prose so a reader can still tell the
   difference). `**Severity:**` starts with `[Critical]`, `[High]`,
   `[Medium]`, or `[Low]` (see `template.md`). Matching is case-insensitive,
   but write the exact casing shown here in new docs. Tooling — including
   this skill's own dashboard, Workflow B — parses these tokens directly
   instead of guessing from prose. Flip the token the moment reality
   changes — a fix lands, or a re-verification changes the severity call —
   even before a fuller Resolution section gets written. Don't let the
   token lag reality the way free-form Status prose has repeatedly done in
   practice.
   **Cross-repo doc** (the same bug tracked in both `corntrol-api-client`
   and `corntrol-api`, or any two runtime instances)? Keep the top-line
   token `[OPEN]` until *every* instance is closed — describe a partial fix
   in prose ("client-side fixed 2026-07-25; corntrol-api copy still open")
   rather than flipping to `[FIXED]` early just because one side landed.
   **`**Tracker:**` is the single source of truth for the ticket key** —
   don't restate or contradict it in the Status prose; link specific MRs
   there instead of repeating the ticket number.
   **Editing an older doc that predates this convention** (no bracket
   tokens, no `Category`/`Tracker` fields) for any substantial reason —
   resolving it, re-verifying it, expanding its scope? Retrofit its header
   block to the current format in the same edit rather than leaving it
   half-migrated for the next person. Doing this to many docs at once as its
   own dedicated pass, rather than incidentally while touching one doc for
   another reason? See Workflow C below — scripted batch edits have a
   failure mode single-doc-by-hand edits don't.
   **A legacy ad hoc tracker field** (e.g. `**Jira:**`, predating the
   generalized `**Tracker:**` field) found while retrofitting a doc? Rename
   it to `**Tracker:**` in place, keep its value, and move it to the
   `Tracker` slot in the field order shown in `template.md` (after
   `Category`, before `Branch`) — don't leave two field names doing the same
   job.

### Examples

- "shelve this as `socket-no-inbound-events`" →
  `docs/known-issues/2026-05-13-socket-no-inbound-events.md`.
- A second, related investigation → a sibling doc, one file per distinct bug.
- No slug given, or a prose description instead → derive a kebab-case slug
  and confirm it before writing.

## Workflow B — Preview known issues (interactive dashboard)

Build a self-contained interactive HTML page — sortable/filterable summary
table (with a leading `#` row-number column, Issue, Category, Severity,
Impact, Status) that opens a detail drawer with the full rendered doc on
click — and serve it on a local HTTP server. Reuses the static shell at
[`assets/dashboard.html`](assets/dashboard.html) verbatim; only the data file
is generated fresh each run.

### Steps

1. **Locate the docs.** Same directory-resolution rule as Workflow A step 1
   (project convention, or nearest `docs/known-issues/` in a monorepo).
   Enumerate `docs/known-issues/*.md` directly in that directory — skip the
   `assets/` subfolder, it holds images, not docs. If zero docs found, say so
   and stop (nothing to preview).

2. **Extract structured data per doc.** For each file, produce an object
   with exactly these fields:

   | Field | Type | How to get it |
   |---|---|---|
   | `slug` | string | filename minus `docs/known-issues/` prefix and `.md` |
   | `file` | string | repo-relative path |
   | `title` | string | H1 text after `# Known Issue — ` (strip the prefix) |
   | `status` | string | verbatim text after `**Status:**` (tolerate label variants like `**Status (at time of shelving):**`), including its leading bracket token if present |
   | `statusKind` | `"open"` \| `"fixed"` | **Mechanical.** Parse the bracket token immediately after `**Status:**`, case-insensitively — `[OPEN]` → `"open"`; `[FIXED]` or `[WONTFIX]` → `"fixed"` (a Won't-Fix/Moot closure buckets with Fixed for filtering purposes — the doc's own `status` text still preserves the real wording for anyone reading detail). Every doc written under the current template carries this token — see `template.md`. Re-derive fresh from each doc's *current* Status line every single run; never hardcode/cache `statusKind` in a persisted per-slug table (e.g. a `JUDGMENT`-style dict reused across runs) — that's exactly how a doc's real-world fix silently stopped showing up as fixed in past runs. A cross-repo doc's token stays `[OPEN]` until every repo instance is closed (see Hard rule 8) — don't infer `"fixed"` just because part of the doc's prose mentions one side landed. For a legacy doc with no bracket token (written before this convention landed), fall back to reading the free-form Status prose for Fixed/Resolved wording — the same never-cache rule still applies. |
   | `severityText` | string | verbatim text after `**Severity:**` (tolerate parenthetical variants), including its leading bracket token if present; if the doc has no Severity line at all, write an honest one-line note explaining that instead of inventing one |
   | `severityLevel` | `"Critical"` \| `"High"` \| `"Medium"` \| `"Low"` | **Mechanical when the doc carries the bracket token** — parse `[Critical]`/`[High]`/`[Medium]`/`[Low]` immediately after `**Severity:**`, case-insensitively, but sanity-check it against the doc's Symptom/Root-cause content before trusting it blindly (an author's first-pass guess can be wrong — override with a judgment call if it clearly disagrees, and note why). Check for a `## Re-verification — <date>` section (see `template.md`) — if the doc has one, its latest entry is the authoritative severity call, not the original header line, since that's the designated place a severity reassessment gets recorded. A `**Finding:** P0-3 (Critical)` line from a filed security-review finding is equivalent to the token — treat it the same way. For a legacy doc with neither, fall back to a full judgment call: Critical → unauthenticated/zero-interaction exploit with a severe outcome (account takeover, arbitrary read/write on shared infra, a hardcoded prod secret, a fleet-wide destructive endpoint with no auth gate at all) — reachable by anyone, today, in production, no special access needed. High → auth bypass / security hole / unbounded resource exhaustion / missing permission gate that still needs some precondition (a specific role, an internal-only path, a narrower blast radius) short of Critical's bar. Medium → races, inconsistencies, error-swallowing, narrow-blast-radius bugs. Low → dead code, cleanliness, contract mismatches with no observed harm. |
   | `category` | string | Prefer the doc's own `**Category:**` line if present (reuses this project's existing taxonomy — see `template.md`). For a legacy doc with no `**Category:**` line, infer one from the doc's topic, picking from the small set of labels already reused by sibling docs in this run — don't invent a new one-off label per doc. A category value is a short label, not a sentence — roughly 1-3 words, under ~40 chars (a product name with a period, like "Socket.io", is still fine — length is the real signal, not punctuation). A value that reads longer than that is a red flag, not a real category — see the sanity-bound check in step 3 below. |
   | `tracker` | string \| null | The doc's own `**Tracker:**` line if present — an issue key or URL in whatever system this project uses (Jira, ClickUp, Linear, GitHub Issues, etc.), verbatim. `null` if the field is absent or explicitly `_None yet._`. Don't infer a tracker reference from prose elsewhere in the doc; only the structured field counts. |
   | `impact` | string | ONE fresh sentence (not copied verbatim), under ~160 chars, summarizing who/what is affected and how badly — for the summary table cell. Whenever `statusKind` for a doc changes since the last run (open→fixed especially), rewrite `impact` too — a fixed issue's impact sentence should describe what *was* wrong and that it's resolved (with the fix's tracker key/MR if the doc names one), not still read like an open threat. |
   | `bodyMarkdown` | string | full raw markdown content of the file from the line after the H1 onward, byte-verbatim (preserves headers/tables/code blocks for the detail-drawer renderer) |

   For **more than ~8 docs**, delegate this extraction to a fresh subagent
   (general-purpose) rather than doing it inline — the raw markdown for many
   docs is large and doesn't need to sit in your own context. Have the
   subagent write the result directly to a `known-issues-data.js` file (see
   format below) and validate it before reporting back. For a handful of
   docs, do it inline.

3. **Emit the data file.** Write a JS file containing exactly:

   ```js
   const DASHBOARD_META = { title: "<project or repo name>", subtitle: "<one short line, e.g. repo(s) covered>" };
   const KNOWN_ISSUES = [ { ... }, { ... }, ... ];
   ```

   `DASHBOARD_META` is optional (the dashboard falls back to a generic
   header if absent) but include it — it's what makes the page read as
   "this project's" dashboard rather than a bare template. Use plain
   double-quoted JS string literals for every field (not template literals —
   `bodyMarkdown` contains backticks). Validate before serving:
   `node --check known-issues-data.js`, then a functional check — e.g.
   `node -e "const c=require('fs').readFileSync('known-issues-data.js','utf8'); const a=new Function(c+';return KNOWN_ISSUES;')(); console.log(a.length)"`
   — confirm the count matches the number of docs found in step 1, every
   item has all 10 fields (`tracker` may be `null`), `severityLevel` and
   `statusKind` are within the allowed enums. Also sanity-check field
   *shape*, not just presence: flag (and go re-read the source doc for) any
   `category` over ~40-50 chars — that's the signature of an extraction bug
   that swallowed a neighboring field's text, not a real category (this
   exact bug shipped once — see Workflow C's hazard note).

4. **Assemble the site.** In a scratch/temp working directory (not inside the
   repo), copy `assets/dashboard.html` verbatim to `index.html` alongside the
   generated `known-issues-data.js` — same directory, unmodified filenames
   (the page's `<script src="known-issues-data.js">` expects that exact
   name).

5. **Serve it.** Pick a free local port (check with `lsof -i :<port>`, retry
   on collision), then start a static server detached from any single
   tool-call's lifecycle so it survives — e.g.
   `nohup python3 -m http.server <port> --bind 127.0.0.1 > server.log 2>&1 & disown`
   run from that directory. Verify both `index.html` and
   `known-issues-data.js` return HTTP 200 via `curl`, then report the URL
   (`http://127.0.0.1:<port>/`) to the user.

6. **Wrap-up.** Mention the dashboard is local-only/ephemeral, and offer to
   save a real file into the repo (e.g. `docs/reports/`) or stop the server
   when the user is done with it — mirroring the Visual Companion wrap-up
   convention.

### Notes

- This workflow is read-only against the repo — it never writes into
  `docs/known-issues/`, only into a scratch directory. Nothing here touches
  git.
- If a doc doesn't follow the template (e.g. missing `**Status:**` /
  `**Severity:**` lines), don't skip it — extract what's really there and
  note the deviation honestly in `severityText`/`status` rather than
  fabricating template-shaped values (same spirit as Hard rule 1 above).
- Rerun this workflow any time to refresh the dashboard after new docs are
  shelved — the data file is regenerated from scratch each time, so it's
  always a snapshot of current `docs/known-issues/*.md`, not something that
  needs manual updating.
- **"Update the dashboard" means re-verify every doc, not just the ones
  named.** When the user asks to update/refresh an already-built dashboard —
  with or without naming specific issues — re-run step 2 against *every* file
  in `docs/known-issues/` fresh from disk (`git status --short` +
  `git log --since=<last known run> -- docs/known-issues/` first, to catch
  both committed and uncommitted changes), not just the doc(s) they mentioned
  and not from memory of what a prior run in this conversation already
  extracted. The whole point of a status-tracking dashboard is that the user
  shouldn't have to name each issue that changed — if a fix landed since the
  last run, the dashboard update must surface it unprompted. Report every
  `statusKind` flip found (open→fixed or otherwise) in the summary back to
  the user, even ones nobody asked about by name.
- Don't trust a doc's own prose to already be self-consistent — a doc's
  top-line `**Status:**` can itself lag its own body (e.g. a "Fixed" status
  landed in a later commit than a re-verification section still saying "still
  open"/"not fixed" inline). Extract `statusKind` from the top-line `Status:`
  field specifically (it's the field this project's docs treat as
  authoritative), not from whichever wording appears first in the file.

## Workflow C — Retrofit or bulk-edit existing docs

Use for a *dedicated batch pass* across many docs at once: migrating the
whole corpus to a newer template convention, renaming/repositioning a field
everywhere it appears, or any other mechanical edit driven by a script
rather than by hand, one doc at a time. This is different from Hard rule 8's
"retrofit an old doc on touch" — that's for one doc already being edited for
another reason. This is for touching many docs *because* they need the same
edit.

### The hazard: fields can wrap across multiple lines

`**Status:**`, `**Severity:**`, and any other field can wrap onto multiple
physical lines with no continuation marker — Workflow B's extraction
convention walks forward from a field's `**Label:**` line until it hits a
blank line, another `**field**`, or a `#` heading, and treats everything in
between as that field's value. A script that inserts a new field "right
after field X's line," using only the index of X's *first* line, strands X's
remaining lines below the newly-inserted line — and the next thing to read
the doc (a human, or the same continuation-walking extractor) silently
folds that stranded prose into the new field's value instead.

This happened for real: a Category-field migration across all 55 docs in
this project inserted the new `**Category:**` line right after
`**Severity:**`'s first line in every doc. In the 4 docs where Severity
happened to wrap onto more than one line, the stranded continuation text got
read back as part of Category — and one dashboard render later broke the
whole table's layout, because HTML sizes a column by its widest cell across
every row, and one of those swallowed values ran to 343 characters.

**The rule for every future batch edit:** before inserting a line after any
existing field, walk forward from that field's `**Label:**` line using the
same continuation logic (stop at blank / `**` / `#`) to find its *true* last
line, and insert after that — never after the field's first line alone.
Removing a field works the same way in reverse: delete every line from its
label to its true last line, not just the label line.

### Steps

1. **Isolate in a worktree.** Same discipline as any other repo-mutating
   work in this project — branch off the base branch, qualify every git
   command with the worktree path, verify before committing.
2. **Script the mechanical edit**, applying the multi-line-field rule above
   for every insertion or removal. Reuse already-verified data as the
   source of truth for judgment-call fields where it exists (e.g. a prior
   Workflow B run's extracted `KNOWN_ISSUES`) instead of re-deriving
   severity/category from scratch — avoids introducing fresh classification
   drift during a purely mechanical pass.
3. **Verify structurally before committing** — for every doc touched,
   confirm each edited field's value is shaped like that field expects
   (Category under ~40-50 chars; Status/Severity
   starting with its bracket token), not just that the field is present.
   This is the check that would have caught the incident above before it
   ever reached a dashboard.
4. **Spot-check a diff sample**, not just the aggregate count — a script
   reporting "55 of 55 updated" can still have silently corrupted a handful.
5. **Commit, push, open an MR** — same non-merging rule as any other change
   in this project.
