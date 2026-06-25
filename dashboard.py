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
