#!/usr/bin/env python3
"""spec-kit-compound pipeline dashboard — read-only localhost view of the chain."""

import re
import json

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


_GOAL_RE = re.compile(r"^#\s*Intent:\s*(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")


def extract_goal(text):
    """Return the text after the first '# Intent:' marker, or ''."""
    m = _GOAL_RE.search(text)
    return m.group(1).strip() if m else ""


def extract_section(text, header):
    """Return stripped bullet lines under '## <header>' until the next '## ', or []."""
    out = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            if in_section:
                break
            in_section = line[3:].strip() == header
            continue
        if in_section:
            m = _BULLET_RE.match(line)
            if m:
                out.append(m.group(1).strip())
    return out


_L3_KINDS = {"L3a": "out-of-scope", "L3b": "constraint", "L3d": "expectation"}


def parse_intentguard(text):
    """Return {'verdict': str|None, 'drift': [...]} from an intentguard report."""
    verdict = parse_frontmatter(text).get("verdict")
    drift = []
    current = None  # active L3 level, or None
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
            current = None
            for level in _L3_KINDS:
                if head.startswith(level):
                    current = level
                    break
            continue
        if not current:
            continue
        m = _BULLET_RE.match(line)
        if not m:
            continue
        body = m.group(1).strip()
        upper = body.upper()
        if "BLOCKED" in upper:
            sev = "blocked"
        elif "REVIEW" in upper:
            sev = "review"
        else:
            continue  # PASS / clean line — not drift
        drift.append({"level": current, "kind": _L3_KINDS[current], "text": body, "severity": sev})
    return {"verdict": verdict, "drift": drift}


import os
import glob

STAGES = [
    "intent", "expectations", "specify", "plan",
    "tasks", "gapfill", "implement", "intentguard", "writeback",
]

# String the gapfill command stamps into tasks.md for appended tests.
_GAPFILL_MARKER = "speckit-compound-gapfill"

STAGE_DESCRIPTIONS = {
    "intent": "goal + constraints + failure conditions",
    "expectations": "success + edge scenarios (validator-only)",
    "specify": "spec.md from intent",
    "plan": "design + architecture",
    "tasks": "dependency-ordered task list",
    "gapfill": "add missing constraint/failure/OOS tests",
    "implement": "build (tasks checked off)",
    "intentguard": "L3 validation -> PASS / REVIEW / BLOCKED",
    "writeback": "persist ADRs / corrections / patterns",
}


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


def scan_state(repo_root, now=None, home=None):
    repo_root = os.path.abspath(repo_root)
    if home is None:
        home = os.path.expanduser("~")
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

        intent_text = _read(intent_path)
        exp_text = _read(exp_path) if os.path.isfile(exp_path) else ""
        guard_text = _read(guard_path) if os.path.isfile(guard_path) else ""
        guard_parsed = parse_intentguard(guard_text) if guard_text else {"verdict": None, "drift": []}
        guard_verdict = guard_parsed["verdict"]

        content = {
            "goal": extract_goal(intent_text),
            "constraints": extract_section(intent_text, "Constraints"),
            "failures": extract_section(intent_text, "Failure conditions"),
            "out_of_scope": extract_section(intent_text, "Out of scope"),
            "expectations_positive": extract_section(exp_text, "Positive scenarios"),
            "expectations_edge": extract_section(exp_text, "Edge / negative scenarios"),
        }

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
        stages["intentguard"]["drift"] = guard_parsed["drift"]

        _compute_states(stages)
        if guard_verdict == "BLOCKED":
            stages["intentguard"]["state"] = "blocked"

        features.append({
            "slug": slug,
            "status": fm.get("status", ""),
            "created": fm.get("created", ""),
            "spec_dir": rel_spec,
            "stages": stages,
            "content": content,
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
        "stage_descriptions": STAGE_DESCRIPTIONS,
        "features": features,
        "orphan_specs": orphan_specs,
        "compound": {"adr": _ls("adr"), "corrections": _ls("corrections"), "patterns": _ls("patterns")},
        "tokens": scan_tokens(home, repo_root),
    }


def _project_slug(repo_root):
    """Claude Code project-dir slug: abspath with os.sep and '.' replaced by '-'."""
    abspath = os.path.abspath(repo_root)
    return abspath.replace(os.sep, "-").replace(".", "-")


def _empty_tokens():
    z = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "billable": 0}
    return {"available": False, "total": dict(z), "sessions": []}


