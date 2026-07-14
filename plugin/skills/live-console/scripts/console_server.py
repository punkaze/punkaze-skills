#!/usr/bin/env python3
"""live-console engine — render a declarative spec into an interactive local
web console, persist every response to a store on disk, and self-terminate on
Submit so the controlling agent is notified (background-process exit) and reads
the store. Stdlib only; no dependencies.

Usage:
    python3 console_server.py <spec.json> [--port N] [--no-open] [--results PATH]

- spec.json  : the console definition (see AUTHORING.md for the schema).
- --results  : where to persist responses (default: <spec_stem>.results.json
               beside the spec). The agent reads this file.
- --port     : fixed port (default: an OS-assigned free port on 127.0.0.1).
- --no-open  : do not auto-open the browser.

Endpoints: GET / , GET /results , GET /spec , GET /asset/<relpath> ,
POST /save (full responses object) , POST /done (mark submitted + exit).
"""
import argparse
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

SPEC = {}
SPEC_DIR = Path(".")
RESULTS = Path("results.json")
_server = None  # set in main(); used by /done to shut down


def load_results():
    if RESULTS.exists():
        try:
            data = json.loads(RESULTS.read_text())
            if isinstance(data, dict) and "responses" in data:
                return data
        except (ValueError, OSError):
            pass
    return {"_meta": {"done": False, "submittedAt": None}, "responses": {}}


def save_results(data):
    tmp = RESULTS.with_suffix(RESULTS.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(RESULTS)


_ASSET_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
}


def resolve_asset(relpath):
    """Resolve an /asset/<relpath> request to a real file UNDER the spec dir
    (path-traversal blocked). Returns (abs_path, content_type) or None."""
    root = SPEC_DIR.resolve()
    target = (root / relpath).resolve()
    # why: only serve files inside the spec directory — the spec is agent-authored,
    # but this still blocks `../../etc/passwd`-style escapes on a localhost port.
    if root not in target.parents and target != root:
        return None
    if not target.is_file():
        return None
    return target, _ASSET_TYPES.get(target.suffix.lower(), "application/octet-stream")


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
  body{margin:0;background:var(--bg);color:var(--fg);
       font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);
         padding:14px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
  header h1{font-size:16px;margin:0;font-weight:650;}
  .summary{display:flex;gap:12px;font-size:13px;color:var(--muted);flex-wrap:wrap;}
  .summary b{font-variant-numeric:tabular-nums;}
  #saved{margin-left:auto;font-size:12px;color:var(--muted);min-width:110px;text-align:right;}
  main{max-width:900px;margin:0 auto;padding:20px 20px 96px;}
  .instr{color:var(--muted);margin:0 0 16px;}
  .item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;
        margin-bottom:14px;border-left:4px solid var(--pend);}
  .item[data-answered="1"]{border-left-color:var(--accent);}
  .item[data-status="pass"]{border-left-color:var(--pass);}
  .item[data-status="fail"]{border-left-color:var(--fail);}
  .item[data-status="skip"]{border-left-color:var(--skip);}
  .item h2{font-size:15px;margin:0 0 4px;display:flex;gap:8px;align-items:baseline;}
  .item h2 .tid{font-size:12px;color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums;}
  .body{color:var(--fg);white-space:pre-wrap;margin:2px 0 4px;}
  .field{margin:10px 0;}
  .label{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600;margin-bottom:3px;}
  .seg{display:inline-flex;flex-wrap:wrap;gap:6px;}
  .seg button,.chip{border:1px solid var(--line);background:transparent;color:var(--fg);
        padding:6px 14px;border-radius:9px;font:inherit;font-size:13px;cursor:pointer;}
  .seg button.on{background:var(--accent);color:var(--accent-fg);border-color:transparent;}
  .seg button.on-pass{background:var(--pass);color:#fff;border-color:transparent;}
  .seg button.on-fail{background:var(--fail);color:#fff;border-color:transparent;}
  .seg button.on-skip{background:var(--skip);color:#fff;border-color:transparent;}
  .stars{display:inline-flex;gap:4px;}
  .stars button{font-size:22px;line-height:1;background:none;border:0;cursor:pointer;color:var(--pend);padding:0 2px;}
  .stars button.on{color:var(--skip);}
  textarea{width:100%;min-height:48px;resize:vertical;background:var(--bg);color:var(--fg);
        border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:inherit;font-size:14px;}
  textarea:focus{outline:2px solid var(--accent);outline-offset:-1px;}
  ul.rank{list-style:none;margin:0;padding:0;}
  ul.rank li{display:flex;align-items:center;gap:8px;background:var(--bg);border:1px solid var(--line);
        border-radius:8px;padding:8px 10px;margin-bottom:6px;cursor:grab;}
  ul.rank li .ord{color:var(--muted);font-variant-numeric:tabular-nums;min-width:18px;}
  ul.rank li .mv{margin-left:auto;display:flex;gap:4px;}
  ul.rank li .mv button{border:1px solid var(--line);background:transparent;color:var(--fg);
        border-radius:6px;cursor:pointer;width:26px;height:24px;}
  li.dragging{opacity:.4;}
  .visuals{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:6px;}
  .vcard{border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;}
  .vcard.chosen{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent) inset;}
  .vcard .frame{background:var(--bg);padding:10px;min-height:80px;overflow:auto;}
  .vcard .frame img{max-width:100%;height:auto;display:block;}
  .vcard .vfoot{padding:8px 10px;display:flex;flex-direction:column;gap:6px;border-top:1px solid var(--line);}
  .vcard .vfoot .vhead{display:flex;align-items:center;gap:8px;}
  .vcard .vfoot .vhead b{font-size:13px;}
  footer{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--line);
         padding:12px 20px;display:flex;align-items:center;gap:14px;justify-content:flex-end;}
  footer .note{margin-right:auto;color:var(--muted);font-size:13px;}
  #submit{background:var(--accent);color:var(--accent-fg);border:0;border-radius:9px;
          padding:10px 22px;font:inherit;font-weight:650;font-size:14px;cursor:pointer;}
  #done-overlay{position:fixed;inset:0;background:var(--bg);display:none;align-items:center;justify-content:center;
          flex-direction:column;gap:10px;z-index:50;text-align:center;padding:24px;}
  #done-overlay.show{display:flex;}
  #done-overlay .big{font-size:20px;font-weight:650;}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="summary" id="summary"></div>
  <span id="saved">—</span>
