#!/usr/bin/env python3
"""compound_refresh.py — read-only health scan of the compound store (v0.8+).

Run by /speckit-compound-writeback at the end of every writeback (the
"refresh" step), or standalone. It never edits anything: it reports findings
and the writeback command proposes archive / merge / upgrade actions for the
human to approve.

Finding kinds:
  no-guard       correction has no enforceable frontmatter and no unenforceable_reason
  dup-rule       two corrections share the same match regex or the same rule text
  dead-paths     correction's paths globs match no file in the repo
  fires-on-tree  correction's regex matches current code (stale rule or live violation)
  bad-regex      correction's match is not a valid grep -E pattern
  superseded     ADR marked Superseded is still in adr/ (archive it)
  stale-guard    ENFORCED.md ledger points at a guard file that no longer exists
  dead-example   pattern's "Examples in this repo" cites a path that no longer exists

Usage:
  compound_refresh.py [--root DIR] [--json]

Exit code is always 0 when the scan runs; findings are advisory.
Stdlib only, so it runs anywhere python3 does.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

STORE = "docs/compound"
ENFORCEABLE = ("paths", "match", "rule", "context")


# ── parsing helpers ─────────────────────────────────────────────
def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def frontmatter(text):
    """Minimal YAML-frontmatter reader: scalars and string lists only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fm, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                fm[key] = [unquote(v) for v in val[1:-1].split(",") if v.strip()]
            else:
                fm[key] = unquote(val) if val else []
            continue
        item = re.match(r"^\s+-\s*(.*)$", line)
        if item and key is not None and isinstance(fm.get(key), list):
            fm[key].append(unquote(item.group(1)))
    return None  # unterminated frontmatter


def unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def section(text, heading):
    """Body of a '## heading' section, up to the next '## '."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lower() == heading.lower()
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


def md_files(root, sub):
    d = os.path.join(root, STORE, sub)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(STORE, sub, n) for n in os.listdir(d) if n.endswith(".md"))


def repo_files(root):
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "-co", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
        return [p for p in out.splitlines() if p]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if not d.startswith(".")]
            files += [os.path.relpath(os.path.join(dp, f), root) for f in fns]
        return files


def glob_match(path, pattern):
    if fnmatch.fnmatch(path, pattern):
        return True
    # "**/*.css" should also match a root-level "app.css"
    return pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:])


# ── checks ──────────────────────────────────────────────────────
def in_scope(path, patterns, own):
    """Repo file is guarded by a correction's paths globs.

    Store docs are excluded (their prose quotes the very snippets corrections
    forbid) unless a glob explicitly targets the store, e.g. a correction about
    other corrections' frontmatter. The correction never scopes itself.
    """
    if path == own:
        return False
    for p in patterns:
        if glob_match(path, p):
            if not path.startswith(STORE + "/") or p.startswith(STORE + "/"):
                return True
    return False


def check_corrections(root, files, findings):
    seen_match, seen_rule = {}, {}

    for rel in md_files(root, "corrections"):
        fm = frontmatter(read(os.path.join(root, rel)))
        if fm is None:
            findings.append(f_("no-guard", rel, "no frontmatter (pre-v0.3, context-only)"))
            continue
        missing = [k for k in ENFORCEABLE if not fm.get(k)]
        if missing:
            if not fm.get("unenforceable_reason"):
                findings.append(f_("no-guard", rel, "missing " + ", ".join(missing)))
            continue

        # the hook keys compound-allow on the file basename, not the slug: field
        slug = os.path.basename(rel)[:-3]
        paths = fm["paths"] if isinstance(fm["paths"], list) else [fm["paths"]]
        match, rule = fm["match"], fm["rule"]

        for table, value in ((seen_match, match.strip()), (seen_rule, rule.strip().lower())):
            if value in table:
                other = table[value]
                findings.append(f_("dup-rule", rel, f"same as {other}"))
                findings.append(f_("dup-rule", other, f"same as {rel}"))
            else:
                table[value] = rel

        scoped = [f for f in files if in_scope(f, paths, rel)]
        if not scoped:
            findings.append(f_("dead-paths", rel, "paths match no file: " + ", ".join(paths)))
            continue

        hits = grep_e(root, match, scoped)
        if hits is None:
            findings.append(f_("bad-regex", rel, f"grep -E rejects: {match}"))
            continue
        bypass = f"compound-allow: {slug}"
        live = [first_line(root, regex=match, rel=h)
                for h in hits if bypass not in read(os.path.join(root, h))]
        if live:
            findings.append(f_("fires-on-tree", rel, "matches " + ", ".join(live[:5])
                               + (f" (+{len(live) - 5} more)" if len(live) > 5 else "")))

    # dedupe identical dup-rule pairs reported via both match and rule
    uniq, out = set(), []
    for f in findings:
        key = (f["kind"], f["file"], f["detail"])
        if key not in uniq:
            uniq.add(key)
            out.append(f)
    findings[:] = out


def grep_e(root, regex, files):
    """Files (relative) whose content matches regex under grep -E. None if regex invalid."""
    hits = []
    for i in range(0, len(files), 200):
        chunk = files[i:i + 200]
        r = subprocess.run(["grep", "-E", "-l", "-e", regex, "--"] + chunk,
                           cwd=root, capture_output=True, text=True)
        if r.returncode == 2 and not r.stdout:
            return None
        hits += [p for p in r.stdout.splitlines() if p]
    return hits


def first_line(root, regex, rel):
    """'path:N' for the first matching line, so a human can triage the hit."""
    r = subprocess.run(["grep", "-E", "-n", "-m1", "-e", regex, "--", rel],
                       cwd=root, capture_output=True, text=True)
    n = r.stdout.split(":", 1)[0]
    return f"{rel}:{n}" if n.isdigit() else rel


def check_adrs(root, findings):
    for rel in md_files(root, "adr"):
        text = read(os.path.join(root, rel))
        fm = frontmatter(text) or {}
        status = str(fm.get("status", "")) or next(
            (l.strip() for l in section(text, "Status").splitlines() if l.strip()), "")
        if status.lower().startswith("superseded"):
            findings.append(f_("superseded", rel, status))


def check_ledger(root, findings):
    rel = os.path.join(STORE, "ENFORCED.md")
    for line in read(os.path.join(root, rel)).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.lstrip().startswith("|") or len(cells) < 3:
            continue
        if cells[0].lower() == "lesson" or set(cells[0]) <= set("-: "):
            continue
        guard = cells[2].strip("`").split("::")[0].strip()
        if guard and not os.path.exists(os.path.join(root, guard)):
            findings.append(f_("stale-guard", rel, f"{cells[0]} → {guard} missing"))


def example_exists(root, path, files):
    """A pattern example path resolves if it exists from the root, or if it is
    shorthand for a deeper file: a trailing partial path (ui/components/X.kt)
    or a '...' elision (app/src/test/.../X.kt)."""
    if os.path.exists(os.path.join(root, path)):
        return True
    parts = [re.escape(p) for p in path.strip("/").split("/...")]
    rx = re.compile(r"(^|/)" + r"(/.+)?".join(parts) + r"/?$")
    return any(rx.search(f) for f in files)


def check_patterns(root, files, findings):
    for rel in md_files(root, "patterns"):
        body = section(read(os.path.join(root, rel)), "Examples in this repo")
        for path in re.findall(r"`([^`\s]+)`", body):
            if "/" in path and not example_exists(root, path, files):
                findings.append(f_("dead-example", rel, f"{path} missing"))


def f_(kind, file, detail):
    return {"kind": kind, "file": file, "detail": detail}


def scan(root):
    findings = []
    if not os.path.isdir(os.path.join(root, STORE)):
        return findings
    files = repo_files(root)
    check_corrections(root, files, findings)
    check_adrs(root, findings)
    check_ledger(root, findings)
    check_patterns(root, files, findings)
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    findings = scan(root)

    if args.json:
        json.dump({"root": root, "findings": findings}, sys.stdout, indent=2)
        print()
        return 0

    n = len(findings)
    print(f"Compound store refresh: {n} finding{'s' if n != 1 else ''}")
    for f in findings:
        print(f"  [{f['kind']}] {f['file']} — {f['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