def _add_usage(acc, u):
    inp = u.get("input_tokens", 0) or 0
    out = u.get("output_tokens", 0) or 0
    cc = u.get("cache_creation_input_tokens", 0) or 0
    cr = u.get("cache_read_input_tokens", 0) or 0
    acc["input"] += inp
    acc["output"] += out
    acc["cache_creation"] += cc
    acc["cache_read"] += cr
    acc["billable"] += inp + out + cc


def scan_tokens(home, repo_root):
    proj = os.path.join(home, ".claude", "projects", _project_slug(repo_root))
    if not os.path.isdir(proj):
        return _empty_tokens()

    total = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "billable": 0}
    sessions = {}  # sid -> {"session","first","last","tokens"}
    for path in sorted(glob.glob(os.path.join(proj, "*.jsonl"))):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        o = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    u = (o.get("message") or {}).get("usage") or o.get("usage")
                    if not isinstance(u, dict):
                        continue
                    sid = o.get("sessionId", "unknown")
                    ts = o.get("timestamp", "")
                    s = sessions.setdefault(sid, {
                        "session": sid, "first": ts, "last": ts,
                        "tokens": {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "billable": 0},
                    })
                    if ts and (not s["first"] or ts < s["first"]):
                        s["first"] = ts
                    if ts and ts > s["last"]:
                        s["last"] = ts
                    _add_usage(s["tokens"], u)
                    _add_usage(total, u)
        except OSError:
            continue

    return {
        "available": True,
        "total": total,
        "sessions": sorted(sessions.values(), key=lambda x: x["first"]),
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
.content{display:none;margin-top:12px}
.row.open .content{display:block}
.content h3{font-family:var(--display);font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:14px 0 6px}
.content ul{margin:0;padding-left:18px} .content li{font-family:var(--mono);font-size:12px;color:#c9d1d9;margin:2px 0}
.goal{font-family:var(--display);font-size:15px;color:var(--text);margin-top:4px}
/* flowchart — the 9-stage chain lit per feature */
.flow{display:flex;gap:0;align-items:stretch;min-width:760px;margin:8px 0}
.fstep{flex:1;text-align:center;padding:8px 6px;border-radius:6px;border:1px solid #30363d;background:#0d1117;position:relative}
.fstep .n{font-family:var(--mono);font-size:11px;color:var(--muted)}
.fstep .lbl{font-family:var(--display);font-size:11px;margin:2px 0}
.fstep .desc{font-size:10px;color:var(--muted);line-height:1.3}
.fstep.done{border-color:var(--done)} .fstep.done .lbl{color:var(--done)}
.fstep.current{border-color:var(--accent);box-shadow:0 0 0 2px rgba(56,139,253,.2)} .fstep.current .lbl{color:var(--accent)}
.fstep.blocked{border-color:var(--blocked)} .fstep.blocked .lbl{color:var(--blocked)}
.farrow{align-self:center;color:#30363d;padding:0 4px;font-family:var(--mono)}
.drift{margin-top:14px;padding:12px;border:1px solid #30363d;border-radius:6px;background:#0d1117}
.drift .badge{font-family:var(--mono);font-size:11px;padding:2px 8px;border-radius:10px}
.badge.blocked{background:rgba(248,81,73,.15);color:var(--blocked)}
.badge.review{background:rgba(210,153,34,.15);color:var(--progress)}
.badge.pass{background:rgba(63,185,80,.15);color:var(--done)}
.drift li.blocked{color:var(--blocked)} .drift li.review{color:var(--progress)}
.about{display:none;padding:16px 28px;border-bottom:1px solid #21262d;color:var(--muted)}
.about.open{display:block}
.about svg{max-width:100%}
.toktotal{cursor:pointer}
</style>
</head>
<body>
<header>
  <h1>spec-kit-compound <span class="sub">· pipeline</span></h1>
  <div style="display:flex;gap:18px;align-items:baseline">
    <div class="live toktotal" id="tokens" title="Click for About / architecture">⌁ —</div>
    <div class="live" id="live"><span class="dot">●</span> connecting…</div>
  </div>
</header>
<section class="about" id="about" aria-label="About — architecture">
  <svg viewBox="0 0 760 90" role="img" aria-label="architecture">
    <defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#7D8590"/></marker></defs>
    <g font-family="JetBrains Mono, monospace" font-size="11" fill="#E6EDF3">
      <rect x="4" y="28" width="170" height="34" rx="5" fill="#161B22" stroke="#30363d"/>
      <text x="14" y="42">filesystem</text><text x="14" y="56" fill="#7D8590">docs/ · specs/ · ~/.claude</text>
      <line x1="178" y1="45" x2="244" y2="45" stroke="#7D8590" marker-end="url(#ah)"/>
      <rect x="248" y="28" width="150" height="34" rx="5" fill="#161B22" stroke="#30363d"/>
      <text x="258" y="49">scan_state()</text>
      <line x1="402" y1="45" x2="468" y2="45" stroke="#7D8590" marker-end="url(#ah)"/>
      <rect x="472" y="28" width="130" height="34" rx="5" fill="#161B22" stroke="#30363d"/>
      <text x="482" y="49">/api/state</text>
      <line x1="606" y1="45" x2="672" y2="45" stroke="#7D8590" marker-end="url(#ah)"/>
      <rect x="676" y="28" width="80" height="34" rx="5" fill="#161B22" stroke="#388BFD"/>
      <text x="686" y="42" fill="#388BFD">page</text><text x="686" y="56" fill="#7D8590">3s poll</text>
    </g>
  </svg>
  <div style="margin-top:8px;font-family:var(--mono);font-size:12px">Read-only · no dependencies · 127.0.0.1 · never runs chain commands.</div>
</section>
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

function flowHtml(feat, state){
  // flowchart — the 9-stage chain lit by the selected feature's stage states
  let h = '<div class="rowscroll"><div class="flow">';
  state.stages.forEach((name,i)=>{
    const st = feat.stages[name];
    const cls = st.state==="done"?"done":st.state==="current"?"current":st.state==="blocked"?"blocked":"";
    const desc = (state.stage_descriptions||{})[name] || "";
    h += `<div class="fstep ${cls}"><div class="n">${String(i+1).padStart(2,"0")}</div>
      <div class="lbl">${esc(name)}</div><div class="desc">${esc(desc)}</div></div>`;
    if(i<state.stages.length-1) h += '<div class="farrow">→</div>';
  });
  return h + '</div></div>';
}

function listBlock(title, items){
  if(!items || !items.length) return "";
  return `<h3>${esc(title)}</h3><ul>${items.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
}

function driftHtml(feat){
  const g = feat.stages.intentguard;
  if(!g.verdict && (!g.drift || !g.drift.length)) return "";
  const vk = g.verdict==="PASS"?"pass":g.verdict==="BLOCKED"?"blocked":"review";
  let h = `<div class="drift"><span class="badge ${vk}">${esc(g.verdict||"not validated")}</span>`;
  if(g.drift && g.drift.length){
    h += `<ul style="margin-top:8px;padding-left:18px">` +
      g.drift.map(x=>`<li class="${esc(x.severity)}"><b>${esc(x.level)}</b> ${esc(x.text)}</li>`).join("") + `</ul>`;
  }
  return h + '</div>';
}

function renderContent(feat, state){
  const c = feat.content || {};
  let h = '<div class="content">';
  if(c.goal) h += `<div class="goal">${esc(c.goal)}</div>`;
  h += flowHtml(feat, state);
  h += listBlock("Constraints", c.constraints);
  h += listBlock("Failure conditions", c.failures);
  h += listBlock("Out of scope", c.out_of_scope);
  h += listBlock("Expectations — positive", c.expectations_positive);
  h += listBlock("Expectations — edge", c.expectations_edge);
  h += driftHtml(feat);
  h += `<h3>Files</h3><ul>${(feat.files||[]).map(f=>`<li>${esc(f)}</li>`).join("")}</ul>`;
  return h + '</div>';
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
      ${renderContent(feat, state)}
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
    const t = state.tokens || {};
    const tokEl = document.getElementById("tokens");
    if(t.available){
      const b = t.total.billable;
      const human = b>=1e6 ? (b/1e6).toFixed(1)+"M" : b>=1e3 ? (b/1e3).toFixed(0)+"k" : String(b);
      tokEl.textContent = `⌁ ${human} tokens · ${t.sessions.length} sessions`;
    } else {
      tokEl.textContent = "⌁ no local transcripts";
    }
    live.classList.remove("stale");
    live.innerHTML = `<span class="dot">●</span> live · scanned ${esc((state.scanned_at||"").slice(11,19)||"now")}`;
  }catch(e){
    live.classList.add("stale");
    live.innerHTML = '<span class="dot">●</span> disconnected — is dashboard.py running?';
  }
}
poll();
setInterval(poll, 3000);
document.getElementById("tokens").addEventListener("click",()=>{
  document.getElementById("about").classList.toggle("open");
});
</script>
</body>
</html>
"""


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
