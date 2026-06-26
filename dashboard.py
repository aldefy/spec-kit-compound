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


def _is_token_prefix(short, long):
    """True if hyphen-tokenized `short` is a leading run of `long`'s tokens.

    Token-level (not substring) so "selective-forwarding" matches
    "selective-forwarding-backend" but "auth" does NOT match "oauth".
    """
    a, b = short.split("-"), long.split("-")
    return len(a) <= len(b) and b[: len(a)] == a


def _match_spec_dir(slug, spec_dirs):
    """Resolve a normalized spec-dir key for an intent slug.

    Exact normalized match wins. Otherwise fall back to a token-prefix match
    in either direction (dir name a prefix of the slug, or vice versa) so that
    a slug like "selective-forwarding-backend" still binds to the spec dir
    "255-selective-forwarding". Returns the matching key or None.
    """
    nslug = _normalize(slug)
    if nslug in spec_dirs:
        return nslug
    for key in spec_dirs:
        if _is_token_prefix(key, nslug) or _is_token_prefix(nslug, key):
            return key
    return None


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

        match_key = _match_spec_dir(slug, spec_dirs)
        rel_spec = spec_dirs.get(match_key) if match_key else None
        if match_key:
            matched_dirs.add(match_key)
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

        # Map each stage to the document it represents, when that file exists,
        # so the UI can open the raw markdown on click. Paths are repo-relative.
        def _rel(p):
            return os.path.relpath(p, repo_root)

        stage_files = {"intent": _rel(intent_path)}
        if os.path.isfile(exp_path):
            stage_files["expectations"] = _rel(exp_path)
        if spec_abs:
            for stage, fn in (("specify", "spec.md"), ("plan", "plan.md"), ("tasks", "tasks.md")):
                fp = os.path.join(spec_abs, fn)
                if os.path.isfile(fp):
                    stage_files[stage] = _rel(fp)
            stage_files["gapfill"] = stage_files.get("tasks")  # gapfill appends to tasks.md
        if os.path.isfile(guard_path):
            stage_files["intentguard"] = _rel(guard_path)

        features.append({
            "slug": slug,
            "status": fm.get("status", ""),
            "created": fm.get("created", ""),
            "spec_dir": rel_spec,
            "stages": stages,
            "stage_files": {k: v for k, v in stage_files.items() if v},
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
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>spec-kit-compound · pipeline</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Doto:wght@400;600;700&family=Space+Grotesk:wght@300;400;500;700&family=Space+Mono:wght@400;700&display=swap');

:root{
  --black:#000000; --surface:#111111; --raised:#1A1A1A; --border:#222222; --border-vis:#333333;
  --t-disabled:#666666; --t-secondary:#999999; --t-primary:#E8E8E8; --t-display:#FFFFFF;
  --accent:#D71921; --success:#4A9E5C; --warning:#D4A843; --interactive:#5B9BF6;
  --display:'Doto',"Space Mono",monospace;
  --ui:'Space Grotesk',system-ui,sans-serif;
  --mono:'Space Mono',ui-monospace,monospace;
}
:root[data-theme="light"]{
  --black:#F5F5F5; --surface:#FFFFFF; --raised:#F0F0F0; --border:#E8E8E8; --border-vis:#CCCCCC;
  --t-disabled:#999999; --t-secondary:#666666; --t-primary:#1A1A1A; --t-display:#000000;
  --interactive:#007AFF;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--black);color:var(--t-primary);font-family:var(--ui);
  font-size:14px;line-height:1.5;font-weight:300;-webkit-font-smoothing:antialiased;
  display:flex;flex-direction:column;height:100vh;overflow:hidden;
  transition:background .3s cubic-bezier(.25,.1,.25,1),color .3s cubic-bezier(.25,.1,.25,1)}

/* labels: Space Mono ALL CAPS — the one consistent voice */
.lbl{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--t-secondary)}
.lbl-dim{color:var(--t-disabled)}

/* ── header ── */
header{display:flex;justify-content:space-between;align-items:center;
  padding:0 24px;height:56px;border-bottom:1px solid var(--border);flex:none;gap:20px}
.wordmark{font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--t-primary);white-space:nowrap}
.wordmark .repo{color:var(--t-disabled)}
.hctl{display:flex;gap:20px;align-items:center}
.heartbeat{display:flex;gap:8px;align-items:center;font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--t-secondary)}
.heartbeat .dot{width:6px;height:6px;border-radius:50%;background:var(--success)}
.heartbeat.stale .dot{background:var(--t-disabled)}
/* theme toggle: segmented control */
.seg{display:flex;border:1px solid var(--border-vis);border-radius:6px;overflow:hidden}
.seg button{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  background:transparent;color:var(--t-secondary);border:0;padding:6px 11px;cursor:pointer;transition:.2s ease-out}
.seg button.on{background:var(--t-display);color:var(--black)}

