# punkaze-skills

A personal collection of [Agent Skills](https://code.claude.com/docs/en/skills) for Claude Code, packaged as an installable plugin.

Currently ships two skills:

| Skill | What it does |
| :---- | :----------- |
| **bruno** | Author, generate, and run [Bruno](https://www.usebruno.com/) `.bru` API collections — with a zero-dependency collection generator and `.bru`/CLI syntax verified against Bruno **3.5.0**. |
| **hetzner-server-provision** | Provision a [Hetzner Cloud](https://www.hetzner.com/cloud) server end-to-end via the `hcloud` CLI — pick type/location, create a firewall (SSH locked to your IP), boot the server, and install Docker + Nginx + Certbot on a hardened, key-only box. |

## Install

```text
/plugin marketplace add punkaze/punkaze-skills
/plugin install skills@punkaze
```

Then invoke a skill by its namespaced name, e.g.:

```text
/skills:bruno
/skills:hetzner-server-provision
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

## License

[Apache-2.0](LICENSE). See [NOTICE](NOTICE) for attribution to the prior community
skills that inspired the `bruno` skill.
