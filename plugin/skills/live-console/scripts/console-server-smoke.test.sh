#!/usr/bin/env bash
# Hermetic smoke test for console_server.py: launches a real server against a
# fixture spec (one visuals[] illustration + one image asset), then exercises
# the full lifecycle a live-console run depends on — page render, asset
# serving, path-traversal guard, save/results round-trip, and submit-triggers-exit.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SERVER="$SCRIPT_DIR/console_server.py"
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

H="$(mktemp -d -t live-console-smoke-XXXXXX)"
MARKER="$(dirname "$H")/live-console-smoke-marker-$$.txt"
PID=""
cleanup() { [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null && kill "$PID" 2>/dev/null; rm -rf "$H" "$MARKER"; }
trap cleanup EXIT

# A real file just outside the spec dir, so the traversal check below proves
# the guard blocks it — not just that the guessed path happens not to exist.
printf 'should never be servable\n' > "$MARKER"

mkdir -p "$H/assets"
# 1x1 PNG so /asset exercises a real binary file, not just JSON.
python3 -c "
import base64
open('$H/assets/pixel.png','wb').write(base64.b64decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='))
"
cat > "$H/spec.json" <<'JSON'
{
  "title": "Smoke — flow check",
  "items": [
    {
      "id": "flow-1",
      "title": "Automation flow — arrows intact? →",
      "visualLabel": "Reference diagram",
      "visuals": [{ "id": "flow", "label": "Flow", "image": "assets/pixel.png" }],
      "fields": [
        { "type": "toggle", "key": "status", "options": ["pass", "fail", "skip"] },
        { "type": "comment", "key": "note" }
      ]
    }
  ]
}
JSON

python3 "$SERVER" "$H/spec.json" --port 0 --no-open > "$H/server.log" 2>&1 &
PID=$!

PORT=""
for _ in $(seq 1 50); do
  PORT="$(grep -o 'http://127.0.0.1:[0-9]*' "$H/server.log" 2>/dev/null | head -1 | grep -o '[0-9]*$' || true)"
  [ -n "$PORT" ] && break
  sleep 0.1
done
[ -n "$PORT" ] || fail "server never printed a port (see $H/server.log)"
BASE="http://127.0.0.1:$PORT"

for _ in $(seq 1 50); do
  curl -s -o /dev/null "$BASE/" && break
  sleep 0.1
done

# --- page renders, SPEC survives serialization intact (unicode arrow, image path) ---
code="$(curl -s -o "$H/page.html" -w '%{http_code}' "$BASE/")"
[ "$code" = "200" ] || fail "GET / -> $code"
grep -q 'assets/pixel.png' "$H/page.html" || fail "image path missing from embedded SPEC"
grep -q '\\u2192\|→' "$H/page.html" || fail "unicode arrow corrupted in embedded SPEC"

# --- asset serving ---
ctype="$(curl -s -o /dev/null -D - "$BASE/asset/assets/pixel.png" | grep -i '^content-type:' | tr -d '\r')"
echo "$ctype" | grep -qi 'image/png' || fail "asset content-type wrong: $ctype"

# --- path traversal blocked (targets a file that actually exists just
# outside the spec dir, so this proves the guard — not a coincidence) ---
code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/asset/..%2f$(basename "$MARKER")")"
[ "$code" = "404" ] || fail "path traversal not blocked (got $code) — should not be able to read $MARKER"

# --- save / results round-trip ---
curl -s -X POST "$BASE/save" -H 'Content-Type: application/json' \
  -d '{"_meta":{"done":false,"submittedAt":null},"responses":{"flow-1":{"status":"pass","note":"ok"}}}' \
  > /dev/null
got="$(curl -s "$BASE/results")"
echo "$got" | grep -q '"status": "pass"' || fail "save/results round-trip lost the response: $got"
echo "$got" | grep -q '"done": false' || fail "done flipped true before submit"

# --- submit marks done and the process exits ---
curl -s -X POST "$BASE/done" > /dev/null
for _ in $(seq 1 50); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.1
done
kill -0 "$PID" 2>/dev/null && fail "server still running after /done"
# read the persisted store straight off disk — the server may have already
# stopped accepting connections by now, same as what the agent reads post-exit.
grep -q '"done": true' "$H/spec.results.json" || fail "results store never flipped done:true"

echo "SMOKE OK"