/* ── master/detail ── */
.app{flex:1;display:grid;grid-template-columns:288px 1fr;min-height:0}
.master{border-right:1px solid var(--border);overflow-y:auto}
.master .grouphd{padding:20px 22px 10px}
.feat{padding:16px 22px;border-bottom:1px solid var(--border);cursor:pointer;transition:.2s ease-out}
.feat:hover{background:var(--surface)}
.feat.sel{background:var(--surface)}
.feat.sel .name{color:var(--t-display)}
.feat .name{font-family:var(--ui);font-weight:400;font-size:14px;color:var(--t-primary);
  word-break:break-word;line-height:1.3}
.feat .meta{margin-top:10px;display:flex;justify-content:space-between;align-items:center;gap:8px}
/* mini segmented bar */
.minibar{display:flex;gap:2px;margin-top:11px}
.minibar i{flex:1;height:4px;background:var(--border)}
.minibar i.done{background:var(--t-display)} .minibar i.current{background:var(--success)}
.minibar i.blocked{background:var(--accent)}
.statetxt{font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase}
.statetxt.pass{color:var(--success)} .statetxt.blocked{color:var(--accent)}
.statetxt.review{color:var(--warning)} .statetxt.none{color:var(--t-disabled)}

/* ── detail ── */
.detail{overflow-y:auto;padding:0 40px 96px}
.detail .empty{color:var(--t-disabled);font-family:var(--mono);text-transform:uppercase;letter-spacing:.06em;text-align:center;padding:120px 20px}

/* HERO — the one expressive moment (Section 2.6 single break) */
.hero{padding:48px 0 8px;display:flex;align-items:flex-end;justify-content:space-between;gap:32px;flex-wrap:wrap}
.hero .left{display:flex;align-items:baseline;gap:16px}
.bignum{font-family:var(--display);font-weight:700;font-size:96px;line-height:.9;letter-spacing:-.03em;color:var(--t-display)}
.bignum .of{color:var(--t-disabled)}
.heroside{display:flex;flex-direction:column;gap:6px;padding-bottom:10px}
.herostate{font-family:var(--mono);font-weight:700;font-size:18px;letter-spacing:.04em;text-transform:uppercase}
.herostate.pass{color:var(--success)} .herostate.blocked{color:var(--accent)}
.herostate.review{color:var(--warning)} .herostate.none{color:var(--t-secondary)}
.heroname{font-family:var(--ui);font-weight:500;font-size:24px;letter-spacing:-.01em;color:var(--t-display);max-width:46ch;line-height:1.15}
.herofacts{display:flex;gap:18px;flex-wrap:wrap;margin-top:4px}
.herofacts .lbl span{color:var(--t-primary);font-family:var(--mono);text-transform:none;letter-spacing:0}
.goal{font-family:var(--ui);font-weight:300;font-size:16px;line-height:1.55;color:var(--t-primary);max-width:68ch;margin:24px 0 0}

/* ── the chain: segmented progress bar (signature viz) ── */
.chainhd{display:flex;justify-content:space-between;align-items:baseline;margin:40px 0 12px}
.chain{display:flex;gap:3px}
.stage{flex:1;min-width:0;background:transparent;border:0;cursor:pointer;padding:0;text-align:left;
  font-family:inherit;color:inherit;display:flex;flex-direction:column;gap:8px}