</header>
<main>
  <p class="instr" id="instr"></p>
  <div id="items"></div>
</main>
<footer>
  <span class="note" id="foot-note"></span>
  <button id="submit">Submit &amp; done</button>
</footer>
<div id="done-overlay">
  <div class="big">✅ Submitted</div>
  <div>Your responses were saved. You can close this tab.</div>
</div>
<script>
const SPEC = __SPEC__;
let RES = __SAVED__;
if(!RES || typeof RES!=="object"){ RES = {_meta:{done:false,submittedAt:null},responses:{}}; }
RES.responses = RES.responses || {};
const itemsEl = document.getElementById("items");
const esc = s => String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

// ---- store API (also the raw-HTML escape hatch: window.Console) --------------
function rec(id){ if(!RES.responses[id]) RES.responses[id]={}; return RES.responses[id]; }
const Console = {
  get(id,key){ return (RES.responses[id]||{})[key]; },
  set(id,key,val){ const r=rec(id); if(val==null||val==="") delete r[key]; else r[key]=val;
                   r.updatedAt=new Date().toISOString(); refreshSummary(); saveDebounced(); },
  submit(){ doSubmit(); },
};
window.Console = Console;

// ---- rendering ---------------------------------------------------------------
function render(){
  itemsEl.innerHTML="";
  document.getElementById("instr").textContent = SPEC.instructions||"";
  if(!SPEC.instructions) document.getElementById("instr").style.display="none";
  if(SPEC.rawHtml){ const d=document.createElement("div"); d.innerHTML=SPEC.rawHtml; itemsEl.appendChild(d); refreshSummary(); return; }
  for(const item of (SPEC.items||[])) itemsEl.appendChild(renderItem(item));
  refreshSummary();
}

