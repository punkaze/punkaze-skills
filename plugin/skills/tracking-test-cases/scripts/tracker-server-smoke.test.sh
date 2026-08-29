#!/usr/bin/env bash
# Hermetic smoke test for tracker_server.py: launches a real server against a
# fixture case list, then exercises the full lifecycle a tracking-test-cases
# run depends on — page render, save round-trip, Submit (records + exits,
# tagged "submit"), and a second launch's Done & close (records + exits,
# tagged "done"), including the full-reset-on-record behavior.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SERVER="$SCRIPT_DIR/tracker_server.py"
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

H="$(mktemp -d -t tracking-test-cases-smoke-XXXXXX)"
PID=""
cleanup() { [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null && kill "$PID" 2>/dev/null; rm -rf "$H"; }
trap cleanup EXIT

cat > "$H/cases.json" <<'JSON'
{
  "branch": "smoke-test",
  "repo": "example/repo",
  "createdAt": "2026-01-01T00:00:00Z",
  "cases": [
    { "id": "TC-01", "title": "Smoke case one", "context": "ctx", "source": "manual" }
  ]
}
JSON

launch() {
  python3 "$SERVER" "$H" --port "$1" --no-open > "$H/server.log" 2>&1 &
  PID=$!
  for _ in $(seq 1 50); do
    curl -sf -o /dev/null "http://127.0.0.1:$1/" && return 0
    sleep 0.1
  done
  fail "server on port $1 never came up: $(cat "$H/server.log")"
}

wait_exit() {
  for _ in $(seq 1 50); do
    kill -0 "$PID" 2>/dev/null || { PID=""; return 0; }
    sleep 0.1
  done
  fail "server did not exit after $1"
}

PORT=8901
launch "$PORT"

page="$(curl -sf "http://127.0.0.1:$PORT/")"
echo "$page" | grep -q "TC-01" || fail "case not rendered on page"
echo "$page" | grep -q '>Submit<' || fail "Submit button missing"
echo "$page" | grep -q 'Done &amp; close' || fail "Done & close button missing"

curl -sf -X POST "http://127.0.0.1:$PORT/save" -H "Content-Type: application/json" \
  -d '{"responses":{"TC-01":{"status":"pass","note":"n1"}},"finalNote":"f1"}' \
  | grep -q '"ok": true' || fail "/save did not return ok"

curl -sf -X POST "http://127.0.0.1:$PORT/submit" \
  | grep -q '"ok": true' || fail "/submit did not return ok"
wait_exit "/submit"

runs=("$H"/runs/*.json)
[ -f "${runs[0]}" ] || fail "no run file written after /submit"
python3 -c "
import json, sys
d = json.load(open('${runs[0]}'))
assert d['action'] == 'submit', d
assert d['results']['TC-01']['status'] == 'pass', d
assert d['finalNote'] == 'f1', d
"
cur="$(cat "$H/.current.json")"
echo "$cur" | grep -q '"responses": {}' || fail ".current.json not blanked after /submit"

PORT=8902
launch "$PORT"
curl -sf -X POST "http://127.0.0.1:$PORT/save" -H "Content-Type: application/json" \
  -d '{"responses":{"TC-01":{"status":"fail"}},"finalNote":null}' \
  | grep -q '"ok": true' || fail "/save (round 2) did not return ok"
curl -sf -X POST "http://127.0.0.1:$PORT/done" \
  | grep -q '"ok": true' || fail "/done did not return ok"
wait_exit "/done"

newest="$(ls -t "$H"/runs/*.json | head -1)"
python3 -c "
import json
d = json.load(open('$newest'))
assert d['action'] == 'done', d
assert d['results']['TC-01']['status'] == 'fail', d
"

echo "SMOKE OK"
