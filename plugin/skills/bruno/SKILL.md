---
name: bruno
description: >-
  Bruno, the Git-friendly API client, and its CLI (bru). Use when authoring or
  editing .bru requests/collections, generating a collection from an OpenAPI
  spec or a codebase's routes, writing Bruno tests or scripts, managing
  environments and secrets, or running collections with `bru run` (local or CI).
metadata:
  author: piyawat
  version: "1.2.0"
  tags: ["api-client", "bruno", "bru", "http", "testing", "ci"]
---

# Bruno — Author, Generate, and Run .bru Collections

Requires the Bruno CLI: `npm install -g @usebruno/cli`. Everything below is
verified against **bru 3.5.0** (`bru --version`).

## Generating a collection — two paths

**Path A — an OpenAPI/Swagger spec exists (preferred).** Look for one first:
`openapi.yaml`, `swagger.json`, a framework's swagger endpoint (Elysia,
NestJS `@nestjs/swagger`, etc.). Then:

```bash
bru import openapi -s <spec.yaml|url> -o <out-dir> -n "My API" --collection-format bru -g path
```

`--collection-format bru` is required — the CLI default (`opencollection`)
emits `.yml` files, not a `.bru` collection. `-g` picks folder grouping: `path`
(by URL structure, usually what you want) or `tags` (by OpenAPI tags, the CLI
default). **Done when** `<out-dir>` contains `bruno.json` and `.bru` files; an
`opencollection.yml` there means the format flag was dropped.

**Path B — no spec.** Read the codebase and write a **routes manifest** (shape
below), then run the bundled generator:

```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/bruno/scripts/generate-bruno.mjs" --manifest routes.json --out ./api-collection
```

Flags: `--force` (overwrite existing files), `--dry-run` (preview, write
nothing). Extract routes by reading the code — do **not** write a
per-framework regex route scanner. **Done when** the generator reports
`wrote N file(s)` and, with the API running, `bru run . -r --env <env>` from
the output dir executes every request.

### Routes manifest

Schema: `${CLAUDE_PLUGIN_ROOT}/skills/bruno/references/routes.schema.json` —
full example: `${CLAUDE_PLUGIN_ROOT}/skills/bruno/references/sample-manifest.json`.

```json
{
  "name": "My API",
  "baseUrl": "http://localhost:3000",
  "auth": { "type": "bearer" },
  "environments": [{ "name": "dev", "baseUrl": "http://localhost:3000", "secretVars": ["authToken"] }],
  "routes": [
    { "method": "POST", "path": "/auth/login", "name": "Login", "body": {"email":"","password":""},
      "auth": false, "script": "token-capture", "tests": ["status-2xx"] },
    { "method": "GET", "path": "/users/:id", "name": "Get User", "auth": true, "tests": ["status-200"] }
  ]
}
```

- Manifest-level `auth.type` becomes collection-level auth in `collection.bru`;
  routes with `auth: true` inherit it.
- Route `auth`: `true` → `auth: inherit`, `false` → `none`, or an explicit
  `"bearer"|"basic"|"inherit"|"none"` per-request override.
- Use `:param` in `path` for path params.
- `script: "token-capture"` adds a post-response script that captures
  `res.body.token` into the runtime variable `authToken`.
- `tests` accepts `status-200`, `status-201`, `status-2xx`.

## .bru syntax (verified against Bruno 3.5.0)

```bru
meta {
  name: Get User
  type: http
  seq: 1
  tags: [smoke]
}

get {
  url: {{baseUrl}}/users/:id
  body: none
  auth: inherit
}

params:path {
  id: 1
}

params:query {
  expand: profile
}

headers {
  Accept: application/json
}

body:json {
  {
    "name": "John"
  }
}

script:post-response {
  if (res.status >= 200 && res.status < 300 && res.body && res.body.token) {
    bru.setVar("authToken", res.body.token);
  }
}

tests {
  test("status is 200", function() {
    expect(res.status).to.equal(200);
  });
}

docs {
  Retrieve a single user by id.
}
```

**Critical syntax rules (these were wrong in other community skills):**
- Query params use **`params:query { }`** — NOT legacy `query { }`.
- Path params: keep **`:param` in the URL** and add a **`params:path { }`** block —
  do NOT substitute `{{param}}`.
- Child requests should use **`auth: inherit`** to reuse collection/folder auth;
  only emit `auth:bearer { token }` / `auth:basic { ... }` for an explicit
  per-request override.

### Collection-level auth — collection.bru