function renderItem(item){
  const el=document.createElement("section"); el.className="item"; el.dataset.id=item.id;
  if(item.rawHtml){ el.innerHTML=item.rawHtml; return el; }
  const tid = item.id ? `<span class="tid">${esc(item.id)}</span> ` : "";
  el.innerHTML = `<h2>${tid}${esc(item.title||"")}</h2>` + (item.body?`<div class="body">${esc(item.body)}</div>`:"");
  if(Array.isArray(item.visuals)) el.appendChild(renderVisuals(item));
  for(const f of (item.fields||[])) el.appendChild(renderField(item,f));
  markItem(el,item);
  return el;
}

function fieldWrap(label){ const w=document.createElement("div"); w.className="field";
  if(label) w.innerHTML=`<div class="label">${esc(label)}</div>`; return w; }

const STATUS_CLASS = {pass:"on-pass",fail:"on-fail",skip:"on-skip",approve:"on-pass",reject:"on-fail",
                     yes:"on-pass",no:"on-fail",na:"on-skip"};

function renderField(item,f){
  const id=item.id, key=f.key;
  if(f.type==="comment"){
    const w=fieldWrap(f.label||"Comment"); const ta=document.createElement("textarea");
    ta.placeholder=f.placeholder||""; ta.value=Console.get(id,key)||"";
    ta.addEventListener("input",()=>Console.set(id,key,ta.value)); w.appendChild(ta); return w;
  }
  if(f.type==="toggle"||f.type==="choice"){
    const multi = f.type==="choice" && f.multiple;
    const w=fieldWrap(f.label|| (f.type==="toggle"?"Status":"Choose")); const seg=document.createElement("div"); seg.className="seg";
    const cur = Console.get(id,key);
    for(const opt of (f.options||[])){
      const val = typeof opt==="object"?opt.value:opt, txt = typeof opt==="object"?(opt.label||opt.value):opt;
      const b=document.createElement("button"); b.textContent=txt;
      const active = multi ? Array.isArray(cur)&&cur.includes(val) : cur===val;
      if(active) b.classList.add(STATUS_CLASS[String(val).toLowerCase()]||"on");
      b.onclick=()=>{
        if(multi){ let arr=Array.isArray(Console.get(id,key))?Console.get(id,key).slice():[];
          arr.includes(val)?arr=arr.filter(x=>x!==val):arr.push(val); Console.set(id,key,arr.length?arr:null); }
        else { Console.set(id,key, cur===val?null:val); }
        rerender(item);
      };
      seg.appendChild(b);
    }
    w.appendChild(seg); return w;
  }
  if(f.type==="rating"){
    const max=f.max||5, w=fieldWrap(f.label||"Rating"), box=document.createElement("div");
    const cur=Console.get(id,key)||0;
    if(f.style==="number"){ box.className="seg";
      for(let n=(f.min||1);n<=max;n++){ const b=document.createElement("button"); b.textContent=n;
        if(n===cur)b.classList.add("on"); b.onclick=()=>{Console.set(id,key,n===cur?null:n);rerender(item);}; box.appendChild(b);} }
    else { box.className="stars";
      for(let n=1;n<=max;n++){ const b=document.createElement("button"); b.textContent="★";
        if(n<=cur)b.classList.add("on"); b.onclick=()=>{Console.set(id,key,n===cur?null:n);rerender(item);}; box.appendChild(b);} }
    w.appendChild(box); return w;
  }
  if(f.type==="rank"){
    const w=fieldWrap(f.label||"Rank (drag to reorder)"); const ul=document.createElement("ul"); ul.className="rank";
    const opts=(f.options||[]).map(o=>typeof o==="object"?o:{value:o,label:o});
    let order=Console.get(id,key); if(!Array.isArray(order)||order.length!==opts.length) order=opts.map(o=>o.value);
    const byVal=Object.fromEntries(opts.map(o=>[o.value,o.label||o.value]));
    const commit=()=>{ Console.set(id,key,order.slice()); paint(); };
    const move=(i,d)=>{ const j=i+d; if(j<0||j>=order.length)return; [order[i],order[j]]=[order[j],order[i]]; commit(); };
    function paint(){ ul.innerHTML="";
      order.forEach((val,i)=>{ const li=document.createElement("li"); li.draggable=true; li.dataset.i=i;
        li.innerHTML=`<span class="ord">${i+1}.</span><span>${esc(byVal[val])}</span>
          <span class="mv"><button data-u>↑</button><button data-d>↓</button></span>`;
        li.querySelector("[data-u]").onclick=()=>move(i,-1);
        li.querySelector("[data-d]").onclick=()=>move(i,1);
        li.addEventListener("dragstart",e=>{li.classList.add("dragging");e.dataTransfer.setData("text/plain",i);});
        li.addEventListener("dragend",()=>li.classList.remove("dragging"));
        li.addEventListener("dragover",e=>e.preventDefault());
        li.addEventListener("drop",e=>{e.preventDefault();const from=+e.dataTransfer.getData("text/plain");
          const [m]=order.splice(from,1); order.splice(i,0,m); commit();});
        ul.appendChild(li); }); }
    paint(); if(!Console.get(id,key)) Console.set(id,key,order.slice()); w.appendChild(ul); return w;
  }
  const w=fieldWrap(f.label||key); w.innerHTML+=`<div class="body">[unsupported field type: ${esc(f.type)}]</div>`; return w;
}

