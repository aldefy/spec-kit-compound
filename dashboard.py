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


_PV_KINDS = {"P3a": "surface", "P3b": "drift-request", "P3d": "constraint"}


def parse_planverify(text):
    """Return {'verdict': str|None, 'drift': [...]} from a planverify report.

    Mirrors parse_intentguard but over the P3a/P3b/P3d sections and the
    planverify verdict vocabulary (PASS / REPLAN_ALLOWED / BLOCKED_DRIFT).
    BLOCKED_DRIFT -> 'blocked' severity, REPLAN_ALLOWED -> 'review'.
    """
    verdict = parse_frontmatter(text).get("verdict")
    drift = []
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
            current = None
            for level in _PV_KINDS:
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
        if "BLOCKED_DRIFT" in upper or "BLOCKED" in upper:
            sev = "blocked"
        elif "REPLAN_ALLOWED" in upper or "REPLAN" in upper or "REVIEW" in upper:
            sev = "review"
        else:
            continue  # PASS / clean line — not drift
        drift.append({"level": current, "kind": _PV_KINDS[current], "text": body, "severity": sev})
    return {"verdict": verdict, "drift": drift}


import os
import glob
import subprocess

STAGES = [
    "intent", "expectations", "specify", "plan",
    "tasks", "gapfill", "planverify", "implement", "intentguard", "writeback",
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
    "planverify": "judge the plan -> PASS / REPLAN_ALLOWED / BLOCKED_DRIFT",
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


def _git(repo_root, *args, timeout=4):
    """Run a read-only git command in repo_root; return stdout, or "" on any
    failure (not a repo, git missing, timeout, non-zero exit). Never raises —
    the dashboard must survive a repo with no git just as gracefully."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_root, *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_base(repo_root):
    """Merge-base of HEAD with the trunk (main, then master). "" if neither."""
    for ref in ("main", "master"):
        b = _git(repo_root, "merge-base", "HEAD", ref).strip()
        if b:
            return b
    return ""


def _numstat_int(tok):
    return int(tok) if tok.isdigit() else 0


# The IMPLEMENT diff is the feature's CODE. Exclude the harness's own plumbing
# and the chain artifacts that already have their own stages (intent, spec,
# plan, tasks, the compound store) — otherwise the diff drowns in non-code.
_DIFF_EXCLUDE = [
    ".", ":!.specify", ":!.claude", ":!.git", ":!.impeccable",
    ":!docs/intents", ":!docs/expectations", ":!docs/compound",
    ":!specs", ":!CLAUDE.md", ":!AGENTS.md", ":!.DS_Store",
]


def scan_diff(repo_root, full=False):
    """Summarize the working branch vs trunk: changed-file list (+counts), and —
    when full=True — the unified diff text (tracked changes plus the contents of
    new untracked files, read-only). This is the IMPLEMENT stage's artifact: the
    code itself. Light by default so /api/state polling stays fast."""
    base = _git_base(repo_root)
    files, seen, untracked = [], set(), []

    status_letter = {}
    if base:
        for line in _git(repo_root, "diff", base, "--name-status", "--", *_DIFF_EXCLUDE).splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                status_letter[parts[-1]] = parts[0][:1]
        for line in _git(repo_root, "diff", base, "--numstat", "--", *_DIFF_EXCLUDE).splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                path = parts[2]
                files.append({
                    "path": path,
                    "add": _numstat_int(parts[0]),
                    "del": _numstat_int(parts[1]),
                    "status": status_letter.get(path, "M"),
                })
                seen.add(path)

    for line in _git(repo_root, "status", "--porcelain", "-uall", "--", *_DIFF_EXCLUDE).splitlines():
        st, path = line[:2], line[3:].strip()
        if "?" in st and path and path not in seen:
            files.append({"path": path, "add": 0, "del": 0, "status": "A"})
            seen.add(path)
            untracked.append(path)

    files.sort(key=lambda f: f["path"])
    out = {
        "base": base[:9],
        "count": len(files),
        "additions": sum(f["add"] for f in files),
        "deletions": sum(f["del"] for f in files),
        "files": files,
    }

    if full:
        text = _git(repo_root, "diff", base, "--", *_DIFF_EXCLUDE) if base else ""
        extra = []
        for path in untracked:
            ap = os.path.join(repo_root, path)
            try:
                if os.path.isfile(ap) and os.path.getsize(ap) < 100_000:
                    c = _read(ap)
                    if c and "\x00" not in c[:2000]:  # skip binary
                        body = "\n".join("+" + ln for ln in c.split("\n")[:200])
                        extra.append(
                            "diff --git a/{p} b/{p}\nnew file\n--- /dev/null\n+++ b/{p}\n{b}".format(p=path, b=body)
                        )
            except Exception:
                pass
        if extra:
            text = (text + "\n" + "\n".join(extra)) if text else "\n".join(extra)
        out["text"] = text[:90_000]
    return out


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


def _store_latest_mtime(repo_root):
    """Newest mtime across the compound store (adr/corrections/patterns), or 0.0
    if empty. Lets writeback be marked done only when a store file is newer than
    this run's guard verdict — so a *pre-seeded* store (older files, e.g. after a
    fresh checkout) does NOT falsely light writeback before it actually runs."""
    latest = 0.0
    for sub in ("adr", "corrections", "patterns"):
        d = os.path.join(repo_root, "docs/compound", sub)
        if os.path.isdir(d):
            for f in glob.glob(os.path.join(d, "*.md")):
                try:
                    latest = max(latest, os.path.getmtime(f))
                except OSError:
                    pass
    return latest


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
    store_mtime = _store_latest_mtime(repo_root)
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
        planverify_path = os.path.join(repo_root, "docs/intents", slug + ".planverify.md")

        tasks_file = os.path.join(spec_abs, "tasks.md") if spec_abs else None
        tasks_text = _read(tasks_file) if tasks_file else ""
        tasks_mtime = os.path.getmtime(tasks_file) if (tasks_file and os.path.isfile(tasks_file)) else 0.0
        task_counts = parse_tasks(tasks_text)

        intent_text = _read(intent_path)
        exp_text = _read(exp_path) if os.path.isfile(exp_path) else ""
        guard_text = _read(guard_path) if os.path.isfile(guard_path) else ""
        guard_parsed = parse_intentguard(guard_text) if guard_text else {"verdict": None, "drift": []}
        guard_verdict = guard_parsed["verdict"]

        planverify_text = _read(planverify_path) if os.path.isfile(planverify_path) else ""
        planverify_parsed = parse_planverify(planverify_text) if planverify_text else {"verdict": None, "drift": []}
        planverify_verdict = planverify_parsed["verdict"]

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
        if os.path.isfile(planverify_path):
            files.append(os.path.relpath(planverify_path, repo_root))
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
            "planverify": done(os.path.isfile(planverify_path)),
            "implement": done(task_counts["total"] > 0 and task_counts["done"] == task_counts["total"]),
            "intentguard": done(os.path.isfile(guard_path)),
            # writeback is done when the guard has run AND the store has a file
            # newer than the task list — i.e. a writeback happened in this feature
            # cycle. Anchored on tasks.md (stable, pre-writeback) rather than the
            # guard verdict, which may be edited after the run (e.g. appending a
            # material-finding note). A pre-seeded store (older than a freshly
            # re-run tasks.md) correctly stays "pending" until writeback runs.
            "writeback": done(os.path.isfile(guard_path) and store_mtime > tasks_mtime),
        }
        stages["tasks"].update(done=task_counts["done"], total=task_counts["total"])
        stages["intentguard"]["verdict"] = guard_verdict
        stages["intentguard"]["drift"] = guard_parsed["drift"]
        stages["planverify"]["verdict"] = planverify_verdict
        stages["planverify"]["drift"] = planverify_parsed["drift"]

        _compute_states(stages)
        if guard_verdict == "BLOCKED":
            stages["intentguard"]["state"] = "blocked"
        if planverify_verdict == "BLOCKED_DRIFT":
            stages["planverify"]["state"] = "blocked"

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
        if os.path.isfile(planverify_path):
            stage_files["planverify"] = _rel(planverify_path)
        if os.path.isfile(guard_path):
            stage_files["intentguard"] = _rel(guard_path)

        # Every document this feature produced — chain docs in pipeline order,
        # then extras (research / data-model / contracts / checklists) — so the
        # viewer can tab through all of them, not just the one-per-stage file.
        doc_list = []
        doc_stage = {}
        for _st in STAGES:
            _fp = stage_files.get(_st)
            if _fp and _fp not in doc_list:
                doc_list.append(_fp)
                doc_stage[_fp] = _st
        if spec_abs and os.path.isdir(spec_abs):
            for _root, _dirs, _fnames in os.walk(spec_abs):
                for _fn in sorted(_fnames):
                    if _fn.endswith(".md"):
                        _rp = _rel(os.path.join(_root, _fn))
                        if _rp not in doc_list:
                            doc_list.append(_rp)
                            # Extras belong to the stage that produces them:
                            # checklists validate the spec; research / data-model /
                            # quickstart / contracts are all /speckit.plan outputs.
                            doc_stage[_rp] = "specify" if "/checklists/" in _rp.replace(os.sep, "/") else "plan"

        # Compound store = writeback's output. List each entry under the writeback
        # stage so the stage is clickable and tabs through what it persisted.
        _newest_store, _newest_m = None, -1.0
        for _sub in ("adr", "corrections", "patterns"):
            _sd = os.path.join(repo_root, "docs/compound", _sub)
            if not os.path.isdir(_sd):
                continue
            for _sf in sorted(glob.glob(os.path.join(_sd, "*.md"))):
                _rp = _rel(_sf)
                if _rp not in doc_list:
                    doc_list.append(_rp)
                doc_stage[_rp] = "writeback"
                try:
                    _m = os.path.getmtime(_sf)
                    if _m > _newest_m:
                        _newest_m, _newest_store = _m, _rp
                except OSError:
                    pass
        if _newest_store:
            stage_files["writeback"] = _newest_store

        features.append({
            "slug": slug,
            "status": fm.get("status", ""),
            "created": fm.get("created", ""),
            "spec_dir": rel_spec,
            "stages": stages,
            "stage_files": {k: v for k, v in stage_files.items() if v},
            "content": content,
            "files": files,
            "docs": doc_list,
            "doc_stage": doc_stage,
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
        "diff": scan_diff(repo_root),
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
  --fs:1;  /* global font-size multiplier — driven by the TEXT size control */
  --docfs:1;  /* document-pane zoom — driven by the A−/A+ control in the viewer header */
}
:root[data-theme="light"]{
  /* warm low-glare paper — softer than bright white, easier on the eyes */
  --black:#E7E2D8; --surface:#EFEBE2; --raised:#DED9CE; --border:#D2CCBE; --border-vis:#B7B0A0;
  --t-disabled:#9A9485; --t-secondary:#6B6457; --t-primary:#2A2620; --t-display:#171410;
  --interactive:#1F6FD6;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--black);color:var(--t-primary);font-family:var(--ui);
  font-size:calc(14px * var(--fs));line-height:1.5;font-weight:300;-webkit-font-smoothing:antialiased;
  display:flex;flex-direction:column;height:100vh;overflow:hidden;
  transition:background .3s cubic-bezier(.25,.1,.25,1),color .3s cubic-bezier(.25,.1,.25,1)}

/* labels: Space Mono ALL CAPS — the one consistent voice */
.lbl{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.08em;text-transform:uppercase;color:var(--t-secondary)}
.lbl-dim{color:var(--t-disabled)}

/* ── header ── */
header{display:flex;justify-content:space-between;align-items:center;
  padding:0 24px;height:56px;border-bottom:1px solid var(--border);flex:none;gap:20px}
.wordmark{font-family:var(--mono);font-size:calc(12px * var(--fs));letter-spacing:.1em;text-transform:uppercase;color:var(--t-primary);white-space:nowrap}
.wordmark .repo{color:var(--t-disabled)}
.hctl{display:flex;gap:20px;align-items:center}
.heartbeat{display:flex;gap:8px;align-items:center;font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.06em;text-transform:uppercase;color:var(--t-secondary)}
.heartbeat .dot{width:6px;height:6px;border-radius:50%;background:var(--success)}
.heartbeat.stale .dot{background:var(--t-disabled)}
/* theme toggle: segmented control */
.seg{display:flex;border:1px solid var(--border-vis);border-radius:6px;overflow:hidden}
.seg button{font-family:var(--mono);font-size:calc(10px * var(--fs));letter-spacing:.08em;text-transform:uppercase;
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
.feat .name{font-family:var(--ui);font-weight:400;font-size:calc(14px * var(--fs));color:var(--t-primary);
  word-break:break-word;line-height:1.3}
.feat .meta{margin-top:10px;display:flex;justify-content:space-between;align-items:center;gap:8px}
/* mini segmented bar */
.minibar{display:flex;gap:2px;margin-top:11px}
.minibar i{flex:1;height:4px;background:var(--border)}
.minibar i.done{background:var(--t-display)} .minibar i.current{background:var(--success)}
.minibar i.blocked{background:var(--accent)}
.statetxt{font-family:var(--mono);font-size:calc(10px * var(--fs));letter-spacing:.06em;text-transform:uppercase}
.statetxt.pass{color:var(--success)} .statetxt.blocked{color:var(--accent)}
.statetxt.review{color:var(--warning)} .statetxt.none{color:var(--t-disabled)}

/* ── detail ── */
.detail{overflow-y:auto;padding:0 40px 96px}
.detail .empty{color:var(--t-disabled);font-family:var(--mono);text-transform:uppercase;letter-spacing:.06em;text-align:center;padding:120px 20px}

/* HERO — the one expressive moment (Section 2.6 single break) */
.hero{padding:48px 0 8px;display:flex;align-items:flex-end;justify-content:space-between;gap:32px;flex-wrap:wrap}
.hero .left{display:flex;align-items:baseline;gap:16px}
.bignum{font-family:var(--display);font-weight:700;font-size:calc(96px * var(--fs));line-height:.9;letter-spacing:-.03em;color:var(--t-display)}
.bignum .of{color:var(--t-disabled)}
.heroside{display:flex;flex-direction:column;gap:6px;padding-bottom:10px}
.herostate{font-family:var(--mono);font-weight:700;font-size:calc(18px * var(--fs));letter-spacing:.04em;text-transform:uppercase}
.herostate.pass{color:var(--success)} .herostate.blocked{color:var(--accent)}
.herostate.review{color:var(--warning)} .herostate.none{color:var(--t-secondary)}
.heroname{font-family:var(--ui);font-weight:500;font-size:calc(24px * var(--fs));letter-spacing:-.01em;color:var(--t-display);max-width:46ch;line-height:1.15}
.herofacts{display:flex;gap:18px;flex-wrap:wrap;margin-top:4px}
.herofacts .lbl span{color:var(--t-primary);font-family:var(--mono);text-transform:none;letter-spacing:0}
.goal{font-family:var(--ui);font-weight:300;font-size:calc(16px * var(--fs));line-height:1.55;color:var(--t-primary);max-width:68ch;margin:24px 0 0}

/* ── the chain: segmented progress bar (signature viz) ── */
.chainhd{display:flex;justify-content:space-between;align-items:baseline;margin:40px 0 12px}
.chainhint{color:var(--interactive);letter-spacing:.08em}
.chain{display:flex;gap:3px}
.stage{flex:1;min-width:0;background:transparent;border:0;cursor:pointer;padding:0;text-align:left;
  font-family:inherit;color:inherit;display:flex;flex-direction:column;gap:8px}
.stage:disabled{cursor:default}
.stage .blk{height:10px;background:var(--border);transition:background .2s ease-out}
.stage.done .blk{background:var(--t-display)}
.stage.current .blk{background:var(--success);animation:wip 1.3s ease-in-out infinite}
@keyframes wip{0%,100%{opacity:1}50%{opacity:.35}}
.stage.blocked .blk{background:var(--accent)}
.stage .cap{font-family:var(--mono);font-size:calc(10px * var(--fs));letter-spacing:.05em;text-transform:uppercase;color:var(--t-disabled);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stage.done .cap,.stage.current .cap{color:var(--t-secondary)}
.stage:not(:disabled) .cap{text-decoration:underline dotted var(--t-disabled);text-underline-offset:3px;text-decoration-thickness:1px}
.stage:not(:disabled):hover .blk{background:var(--t-secondary)}
.stage:not(:disabled):hover .cap{color:var(--t-primary);text-decoration-style:solid}
.stage.sel .blk{outline:1px solid var(--interactive);outline-offset:2px}
.stage.sel .cap{color:var(--interactive);text-decoration-style:solid;text-decoration-color:var(--interactive)}
.stage .num{font-family:var(--mono);font-size:calc(9px * var(--fs));color:var(--t-disabled);letter-spacing:.05em}

/* ── doc viewer ── */
.viewer{margin-top:36px}
.vh{display:flex;justify-content:space-between;align-items:center;gap:16px;
  padding-bottom:12px;border-bottom:1px solid var(--border)}
.vh .path{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.04em;color:var(--t-secondary);word-break:break-all}
.vh .path b{color:var(--t-primary);text-transform:uppercase;letter-spacing:.08em}
.vctl{display:flex;gap:10px;align-items:center}
.vbody{padding:18px 0 0;max-height:46vh;overflow:auto;zoom:var(--docfs)}
.vbody h3{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.08em;text-transform:uppercase;
  color:var(--t-secondary);margin:22px 0 10px} .vbody h3:first-child{margin-top:0}
.vbody ul{margin:0;padding:0;list-style:none}
.vbody li{font-family:var(--ui);font-weight:300;font-size:calc(14px * var(--fs));color:var(--t-primary);
  padding:7px 0;border-bottom:1px solid var(--border);line-height:1.45}
.vbody .raw{font-family:var(--mono);font-size:12.5px;line-height:1.7;white-space:pre-wrap;
  word-break:break-word;color:var(--t-primary);margin:0}
/* ── rendered markdown (self-contained renderer; no CDN) ── */
.md{font-family:var(--ui);font-weight:300;font-size:calc(14px * var(--fs));color:var(--t-primary);line-height:1.6}
.md-h{font-family:var(--mono);letter-spacing:.04em;color:var(--t-display);line-height:1.25;margin:20px 0 10px}
.md-h:first-child{margin-top:0}
.md-h1{font-size:calc(20px * var(--fs));text-transform:none} .md-h2{font-size:calc(16px * var(--fs))}
.md-h3{font-size:calc(12px * var(--fs));letter-spacing:.08em;text-transform:uppercase;color:var(--t-secondary)}
.md-h4,.md-h5,.md-h6{font-size:calc(11px * var(--fs));letter-spacing:.08em;text-transform:uppercase;color:var(--t-secondary)}
.md-p{margin:0 0 12px}
.md-ul,.md-ol{margin:0 0 12px;padding-left:22px}
.md-ul{list-style:disc} .md-ol{list-style:decimal}
.md li{padding:3px 0;line-height:1.5}
.md-ul.tasklist{list-style:none;padding-left:0}
.md-ul.tasklist li{font-family:var(--mono);font-size:calc(12px * var(--fs));display:flex;gap:10px;align-items:baseline}
.md-ul.tasklist .box{color:var(--t-disabled);flex:0 0 auto} .md-ul.tasklist li.x .box{color:var(--success)}
.md code{font-family:var(--mono);font-size:.92em;background:var(--surface);border:1px solid var(--border);border-radius:3px;padding:1px 5px}
.md a{color:var(--interactive);text-decoration:underline;text-underline-offset:2px}
.md strong{font-weight:700;color:var(--t-display)} .md em{font-style:italic}
.md-code{font-family:var(--mono);font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word;
  background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin:0 0 14px;color:var(--t-primary);overflow-x:auto}
.md-bq{border-left:3px solid var(--border-vis);margin:0 0 12px;padding:4px 0 4px 14px;color:var(--t-secondary)}
.md-hr{border:0;border-top:1px solid var(--border);margin:18px 0}
.md-table{border-collapse:collapse;width:100%;margin:0 0 14px;font-size:calc(13px * var(--fs));display:block;overflow-x:auto}
.md-table th,.md-table td{border:1px solid var(--border-vis);padding:6px 10px;text-align:left;vertical-align:top}
.md-table th{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.04em;text-transform:uppercase;color:var(--t-secondary);background:var(--surface)}
.vbody .tasklist li{font-family:var(--mono);font-size:calc(12px * var(--fs));display:flex;gap:10px;align-items:baseline}
.vbody .tasklist li .box{color:var(--t-disabled);flex:0 0 auto;white-space:nowrap}
.dtree{margin:12px 0 0;border:1px solid var(--border-vis);border-radius:6px;padding:8px 10px;max-height:22vh;overflow:auto}
.dfile{display:flex;align-items:baseline;gap:10px;font-family:var(--mono);font-size:calc(11px * var(--fs));padding:2px 0}
.dst{flex:0 0 auto;width:14px;text-align:center;font-weight:700}
.dst.dA{color:var(--success)} .dst.dM{color:var(--interactive)} .dst.dD{color:var(--accent)} .dst.dR{color:var(--warning)}
.dpath{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--t-primary)}
.dnum{flex:0 0 auto;color:var(--t-disabled);font-size:calc(10px * var(--fs));letter-spacing:.04em}
.vbody .diff{font-family:var(--mono);font-size:12.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;margin:0}
.diff .dadd{color:var(--success)} .diff .ddel{color:var(--accent)} .diff .dhunk{color:var(--interactive)} .diff .dmeta{color:var(--t-disabled)}
.dadd{color:var(--success)} .ddel{color:var(--accent)}
.stage.optional .blk{background:transparent;border:1px dashed var(--t-disabled)}
.stage.optional.done .blk{background:var(--t-display);border-color:var(--t-display)}
.stage.optional .cap{opacity:.7}
.vbody .tasklist li.x .box{color:var(--success)}
.vbody .loading{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.08em;text-transform:uppercase;color:var(--t-disabled)}
.vbody .drift li.blocked{color:var(--accent)} .vbody .drift li.review{color:var(--warning)}
.vbody .drift b{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.06em;margin-right:8px}
.gbadge{font-family:var(--mono);font-size:calc(12px * var(--fs));letter-spacing:.06em;text-transform:uppercase}
.gbadge.pass{color:var(--success)} .gbadge.blocked{color:var(--accent)} .gbadge.review{color:var(--warning)}

/* ── footer stats: stat rows, no cards ── */
.stats{margin-top:48px;display:grid;grid-template-columns:1fr 1fr;gap:0 48px}
.statgroup{border-top:1px solid var(--border-vis);padding-top:14px}
.statrow{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;gap:12px}
.statrow .k{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.06em;text-transform:uppercase;color:var(--t-secondary)}
.statrow .v{font-family:var(--mono);font-size:calc(13px * var(--fs));color:var(--t-primary)}
.statrow .v.dim{color:var(--t-disabled)}
.storelist{font-family:var(--mono);font-size:calc(11px * var(--fs));color:var(--t-disabled);line-height:1.7;margin-top:8px;word-break:break-word;display:flex;flex-wrap:wrap;gap:6px}
.storedoc{font-family:var(--mono);font-size:calc(11px * var(--fs));letter-spacing:.04em;background:transparent;color:var(--t-secondary);border:1px solid var(--border-vis);border-radius:5px;padding:4px 9px;cursor:pointer;transition:.15s ease-out}
.storedoc:hover{color:var(--t-display);border-color:var(--t-display)}
.doctabs{display:flex;flex-wrap:wrap;gap:5px;margin:14px 0 0}
.doctabs button{font-family:var(--mono);font-size:calc(10px * var(--fs));letter-spacing:.06em;text-transform:uppercase;background:transparent;color:var(--t-secondary);border:1px solid var(--border-vis);border-radius:5px;padding:5px 10px;cursor:pointer;transition:.15s ease-out}
.doctabs button.on{background:var(--t-display);color:var(--black);border-color:var(--t-display)}
.doctabs button:hover{color:var(--t-display)}
.footnote{margin-top:40px;font-family:var(--mono);font-size:calc(10px * var(--fs));letter-spacing:.06em;text-transform:uppercase;color:var(--t-disabled)}

@media (max-width:860px){
  .app{grid-template-columns:1fr;grid-template-rows:auto 1fr}
  .master{border-right:0;border-bottom:1px solid var(--border);max-height:32vh}
  .detail{padding:0 22px 64px}
  .bignum{font-size:calc(64px * var(--fs))}
  .stats{grid-template-columns:1fr;gap:0}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
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
    <div class="seg" id="fontseg" title="text size">
      <button data-fs="1" class="on">S</button>
      <button data-fs="1.2">M</button>
      <button data-fs="1.45">L</button>
      <button data-fs="1.75">XL</button>
    </div>
    <div class="heartbeat" id="hb"><span class="dot"></span><span id="hbtxt">CONNECTING</span></div>
  </div>
</header>

<div class="app">
  <aside class="master" id="master"></aside>
  <section class="detail" id="detail"><div class="empty">[ LOADING PIPELINE ]</div></section>
</div>

<script>
const LABELS={intent:"INTENT",expectations:"EXPECT",specify:"SPEC",plan:"PLAN",tasks:"TASKS",gapfill:"GAPFILL",planverify:"PLANVERIFY",implement:"IMPL",intentguard:"GUARD",writeback:"WRITEBACK"};
let STATE=null, SEL=null, SELSTAGE=null, SELDOC=null, VIEWMODE="summary";
const docCache={}; let DOCSHOWN=null, DIFFTEXT=null;

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

function docLabel(p){
  const parts=p.split('/'); let f=parts.pop().replace(/\.md$/,'');
  const m=f.match(/\.(intent|expectations|planverify|intentguard)$/); if(m) f=m[1];
  const dir=parts.pop()||'';
  const pre=dir==='contracts'?'CONTRACT·':dir==='checklists'?'CHECK·':'';
  return (pre+f).toUpperCase();
}
function stageForDoc(feat,path){ const ds=feat.doc_stage||{}; if(ds[path]) return ds[path]; const sf=feat.stage_files||{}; for(const k in sf){ if(sf[k]===path) return k; } return ""; }
function docsForStage(feat,stage){ const ds=feat.doc_stage||{}, sf=feat.stage_files||{}, all=feat.docs||[]; const out=all.filter(d=>ds[d]===stage); const own=sf[stage]; if(own && out.indexOf(own)<0) out.unshift(own); return out; }
function openDoc(p){ SELDOC=p; renderViewer(); }
function showSummary(stage){ SELSTAGE=stage; SELDOC=null; VIEWMODE="summary"; renderViewer(); }

function hasSummary(feat,stage){
  const c=feat.content||{};
  if(stage==="intent") return !!(c.goal||(c.constraints||[]).length||(c.failures||[]).length||(c.out_of_scope||[]).length);
  if(stage==="expectations") return !!((c.expectations_positive||[]).length||(c.expectations_edge||[]).length);
  if(stage==="intentguard") return !!(feat.stages.intentguard.verdict||(feat.stages.intentguard.drift||[]).length);
  if(stage==="planverify") return !!(feat.stages.planverify.verdict||(feat.stages.planverify.drift||[]).length);
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
    if(g.drift&&g.drift.length) h+=`<ul class="drift" style="margin-top:12px">`+g.drift.map(x=>`<li class="${esc(x.severity)}"><b>${esc(x.level)}</b>${mdInline(x.text)}</li>`).join("")+`</ul>`;
    return h;
  }
  if(stage==="planverify"){
    const g=feat.stages.planverify, vk=g.verdict==="PASS"?"pass":g.verdict==="BLOCKED_DRIFT"?"blocked":"review";
    let h=`<div class="gbadge ${vk}">${esc(g.verdict||"NOT VERIFIED")}</div>`;
    if(g.drift&&g.drift.length) h+=`<ul class="drift" style="margin-top:12px">`+g.drift.map(x=>`<li class="${esc(x.severity)}"><b>${esc(x.level)}</b>${mdInline(x.text)}</li>`).join("")+`</ul>`;
    return h;
  }
  return "";
}
/* inline markdown: code, bold, italic, links — all escaped first */
function mdInline(s){
  s=esc(s);
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s=s.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  s=s.replace(/(^|[^*])\*([^*]+)\*/g,'$1<em>$2</em>');
  s=s.replace(/\[([^\]]+)\]\(([^)]+)\)/g,(m,t,u)=>/^https?:\/\//.test(u)?`<a href="${esc(u)}" target="_blank" rel="noopener">${t}</a>`:t);
  return s;
}
/* block markdown -> HTML. Self-contained (CSP forbids any CDN lib). Handles
   headings, fenced + indented code, blockquotes, hr, GFM tables, ordered /
   unordered / task lists, and paragraphs. */
function mdHtml(text){
  if(text==null) return `<div class="loading">[ LOADING ]</div>`;
  // strip a leading YAML frontmatter block — shown via the SUMMARY tab instead
  text=text.replace(/^---\n[\s\S]*?\n---\n?/,'');
  const lines=text.split("\n"); let h="",i=0;
  const closeList=st=>{ while(st.length) h+=st.pop()==="ol"?"</ol>":"</ul>"; };
  const lst=[];
  while(i<lines.length){
    let l=lines[i];
    // fenced code
    const fence=l.match(/^```(.*)$/);
    if(fence){ closeList(lst); i++; let buf=[];
      while(i<lines.length && !/^```/.test(lines[i])){ buf.push(lines[i]); i++; }
      i++; h+=`<pre class="md-code">${esc(buf.join("\n"))}</pre>`; continue; }
    // table: header row | --- row | body rows
    if(/^\s*\|.*\|\s*$/.test(l) && i+1<lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i+1])){
      closeList(lst);
      const cells=r=>r.trim().replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
      const head=cells(l); i+=2; let rows=[];
      while(i<lines.length && /^\s*\|.*\|\s*$/.test(lines[i])){ rows.push(cells(lines[i])); i++; }
      h+=`<table class="md-table"><thead><tr>${head.map(c=>`<th>${mdInline(c)}</th>`).join("")}</tr></thead><tbody>`
        +rows.map(r=>`<tr>${r.map(c=>`<td>${mdInline(c)}</td>`).join("")}</tr>`).join("")+`</tbody></table>`;
      continue;
    }
    const hd=l.match(/^(#{1,6})\s+(.*)$/);
    if(hd){ closeList(lst); const n=hd[1].length; h+=`<h${n} class="md-h md-h${n}">${mdInline(hd[2])}</h${n}>`; i++; continue; }
    if(/^\s*([-*_])\1{2,}\s*$/.test(l)){ closeList(lst); h+=`<hr class="md-hr">`; i++; continue; }
    const bq=l.match(/^>\s?(.*)$/);
    if(bq){ closeList(lst); h+=`<blockquote class="md-bq">${mdInline(bq[1])}</blockquote>`; i++; continue; }
    const task=l.match(/^\s*[-*]\s+\[( |x|X)\]\s+(.*)$/);
    if(task){ if(lst[lst.length-1]!=="ul"){ closeList(lst); h+=`<ul class="md-ul tasklist">`; lst.push("ul"); }
      h+=`<li class="${task[1]===' '?'':'x'}"><span class="box">${task[1]===' '?'[ ]':'[x]'}</span>${mdInline(task[2])}</li>`; i++; continue; }
    const ul=l.match(/^\s*[-*]\s+(.*)$/);
    if(ul){ if(lst[lst.length-1]!=="ul"){ closeList(lst); h+=`<ul class="md-ul">`; lst.push("ul"); }
      h+=`<li>${mdInline(ul[1])}</li>`; i++; continue; }
    const ol=l.match(/^\s*\d+\.\s+(.*)$/);
    if(ol){ if(lst[lst.length-1]!=="ol"){ closeList(lst); h+=`<ol class="md-ol">`; lst.push("ol"); }
      h+=`<li>${mdInline(ol[1])}</li>`; i++; continue; }
    if(/^\s*$/.test(l)){ closeList(lst); i++; continue; }
    // paragraph: gather consecutive non-blank, non-structural lines
    closeList(lst); let para=[l]; i++;
    while(i<lines.length && !/^\s*$/.test(lines[i]) && !/^(#{1,6}\s|```|>\s?|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i]) && !/^\s*\|.*\|\s*$/.test(lines[i])){ para.push(lines[i]); i++; }
    h+=`<p class="md-p">${mdInline(para.join(" "))}</p>`;
  }
  closeList(lst);
  return `<div class="md">${h}</div>`;
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
  return mdHtml(text);
}
async function fetchDoc(path){
  if(docCache[path]) return docCache[path];
  try{ const r=await fetch("/api/doc?path="+encodeURIComponent(path),{cache:"no-store"}); docCache[path]=await r.json(); }
  catch(e){ docCache[path]={content:"[ FAILED TO LOAD ]"}; }
  return docCache[path];
}
async function fetchDiff(){
  try{ const r=await fetch("/api/diff",{cache:"no-store"}); DIFFTEXT=await r.json(); }
  catch(e){ DIFFTEXT={files:[],text:"[ FAILED TO LOAD DIFF ]"}; }
  return DIFFTEXT;
}
function diffLineCls(l){
  if(l.startsWith("+")&&!l.startsWith("+++")) return "dadd";
  if(l.startsWith("-")&&!l.startsWith("---")) return "ddel";
  if(l.startsWith("@@")) return "dhunk";
  if(l.startsWith("diff ")||l.startsWith("new file")||l.startsWith("+++")||l.startsWith("---")||l.startsWith("index ")) return "dmeta";
  return "";
}
function diffHtml(text){
  if(!text) return `<div class="loading">[ NO TEXT DIFF YET ]</div>`;
  return `<pre class="diff">`+text.split("\n").map(l=>`<span class="${diffLineCls(l)}">${esc(l)}</span>`).join("\n")+`</pre>`;
}
function renderDiffView(feat,wrap){
  const meta=STATE.diff||{files:[],count:0,additions:0,deletions:0};
  if(DIFFTEXT===null) fetchDiff().then(()=>renderViewer());
  const tree=meta.files.length
    ? meta.files.map(f=>{ const num=(f.add?("+"+f.add+" "):"")+(f.del?("−"+f.del):"");
        return `<div class="dfile"><span class="dst d${esc(f.status)}">${esc(f.status)}</span><span class="dpath" title="${esc(f.path)}">${esc(f.path)}</span><span class="dnum">${esc(num)}</span></div>`; }).join("")
    : `<div class="loading">[ NO FILE CHANGES YET — IMPLEMENT HASN'T WRITTEN CODE ]</div>`;
  wrap.innerHTML=`<div class="vh">
      <div class="path">GIT DIFF · vs ${esc(meta.base||"main")} · ${meta.count} FILE${meta.count===1?"":"S"} · <span class="dadd">+${meta.additions}</span> <span class="ddel">−${meta.deletions}</span></div>
      <div class="vctl"><div class="seg vzoom"><button data-dz="-1" title="smaller document text">A−</button><button data-dz="1" title="larger document text">A+</button></div></div>
    </div>
    <div class="dtree">${tree}</div>
    <div class="vbody">${diffHtml((DIFFTEXT||{}).text)}</div>`;
  wrap.querySelectorAll(".vzoom button").forEach(b=>b.onclick=()=>docZoom(parseInt(b.dataset.dz)));
}

function renderViewer(){
  const feat=feature(), wrap=document.getElementById("viewer");
  if(!wrap) return;
  if(!feat){ wrap.innerHTML=`<div class="vbody"><div class="loading">[ SELECT A FEATURE ]</div></div>`; return; }
  if(SELSTAGE==='implement' && !(feat.stage_files||{}).implement){ DOCSHOWN=null; return renderDiffView(feat,wrap); }
  const isStoreDoc=!!SELDOC && SELDOC.indexOf("docs/compound/")===0;
  const docs=isStoreDoc?[SELDOC]:(SELSTAGE?docsForStage(feat,SELSTAGE):(feat.docs||[]));
  const sumStage=(!isStoreDoc && SELSTAGE && hasSummary(feat,SELSTAGE))?SELSTAGE:null;
  const showingSummary=!SELDOC && VIEWMODE==="summary" && !!sumStage;
  let curDoc=SELDOC;
  if(!showingSummary && !curDoc){ curDoc=(SELSTAGE?(feat.stage_files||{})[SELSTAGE]:null)||docs[0]||null; }
  DOCSHOWN=showingSummary?null:curDoc;  // the doc on screen — poll() live-refreshes its cache
  let tabs="";
  if(sumStage) tabs+=`<button data-sum="${esc(sumStage)}" class="${showingSummary?'on':''}">SUMMARY</button>`;
  tabs+=docs.map(d=>`<button data-doc="${esc(d)}" class="${(!showingSummary&&d===curDoc)?'on':''}" title="${esc(d)}">${esc(docLabel(d))}</button>`).join("");
  let body, headtxt;
  if(showingSummary){ body=summaryFor(feat,sumStage); headtxt=esc((LABELS[sumStage]||sumStage)+" · SUMMARY"); }
  else if(curDoc){ const dc=docCache[curDoc]; headtxt=esc(curDoc);
    if(dc){ body=rawHtml(stageForDoc(feat,curDoc),dc.content); }
    else { body=`<div class="loading">[ LOADING ]</div>`; fetchDoc(curDoc).then(()=>renderViewer()); } }
  else { body=`<div class="loading">[ NO DOCUMENTS YET ]</div>`; headtxt="—"; }
  wrap.innerHTML=`<div class="vh">
      <div class="path">${headtxt}</div>
      <div class="vctl"><div class="seg vzoom"><button data-dz="-1" title="smaller document text">A−</button><button data-dz="1" title="larger document text">A+</button></div></div>
    </div>
    ${(docs.length||sumStage)?`<div class="doctabs">${tabs}</div>`:""}
    <div class="vbody">${body}</div>`;
  wrap.querySelectorAll(".vzoom button").forEach(b=>b.onclick=()=>docZoom(parseInt(b.dataset.dz)));
  wrap.querySelectorAll(".doctabs button[data-doc]").forEach(b=>b.onclick=()=>openDoc(b.dataset.doc));
  wrap.querySelectorAll(".doctabs button[data-sum]").forEach(b=>b.onclick=()=>showSummary(b.dataset.sum));
}

function chainHtml(feat){
  const OPTIONAL={gapfill:1};
  const diffN=(STATE.diff||{}).count||0;
  let h='<div class="chain">';
  STATE.stages.forEach((name,i)=>{
    const st=feat.stages[name];
    // implement produces CODE, not a doc — its artifact is the git diff, so it's
    // clickable (and shown as active) whenever the branch has changes.
    const hasDoc=!!(feat.stage_files||{})[name] || (name==='implement' && diffN>0);
    let scls=stageCls(st);
    if(name==='implement' && diffN>0 && st.state!=='done' && st.state!=='current') scls='current';
    const cls=scls+(name===SELSTAGE?" sel":"")+(OPTIONAL[name]?" optional":"");
    h+=`<button class="stage ${cls}" data-stage="${esc(name)}" ${hasDoc?"":"disabled"}${OPTIONAL[name]?' title="optional stage — safe to skip"':''}>
        <span class="blk"></span>
        <span class="cap">${esc(LABELS[name]||name)}</span>
      </button>`;
  });
  return h+'</div>';
}

function renderDetail(){
  const d=document.getElementById("detail"), feat=feature();
  // Preserve scroll across the 3s poll re-render: the whole detail pane scrolls,
  // and the doc body (.vbody) scrolls independently. Rebuilding innerHTML resets
  // both to 0 — capture and restore so the view doesn't jump to the top.
  const _detailTop=d.scrollTop;
  const _vb=d.querySelector(".vbody"); const _vbTop=_vb?_vb.scrollTop:0;
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
  h+=`<div class="chainhd"><span class="lbl">PIPELINE</span><span class="lbl chainhint">▸ CLICK ANY STAGE TO OPEN ITS DOCS</span></div>`;
  h+=chainHtml(feat);
  h+=`<div class="viewer" id="viewer"></div>`;
  h+=statsHtml();
  d.innerHTML=h;
  d.querySelectorAll(".stage[data-stage]").forEach(b=>{ if(b.disabled) return;
    b.onclick=()=>{ SELSTAGE=b.dataset.stage; SELDOC=null; VIEWMODE=hasSummary(feature(),SELSTAGE)?"summary":"raw";
      d.querySelectorAll(".stage").forEach(x=>x.classList.remove("sel")); b.classList.add("sel"); renderViewer(); };
  });
  d.querySelectorAll(".storedoc[data-doc]").forEach(b=>b.onclick=()=>openDoc(b.dataset.doc));
  renderViewer();
  // restore scroll positions captured before the rebuild
  d.scrollTop=_detailTop;
  const _nvb=d.querySelector(".vbody"); if(_nvb) _nvb.scrollTop=_vbTop;
}

function statsHtml(){
  const cp=STATE.compound||{adr:[],corrections:[],patterns:[]}, tok=STATE.tokens||{};
  const sdoc=(sub,name)=>`<button class="storedoc" data-doc="docs/compound/${sub}/${esc(name)}" title="${esc(name)}">${esc(name.replace(/\.md$/,''))}</button>`;
  const sitems=[...cp.adr.map(n=>sdoc('adr',n)),...cp.corrections.map(n=>sdoc('corrections',n)),...cp.patterns.map(n=>sdoc('patterns',n))];
  let store=`<div class="statgroup"><div class="lbl" style="margin-bottom:6px">COMPOUND STORE</div>
    <div class="storelist">${sitems.length?sitems.join(""):"EMPTY — GROWS FROM YOUR FIRST WRITEBACK"}</div></div>`;
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
(function(){ let t="dark";
  const q=new URLSearchParams(location.search).get("theme");   // ?theme=light|dark wins (shareable link / screenshots)
  if(q==="light"||q==="dark"){ t=q; }
  else{ try{ t=localStorage.getItem("skc-theme")||(window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"); }catch(e){} }
  setTheme(t); })();

/* ── text size ── */
function setFont(fs){
  document.documentElement.style.setProperty("--fs",fs);
  document.querySelectorAll("#fontseg button").forEach(b=>b.classList.toggle("on",b.dataset.fs===fs));
  try{ localStorage.setItem("skc-fs",fs); }catch(e){}
}
document.querySelectorAll("#fontseg button").forEach(b=>b.onclick=()=>setFont(b.dataset.fs));
(function(){
  const q=new URLSearchParams(location.search).get("fs");   // ?fs=1.45 wins (shareable link / screenshots)
  let fs=q; if(!fs){ try{ fs=localStorage.getItem("skc-fs"); }catch(e){} }
  if(fs) setFont(fs);
})();

/* ── doc-pane zoom (independent of the global TEXT size) ── */
let DOCFS=1;
function docZoom(d){
  DOCFS=Math.min(2.5,Math.max(0.7,+(DOCFS+d*0.15).toFixed(2)));
  document.documentElement.style.setProperty("--docfs",DOCFS);
  try{ localStorage.setItem("skc-docfs",DOCFS); }catch(e){}
}
(function(){ try{ const d=parseFloat(localStorage.getItem("skc-docfs")); if(d){ DOCFS=d; document.documentElement.style.setProperty("--docfs",d); } }catch(e){} })();

/* ── poll ── */
async function poll(){
  const hb=document.getElementById("hb"), txt=document.getElementById("hbtxt");
  try{
    const r=await fetch("/api/state",{cache:"no-store"}); STATE=await r.json();
    // Live-refresh the doc currently on screen so an actively-written file
    // (e.g. gapfill appending to tasks.md) updates in place — no stale cache,
    // no LOADING flicker. Other docs stay cached until opened.
    if(DOCSHOWN){ try{ const dr=await fetch("/api/doc?path="+encodeURIComponent(DOCSHOWN),{cache:"no-store"}); const dj=await dr.json(); if(dj&&dj.content!=null) docCache[DOCSHOWN]=dj; }catch(e){} }
    if(SELSTAGE==='implement'){ try{ const xr=await fetch("/api/diff",{cache:"no-store"}); DIFFTEXT=await xr.json(); }catch(e){} }
    document.getElementById("repo").textContent="— "+((STATE.repo||"PIPELINE").toUpperCase());
    if(SEL===null && (STATE.features||[]).length){
      SEL=STATE.features[0].slug;
      if(SELSTAGE===null && SELDOC===null){ const f0=STATE.features[0], sf=f0.stage_files||{};
        // ?stage=planverify deep-links a stage (shareable / screenshots); else
        // auto-pick the latest done|current stage that has a doc.
        const qs=new URLSearchParams(location.search).get("stage");
        if(qs && sf[qs]){ SELSTAGE=qs; VIEWMODE=hasSummary(f0,qs)?"summary":"raw"; }
        else for(let i=STATE.stages.length-1;i>=0;i--){ const n=STATE.stages[i]; const stt=(f0.stages[n]||{}).state;
          if(sf[n] && (stt==="done"||stt==="current")){ SELSTAGE=n; VIEWMODE=hasSummary(f0,n)?"summary":"raw"; break; } } }
    }
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
import urllib.request
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
            elif parsed.path == "/api/diff":
                self._send(200, json.dumps(scan_diff(repo_root, full=True)), "application/json")
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


def _live_dashboard(port, repo_name):
    """If a compound dashboard for `repo_name` is already serving on `port`,
    return its URL; else None — so a second launch reuses the first instead of
    spawning a duplicate on the next port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=0.4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None  # nothing reachable here
    if not isinstance(data, dict) or "stages" not in data:
        return None  # some other server on this port — leave it alone
    if data.get("repo") and data["repo"] != repo_name:
        return None  # a dashboard, but for a different repo — caller picks another port
    return f"http://127.0.0.1:{port}/"


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

    repo_name = os.path.basename(os.path.abspath(repo_root))
    httpd = None
    for port in range(args.port, args.port + 11):
        # Already serving THIS repo here? Reuse it — don't spawn a duplicate.
        existing = _live_dashboard(port, repo_name)
        if existing:
            print(f"dashboard already running → {existing}  (reusing — not starting a second)", flush=True)
            if args.open:
                webbrowser.open(existing)
            return 0
        try:
            httpd = HTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            continue  # port busy with something else → try the next
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
