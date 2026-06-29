# punkaze-skills

A personal collection of [Agent Skills](https://code.claude.com/docs/en/skills) for Claude Code, packaged as an installable plugin.

Currently ships four skills:

| Skill | What it does |
| :---- | :----------- |
| **bruno** | Author, generate, and run [Bruno](https://www.usebruno.com/) `.bru` API collections — with a zero-dependency collection generator and `.bru`/CLI syntax verified against Bruno **3.5.0**. |
| **hetzner-server-provision** | Provision a [Hetzner Cloud](https://www.hetzner.com/cloud) server end-to-end via the `hcloud` CLI — pick type/location, create a firewall (SSH locked to your IP), boot the server, and install Docker + Nginx + Certbot on a hardened, key-only box. |
| **worktree-setup** | Spin up isolated git worktree(s) for a task on any project — config-driven, deciding single vs dual/multi-repo scope (identical branch names on coupled repos), cutting from the right base branch, copying env files, and running the right install command. |
| **free-disk-space** | Find what's safe to delete to reclaim disk space on macOS/Linux and hand you copy-paste cleanup commands, sorted by reclaimable size with a per-row safety flag. Read-only by default — it investigates and reports, never deleting anything on its own. |

## Install

```text
/plugin marketplace add punkaze/punkaze-skills
/plugin install skills@punkaze
```

Then invoke a skill by its namespaced name, e.g.:

```text
/skills:bruno
/skills:hetzner-server-provision
/skills:worktree-setup
/skills:free-disk-space
```

(Claude also invokes skills automatically when a task matches their description.)

### Try it without installing

```bash
git clone https://github.com/punkaze/punkaze-skills
claude --plugin-dir ./punkaze-skills/plugin
```

## The `bruno` skill

Helps you work with Bruno, the open-source, Git-friendly API client, and its CLI (`bru`):

- **Generate collections** two ways — `bru import openapi` when a spec exists, or a bundled zero-dependency Node generator (`generate-bruno.mjs`) fed by a routes manifest you describe.
- **Correct `.bru` syntax** verified against the official Bruno repo: `params:query`, `:param` + `params:path`, `auth: inherit`, `vars:secret`, `body:json`, `tests`, `docs`.
- **Safe by default** — captured tokens use `bru.setVar` (runtime-only, never written to disk); documents the CLI `--sandbox safe` default.
- **CI-ready** `bru run` guidance (JUnit/HTML reporters, `--bail`, `--tests-only`, tags).

Skill contents live in [`plugin/skills/bruno/`](plugin/skills/bruno):

```
plugin/skills/bruno/
├── SKILL.md
├── scripts/
│   ├── generate-bruno.mjs        # the generator (zero deps)
│   └── generate-bruno.test.mjs   # node:test suite
└── references/
    ├── routes.schema.json        # manifest contract
    ├── sample-manifest.json
    └── examples/                 # verified .bru output samples
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
    └── scan.sh   # read-only OS-aware scanner (macOS/Linux), structured output
```

### Run the scanner

```bash
# defaults to scanning $HOME; pass a narrower root for a faster project scan
plugin/skills/free-disk-space/scripts/scan.sh ~/projects
```

## License

[Apache-2.0](LICENSE). See [NOTICE](NOTICE) for attribution to the prior community
skills that inspired the `bruno` skill.