.stage:disabled{cursor:default}
.stage .blk{height:10px;background:var(--border);transition:background .2s ease-out}
.stage.done .blk{background:var(--t-display)}
.stage.current .blk{background:var(--success)}
.stage.blocked .blk{background:var(--accent)}
.stage .cap{font-family:var(--mono);font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:var(--t-disabled);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stage.done .cap,.stage.current .cap{color:var(--t-secondary)}
.stage.sel .blk{outline:1px solid var(--interactive);outline-offset:2px}
.stage.sel .cap{color:var(--interactive)}
.stage:not(:disabled):hover .cap{color:var(--t-primary)}
.stage .num{font-family:var(--mono);font-size:9px;color:var(--t-disabled);letter-spacing:.05em}

/* ── doc viewer ── */
.viewer{margin-top:36px}
.vh{display:flex;justify-content:space-between;align-items:center;gap:16px;
  padding-bottom:12px;border-bottom:1px solid var(--border)}
.vh .path{font-family:var(--mono);font-size:11px;letter-spacing:.04em;color:var(--t-secondary);word-break:break-all}
.vh .path b{color:var(--t-primary);text-transform:uppercase;letter-spacing:.08em}
.vbody{padding:18px 0 0;max-height:46vh;overflow:auto}
.vbody h3{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--t-secondary);margin:22px 0 10px} .vbody h3:first-child{margin-top:0}
.vbody ul{margin:0;padding:0;list-style:none}
.vbody li{font-family:var(--ui);font-weight:300;font-size:14px;color:var(--t-primary);
  padding:7px 0;border-bottom:1px solid var(--border);line-height:1.45}
.vbody .raw{font-family:var(--mono);font-size:12.5px;line-height:1.7;white-space:pre-wrap;
  word-break:break-word;color:var(--t-primary);margin:0}
.vbody .tasklist li{font-family:var(--mono);font-size:12px;display:flex;gap:10px}
.vbody .tasklist li .box{color:var(--t-disabled)}
.vbody .tasklist li.x .box{color:var(--success)}
.vbody .loading{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--t-disabled)}
.vbody .drift li.blocked{color:var(--accent)} .vbody .drift li.review{color:var(--warning)}
.vbody .drift b{font-family:var(--mono);font-size:11px;letter-spacing:.06em;margin-right:8px}
.gbadge{font-family:var(--mono);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.gbadge.pass{color:var(--success)} .gbadge.blocked{color:var(--accent)} .gbadge.review{color:var(--warning)}

/* ── footer stats: stat rows, no cards ── */
.stats{margin-top:48px;display:grid;grid-template-columns:1fr 1fr;gap:0 48px}
.statgroup{border-top:1px solid var(--border-vis);padding-top:14px}
.statrow{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;gap:12px}
.statrow .k{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--t-secondary)}
.statrow .v{font-family:var(--mono);font-size:13px;color:var(--t-primary)}
.statrow .v.dim{color:var(--t-disabled)}
.storelist{font-family:var(--mono);font-size:11px;color:var(--t-disabled);line-height:1.7;margin-top:8px;word-break:break-word}
.footnote{margin-top:40px;font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--t-disabled)}

