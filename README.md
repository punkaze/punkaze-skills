# punkaze-skills

A personal collection of [Agent Skills](https://code.claude.com/docs/en/skills) for Claude Code, packaged as an installable plugin.

Currently ships one skill:

| Skill | What it does |
| :---- | :----------- |
| **bruno** | Author, generate, and run [Bruno](https://www.usebruno.com/) `.bru` API collections — with a zero-dependency collection generator and `.bru`/CLI syntax verified against Bruno **3.5.0**. |

## Install

```text
/plugin marketplace add punkaze/punkaze-skills
/plugin install skills@punkaze
```

Then invoke a skill by its namespaced name, e.g.:

```text
/skills:bruno
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

## License

[Apache-2.0](LICENSE). See [NOTICE](NOTICE) for attribution to the prior community
skills that inspired the `bruno` skill.
