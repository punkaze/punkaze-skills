#!/usr/bin/env python3
"""tracking-test-cases engine — render a persistent, branch-scoped test-case
checklist, diff against the most recent prior run, and self-terminate on
either footer button so the calling agent is notified (background-process
exit) and reads the new run back. Stdlib only.

Both Submit and Done & close record the round (write a runs/ snapshot, blank
the checklist) and exit the server — the calling agent picks up results
either way. They differ only in intent, tagged on the run as "action":
Submit ("submit") means "capture this round, I'll keep testing" — the agent
should relaunch a fresh console for another round unprompted. Done & close
("done", confirm dialog) means this QA pass is over.

Usage:
    python3 tracker_server.py <storage_dir> [--port N] [--no-open]

<storage_dir> MUST already contain cases.json — this script does not create
it (the calling agent authors it, same division of labor as live-console).

Layout inside <storage_dir>:
    cases.json           - the case list (never modified by this script)
    runs/<ISO8601>.json  - one immutable snapshot per completed run, tagged
                           with the action ("submit" or "done") that closed it
    .current.json        - in-progress results for the run underway; reset to
                           blank the moment a round is recorded — the full
                           record already lives forever in that round's
                           runs/ snapshot — every round requires an active
                           re-click per case, nothing rides along unverified

Endpoints: GET / , POST /save , POST /submit , POST /done
"""
import argparse
import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

STORAGE_DIR = Path(".")
CASES = []
CURRENT_FILE = Path(".current.json")
_server = None


def load_current():
    if CURRENT_FILE.exists():
        try:
            data = json.loads(CURRENT_FILE.read_text())
            if isinstance(data, dict) and "responses" in data:
                return data
        except (ValueError, OSError):
            pass
    return {"responses": {}, "finalNote": None}


def save_current(data):
    tmp = CURRENT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(CURRENT_FILE)


def newest_run():
    runs_dir = STORAGE_DIR / "runs"
    if not runs_dir.is_dir():
        return {}
    files = sorted(runs_dir.glob("*.json"))
    if not files:
        return {}
    try:
        data = json.loads(files[-1].read_text())
        return data.get("results", {})
    except (ValueError, OSError):
        return {}


