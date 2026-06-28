---
name: bruno
description: >-
  Work with Bruno, the open-source Git-friendly API client, and its CLI (bru).
  Use when a user asks to create or generate .bru requests/collections, scaffold
  a Bruno collection from API routes or an OpenAPI spec, write Bruno tests or
  scripts, manage environments/variables, or run collections in CI with `bru run`.
metadata:
  author: piyawat
  version: "1.0.0"
  tags: ["api-client", "bruno", "bru", "http", "testing", "ci"]
---

# Bruno — Author, Generate, and Run .bru Collections

## When to use

- Create or edit `.bru` requests/collections by hand.
- Generate a whole collection from a codebase's routes or an OpenAPI spec.
- Write tests/scripts, manage environments, run collections via `bru run` (CI).

Requires the Bruno CLI: `npm install -g @usebruno/cli` (this skill targets
**bru 3.5.0**). Verify with `bru --version`.

## Generating a collection — two paths

**Path A — an OpenAPI/Swagger spec exists (preferred).** Use the native CLI:
```bash
bru import openapi -s <spec.yaml|url> -o <out-dir> -n "My API" -g path
```
Look for a spec first: `openapi.yaml`, `swagger.json`, an Elysia/Swagger
endpoint, NestJS `@nestjs/swagger` output, etc. `-g path|tags` controls grouping.

**Path B — no spec.** Read the codebase, produce a **routes manifest** that
conforms to `references/routes.schema.json`, then run the bundled generator:
```bash
node scripts/generate-bruno.mjs --manifest routes.json --out ./api-collection
```
Flags: `--force` (overwrite existing files), `--dry-run` (preview, write nothing).

Do **not** write a per-framework regex route scanner — extract routes by reading
the code, then hand the manifest to the generator.

### Manifest shape (see references/routes.schema.json)

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
Route `auth`: `true` → `auth: inherit`, `false` → `none`, or an explicit
`"bearer"|"basic"|"inherit"|"none"`. Use `:param` in `path` for path params.
`script: "token-capture"` adds a post-response script that captures
`res.body.token` into a runtime variable. `tests` accepts `status-200`,
`status-201`, `status-2xx`.

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
  single run. **Use this for chaining secrets like auth tokens between requests** —
  the value stays in memory and is never written to disk.
- `bru.setEnvVar(key, val)` / `bru.getEnvVar(key)` — environment variable.
  ⚠️ **In Bruno v4, `setEnvVar` writes to the environment file on disk** (and even
  in 3.5.0 with `{ persist: true }`). A secret persisted this way can be committed
  to Git. Use `setEnvVar` only for non-secret config you intend to persist; prefer
  `setVar` for tokens/secrets.
- Response: `res.status`, `res.body`, `res.responseTime`.

## Running with `bru run` (CLI 3.5.0)

Run from the **collection root** (the directory containing `bruno.json`):
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
Note: `bru run` errors with "You can run only at the root of a collection" if the
current directory is not the collection root.

**Sandbox (v3 default changed):** the CLI defaults to **`--sandbox safe`** — no
filesystem access, no `require()` of external npm packages. Only pass
`--sandbox developer` when you trust the collection and genuinely need fs/exec/
npm in scripts; it is dangerous with untrusted collections.

**Secrets:** prefer `--env-file` or `--env-var KEY=$SHELL_VAR`; never paste a live
secret literal on the command line (it leaks into shell history).