function renderVisuals(item){
  const id=item.id, w=document.createElement("div"); w.className="field";
  w.innerHTML=`<div class="label">${esc(item.visualLabel||"Compare — choose one and comment")}</div>`;
  const grid=document.createElement("div"); grid.className="visuals";
  const pick=Console.get(id,"pick"); const notes=Console.get(id,"notes")||{};
  for(const v of item.visuals){
    const card=document.createElement("div"); card.className="vcard"+(pick===v.id?" chosen":"");
    const frame=document.createElement("div"); frame.className="frame";
    if(v.image){ const img=document.createElement("img"); img.src="/asset/"+encodeURI(v.image); img.alt=v.label||v.id; frame.appendChild(img); }
    else if(v.html){ frame.innerHTML=v.html; }
    const foot=document.createElement("div"); foot.className="vfoot";
    const head=document.createElement("div"); head.className="vhead";
    const choose=document.createElement("button"); choose.className="chip"+(pick===v.id?" ":"");
    choose.textContent = pick===v.id?"✓ Chosen":"Choose";
    if(pick===v.id) choose.classList.add("on");
    choose.onclick=()=>{ Console.set(id,"pick", pick===v.id?null:v.id); rerender(item); };
    head.innerHTML=`<b>${esc(v.label||v.id)}</b>`; head.appendChild(choose);
    const ta=document.createElement("textarea"); ta.placeholder="Notes on this option…"; ta.value=notes[v.id]||"";
    ta.addEventListener("input",()=>{ const n=Object.assign({},Console.get(id,"notes")||{});
      if(ta.value) n[v.id]=ta.value; else delete n[v.id]; Console.set(id,"notes",Object.keys(n).length?n:null); });
    foot.appendChild(head); foot.appendChild(ta);
    card.appendChild(frame); card.appendChild(foot); grid.appendChild(card);
  }
  w.appendChild(grid); return w;
}

function isAnswered(item){
  const r=RES.responses[item.id]; if(!r) return false;
  return Object.keys(r).some(k=>k!=="updatedAt" && r[k]!=null && r[k]!=="" &&
    !(Array.isArray(r[k])&&r[k].length===0) && !(typeof r[k]==="object"&&!Array.isArray(r[k])&&Object.keys(r[k]).length===0));
}
function markItem(el,item){
  el.dataset.answered=isAnswered(item)?"1":"0";
  const r=RES.responses[item.id]||{};
  const st=[r.status,r.pick].find(x=>x!=null);
  if(r.status) el.dataset.status=String(r.status).toLowerCase(); else delete el.dataset.status;
}
function rerender(item){ const old=[...itemsEl.children].find(x=>x.dataset.id===item.id);
  if(old){ const fresh=renderItem(item); old.replaceWith(fresh); } refreshSummary(); }

