#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));

// Registry lookup precedence, so the same code works as a local standalone
// skill AND as an installed plugin (whose own dir is wiped on update):
//   1. WORKTREE_REGISTRY_DIR        — explicit override
//   2. $CLAUDE_PLUGIN_DATA/projects — persistent plugin data (survives updates)
//   3. <script>/../projects         — bundled/local fallback
export function registryDir(env = process.env) {
  if (env.WORKTREE_REGISTRY_DIR) return env.WORKTREE_REGISTRY_DIR;
  if (env.CLAUDE_PLUGIN_DATA) return join(env.CLAUDE_PLUGIN_DATA, "projects");
  return join(SCRIPT_DIR, "..", "projects");
}

// ---------- pure ----------

export function originMatches(origin, remoteMatch) {
  if (!origin || remoteMatch == null) return false;
  const list = Array.isArray(remoteMatch) ? remoteMatch : [remoteMatch];
  return list.some((m) => m && origin.includes(m));
}

export function loadRegistry(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => {
      const path = join(dir, f);
      return { path, config: JSON.parse(readFileSync(path, "utf8")) };
    });
}

export function resolve({ topLevel, origin, registry, hasInRepo }) {
  if (topLevel && hasInRepo) {
    return { status: "in-repo", configPath: join(topLevel, ".worktree.json") };
  }
  const matches = registry.filter((e) => originMatches(origin, e.config.remoteMatch));
  if (matches.length === 0) return { status: "none" };
  if (matches.length > 1) return { status: "ambiguous", candidates: matches.map((m) => m.path) };
  return { status: "registry", configPath: matches[0].path, project: matches[0].config.project };
}

export function repoFields(config, key) {
  const repo = (config.repos || []).find((r) => r.key === key);
  if (!repo) return null;
  return {
    dir: repo.dir,
    install: repo.install || "",
    baseBranch: repo.baseBranch || config.baseBranch || "",
    envFiles: repo.envFiles || [],
    parentHint: config.parentHint || "",
  };
}

// ---------- CLI ----------

function sq(v) {
  return "'" + String(v).replace(/'/g, "'\\''") + "'";
}

function gitOut(args, cwd) {
  try {
    return execSync(`git ${args}`, { cwd, stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return "";
  }
}

function parseOpts(argv) {
  const o = {};
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--config") o.config = argv[++i];
    else if (a === "--repo") o.repo = argv[++i];
    else if (a === "--origin") o.origin = argv[++i];
    else if (a === "--cwd") o.cwd = argv[++i];
  }
  return o;
}

function main(argv) {
  const cmd = argv[0];
  const o = parseOpts(argv);

  if (cmd === "resolve") {
    const cwd = o.cwd || process.cwd();
    const topLevel = gitOut("rev-parse --show-toplevel", cwd);
    const origin = gitOut("remote get-url origin", cwd);
    const hasInRepo = topLevel ? existsSync(join(topLevel, ".worktree.json")) : false;
    const out = resolve({ topLevel, origin, registry: loadRegistry(registryDir()), hasInRepo });
    process.stdout.write(JSON.stringify(out));
    return;
  }

  if (cmd === "repo") {
    const config = JSON.parse(readFileSync(o.config, "utf8"));
    const f = repoFields(config, o.repo);
    if (!f) process.exit(1);
    const lines = [
      `REPO_DIR=${sq(f.dir)}`,
      `REPO_INSTALL=${sq(f.install)}`,
      `REPO_BASE=${sq(f.baseBranch)}`,
      `CONFIG_PARENT_HINT=${sq(f.parentHint)}`,
      `REPO_ENVFILES=${sq(f.envFiles.join("\n"))}`,
    ];
    process.stdout.write(lines.join("\n") + "\n");
    return;
  }

  if (cmd === "guard") {
    const config = JSON.parse(readFileSync(o.config, "utf8"));
    process.exit(originMatches(o.origin, config.remoteMatch) ? 0 : 1);
  }

  process.stderr.write("usage: resolve-config.mjs <resolve|repo|guard> [opts]\n");
  process.exit(2);
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) main(process.argv.slice(2));
