# Authoring a live-console spec

A spec is a JSON file. `console_server.py` renders it, persists responses to a
sibling `<spec_stem>.results.json`, and self-terminates on Submit. Read this
only when writing a spec by hand or reaching for the raw-HTML escape hatch — the
templates in `templates/` cover the common shapes.

## Top level

```jsonc
{
  "_about": "optional one-line purpose; ignored by the engine, read when listing templates",
  "title": "string (header + browser title)",
  "instructions": "optional blurb shown under the header",
  "items": [ /* Item, … */ ],
  "rawHtml": "optional — replaces the whole items area (see Escape hatch)"
}
```

## Item

```jsonc
{
  "id": "stable-key",           // required; becomes the responses key
  "title": "string",
  "body": "plain text; newlines preserved",
  "fields": [ /* Field, … */ ], // response widgets, in order
  "visuals": [ /* Visual, … */ ],// optional; renders a compare-and-pick grid
  "visualLabel": "override the visuals section label",
  "rawHtml": "optional — replaces this item's body (see Escape hatch)"
}
```

## Fields → stored value

| `type`   | Extra keys                          | Stored under `responses[itemId][key]` |
|----------|-------------------------------------|----------------------------------------|
| `toggle` | `options: string[]`                 | chosen string (click again clears). `pass`/`fail`/`skip`, `approve`/`reject`, `yes`/`no`/`na` get color coding; key `status` also colors the item's left border and feeds the header tally. |
| `comment`| `placeholder?`                      | free text |
| `choice` | `options: (string \| {value,label})[]`, `multiple?: bool` | single → string; `multiple:true` → string[] |
| `rating` | `min?=1`, `max?=5`, `style?: "stars" \| "number"` | number |
| `rank`   | `options: (string \| {value,label})[]` | ordered array of `value`s (drag to reorder, or ↑/↓) |

All fields take an optional `label`. `key` must be unique within an item.

## Visuals (compare + pick + comment)

Each item with a `visuals` array renders a card grid. Each visual is:

```jsonc
{ "id": "a", "label": "Option A", "html": "<inline markup>" }
// or
{ "id": "c", "label": "From screenshot", "image": "assets/opt-c.png" }
```

- `html` is injected inline; `image` is a path **relative to the spec file's
  directory** (served over `/asset/…`; paths outside that directory are refused).
  Put images beside the spec (e.g. an `assets/` subfolder).
- Stored: `responses[itemId].pick` = chosen visual `id`; `responses[itemId].notes`
  = `{ visualId: comment }`. No item-level `fields` are needed for a visual item,
  but you may add more.

## Visual-first authoring

Default to showing, not describing, whenever content is spatial: a layout, a
flow, a before/after, an architecture, a UI mock. A diagram reads in one
glance; the same thing in `body` prose takes a paragraph and still leaves room
to misread it.

**A single-entry `visuals` array is a plain illustration, not only a compare
grid.** The "Choose" chip still renders but is optional — nothing forces a
click, and Submit doesn't require one. Override `visualLabel` so it reads as
reference material, not a decision:

```jsonc
{
  "id": "flow-check",
  "title": "Does this automation flow look right?",
  "visualLabel": "Reference diagram",
  "visuals": [
    { "id": "flow", "label": "Automation flow", "image": "assets/flow.png" }
  ],
  "fields": [
    { "type": "toggle", "key": "status", "options": ["pass", "fail", "skip"] },
    { "type": "comment", "key": "note", "placeholder": "What's wrong, if anything…" }
  ]
}
```

No image file on hand? Hand-author the diagram as inline boxes/arrows SVG or
HTML in `visuals[].html` — same rendering path as the compare grid, no new
dependency. Reserve `body` for what's genuinely textual (steps, expected
values, edge cases); pair it with a diagram rather than asking prose to carry
spatial information alone. `body` and `visuals` freely coexist on one item —
use both when there's real text (steps, thresholds) alongside the picture, use
`visuals` alone when the diagram is self-explanatory.

## Escape hatch (raw HTML)

Set `rawHtml` on an item (replaces its body) or on the spec (replaces all items).
Your markup drives the store through the global JS API — the save/Submit
plumbing still works:

```js
Console.get(itemId, key)        // current saved value
Console.set(itemId, key, value) // update + debounced auto-save (null/"" clears)
Console.submit()                // same as the Submit button (persist + exit)
```

Use real `id`s so the agent can read the values back out of `responses`.

## Store shape (what the agent reads)

```jsonc
{
  "_meta": { "done": true, "submittedAt": "ISO-8601" },
  "responses": {
    "TC-01": { "status": "pass", "note": "…", "updatedAt": "…" }
  }
}
```

`_meta.done` flips to `true` only on Submit. Every change auto-saves, so the file
is readable mid-session too (before Submit `done` is `false`).