function refreshSummary(){
  const items=SPEC.items||[]; const total=items.length;
  const answered=items.filter(isAnswered).length;
  // tally the first toggle field's values across items (pass/fail/skip-style)
  const tally={};
  for(const it of items){ const r=RES.responses[it.id]; if(r&&r.status){const s=String(r.status);tally[s]=(tally[s]||0)+1;} }
  const chips=Object.entries(tally).map(([k,n])=>`<span><b>${n}</b> ${esc(k)}</span>`).join("");
  document.getElementById("summary").innerHTML =
     (total?`<span><b>${answered}</b>/${total} answered</span>`:"") + chips;
  const un=total-answered;
  document.getElementById("foot-note").textContent = un>0?`${un} item${un>1?"s":""} not yet answered`:"";
  for(const it of items){ const el=[...itemsEl.children].find(x=>x.dataset.id===it.id); if(el) markItem(el,it); }
}

// ---- persistence + submit ----------------------------------------------------
let t=null;
function saveDebounced(){ clearTimeout(t); t=setTimeout(save,400); }
function save(){ setSaved("saving…");
  return fetch("/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(RES)})
    .then(r=>{if(!r.ok)throw 0; setSaved("saved "+new Date().toLocaleTimeString());})
    .catch(()=>setSaved("⚠ save failed")); }
function setSaved(s){ document.getElementById("saved").textContent=s; }
function doSubmit(){
  save().finally(()=>{
    fetch("/done",{method:"POST"}).catch(()=>{}).finally(()=>{
      document.getElementById("done-overlay").classList.add("show");
    });
  });
}
document.getElementById("submit").onclick=doSubmit;
render();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or ctype.endswith("json") or "svg" in ctype else ""))
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            page = (PAGE
                    .replace("__TITLE__", (SPEC.get("title") or "live-console"))
                    .replace("__SPEC__", json.dumps(SPEC, ensure_ascii=False))
                    .replace("__SAVED__", json.dumps(load_results(), ensure_ascii=False)))
            self._send(200, page, "text/html")
        elif path == "/results":
            self._send(200, json.dumps(load_results(), ensure_ascii=False))
        elif path == "/spec":
            self._send(200, json.dumps(SPEC, ensure_ascii=False))
        elif path.startswith("/asset/"):
            got = resolve_asset(unquote(path[len("/asset/"):]))
            if got is None:
                self._send(404, json.dumps({"error": "asset not found / out of root"}))
            else:
                target, ctype = got
                self._send(200, target.read_bytes(), ctype)
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
                data.setdefault("_meta", {"done": False, "submittedAt": None})
                data.setdefault("responses", {})
                save_results(data)
                self._send(200, json.dumps({"ok": True}))
            except (ValueError, OSError) as e:
                self._send(400, json.dumps({"error": str(e)}))
        elif path == "/done":
            data = load_results()
            from datetime import datetime, timezone
            data["_meta"] = {"done": True, "submittedAt": datetime.now(timezone.utc).isoformat()}
            save_results(data)
            self._send(200, json.dumps({"ok": True}))
            # why: shut the server down AFTER the response flushes → process exits →
            # the agent's background-task watch fires and it reads RESULTS.
            threading.Thread(target=_server.shutdown, daemon=True).start()
        else:
            self._send(404, json.dumps({"error": "not found"}))


def main():
    global SPEC, SPEC_DIR, RESULTS, _server
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--results")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    SPEC = json.loads(spec_path.read_text())
    SPEC_DIR = spec_path.parent
    RESULTS = Path(args.results).resolve() if args.results else spec_path.with_suffix(".results.json")
    if not RESULTS.exists():
        save_results(load_results())

    _server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    port = _server.server_address[1]
    url = f"http://127.0.0.1:{port}"
    print(f"live-console: {SPEC.get('title','(untitled)')}")
    print(f"  url     : {url}")
    print(f"  results : {RESULTS}")
    print("  waiting for Submit (server exits on submit) — or read the results file anytime.")
    sys.stdout.flush()
    if not args.no_open and sys.platform == "darwin":
        try:
            subprocess.run(["open", url], check=False)
        except OSError:
            pass
    _server.serve_forever()
    print("live-console: submitted — server stopped.")


if __name__ == "__main__":
    main()
