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