def _json_for_html(obj):
    # ponytail: json.dumps doesn't escape "/", so a literal "</script>" in the
    # data would close the page's <script> tag early — escape it here.
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{--bg:#f6f7f9;--card:#fff;--fg:#1c1e21;--muted:#6b7280;--line:#e3e6ea;
        --pass:#16a34a;--fail:#dc2626;--skip:#d97706;--pend:#9ca3af;--accent:#2563eb;--accent-fg:#fff;}
  @media (prefers-color-scheme:dark){:root{--bg:#15171a;--card:#1e2125;--fg:#e6e8eb;--muted:#9aa2ad;
        --line:#2c3037;--pass:#4ade80;--fail:#f87171;--skip:#fbbf24;--pend:#6b7280;--accent:#60a5fa;--accent-fg:#0b1220;}}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);
         padding:14px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
  header h1{font-size:16px;margin:0;font-weight:650;}
  header .sub{font-size:12px;color:var(--muted);}
  .summary{display:flex;gap:12px;font-size:13px;color:var(--muted);flex-wrap:wrap;margin-left:auto;}
  .summary b{font-variant-numeric:tabular-nums;}
  .summary .tally-pass{color:var(--pass);}
  .summary .tally-fail{color:var(--fail);}
  .summary .tally-skip{color:var(--skip);}
  #saved{font-size:12px;color:var(--muted);min-width:110px;text-align:right;}
  main{max-width:900px;margin:0 auto;padding:20px 20px 96px;}
  .item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;
        margin-bottom:14px;border-left:4px solid var(--pend);}
  .item[data-tone="pass"]{border-left-color:var(--pass);}
  .item[data-tone="fail"]{border-left-color:var(--fail);}
  .item[data-tone="skip"]{border-left-color:var(--skip);}
  .item h2{font-size:15px;margin:0 0 4px;display:flex;gap:8px;align-items:baseline;}
  .item h2 .tid{font-size:12px;color:var(--muted);font-weight:600;}
  .prev-status{font-size:11px;color:var(--muted);margin:0 0 8px;}
  .prev-status .prev-pass{color:var(--pass);font-weight:700;}
  .prev-status .prev-fail{color:var(--fail);font-weight:700;}
  .prev-status .prev-skip{color:var(--skip);font-weight:700;}
  .body{color:var(--fg);white-space:pre-wrap;margin:2px 0 4px;}
  .steps{margin:6px 0 10px;padding-left:1.4em;}
  .steps li{font:13px/1.6 ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;margin-bottom:2px;}
  .expected{display:inline-block;padding:6px 10px;border-radius:6px;margin:2px 0 4px;font-size:13px;
        background:color-mix(in srgb, var(--pass) 14%, transparent);
        border:1px solid color-mix(in srgb, var(--pass) 40%, var(--line));color:var(--pass);}
  .field{margin:10px 0;}
  .label{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600;margin-bottom:3px;}
  .dropzone{border-radius:8px;transition:outline-color .1s;outline:2px dashed transparent;outline-offset:3px;}
  .dropzone.dragover{outline-color:var(--accent);background:color-mix(in srgb, var(--accent) 6%, transparent);}
  .attachments{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;}
  .attach{position:relative;width:84px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--bg);}
  .attach img{width:100%;height:64px;object-fit:cover;display:block;}
  .attach-name{font-size:10px;color:var(--muted);padding:3px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .attach-remove{position:absolute;top:2px;right:2px;width:18px;height:18px;border-radius:50%;border:0;
        background:rgba(0,0,0,.55);color:#fff;font-size:12px;line-height:1;cursor:pointer;padding:0;}
  .attach-text{width:auto;min-width:220px;max-width:340px;padding:7px 9px 9px;}
  .attach-text .attach-name{padding:0 0 4px;font-weight:600;color:var(--fg);white-space:normal;}
  .attach-preview{margin:0;font:11.5px/1.5 ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;
        white-space:pre-wrap;word-break:break-word;color:var(--muted);max-height:150px;overflow:auto;}
  .attach-preview.expanded{max-height:360px;}
  .attach-toggle{display:block;margin-top:4px;border:0;background:none;color:var(--accent);
        font-size:11px;cursor:pointer;padding:0;font:inherit;}
  .attach-filehint{font-size:10px;color:var(--muted);text-align:center;padding:14px 4px;
        font-weight:600;letter-spacing:.04em;}
  .seg{display:inline-flex;flex-wrap:wrap;gap:6px;}
  .seg button{border:1px solid var(--line);background:transparent;color:var(--fg);
        padding:6px 14px;border-radius:9px;font:inherit;font-size:13px;cursor:pointer;}
  .seg button.on-pass{background:var(--pass);color:#fff;border-color:transparent;}
  .seg button.on-fail{background:var(--fail);color:#fff;border-color:transparent;}
  .seg button.on-skip{background:var(--skip);color:#fff;border-color:transparent;}
  textarea{width:100%;min-height:48px;resize:vertical;background:var(--bg);color:var(--fg);
        border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:inherit;font-size:14px;}
  textarea:focus{outline:2px solid var(--accent);outline-offset:-1px;}
  footer{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--line);
         padding:12px 20px;display:flex;align-items:center;gap:14px;justify-content:flex-end;}
  footer .note{margin-right:auto;color:var(--muted);font-size:13px;}
  #done{background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:9px;
          padding:10px 22px;font:inherit;font-weight:650;font-size:14px;cursor:pointer;}
  #submit:disabled,#done:disabled{opacity:.6;cursor:default;}
  #submit{background:var(--accent);color:var(--accent-fg);border:0;border-radius:9px;
          padding:10px 22px;font:inherit;font-weight:650;font-size:14px;cursor:pointer;}
  .overlay{position:fixed;inset:0;background:var(--bg);display:none;align-items:center;justify-content:center;
          flex-direction:column;gap:10px;z-index:50;text-align:center;padding:24px;}
  .overlay.show{display:flex;}
</style>
</head>
<body>
<header>
  <div>
    <h1>__TITLE__</h1>
    <div class="sub">__SUBTITLE__</div>
  </div>
  <div class="summary" id="summary"></div>
  <span id="saved">—</span>
</header>
<main>
  <div id="items"></div>
</main>
<footer>
  <span class="note" id="foot-note"></span>
  <button id="submit">Submit</button>
  <button id="done">Done &amp; close</button>
</footer>
<div id="submit-overlay" class="overlay">
  <div style="font-size:20px;font-weight:650;">📋 Got your results</div>
  <div>Picking them up now — you can close this tab. I'll open a fresh one for the next round.</div>
</div>
<div id="done-overlay" class="overlay">
  <div style="font-size:20px;font-weight:650;">✅ Run recorded</div>
  <div>You can close this tab.</div>
</div>
<script>
const CASES = __CASES__;
const PREV = __PREV__;
let CUR = __CURRENT__;
if(!CUR || typeof CUR!=="object") CUR = {responses:{}, finalNote:null};
CUR.responses = CUR.responses || {};

const esc = s => String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const TONE = {pass:"pass", fail:"fail", skip:"skip"};

function rec(id){ if(!CUR.responses[id]) CUR.responses[id]={}; return CUR.responses[id]; }
function get(id,key){ return (CUR.responses[id]||{})[key]; }
function set(id,key,val){ const r=rec(id); if(val==null||val==="") delete r[key]; else r[key]=val;
  r.updatedAt=new Date().toISOString(); refresh(); saveDebounced(); }

const itemsEl = document.getElementById("items");
const MAX_DROP_BYTES = 10 * 1024 * 1024; // 10MB — sanity guard, not a hard product limit

function isTextLike(file){
  if(file.type && file.type.startsWith("text/")) return true;
  if(file.type === "application/json") return true;
  return /\.(txt|log|md|json|csv|ya?ml|diff|patch|js|ts|jsx|tsx|py|rb|go|java|c|cpp|h|sh)$/i.test(file.name);
}

// First few lines/chars only — the full content always travels in a.content,
// this is just what's shown before the user clicks "Show more".
function textPreview(content, maxLines, maxChars){
  const lines = content.split("\n");
  let preview = lines.slice(0, maxLines).join("\n");
  const truncated = lines.length > maxLines || content.length > maxChars;
  if(preview.length > maxChars) preview = preview.slice(0, maxChars);
  return {preview, truncated};
}

function fileExtLabel(name){
  const m = name.match(/\.([a-z0-9]+)$/i);
  return m ? m[1].toUpperCase() : "FILE";
}

function buildAttachCard(a, i, list, container, getAttachments, setAttachments){
  const fig = document.createElement("div");
  fig.className = a.kind === "text" ? "attach attach-text" : "attach";
  const cap = document.createElement("div"); cap.className = "attach-name"; cap.textContent = a.name;
  if(a.kind === "image"){
    const img = document.createElement("img"); img.src = a.dataUrl; fig.appendChild(img);
    fig.appendChild(cap);
  } else if(a.kind === "file"){
    fig.appendChild(cap);
    const hint = document.createElement("div"); hint.className = "attach-filehint"; hint.textContent = fileExtLabel(a.name);
    fig.appendChild(hint);
  } else {
    fig.appendChild(cap);
    const {preview, truncated} = textPreview(a.content || "", 6, 300);
    const pre = document.createElement("pre"); pre.className = "attach-preview";
    pre.textContent = preview + (truncated ? "\n…" : "");
    fig.appendChild(pre);
    if(truncated){
      const toggle = document.createElement("button"); toggle.className = "attach-toggle"; toggle.textContent = "Show more";
      let expanded = false;
      toggle.onclick = () => {
        expanded = !expanded;
        pre.textContent = expanded ? a.content : preview + "\n…";
        pre.classList.toggle("expanded", expanded);
        toggle.textContent = expanded ? "Show less" : "Show more";
      };
      fig.appendChild(toggle);
    }
  }
  const rm = document.createElement("button"); rm.className = "attach-remove"; rm.textContent = "×";
  rm.onclick = () => {
    const next = list.slice(); next.splice(i, 1); setAttachments(next);
    renderAttachments(container, getAttachments, setAttachments); saveDebounced();
  };
  fig.appendChild(rm);
  return fig;
}

// Media (images/video/pdf/anything else binary) renders as its own row
// first, text-content previews (json/txt/logs/code) as a separate row below
// — kept apart rather than one mixed flex-wrap, since a small image thumb
// and a wide text-preview card read badly interleaved on the same line.
function renderAttachments(container, getAttachments, setAttachments){
  container.innerHTML = "";
  const list = getAttachments() || [];
  if(!list.length) return;
  const mediaRow = document.createElement("div"); mediaRow.className = "attachments";
  const textRow = document.createElement("div"); textRow.className = "attachments";
  list.forEach((a, i) => {
    const card = buildAttachCard(a, i, list, container, getAttachments, setAttachments);
    (a.kind === "text" ? textRow : mediaRow).appendChild(card);
  });
  if(mediaRow.children.length) container.appendChild(mediaRow);
  if(textRow.children.length) container.appendChild(textRow);
}

// Dropped files always become attachment cards, never raw text stuffed into
// the note — the note stays for what the user actually typed. Text-like
// files (logs, json, code…) get a truncated+expandable preview; real images
// get a thumbnail; anything else binary (video, pdf, zip…) gets a plain
// filename+type card rather than being force-rendered as a broken <img>.
// Browsers never expose a dropped file's real filesystem path, so this is
// the honest alternative: embed the content itself.
function wireDropZone(zone, getAttachments, setAttachments, repaint){
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", e => {
    e.preventDefault(); zone.classList.remove("dragover");
    for(const file of e.dataTransfer.files){
      if(file.size > MAX_DROP_BYTES){
        alert(`${file.name} is over 10MB — skipped.`); continue;
      }
      const reader = new FileReader();
      if(isTextLike(file)){
        reader.onload = () => {
          setAttachments((getAttachments() || []).concat([{name: file.name, kind: "text", content: reader.result}]));
          repaint(); saveDebounced();
        };
        reader.readAsText(file);
      } else {
        const kind = (file.type && file.type.startsWith("image/")) ? "image" : "file";
        reader.onload = () => {
          setAttachments((getAttachments() || []).concat([{name: file.name, kind, dataUrl: reader.result}]));
          repaint(); saveDebounced();
        };
        reader.readAsDataURL(file);
      }
    }
  });
}

function noteFieldWithDrop(labelText, placeholderText, getNote, setNote, getAttachments, setAttachments){
  const field = document.createElement("div"); field.className = "field dropzone";
  if(labelText) field.innerHTML = `<div class="label">${esc(labelText)}</div>`;
  const ta = document.createElement("textarea"); ta.placeholder = placeholderText;
  ta.value = getNote() || "";
  ta.addEventListener("input", () => setNote(ta.value));
  field.appendChild(ta);
  const attachWrap = document.createElement("div");
  field.appendChild(attachWrap);
  const repaint = () => renderAttachments(attachWrap, getAttachments, setAttachments);
  repaint();
  wireDropZone(field, getAttachments, setAttachments, repaint);
  return field;
}

function render(){
  itemsEl.innerHTML = "";
  for(const c of CASES){
    const el = document.createElement("section"); el.className="item"; el.dataset.id=c.id;
    const prevStatus = (PREV[c.id]||{}).status;
    const prevLine = prevStatus
      ? `<div class="prev-status">Last run: <span class="prev-${esc(prevStatus)}">${esc(prevStatus)}</span></div>` : "";
    el.innerHTML = `<h2><span class="tid">${esc(c.id)}</span>${esc(c.title||"")}</h2>` + prevLine +
      (c.context?`<div class="body">${esc(c.context)}</div>`:"") +
      (Array.isArray(c.steps)&&c.steps.length?`<ol class="steps">${c.steps.map(s=>`<li>${esc(s)}</li>`).join("")}</ol>`:"") +
      (c.expected?`<div class="expected"><b>Expected:</b> ${esc(c.expected)}</div>`:"");
    const statusField = document.createElement("div"); statusField.className="field";
    statusField.innerHTML = `<div class="label">Status</div>`;
    const seg = document.createElement("div"); seg.className="seg";
    for(const opt of ["pass","fail","skip"]){
      const b = document.createElement("button"); b.textContent = opt;
      const cur = get(c.id,"status");
      if(cur===opt) b.classList.add("on-"+opt);
      b.onclick = () => { set(c.id,"status", cur===opt?null:opt); render(); };
      seg.appendChild(b);
    }
    statusField.appendChild(seg); el.appendChild(statusField);
    el.appendChild(noteFieldWithDrop("Note", "What you observed… (drop a log/screenshot to attach)",
      () => get(c.id,"note"), (v) => set(c.id,"note", v),
      () => get(c.id,"attachments"), (list) => set(c.id,"attachments", list.length?list:null)));
    const status = get(c.id,"status");
    if(status && TONE[status]) el.dataset.tone = TONE[status];
    itemsEl.appendChild(el);
  }
  const fn = document.createElement("section"); fn.className="item"; fn.style.borderLeftStyle="dashed";
  fn.innerHTML = `<h2>Overall notes</h2>`;
  fn.appendChild(noteFieldWithDrop("", "Anything else worth flagging… (drop a log/screenshot to attach)",
    () => CUR.finalNote, (v) => { CUR.finalNote = v; saveDebounced(); },
    () => CUR.finalAttachments, (list) => { CUR.finalAttachments = list.length?list:null; saveDebounced(); }));
  itemsEl.appendChild(fn);
  refresh();
}

function refresh(){
  const total = CASES.length;
  const answered = CASES.filter(c => get(c.id,"status")).length;
  const tally = {pass:0, fail:0, skip:0};
  for(const c of CASES){ const s = get(c.id,"status"); if(s && tally[s]!=null) tally[s]++; }
  const chips = Object.entries(tally).filter(([,n])=>n>0)
    .map(([k,n]) => `<span class="tally-${k}"><b>${n}</b> ${k}</span>`).join("");
  document.getElementById("summary").innerHTML = `<span><b>${answered}</b>/${total} answered</span>${chips}`;
  document.getElementById("foot-note").textContent =
    (total-answered) > 0 ? `${total-answered} case(s) not yet answered` : "";
}

let t=null;
function saveDebounced(){ clearTimeout(t); t=setTimeout(save,400); }
function save(){ setSaved("saving…");
  return fetch("/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(CUR)})
    .then(r=>{if(!r.ok)throw 0; setSaved("saved "+new Date().toLocaleTimeString());})
    .catch(()=>setSaved("⚠ save failed")); }
function setSaved(s){ document.getElementById("saved").textContent=s; }

// Both buttons record this round (write a runs/ snapshot, blank the working
// copy) and let the server exit — that exit is the calling agent's
// read-results signal either way. Submit skips the confirm dialog (it means
// "capture this and I'll keep testing" — the agent reopens a fresh console
// unprompted); Done & close confirms first since it ends the session.
function doSubmit(){
  const btn = document.getElementById("submit");
  btn.disabled = true; btn.textContent = "Submitting…";
  save().finally(() => {
    fetch("/submit",{method:"POST"}).catch(()=>{}).finally(() => {
      document.getElementById("submit-overlay").classList.add("show");
    });
  });
}
function doDone(){
  if(!confirm("Record this round as final and close the test-tracking session?")) return;
  const btn = document.getElementById("done");
  btn.disabled = true; btn.textContent = "Closing…";
  save().finally(()=>{
    fetch("/done",{method:"POST"}).catch(()=>{}).finally(()=>{
      document.getElementById("done-overlay").classList.add("show");
    });
  });
}
document.getElementById("submit").onclick = doSubmit;
document.getElementById("done").onclick = doDone;
render();
</script>
</body>
</html>"""


def _record_run(action):
    # Shared by /submit and /done — both write the snapshot, blank current,
    # and shut down; only the tagged "action" differs, so the calling agent
    # can tell "capture and keep testing" (submit) from "QA pass over" (done).
    data = load_current()
    runs_dir = STORAGE_DIR / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_file = runs_dir / f"{stamp}.json"
    run_file.write_text(json.dumps({
        "runAt": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "results": data.get("responses", {}),
        "finalNote": data.get("finalNote"),
        "finalAttachments": data.get("finalAttachments"),
    }, indent=2, ensure_ascii=False))
    # Next round starts fully blank — status included. The complete record
    # (status, notes, attachments) is already preserved forever in the run
    # file just written; carrying a status forward would let a case go
    # un-re-checked for a whole round while still silently showing "pass".
    # Forcing a real click each round is the point.
    save_current({"responses": {}, "finalNote": None})
    return run_file


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            title = f"Test tracking — {STORAGE_DIR.parent.name}/{STORAGE_DIR.name}"
            # ponytail: escape "</" everywhere spliced into the page (not just
            # JSON) so a case title/body containing "</script>" can't close the
            # tag early, and substitute all placeholders in one pass so an
            # injected value containing e.g. "__CURRENT__" isn't re-scanned by
            # a later .replace() call.
            subs = {
                "__TITLE__": title.replace("</", "<\\/"),
                "__SUBTITLE__": f"{len(CASES)} case(s)".replace("</", "<\\/"),
                "__CASES__": _json_for_html(CASES),
                # Recomputed per request, not the startup-time snapshot — a
                # round Submitted without stopping the server must show up
                # as "Last run" on the very next reload.
                "__PREV__": _json_for_html(newest_run()),
                "__CURRENT__": _json_for_html(load_current()),
            }
            page = re.sub(r"__(?:TITLE|SUBTITLE|CASES|PREV|CURRENT)__", lambda m: subs[m.group(0)], PAGE)
            self._send(200, page, "text/html")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b""
        if path == "/save":
            try:
                data = json.loads(raw or b"{}")
                if not isinstance(data, dict):
                    raise ValueError("expected object")
                data.setdefault("responses", {})
                save_current(data)
                self._send(200, json.dumps({"ok": True}))
            except (ValueError, OSError) as e:
                self._send(400, json.dumps({"error": str(e)}))
        elif path == "/submit":
            run_file = _record_run("submit")
            self._send(200, json.dumps({"ok": True, "run": str(run_file)}))
            threading.Thread(target=_server.shutdown, daemon=True).start()
        elif path == "/done":
            run_file = _record_run("done")
            self._send(200, json.dumps({"ok": True, "run": str(run_file)}))
            threading.Thread(target=_server.shutdown, daemon=True).start()
        else:
            self._send(404, json.dumps({"error": "not found"}))


def main():
    global STORAGE_DIR, CASES, CURRENT_FILE, _server
    ap = argparse.ArgumentParser()
    ap.add_argument("storage_dir")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    STORAGE_DIR = Path(args.storage_dir).resolve()
    cases_file = STORAGE_DIR / "cases.json"
    if not cases_file.is_file():
        print(f"error: {cases_file} does not exist — create it before launching", file=sys.stderr)
        sys.exit(1)
    try:
        spec = json.loads(cases_file.read_text())
    except (ValueError, OSError) as e:
        print(f"error: failed to read {cases_file}: {e}", file=sys.stderr)
        sys.exit(1)
    CASES = spec.get("cases", [])
    CURRENT_FILE = STORAGE_DIR / ".current.json"

    _server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    port = _server.server_address[1]
    url = f"http://127.0.0.1:{port}"
    print(f"tracking-test-cases: {STORAGE_DIR}")
    print(f"  url   : {url}")
    print(f"  cases : {len(CASES)}")
    print("  waiting for Submit or Done & close (either exits the server)")
    sys.stdout.flush()
    if not args.no_open and sys.platform == "darwin":
        try:
            subprocess.run(["open", url], check=False)
        except OSError:
            pass
    _server.serve_forever()
    print("tracking-test-cases: done — server stopped.")


if __name__ == "__main__":
    main()
