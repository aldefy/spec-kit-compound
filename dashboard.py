#!/usr/bin/env python3
"""spec-kit-compound pipeline dashboard — read-only localhost view of the chain."""

import re

_TASK_RE = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s")


def parse_frontmatter(text):
    """Return flat key:value scalars from a leading ---fenced YAML block, or {}."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out


def parse_tasks(text):
    """Count GFM checkbox lines: {'done': n_checked, 'total': n_boxes}."""
    done = total = 0
    for line in text.splitlines():
        m = _TASK_RE.match(line)
        if m:
            total += 1
            if m.group(1) in ("x", "X"):
                done += 1
    return {"done": done, "total": total}


import os
import glob

STAGES = [
    "intent", "expectations", "specify", "plan",
    "tasks", "gapfill", "implement", "intentguard", "writeback",
]

# String the gapfill command stamps into tasks.md for appended tests.
_GAPFILL_MARKER = "speckit-compound-gapfill"


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _normalize(name):
    """Lowercase, strip a leading NNN- numeric prefix (spec-dir convention)."""
    base = os.path.basename(name).lower()
    return re.sub(r"^\d+-", "", base)


def _stage_present(spec_dir_abs, filename):
    return os.path.isfile(os.path.join(spec_dir_abs, filename))


def _compute_states(stages):
    """Mark the first non-done stage as 'current'. Blocked is applied separately."""
    seen_pending = False
    for name in STAGES:
        st = stages[name]
        if st["state"] == "done":
            continue
        if not seen_pending:
            st["state"] = "current"
            seen_pending = True
    return stages


def scan_state(repo_root, now=None):
    repo_root = os.path.abspath(repo_root)
    intents = sorted(glob.glob(os.path.join(repo_root, "docs/intents/*.intent.md")))

    # Map normalized spec-dir name -> relative spec dir path.
    spec_dirs = {}
    specs_root = os.path.join(repo_root, "specs")
    if os.path.isdir(specs_root):
        for entry in sorted(os.listdir(specs_root)):
            full = os.path.join(specs_root, entry)
            if os.path.isdir(full):
                spec_dirs[_normalize(entry)] = os.path.relpath(full, repo_root)

    features = []
    matched_dirs = set()
    for intent_path in intents:
        fname = os.path.basename(intent_path)
        slug_from_file = fname[: -len(".intent.md")]
        fm = parse_frontmatter(_read(intent_path))
        slug = fm.get("slug") or slug_from_file

        rel_spec = spec_dirs.get(_normalize(slug))
        if rel_spec:
            matched_dirs.add(_normalize(slug))
        spec_abs = os.path.join(repo_root, rel_spec) if rel_spec else None

        exp_path = os.path.join(repo_root, "docs/expectations", slug + ".expectations.md")
        guard_path = os.path.join(repo_root, "docs/intents", slug + ".intentguard.md")

        tasks_text = _read(os.path.join(spec_abs, "tasks.md")) if spec_abs else ""
        task_counts = parse_tasks(tasks_text)

        guard_verdict = None
        if os.path.isfile(guard_path):
            guard_verdict = parse_frontmatter(_read(guard_path)).get("verdict")

        files = [os.path.relpath(intent_path, repo_root)]
        if os.path.isfile(exp_path):
            files.append(os.path.relpath(exp_path, repo_root))
        if os.path.isfile(guard_path):
            files.append(os.path.relpath(guard_path, repo_root))

        def done(flag):
            return {"state": "done"} if flag else {"state": "pending"}

        stages = {
            "intent": done(True),
            "expectations": done(os.path.isfile(exp_path)),
            "specify": done(bool(spec_abs) and _stage_present(spec_abs, "spec.md")),
            "plan": done(bool(spec_abs) and _stage_present(spec_abs, "plan.md")),
            "tasks": done(bool(spec_abs) and _stage_present(spec_abs, "tasks.md")),
            "gapfill": done(_GAPFILL_MARKER in tasks_text),
            "implement": done(task_counts["total"] > 0 and task_counts["done"] == task_counts["total"]),
            "intentguard": done(os.path.isfile(guard_path)),
            "writeback": done(False),
        }
        stages["tasks"].update(done=task_counts["done"], total=task_counts["total"])
        stages["intentguard"]["verdict"] = guard_verdict

        _compute_states(stages)
        if guard_verdict == "BLOCKED":
            stages["intentguard"]["state"] = "blocked"

        features.append({
            "slug": slug,
            "status": fm.get("status", ""),
            "created": fm.get("created", ""),
            "spec_dir": rel_spec,
            "stages": stages,
            "files": files,
        })

    orphan_specs = []
    for norm, rel in spec_dirs.items():
        if norm in matched_dirs:
            continue
        abs_dir = os.path.join(repo_root, rel)
        present = [
            stage for stage, fn in (("specify", "spec.md"), ("plan", "plan.md"), ("tasks", "tasks.md"))
            if os.path.isfile(os.path.join(abs_dir, fn))
        ]
        orphan_specs.append({"dir": rel, "stages_present": present})

    def _ls(sub):
        p = os.path.join(repo_root, "docs/compound", sub)
        return sorted(os.path.basename(x) for x in glob.glob(os.path.join(p, "*.md"))) if os.path.isdir(p) else []

    return {
        "scanned_at": now or "",
        "repo": os.path.basename(repo_root),
        "stages": STAGES,
        "features": features,
        "orphan_specs": orphan_specs,
        "compound": {"adr": _ls("adr"), "corrections": _ls("corrections"), "patterns": _ls("patterns")},
    }


PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>spec-kit-compound · pipeline</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');
:root{
  --ground:#0E1116; --surface:#161B22; --text:#E6EDF3; --muted:#7D8590;
  --done:#3FB950; --progress:#D29922; --blocked:#F85149; --accent:#388BFD;
  --display:'Space Grotesk',system-ui,sans-serif;
  --body:'Inter',system-ui,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--text);font-family:var(--body);
  font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
header{display:flex;justify-content:space-between;align-items:baseline;
  padding:20px 28px;border-bottom:1px solid #21262d}
h1{font-family:var(--display);font-weight:700;font-size:18px;margin:0;letter-spacing:-.01em}
h1 .sub{color:var(--muted);font-weight:500}
.live{font-family:var(--mono);font-size:12px;color:var(--muted)}
.live .dot{color:var(--done)}
.live.stale .dot{color:var(--muted)}
main{padding:20px 28px;max-width:1200px}
.legend,.row{display:grid;grid-template-columns:200px 1fr;gap:16px;align-items:center}
.legend{padding:0 0 12px;color:var(--muted);font-family:var(--mono);font-size:11px}
.lanes{display:flex;justify-content:space-between}
.lane{flex:1;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rowscroll{overflow-x:auto}
.row{padding:14px 0;border-top:1px solid #21262d;cursor:pointer}
.slug{font-family:var(--display);font-weight:500}
.rail{display:flex;align-items:center;min-width:520px}
.node{width:14px;height:14px;border-radius:50%;border:2px solid var(--muted);
  background:transparent;flex:none}
.seg{flex:1;height:2px;background:#30363d;border-top:1px dashed #30363d}
.node.done{background:var(--done);border-color:var(--done)}
.seg.done{background:var(--done);border-top:2px solid var(--done)}
.node.current{border-color:var(--accent);box-shadow:0 0 0 3px rgba(56,139,253,.25);
  animation:pulse 1.8s ease-in-out infinite}
.node.blocked{background:var(--blocked);border-color:var(--blocked)}
.meta{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:6px}
.meta .blocked{color:var(--blocked)} .meta .review{color:var(--progress)} .meta .pass{color:var(--done)}
.panel{margin-top:28px;padding:16px;background:var(--surface);border:1px solid #21262d;border-radius:8px}
.panel h2{font-family:var(--display);font-size:13px;margin:0 0 10px;letter-spacing:.02em;color:var(--muted);text-transform:uppercase}
.files{font-family:var(--mono);font-size:12px;color:var(--muted);display:none;margin-top:10px}
.row.open .files{display:block}
.empty{color:var(--muted);text-align:center;padding:60px 0;font-family:var(--mono)}
@keyframes pulse{0%,100%{box-shadow:0 0 0 3px rgba(56,139,253,.25)}50%{box-shadow:0 0 0 6px rgba(56,139,253,.08)}}
@media (prefers-reduced-motion: reduce){.node.current{animation:none}}
</style>
</head>
<body>
<header>
  <h1>spec-kit-compound <span class="sub">· pipeline</span></h1>
  <div class="live" id="live"><span class="dot">●</span> connecting…</div>
</header>
<main id="main"><div class="empty">Loading…</div></main>
<script>
const STAGE_LABELS = ["INTENT","EXP","SPEC","PLAN","TASKS","GAP","IMPL","GUARD","WB"];
function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}

function railHtml(feat){
  let h = '<div class="rail">';
  feat.stages_order.forEach((name,i)=>{
    const st = feat.stages[name];
    const cls = st.state==="done"?"done":st.state==="current"?"current":st.state==="blocked"?"blocked":"";
    h += `<span class="node ${cls}" title="${esc(name)}: ${esc(st.state)}"></span>`;
    if(i < feat.stages_order.length-1){
      const segDone = st.state==="done" ? "done":"";
      h += `<span class="seg ${segDone}"></span>`;
    }
  });
  return h + '</div>';
}

function metaHtml(feat){
  const t = feat.stages.tasks;
  const g = feat.stages.intentguard;
  let bits = [];
  if(t.total>0) bits.push(`tasks ${t.done}/${t.total}`);
  if(g.verdict){
    const k = g.verdict==="PASS"?"pass":g.verdict==="BLOCKED"?"blocked":"review";
    bits.push(`<span class="${k}">GUARD ${esc(g.verdict)}</span>`);
  }
  if(!feat.spec_dir) bits.push("no spec dir matched");
  return bits.join(" · ");
}

function render(state){
  const main = document.getElementById("main");
  if(!state.features.length && !state.orphan_specs.length){
    main.innerHTML = '<div class="empty">No features yet. Run <b>/speckit-compound-intent</b> to start the chain.</div>';
    return;
  }
  let h = '<div class="legend"><div></div><div class="rowscroll"><div class="lanes" style="min-width:520px">';
  STAGE_LABELS.forEach((l,i)=>{ h += `<div class="lane">${String(i+1).padStart(2,"0")} ${l}</div>`; });
  h += '</div></div></div>';

  state.features.forEach(feat=>{
    feat.stages_order = state.stages;
    h += `<div class="row" tabindex="0">
      <div><div class="slug">${esc(feat.slug)}</div><div class="meta">${metaHtml(feat)}</div></div>
      <div class="rowscroll">${railHtml(feat)}</div>
      <div class="files">${feat.files.map(esc).join("<br>")}</div>
    </div>`;
  });

  if(state.orphan_specs.length){
    h += '<div class="panel"><h2>Orphan spec dirs (no intent)</h2>';
    state.orphan_specs.forEach(o=>{ h += `<div class="meta">${esc(o.dir)} — ${o.stages_present.map(esc).join(", ")||"empty"}</div>`; });
    h += '</div>';
  }

  const c = state.compound;
  h += `<div class="panel"><h2>Compound store</h2>
    <div class="meta">ADRs ${c.adr.length} · Corrections ${c.corrections.length} · Patterns ${c.patterns.length}</div>
    <div class="meta">${[...c.adr,...c.corrections,...c.patterns].map(esc).join("  ·  ")||"empty — grows from your first writeback"}</div>
  </div>`;

  main.innerHTML = h;
  main.querySelectorAll(".row").forEach(r=>{
    const toggle=()=>r.classList.toggle("open");
    r.addEventListener("click",toggle);
    r.addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();toggle();}});
  });
}

async function poll(){
  const live = document.getElementById("live");
  try{
    const r = await fetch("/api/state",{cache:"no-store"});
    const state = await r.json();
    render(state);
    live.classList.remove("stale");
    live.innerHTML = `<span class="dot">●</span> live · scanned ${esc((state.scanned_at||"").slice(11,19)||"now")}`;
  }catch(e){
    live.classList.add("stale");
    live.innerHTML = '<span class="dot">●</span> disconnected — is dashboard.py running?';
  }
}
poll();
setInterval(poll, 3000);
</script>
</body>
</html>
"""


import json
import argparse
import datetime
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def find_repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, "extension.yml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start)
        cur = parent


def make_handler(repo_root):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence default stderr logging
            pass

        def _send(self, status, body, ctype):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE_HTML, "text/html")
            elif self.path == "/api/state":
                now = datetime.datetime.now().isoformat(timespec="seconds")
                self._send(200, json.dumps(scan_state(repo_root, now=now)), "application/json")
            else:
                self._send(404, "not found", "text/plain")

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description="spec-kit-compound pipeline dashboard")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    args = ap.parse_args(argv)

    repo_root = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
    handler = make_handler(repo_root)

    httpd = None
    for port in range(args.port, args.port + 11):
        try:
            httpd = HTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            continue
    if httpd is None:
        print("error: no free port in range", flush=True)
        return 1

    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"spec-kit-compound dashboard → {url}  (scanning {repo_root})", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
