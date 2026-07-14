---
name: live-console
description: >-
  Interactive local web console for structured human input the agent reads back
  (no copy-paste). Use when the user asks to "open a live console", spin up an
  interactive/local web page to review or sign off on items, mark up a checklist
  / test cases / options in the browser and have you read their responses, or
  collect pass-fail-skip / ratings / rankings / pick-one choices in a browser
  surface. NOT for static previews or plain HTML pages.
---

# live-console

Spin up a **console**: a zero-dependency local web app, rendered from a
declarative **spec**, that persists every response the user gives to a store on
disk and self-terminates on Submit — so you read their answers back without
copy-paste. The engine (`scripts/console_server.py`) owns all page behavior;
you only author the spec.

## Run loop

1. **Choose the surface.** Start from a **template** — list `templates/` and
   read each file's `_about` line for its purpose — or write a spec from
   scratch. Copy your starting point into the session scratchpad and fill in
   real items.
   *Done when:* a spec file exists in the scratchpad with a `title` and ≥1 item,
   every field has a `type` + `key`, and any referenced images sit beside the
   spec. Anything the schema can't express → raw-HTML escape hatch (see
   `AUTHORING.md`).
2. **Launch (background).** Run, as a background process:
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/live-console/scripts/console_server.py" <spec.json>`
   *Done when:* the printed `url` opened in the browser and you've noted the
   printed `results` file path.
3. **Hand off and wait.** Tell the user the console is open and to click
   **Submit & done** when finished. Do NOT poll. *Done when:* the background
   process **exits** (Submit) — that exit is your wake signal — or the user says
   to check now.
4. **Read and report — exhaustive, visually grouped.** Read the results file.
   Report as a compact table or status-grouped list (✅/❌/⏭) rather than a
   paragraph per item. Account for **every item in the spec**: state each
   item's response, and explicitly flag any left unanswered or marked
   fail/reject, drilling into fails. *Done when:* no spec item is silently
   omitted — each is named as answered (with its value) or flagged
   unanswered/failed.
5. **Clean up.** If the server is still running (the user read early without
   submitting), stop it. *Done when:* no console process running, its port free.

## Field types (detail in `AUTHORING.md`)

`toggle` (pass/fail/skip, approve/reject) · `comment` · `choice` (single/multi) ·
`rating` (stars/number) · `rank` (drag-reorder) · item `visuals` (compare HTML
snippets or image files → pick one + comment each; a single entry doubles as a
plain illustration — a diagram beats a paragraph, see AUTHORING.md).

**Visual-first:** if an item's content is inherently spatial (a flow, a layout,
a before/after, an architecture) — show it, don't describe it. See
AUTHORING.md's "Visual-first authoring."

## Facts

- **Store:** `<spec_stem>.results.json` beside the spec — `{_meta:{done,submittedAt}, responses:{itemId:{key:value,updatedAt}}}`. Auto-saved on every change, so it's readable mid-session; `_meta.done` flips to `true` only on Submit.
- **Notify:** the server runs in the background and **exits on Submit** — no polling; the exit is the signal to read the store.
- **Defaults:** binds `127.0.0.1` only, OS-assigned free port, auto-opens the browser (macOS), theme-aware, ephemeral scratchpad store. Flags: `--port N`, `--no-open`, `--results PATH`.
- **Schema + raw-HTML escape hatch (`Console.set/get/submit`):** see [`AUTHORING.md`](AUTHORING.md).
