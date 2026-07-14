# skills

A personal collection of [Agent Skills](https://code.claude.com/docs/en/skills) for Claude Code, packaged as an installable plugin.

Currently ships six skills:

| Skill | What it does |
| :---- | :----------- |
| **bruno** | Author, generate, and run [Bruno](https://www.usebruno.com/) `.bru` API collections — with a zero-dependency collection generator and `.bru`/CLI syntax verified against Bruno **3.5.0**. |
| **hetzner-server-provision** | Provision a [Hetzner Cloud](https://www.hetzner.com/cloud) server end-to-end via the `hcloud` CLI — pick type/location, create a firewall (SSH locked to your IP), boot the server, and install Docker + Nginx + Certbot on a hardened, key-only box. |
| **worktree-setup** | Spin up isolated git worktree(s) for a task on any project — config-driven, deciding single vs dual/multi-repo scope (identical branch names on coupled repos), cutting from the right base branch, copying env files, and running the right install command. |
| **free-disk-space** | Find what's safe to delete to reclaim disk space on macOS/Linux and hand you copy-paste cleanup commands, sorted by reclaimable size with a per-row safety flag. Read-only by default — it investigates and reports, never deleting anything on its own. |
| **live-console** | Spin up a zero-dependency local web console from a declarative JSON spec — pass/fail/skip, ratings, rankings, pick-one comparisons, and diagram/screenshot review — that persists every response and self-terminates on Submit so you read answers back without copy-paste. |
| **tracking-test-cases** | A persistent, branch-scoped pre-PR manual QA checklist — diffs each run against the last one, survives worktree deletion after merge, and hands results back the moment you record a round. |

## Install

```text
/plugin marketplace add punkaze/skills
/plugin install skills@punkaze
```

Then invoke a skill by its namespaced name, e.g.:

```text
/skills:bruno
/skills:hetzner-server-provision
/skills:worktree-setup
/skills:free-disk-space
/skills:live-console
/skills:tracking-test-cases
```

(Claude also invokes skills automatically when a task matches their description.)

### Install a single skill

The plugin installs all skills together. To install just one, copy its folder into
`~/.claude/skills/` — swap `bruno` for any skill name from the table above:

```bash
mkdir -p ~/.claude/skills
curl -sL https://github.com/punkaze/skills/archive/main.tar.gz \
  | tar -xz -C ~/.claude/skills --strip-components=3 skills-main/plugin/skills/bruno
```

Skills installed this way are invoked without the plugin namespace, e.g. `/bruno`.

### Try it without installing

```bash
git clone https://github.com/punkaze/skills
claude --plugin-dir ./skills/plugin
```

## The `bruno` skill

Helps you work with [Bruno](https://www.usebruno.com/), the open-source, Git-friendly API client, and its CLI (`bru`). Every command and syntax rule in the skill is verified against a real **bru 3.5.0** install.

What it can do:

- **Author and edit `.bru` files** — requests, headers, `body:json`, post-response scripts, `tests`, and `docs` blocks, with the modern syntax agents usually get wrong: `params:query` (not legacy `query { }`), `:param` in the URL + `params:path` (not `{{param}}` substitution), and `auth: inherit` backed by collection-level auth in `collection.bru`.
- **Generate a collection from an OpenAPI/Swagger spec** — `bru import openapi … --collection-format bru` (the flag matters: the CLI default emits opencollection `.yml` files, not a `.bru` collection).
- **Generate a collection straight from code** — no spec needed. Describe the API as a routes manifest ([`routes.schema.json`](plugin/skills/bruno/references/routes.schema.json)); the bundled zero-dependency generator emits `bruno.json`, `collection.bru` with collection-level auth, per-resource folders, requests, environments, a login token-capture script, and status-code test presets.
- **Write test and script blocks** — `test()`/`expect()` assertions, post-response scripts, and chaining values between requests (e.g. capture a login token, reuse it on later requests).
- **Manage environments and secrets safely** — environment `.bru` files, `vars:secret` (names on disk, never values), `bru.setVar` for runtime-only tokens, and `--env-var KEY=$SHELL_VAR` so secrets stay out of shell history.
- **Run collections locally or in CI** — `bru run` recipes: recursive runs, env selection/overrides, JUnit/HTML reporters, `--bail --tests-only` for CI gates, tag filtering, CSV/JSON data-driven iterations, and the `--sandbox safe` default explained.

The generated auth chain is tested end-to-end against a live server: login → `bru.setVar("authToken")` → `{{authToken}}` in `collection.bru` → `auth: inherit` on child requests.

Skill contents live in [`plugin/skills/bruno/`](plugin/skills/bruno):

```
plugin/skills/bruno/
├── SKILL.md
├── scripts/
│   ├── generate-bruno.mjs        # the generator (zero deps)
│   └── generate-bruno.test.mjs   # node:test suite
└── references/
    ├── routes.schema.json        # manifest contract
    └── sample-manifest.json      # full manifest example
```

### Run the generator

```bash
node plugin/skills/bruno/scripts/generate-bruno.mjs \
  --manifest plugin/skills/bruno/references/sample-manifest.json \
  --out ./api-collection
```

### Run the tests

```bash
node --test plugin/skills/bruno/scripts/generate-bruno.test.mjs
```

## The `hetzner-server-provision` skill

Provisions a production-ready [Hetzner Cloud](https://www.hetzner.com/cloud) server end-to-end using the official [`hcloud`](https://github.com/hetznercloud/cli) CLI:

- **One-command provision** — uploads your SSH key (deduped by fingerprint, not just name), creates a firewall, boots the server, and waits for it to be running. Idempotent and safe to re-run.
- **Secure by default** — port 22 is locked to your detected public IP (override with `--ssh-source`); 80/443/ICMP stay public. The server is then hardened to key-only SSH with automatic security updates, and host keys are pinned on first connect (`accept-new`).
- **Capacity-aware** — falls back across EU locations (`hel1 → nbg1 → fsn1`) when one is full.
- **Right-sized** — `list-server-types.sh` shows live per-location pricing so you pick the cheapest fit.

Skill contents live in [`plugin/skills/hetzner-server-provision/`](plugin/skills/hetzner-server-provision):

```
plugin/skills/hetzner-server-provision/
├── SKILL.md
└── scripts/
    ├── list-server-types.sh   # live pricing, --location/--arch filters
    ├── provision.sh           # key + firewall + server, idempotent
    └── bootstrap-remote.sh    # Docker/Nginx/Certbot + SSH hardening + auto-updates
```

Requires the `hcloud` CLI (`brew install hcloud`) and a Hetzner API token via `HCLOUD_TOKEN` or an `hcloud context`.

```bash
# pick a type, then provision (SSH auto-locked to your IP)
plugin/skills/hetzner-server-provision/scripts/list-server-types.sh --location hel1
plugin/skills/hetzner-server-provision/scripts/provision.sh \
  --name my-app-dev --type cx23 --ssh-key-file ~/.ssh/id_ed25519.pub
```

## The `worktree-setup` skill

Spin up isolated [git worktree(s)](https://git-scm.com/docs/git-worktree) for a task on **any** project, driven by a small per-project config:

- **Decides scope** — single vs dual/multi-repo. When a change touches a declared shared surface (e.g. an API contract or shared schema across sibling repos), it creates a worktree in each coupled repo with the **same branch name**; otherwise just one.
- **Config-driven** — a zero-dependency Node resolver picks the right config for the current repo: an in-repo `.worktree.json` (single-repo projects) or a registry under `${CLAUDE_PLUGIN_DATA}/projects/` (multi-repo; persists across plugin updates, override with `WORKTREE_REGISTRY_DIR`). See [`projects/example.json`](plugin/skills/worktree-setup/projects/example.json) for the format.
- **Safe mechanics** — cuts from `origin/<base>` so the main checkout's branch is never touched, unsets upstream, copies the configured (gitignored) env files, and runs the configured install command.
- **Init flow** — in an unconfigured repo, it detects sibling repos, base branch, and install command, then writes a config after you confirm.

Skill contents live in [`plugin/skills/worktree-setup/`](plugin/skills/worktree-setup):

```
plugin/skills/worktree-setup/
├── SKILL.md
├── scripts/
│   ├── new-worktree.sh         # config-driven engine (one repo per call)
│   ├── resolve-config.mjs      # resolve / repo / guard (zero deps)
│   ├── resolve-config.test.mjs # node:test
│   └── engine-smoke.test.sh    # real worktree against a temp origin
├── references/
│   └── worktree.schema.json    # config contract
└── projects/
    └── example.json            # sanitized sample config
```

### Run the tests

```bash
node --test plugin/skills/worktree-setup/scripts/resolve-config.test.mjs
plugin/skills/worktree-setup/scripts/engine-smoke.test.sh
```

## The `free-disk-space` skill

Find what's safe to delete to reclaim disk space on **macOS or Linux**, and get
copy-paste cleanup commands — without an agent deleting anything for you:

- **Read-only investigation** — an OS-detecting scanner (`scan.sh`) emits a
  structured report: free space (from the right volume), the biggest reclaimable
  locations, umbrella cache totals, and project `node_modules` / stale worktrees.
- **One flat report table** — `What · Path · Reclaim · Impact · How to clear ·
  Safety`, sorted by reclaimable size, with a 🟢/🟡/🟠 safety flag per row.
- **Accurate sizes** — each row is measured at the exact path its command clears;
  partial cleaners (prune/uninstall) are marked, and umbrella totals are kept
  separate so nothing is double-counted.
- **Never deletes on its own** — the skill investigates and hands over commands.
  If asked to delete, it explains why an agent shouldn't, and only ever proceeds
  through an explicit per-step permission gate that holds even in auto-accept mode.

Skill contents live in [`plugin/skills/free-disk-space/`](plugin/skills/free-disk-space):

```
plugin/skills/free-disk-space/
├── SKILL.md
└── scripts/
    ├── scan.sh             # read-only OS-aware scanner (macOS/Linux), structured output
    └── scan-smoke.test.sh  # hermetic smoke test (fakes $HOME; asserts the report contract)
```

### Run the scanner

```bash
# defaults to scanning $HOME; pass a narrower root for a faster project scan
plugin/skills/free-disk-space/scripts/scan.sh ~/projects
```

### Run the test

```bash
plugin/skills/free-disk-space/scripts/scan-smoke.test.sh
```

## The `live-console` skill

Spin up a **console** — a stdlib-only local web app rendered from a declarative
JSON spec — for structured human review that the agent reads back without
copy-paste:

- **Zero dependencies** — pure Python stdlib `http.server`; binds `127.0.0.1`
  only, auto-opens the browser, self-terminates the moment the human clicks
  **Submit**, so the agent never has to poll.
- **Five field types** — `toggle` (pass/fail/skip, approve/reject), `comment`,
  `choice` (single/multi), `rating` (stars/number), `rank` (drag-to-reorder).
- **Visual-first** — an item's `visuals[]` renders a compare-and-pick grid of
  images/HTML, or — a single entry — a plain contextual diagram/screenshot.
  A picture beats a paragraph for anything spatial: a flow, a layout, an
  architecture.
- **Raw-HTML escape hatch** — anything the schema can't express drives the
  same auto-saving store directly through `Console.get/set/submit`.
- **Auto-saving store** — every change persists to `<spec>.results.json`
  immediately; `_meta.done` flips to `true` only on Submit, so the file is
  safely readable mid-session too.

Skill contents live in [`plugin/skills/live-console/`](plugin/skills/live-console):

```
plugin/skills/live-console/
├── SKILL.md
├── AUTHORING.md                     # full spec schema + visual-first authoring guide
├── scripts/
│   ├── console_server.py            # the engine (stdlib only, no deps)
│   └── console-server-smoke.test.sh
└── templates/
    ├── test-tracker.json
    ├── approval-signoff.json
    ├── ranked-list.json
    ├── ab-visual-pick.json
    └── diagram-review.json
```

### Run the test

```bash
plugin/skills/live-console/scripts/console-server-smoke.test.sh
```

## The `tracking-test-cases` skill

A pre-PR manual QA checklist scoped to the current git branch:

- **Survives worktree deletion** — stored globally at
  `~/.claude/test-tracking/<repo>/<branch>/`, outside any repo checkout, so
  results are still there after the branch's worktree is removed post-merge.
- **Diffs against the last run** — every case shows its own "Last run: X"
  status inline, so re-running after a fix makes what changed obvious.
- **Two footer actions, both hand results back** — **Submit** (highlighted)
  records the round and reopens a fresh console automatically, for testing
  across several rounds in one sitting; **Done & close** (confirm dialog)
  records the same way and ends the session. Either one exits the server,
  which is the agent's signal to read the new run back — no polling.
- **Full reset every round** — status, notes, and attachments all start
  blank each round, so a case can't silently coast on a stale "pass"; the
  complete record from every round lives forever in its own `runs/` snapshot.
- **Attachments via drag-and-drop** — drop a log/screenshot/JSON file onto a
  note field and it's embedded directly (text gets a truncated preview,
  images a thumbnail, anything else a filename card) — browsers don't expose
  a dropped file's real path, so embedding the content is the honest option.

Skill contents live in [`plugin/skills/tracking-test-cases/`](plugin/skills/tracking-test-cases):

```
plugin/skills/tracking-test-cases/
├── SKILL.md
└── scripts/
    ├── base_branch.py               # resolve repo/branch identity + base branch
    ├── tracker_server.py            # the engine (stdlib only, no deps)
    ├── base-branch-smoke.test.py
    └── tracker-server-smoke.test.sh
```

### Run the tests

```bash
python3 plugin/skills/tracking-test-cases/scripts/base-branch-smoke.test.py
plugin/skills/tracking-test-cases/scripts/tracker-server-smoke.test.sh
```

## License

[Apache-2.0](LICENSE). See [NOTICE](NOTICE) for attribution to the prior community
skills that inspired the `bruno` skill.