`auth: inherit` resolves against `collection.bru` at the collection root (or a
folder's `folder.bru`). **Without it, "inherited" requests send no auth at all:**

```bru
meta {
  name: My API
}

auth {
  mode: bearer
}

auth:bearer {
  token: {{authToken}}
}
```

## Response examples (native `example { }` block)

Bruno's `.bru` format has a native, GUI-recognized block for saved example
responses — distinct from free-text `docs { }` prose. Verified against the
actual `@usebruno/lang` v2 parser (`bruToJsonV2`), not just written from memory:

```bru
example {
  name: Successful deletion
  description: Anonymizes the account and returns { deleted: true }

  request: {
    url: {{baseUrl}}/auth/me
    method: delete
    mode: none
  }

  response: {
    status: {
      code: 200
      text: OK
    }

    body: {
      type: json
      content: '''
        {
          "success": true,
          "data": {
            "deleted": true
          }
        }
      '''
    }
  }
}
```

A file can hold multiple `example { }` blocks — one per distinct response case
(success, a validation error, a conflict, etc.), each with its own `name`.
`request` mirrors the top-level method block's shape (`url`, `method`,
`mode`/`body:json` for a request body); `response.body.content` is a multiline
string (`'''…'''`) holding the literal JSON text.

**Workflow rule:** whenever creating or editing an endpoint's `.bru` file,
always add or update its `example { }` block(s) — don't leave this for a
separate pass. A plausible, hand-written example (matching the route's actual
response shape) is fine by default. If getting a REAL captured response would
require actually calling the live endpoint (`bru run`, curl against a running
server, etc.), ask the user before doing that — don't invoke a live endpoint
unprompted just to harvest a response for documentation.

When a live check against the endpoint already happened this session (an e2e
verification pass, manual testing, etc.) or the user explicitly asks for real
captured responses, use the actual response instead of a hand-written one —
real evidence beats a guess, and it's already sitting there. If that same
verification pass cheaply exercised more than one distinct case (a boundary
flag flipping true/false, an empty vs. populated result), capture each as its
own named `example { }` block — don't invent extra live calls beyond what real
testing already produced just to fill out cases. A large real response (a long
array, a deeply nested payload) is still worth trimming to one or two
representative elements for readability — note the trim in `description`
(e.g. "trimmed to 1 of 5 records"), and never edit the values themselves.

## Environments

```bru
vars {
  baseUrl: http://localhost:3000
}
vars:secret [
  authToken
]
```
Secret variable **names** go in `vars:secret [ ]`; their **values are never
written to disk** — set them at runtime or via the GUI. Bruno also supports typed
vars (`@number`, `@boolean`, `@object`) and multiline values with `'''…'''`.

## Variables in scripts

- `bru.setVar(key, val)` / `bru.getVar(key)` — runtime/in-memory, scoped to a
  single run, never written to disk. **Use this for chaining secrets like auth
  tokens between requests.**
- `bru.setEnvVar(key, val)` / `bru.getEnvVar(key)` — environment variable.
  The Bruno GUI can save environment edits into the environment file — a secret
  set this way can end up committed to Git. Use `setEnvVar` only for non-secret
  config; prefer `setVar` for tokens.
- Response: `res.status`, `res.body`, `res.responseTime`.

## Running with `bru run` (CLI 3.5.0)

Run from the **collection root** (the directory containing `bruno.json`) —
anywhere else fails with "You can run only at the root of a collection".

```bash
bru run . -r --env dev                            # run the whole collection recursively
bru run folder -r --env dev                       # run a folder recursively
bru run request.bru --env-file env.bru            # explicit env file
bru run . -r --env dev --env-var token=$TOK       # override one var from shell (no secret in history)
bru run . -r --reporter-junit results.xml --reporter-html report.html
bru run . -r --bail --tests-only                  # CI: stop on first failure, only requests with tests
bru run . -r --csv-file-path data.csv --parallel  # data-driven, parallel iterations
bru run . -r --tags smoke --exclude-tags wip      # filter by meta tags
```

**Sandbox (v3 default changed):** the CLI defaults to **`--sandbox safe`** — no
filesystem access, no `require()` of external npm packages. Only pass
`--sandbox developer` when you trust the collection and genuinely need fs/exec/
npm in scripts; it is dangerous with untrusted collections.

**Secrets:** prefer `--env-file` or `--env-var KEY=$SHELL_VAR`; never paste a live
secret literal on the command line (it leaks into shell history).
