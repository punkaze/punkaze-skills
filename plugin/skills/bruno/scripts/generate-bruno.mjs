#!/usr/bin/env node
import { readFileSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// ---------- pure helpers ----------

export function slug(str) {
  return String(str).trim().toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function pathParams(path) {
  return [...String(path).matchAll(/:([A-Za-z0-9_]+)/g)].map((m) => m[1]);
}

export function resourceOf(route) {
  if (route.folder) return route.folder;
  const seg = String(route.path).split("/").filter(Boolean)[0] || "root";
  return seg.replace(/^:/, "").replace(/[^A-Za-z0-9_-]/g, "") || "root";
}

export function groupRoutes(routes) {
  const groups = {};
  for (const r of routes) {
    const key = resourceOf(r);
    (groups[key] ||= []).push(r);
  }
  return groups;
}

export function resolveAuth(route, manifest) {
  const a = route.auth;
  if (a === false) return "none";
  if (typeof a === "string") return a;
  if (a === true) return "inherit";
  const ct = manifest && manifest.auth && manifest.auth.type;
  return ct && ct !== "none" ? "inherit" : "none";
}

function cap(s) {
  return String(s).charAt(0).toUpperCase() + String(s).slice(1);
}

function indentJson(obj, n) {
  const pad = " ".repeat(n);
  return JSON.stringify(obj, null, 2).split("\n").map((l) => pad + l).join("\n");
}

// ---------- renderers ----------

const TEST_PRESETS = {
  "status-200": 'test("status is 200", function() {\n  expect(res.status).to.equal(200);\n});',
  "status-201": 'test("status is 201", function() {\n  expect(res.status).to.equal(201);\n});',
  "status-2xx": 'test("status is 2xx", function() {\n  expect(res.status).to.be.within(200, 299);\n});',
};

export function renderRequest(route, seq, manifest = {}) {
  const method = String(route.method).toLowerCase();
  const auth = resolveAuth(route, manifest);
  const hasBody = ["post", "put", "patch"].includes(method) && route.body != null;
  const L = [];

  L.push("meta {");
  L.push(`  name: ${route.name}`);
  L.push("  type: http");
  L.push(`  seq: ${seq}`);
  if (route.tags && route.tags.length) L.push(`  tags: [${route.tags.join(", ")}]`);
  L.push("}", "");

  L.push(`${method} {`);
  L.push(`  url: {{baseUrl}}${route.path}`);
  L.push(`  body: ${hasBody ? "json" : "none"}`);
  L.push(`  auth: ${auth}`);
  L.push("}", "");

  if (auth === "bearer") {
    L.push("auth:bearer {", "  token: {{authToken}}", "}", "");
  } else if (auth === "basic") {
    L.push("auth:basic {", "  username: {{username}}", "  password: {{password}}", "}", "");
  }

  const pps = pathParams(route.path);
  if (pps.length) {
    L.push("params:path {");
    for (const p of pps) L.push(`  ${p}: `);
    L.push("}", "");
  }

  if (route.query && Object.keys(route.query).length) {
    L.push("params:query {");
    for (const [k, v] of Object.entries(route.query)) L.push(`  ${k}: ${v}`);
    L.push("}", "");
  }

  const headers = { Accept: "application/json", ...(route.headers || {}) };
  if (hasBody) headers["Content-Type"] = "application/json";
  L.push("headers {");
  for (const [k, v] of Object.entries(headers)) L.push(`  ${k}: ${v}`);
  L.push("}", "");

  if (hasBody) {
    L.push("body:json {", indentJson(route.body, 2), "}", "");
  }

  if (route.script === "token-capture") {
    // Use bru.setVar (runtime-only) so the captured token is never written to
    // disk — unlike an env var, which the Bruno GUI can save into a committed
    // environment file.
    L.push("script:post-response {");
    L.push("  if (res.status >= 200 && res.status < 300 && res.body && res.body.token) {");
    L.push('    bru.setVar("authToken", res.body.token);');
    L.push("  }");
    L.push("}", "");
  }

  if (route.tests && route.tests.length) {
    L.push("tests {");
    for (const t of route.tests) {
      const block = TEST_PRESETS[t];
      if (block) for (const line of block.split("\n")) L.push("  " + line);
    }
    L.push("}", "");
  }

  if (route.docs) {
    L.push("docs {", `  ${route.docs}`, "}", "");
  }

  return L.join("\n").replace(/\n+$/, "\n");
}

export function renderEnvironment(env) {
  const L = ["vars {", `  baseUrl: ${env.baseUrl}`];
  for (const [k, v] of Object.entries(env.vars || {})) L.push(`  ${k}: ${v}`);
  L.push("}");
  const secrets = env.secretVars || [];
  if (secrets.length) {
    L.push("vars:secret [");
    L.push(secrets.map((s) => `  ${s}`).join(",\n"));
    L.push("]");
  }
  return L.join("\n") + "\n";
}

export function renderBrunoJson(manifest) {
  const obj = { version: "1", name: manifest.name, type: "collection" };
  if (manifest.ignore && manifest.ignore.length) obj.ignore = manifest.ignore;
  return JSON.stringify(obj, null, 2) + "\n";
}

export function renderFolder(name) {
  return `meta {\n  name: ${cap(name)}\n}\n`;
}

// collection.bru at the root is what `auth: inherit` in child requests
// resolves against — without it, "inherited" requests send no auth at all.
export function renderCollectionBru(manifest) {
  const type = (manifest.auth && manifest.auth.type) || "none";
  const L = ["meta {", `  name: ${manifest.name}`, "}", ""];
  L.push("auth {", `  mode: ${type}`, "}");
  if (type === "bearer") {
    L.push("", "auth:bearer {", "  token: {{authToken}}", "}");
  } else if (type === "basic") {
    L.push("", "auth:basic {", "  username: {{username}}", "  password: {{password}}", "}");
  }
  return L.join("\n") + "\n";
}

// ---------- assembler ----------

export function buildCollection(manifest) {
  const files = {};
  files["bruno.json"] = renderBrunoJson(manifest);
  files["collection.bru"] = renderCollectionBru(manifest);
  for (const env of manifest.environments || []) {
    files[`environments/${env.name}.bru`] = renderEnvironment(env);
  }
  const groups = groupRoutes(manifest.routes || []);
  for (const [resource, routes] of Object.entries(groups)) {
    files[`${resource}/folder.bru`] = renderFolder(resource);
    let seq = 1;
    for (const r of routes) {
      files[`${resource}/${slug(r.name)}.bru`] = renderRequest(r, seq++, manifest);
    }
  }
  return files;
}

// ---------- side effects ----------

export function writeCollection(files, outDir, { force = false, dryRun = false } = {}) {
  const written = [];
  const skipped = [];
  for (const [rel, content] of Object.entries(files)) {
    const full = join(outDir, rel);
    if (existsSync(full) && !force) { skipped.push(rel); continue; }
    if (!dryRun) {
      mkdirSync(dirname(full), { recursive: true });
      writeFileSync(full, content);
    }
    written.push(rel);
  }
  return { written, skipped };
}

// ---------- CLI ----------

export function parseArgs(argv) {
  const args = { force: false, dryRun: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--manifest") args.manifest = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "--force") args.force = true;
    else if (a === "--dry-run") args.dryRun = true;
    else if (a === "-h" || a === "--help") args.help = true;
  }
  return args;
}

function main(argv) {
  const args = parseArgs(argv);
  if (args.help || !args.manifest || !args.out) {
    console.log("Usage: node generate-bruno.mjs --manifest <path> --out <dir> [--force] [--dry-run]");
    process.exit(args.help ? 0 : 1);
  }
  const manifest = JSON.parse(readFileSync(args.manifest, "utf8"));
  const files = buildCollection(manifest);
  const { written, skipped } = writeCollection(files, args.out, { force: args.force, dryRun: args.dryRun });
  console.log(`${args.dryRun ? "[dry-run] " : ""}wrote ${written.length} file(s) to ${args.out}`);
  if (skipped.length) {
    console.log(`skipped ${skipped.length} existing file(s) (use --force to overwrite)`);
  }
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) main(process.argv.slice(2));
