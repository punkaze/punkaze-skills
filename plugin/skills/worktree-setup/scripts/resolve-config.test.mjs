import { test } from "node:test";
import assert from "node:assert/strict";
import { originMatches, resolve, repoFields, registryDir } from "./resolve-config.mjs";

test("registryDir precedence: override > plugin-data > bundled", () => {
  assert.equal(registryDir({ WORKTREE_REGISTRY_DIR: "/x" }), "/x");
  assert.equal(registryDir({ CLAUDE_PLUGIN_DATA: "/data" }), "/data/projects");
  assert.ok(registryDir({}).endsWith("/projects"));
});

test("originMatches handles string, array, miss, null", () => {
  assert.equal(originMatches("git@gitlab.com:acme/backend.git", "acme/backend"), true);
  assert.equal(originMatches("git@github.com:acme/web-app.git", ["nope", "web-app"]), true);
  assert.equal(originMatches("git@github.com:x/y.git", "zzz"), false);
  assert.equal(originMatches("", "x"), false);
  assert.equal(originMatches("origin", null), false);
});

test("resolve prefers in-repo config", () => {
  const out = resolve({ topLevel: "/repo", origin: "anything", registry: [], hasInRepo: true });
  assert.deepEqual(out, { status: "in-repo", configPath: "/repo/.worktree.json" });
});

test("resolve single registry match", () => {
  const registry = [
    { path: "/r/api.json", config: { project: "api", remoteMatch: "acme/backend" } },
    { path: "/r/web.json", config: { project: "web", remoteMatch: "web-app" } },
  ];
  const out = resolve({ topLevel: "/repo", origin: "x/web-app.git", registry, hasInRepo: false });
  assert.equal(out.status, "registry");
  assert.equal(out.configPath, "/r/web.json");
  assert.equal(out.project, "web");
});

test("resolve zero match -> none", () => {
  const out = resolve({ topLevel: "/repo", origin: "x/unknown.git", registry: [
    { path: "/r/web.json", config: { project: "web", remoteMatch: "web-app" } },
  ], hasInRepo: false });
  assert.equal(out.status, "none");
});

test("resolve >1 match -> ambiguous with candidates", () => {
  const registry = [
    { path: "/r/a.json", config: { project: "a", remoteMatch: "shared" } },
    { path: "/r/b.json", config: { project: "b", remoteMatch: ["x", "shared"] } },
  ];
  const out = resolve({ topLevel: "/repo", origin: "host/shared-thing.git", registry, hasInRepo: false });
  assert.equal(out.status, "ambiguous");
  assert.deepEqual(out.candidates, ["/r/a.json", "/r/b.json"]);
});

test("repoFields returns dir/install/base/envFiles with per-repo base override", () => {
  const config = { baseBranch: "develop", parentHint: null, repos: [
    { key: "api", dir: "myapp-api", install: "npm install", envFiles: [".env"] },
    { key: "legacy", dir: "old", install: "npm i", baseBranch: "main" },
  ]};
  assert.deepEqual(repoFields(config, "api"),
    { dir: "myapp-api", install: "npm install", baseBranch: "develop", envFiles: [".env"], parentHint: "" });
  assert.equal(repoFields(config, "legacy").baseBranch, "main");
  assert.equal(repoFields(config, "missing"), null);
});