@media (max-width:860px){
  .app{grid-template-columns:1fr;grid-template-rows:auto 1fr}
  .master{border-right:0;border-bottom:1px solid var(--border);max-height:32vh}
  .detail{padding:0 22px 64px}
  .bignum{font-size:64px}
  .stats{grid-template-columns:1fr;gap:0}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<header>
  <div class="wordmark">SPEC·KIT·COMPOUND <span class="repo" id="repo">— PIPELINE</span></div>
  <div class="hctl">
    <div class="seg" id="themeseg">
      <button data-th="dark" class="on">DARK</button>
      <button data-th="light">LIGHT</button>
    </div>
    <div class="heartbeat" id="hb"><span class="dot"></span><span id="hbtxt">CONNECTING</span></div>
  </div>
</header>

<div class="app">
  <aside class="master" id="master"></aside>
  <section class="detail" id="detail"><div class="empty">[ LOADING PIPELINE ]</div></section>
</div>

<script>
const LABELS={intent:"INTENT",expectations:"EXPECT",specify:"SPEC",plan:"PLAN",tasks:"TASKS",gapfill:"GAPFILL",implement:"IMPL",intentguard:"GUARD",writeback:"WRITEBACK"};
let STATE=null, SEL=null, SELSTAGE=null, VIEWMODE="summary";
const docCache={};

function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function human(n){return n>=1e6?(n/1e6).toFixed(2)+"M":n>=1e3?(n/1e3).toFixed(0)+"K":String(n);}
function stageCls(st){return st.state==="done"?"done":st.state==="current"?"current":st.state==="blocked"?"blocked":"";}

function guardChip(feat){
  const g=feat.stages.intentguard;
  if(g.state==="blocked"||g.verdict==="BLOCKED") return ['blocked','BLOCKED'];
  if(g.verdict==="PASS") return ['pass','GUARD PASS'];
  if(g.verdict) return ['review',g.verdict];
  return ['none','NOT VALIDATED'];
}
function doneCount(feat){ return STATE.stages.filter(n=>feat.stages[n].state==="done").length; }

/* ── master ── */
function renderMaster(){
  const m=document.getElementById("master");
  const feats=STATE.features||[];
  let h=`<div class="grouphd lbl">${feats.length} FEATURE${feats.length===1?"":"S"}</div>`;
  if(!feats.length) h+=`<div class="feat" style="cursor:default"><div class="name lbl">RUN /SPECKIT-COMPOUND-INTENT</div></div>`;
  feats.forEach(f=>{
    const [ck,ctxt]=guardChip(f);
    const bars=STATE.stages.map(n=>`<i class="${stageCls(f.stages[n])}"></i>`).join("");
    const t=f.stages.tasks;
    h+=`<div class="feat ${f.slug===SEL?'sel':''}" data-slug="${esc(f.slug)}">
      <div class="name">${esc(f.slug)}</div>
      <div class="minibar">${bars}</div>
      <div class="meta"><span class="statetxt ${ck}">${ctxt}</span>${t.total>0?`<span class="lbl lbl-dim">${t.done}/${t.total} TASKS</span>`:''}</div>
    </div>`;
  });
  if((STATE.orphan_specs||[]).length){
    h+=`<div class="grouphd lbl lbl-dim">ORPHAN SPECS</div>`;
    STATE.orphan_specs.forEach(o=>{
      h+=`<div class="feat" style="cursor:default"><div class="name lbl">${esc(o.dir)}</div>
        <div class="meta"><span class="lbl lbl-dim">${(o.stages_present||[]).map(esc).join(" · ")||"EMPTY"}</span></div></div>`;
    });
  }
  m.innerHTML=h;
  m.querySelectorAll(".feat[data-slug]").forEach(el=>{
    el.onclick=()=>{ SEL=el.dataset.slug; SELSTAGE=null; renderMaster(); renderDetail(); };
  });
}

/* ── detail ── */
function feature(){ return (STATE.features||[]).find(f=>f.slug===SEL); }

function hasSummary(feat,stage){
  const c=feat.content||{};
  if(stage==="intent") return !!(c.goal||(c.constraints||[]).length||(c.failures||[]).length||(c.out_of_scope||[]).length);
  if(stage==="expectations") return !!((c.expectations_positive||[]).length||(c.expectations_edge||[]).length);
  if(stage==="intentguard") return !!(feat.stages.intentguard.verdict||(feat.stages.intentguard.drift||[]).length);
  return false;
}
function listBlock(t,items){ return (!items||!items.length)?"":`<h3>${esc(t)}</h3><ul>${items.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`; }
function summaryFor(feat,stage){
  const c=feat.content||{};
  if(stage==="intent") return (c.goal?`<h3>Goal</h3><ul><li>${esc(c.goal)}</li></ul>`:"")+listBlock("Constraints",c.constraints)+listBlock("Failure conditions",c.failures)+listBlock("Out of scope",c.out_of_scope);
  if(stage==="expectations") return listBlock("Positive scenarios",c.expectations_positive)+listBlock("Edge / negative scenarios",c.expectations_edge);
  if(stage==="intentguard"){
    const g=feat.stages.intentguard, vk=g.verdict==="PASS"?"pass":g.verdict==="BLOCKED"?"blocked":"review";
    let h=`<div class="gbadge ${vk}">${esc(g.verdict||"NOT VALIDATED")}</div>`;
    if(g.drift&&g.drift.length) h+=`<ul class="drift" style="margin-top:12px">`+g.drift.map(x=>`<li class="${esc(x.severity)}"><b>${esc(x.level)}</b>${esc(x.text)}</li>`).join("")+`</ul>`;
    return h;
  }
  return "";
}
function rawHtml(stage,text){
  if(text==null) return `<div class="loading">[ LOADING ]</div>`;
  if(stage==="tasks"||stage==="gapfill"){
    const items=text.split("\n").map(l=>{
      const m=l.match(/^\s*[-*]\s+\[( |x|X)\]\s+(.*)$/);
      return m?`<li class="${m[1]===' '?'':'x'}"><span class="box">${m[1]===' '?'[ ]':'[x]'}</span>${esc(m[2])}</li>`:null;
    }).filter(Boolean);
    if(items.length) return `<ul class="tasklist">${items.join("")}</ul>`;
  }
  return `<pre class="raw">${esc(text)}</pre>`;
}
async function fetchDoc(path){
  if(docCache[path]) return docCache[path];
  try{ const r=await fetch("/api/doc?path="+encodeURIComponent(path),{cache:"no-store"}); docCache[path]=await r.json(); }
  catch(e){ docCache[path]={content:"[ FAILED TO LOAD ]"}; }
  return docCache[path];
}

function renderViewer(){
  const feat=feature(), wrap=document.getElementById("viewer");
  if(!wrap) return;
  if(!SELSTAGE){ wrap.innerHTML=`<div class="vbody"><div class="loading">[ SELECT A STAGE TO READ ITS DOCUMENT ]</div></div>`; return; }
  const path=(feat.stage_files||{})[SELSTAGE], label=LABELS[SELSTAGE]||SELSTAGE, summaryOk=hasSummary(feat,SELSTAGE);
  if(VIEWMODE==="summary" && !summaryOk) VIEWMODE="raw";
  let body;
  if(VIEWMODE==="summary"){ body=summaryFor(feat,SELSTAGE); }
  else{ const doc=path?docCache[path]:null; body=rawHtml(SELSTAGE,doc?doc.content:null);
    if(path&&!doc) fetchDoc(path).then(()=>{ if(SELSTAGE&&VIEWMODE==="raw") renderViewer(); }); }
  const tabs = summaryOk
    ? `<button data-m="summary" class="${VIEWMODE==='summary'?'on':''}">SUMMARY</button>
       <button data-m="raw" class="${VIEWMODE==='raw'?'on':''}" ${path?"":"disabled"}>RAW</button>`
    : `<button data-m="raw" class="on">DOCUMENT</button>`;
  wrap.innerHTML=`<div class="vh">
      <div class="path"><b>${esc(label)}</b> · ${path?esc(path):"NO FILE"}</div>
      <div class="seg vtabs">${tabs}</div>
    </div><div class="vbody">${body}</div>`;
  wrap.querySelectorAll(".vtabs button").forEach(b=>{ if(!b.disabled) b.onclick=()=>{ VIEWMODE=b.dataset.m; renderViewer(); }; });
}

function chainHtml(feat){
  let h='<div class="chain">';
  STATE.stages.forEach((name,i)=>{
    const st=feat.stages[name], hasDoc=!!(feat.stage_files||{})[name];
    const cls=stageCls(st)+(name===SELSTAGE?" sel":"");
    h+=`<button class="stage ${cls}" data-stage="${esc(name)}" ${hasDoc?"":"disabled"}>
        <span class="blk"></span>
        <span class="cap">${esc(LABELS[name]||name)}</span>
      </button>`;
  });
  return h+'</div>';
}

function renderDetail(){
  const d=document.getElementById("detail"), feat=feature();
  if(!feat){ d.innerHTML=`<div class="empty">${(STATE.features||[]).length?"[ SELECT A FEATURE ]":"[ NO FEATURES — RUN /SPECKIT-COMPOUND-INTENT ]"}</div>`; return; }
  const [ck,ctxt]=guardChip(feat), c=feat.content||{};
  const done=doneCount(feat), total=STATE.stages.length;
  let h=`<div class="hero">
    <div class="left">
      <div class="bignum">${String(done).padStart(2,"0")}<span class="of">/${String(total).padStart(2,"0")}</span></div>
      <div class="heroside">
        <div class="lbl">STAGES COMPLETE</div>
        <div class="herostate ${ck}">${ctxt}</div>
      </div>
    </div>
    <div class="heroside" style="align-items:flex-start">
      <div class="heroname">${esc(feat.slug)}</div>
      <div class="herofacts">
        ${feat.status?`<div class="lbl">STATUS <span>${esc(feat.status)}</span></div>`:''}
        ${feat.spec_dir?`<div class="lbl">DIR <span>${esc(feat.spec_dir)}</span></div>`:`<div class="lbl lbl-dim">NO SPEC DIR</div>`}
      </div>
    </div>
  </div>`;
  if(c.goal) h+=`<p class="goal">${esc(c.goal)}</p>`;
  h+=`<div class="chainhd"><span class="lbl">PIPELINE</span><span class="lbl lbl-dim">CLICK A STAGE TO READ ITS DOC</span></div>`;
  h+=chainHtml(feat);
  h+=`<div class="viewer" id="viewer"></div>`;
  h+=statsHtml();
  d.innerHTML=h;
  d.querySelectorAll(".stage[data-stage]").forEach(b=>{ if(b.disabled) return;
    b.onclick=()=>{ SELSTAGE=b.dataset.stage; VIEWMODE=hasSummary(feature(),SELSTAGE)?"summary":"raw";
      d.querySelectorAll(".stage").forEach(x=>x.classList.remove("sel")); b.classList.add("sel"); renderViewer(); };
  });
  renderViewer();
}

function statsHtml(){
  const cp=STATE.compound||{adr:[],corrections:[],patterns:[]}, tok=STATE.tokens||{};
  let store=`<div class="statgroup"><div class="lbl" style="margin-bottom:6px">COMPOUND STORE</div>
    <div class="statrow"><span class="k">ADRs</span><span class="v">${cp.adr.length}</span></div>
    <div class="statrow"><span class="k">Corrections</span><span class="v">${cp.corrections.length}</span></div>
    <div class="statrow"><span class="k">Patterns</span><span class="v">${cp.patterns.length}</span></div>
    <div class="storelist">${[...cp.adr,...cp.corrections,...cp.patterns].map(esc).join(" · ")||"EMPTY — GROWS FROM YOUR FIRST WRITEBACK"}</div></div>`;
  let toks=`<div class="statgroup"><div class="lbl" style="margin-bottom:6px">TOKEN SPEND · THIS PROJECT</div>`;
  if(tok.available){
    toks+=`<div class="statrow"><span class="k">Billable</span><span class="v">${human(tok.total.billable)}</span></div>
      <div class="statrow"><span class="k">Sessions</span><span class="v">${tok.sessions.length}</span></div>
      <div class="statrow"><span class="k">Input · Output</span><span class="v">${human(tok.total.input)} · ${human(tok.total.output)}</span></div>
      <div class="statrow"><span class="k">Cache write</span><span class="v">${human(tok.total.cache_creation)}</span></div>
      <div class="statrow"><span class="k">Cache read</span><span class="v dim">${human(tok.total.cache_read)} · excluded</span></div>`;
  }else{ toks+=`<div class="statrow"><span class="k">Transcripts</span><span class="v dim">NONE</span></div>`; }
  toks+=`</div>`;
  return `<div class="stats">${store}${toks}</div>
    <div class="footnote">READ-ONLY · NO DEPENDENCIES · 127.0.0.1 · NEVER RUNS CHAIN COMMANDS</div>`;
}

/* ── theme ── */
function setTheme(th){
  document.documentElement.setAttribute("data-theme",th);
  document.querySelectorAll("#themeseg button").forEach(b=>b.classList.toggle("on",b.dataset.th===th));
  try{ localStorage.setItem("skc-theme",th); }catch(e){}
}
document.querySelectorAll("#themeseg button").forEach(b=>b.onclick=()=>setTheme(b.dataset.th));
(function(){ let t="dark"; try{ t=localStorage.getItem("skc-theme")||(window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"); }catch(e){} setTheme(t); })();

/* ── poll ── */
async function poll(){
  const hb=document.getElementById("hb"), txt=document.getElementById("hbtxt");
  try{
    const r=await fetch("/api/state",{cache:"no-store"}); STATE=await r.json();
    document.getElementById("repo").textContent="— "+((STATE.repo||"PIPELINE").toUpperCase());
    if(SEL===null && (STATE.features||[]).length) SEL=STATE.features[0].slug;
    renderMaster(); renderDetail();
    hb.classList.remove("stale"); txt.textContent="LIVE · "+((STATE.scanned_at||"").slice(11,19)||"NOW");
  }catch(e){ hb.classList.add("stale"); txt.textContent="DISCONNECTED"; }
}
poll(); setInterval(poll,3000);
</script>
</body>
</html>
"""


import argparse
import datetime
import webbrowser
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer


def find_repo_root(start):
    """Resolve the spec-kit project root to scan.

    Walks up from ``start`` and prefers a ``.specify/`` directory (the spec-kit
    project root — this is what holds ``docs/`` and ``specs/``, and is the
    correct anchor when this script ships inside ``.specify/extensions/compound/``
    of a host repo like equal). Falls back to a directory containing
    ``extension.yml`` for dev mode in this repo, which has no ``.specify/``.
    Returns ``start`` unchanged if neither anchor is found.
    """
    start = os.path.abspath(start)
    extension_yml_root = None
    cur = start
    while True:
        if os.path.isdir(os.path.join(cur, ".specify")):
            return cur
        if extension_yml_root is None and os.path.isfile(os.path.join(cur, "extension.yml")):
            extension_yml_root = cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return extension_yml_root or start
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
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                self._send(200, PAGE_HTML, "text/html")
            elif parsed.path == "/api/state":
                now = datetime.datetime.now().isoformat(timespec="seconds")
                self._send(200, json.dumps(scan_state(repo_root, now=now)), "application/json")
            elif parsed.path == "/api/doc":
                self._serve_doc(urllib.parse.parse_qs(parsed.query).get("path", [""])[0])
            else:
                self._send(404, "not found", "text/plain")

        def _serve_doc(self, rel):
            """Serve a repo-relative markdown file as JSON, sandboxed to repo_root."""
            if not rel:
                return self._send(400, json.dumps({"error": "missing path"}), "application/json")
            # Resolve and confirm the target stays inside repo_root (no traversal,
            # no symlink escape) before reading anything off disk.
            base = os.path.realpath(repo_root)
            target = os.path.realpath(os.path.join(base, rel))
            if target != base and not target.startswith(base + os.sep):
                return self._send(403, json.dumps({"error": "outside repo"}), "application/json")
            if not os.path.isfile(target):
                return self._send(404, json.dumps({"error": "not found"}), "application/json")
            self._send(200, json.dumps({
                "path": os.path.relpath(target, base),
                "content": _read(target),
            }), "application/json")

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description="spec-kit-compound pipeline dashboard")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    ap.add_argument("--repo", default=None,
                    help="path to the spec-kit project to scan (default: auto-detect from cwd, "
                         "then this script's location)")
    args = ap.parse_args(argv)

    if args.repo:
        repo_root = os.path.abspath(args.repo)
    else:
        # Prefer the invocation cwd (the host repo when run from there), then
        # fall back to the script's own location for dev mode.
        repo_root = find_repo_root(os.getcwd())
        if not os.path.isdir(os.path.join(repo_root, ".specify")) and \
           not os.path.isfile(os.path.join(repo_root, "extension.yml")):
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
