#!/usr/bin/env python3
"""compound_next.py — what to run next in a spec-kit-compound project (v0.9+).

Backs /speckit-compound-help. Read-only: reuses the dashboard's stage scan
(dashboard.scan_state) and the store scanner (compound_refresh.scan), and
prints the next command for each active feature, most urgent first.

Usage:
  compound_next.py [--root DIR] [--json] [--all]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]

import compound_refresh  # noqa: E402
import dashboard  # noqa: E402

COMMANDS = {
    "intent": "/speckit-compound-intent",
    "expectations": "/speckit-compound-expectations",
    "specify": "/speckit-specify",
    "plan": "/speckit-plan",
    "tasks": "/speckit-tasks",
    "gapfill": "/speckit-compound-gapfill",
    "planverify": "/speckit-compound-planverify",
    "implement": "/speckit-implement",
    "intentguard": "/speckit-compound-intentguard",
    "writeback": "/speckit-compound-writeback",
}


def step(command, why, feature=None, urgent=False):
    return {"command": command, "why": why, "feature": feature, "urgent": urgent}


def feature_step(f):
    slug, st = f["slug"], f["stages"]
    ig, pv = st["intentguard"], st["planverify"]

    if ig.get("state") == "blocked" or ig.get("verdict") == "BLOCKED":
        return step(COMMANDS["intentguard"],
                    f"intentguard is BLOCKED: fix the violations listed in "
                    f"docs/intents/{slug}.intentguard.md, then re-run the guard", slug, True)
    if pv.get("state") == "blocked" or pv.get("verdict") == "BLOCKED_DRIFT":
        return step(COMMANDS["planverify"],
                    f"planverify is BLOCKED_DRIFT: revise the plan / tasks per "
                    f"docs/intents/{slug}.planverify.md, then re-verify", slug, True)

    current = next((n for n in dashboard.STAGES if st[n].get("state") == "current"), None)
    if current is None:
        return None

    if f.get("size") == "lite" and current == "implement":
        return step(COMMANDS["intentguard"],
                    "lite path: implement the change directly, then run the guard "
                    "(it judges the diff against the intent alone)", slug)
    if current == "implement":
        t = st["tasks"]
        done, total = t.get("done", 0), t.get("total", 0)
        return step(COMMANDS["implement"], f"{done}/{total} tasks done", slug)
    if current == "writeback" and ig.get("verdict") == "REVIEW NEEDED":
        return step(COMMANDS["writeback"],
                    "intentguard says REVIEW NEEDED: have a human clear the items first", slug)
    return step(COMMANDS[current], dashboard.STAGE_DESCRIPTIONS.get(current, ""), slug)


def plan(root):
    if not os.path.isdir(os.path.join(root, "docs/compound")):
        return [step("/speckit-compound-load",
                     "no compound store yet: load scaffolds docs/compound/ and reads it into context")]

    state = dashboard.scan_state(root, include_heavy=False)
    active = [f for f in state["features"] if str(f.get("status", "")).lower() != "completed"]
    steps = [s for s in (feature_step(f) for f in active) if s]
    steps.sort(key=lambda s: not s["urgent"])

    if not steps:
        steps.append(step(COMMANDS["intent"],
                          "no active feature: start one (add 'lite' for small work: "
                          "3 files or fewer, no new dependency, contract or module)"))

    findings = compound_refresh.scan(root)
    if findings:
        n = len(findings)
        steps.append(step("/speckit-compound-writeback refresh",
                          f"the store has {n} refresh finding{'s' if n != 1 else ''} "
                          f"(stale, duplicate or unguarded entries)"))
    return steps


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="list every active feature (text mode shows 5)")
    args = ap.parse_args()
    root = os.path.abspath(args.root) if args.root else dashboard.find_repo_root(os.getcwd())
    steps = plan(root)

    if args.json:
        json.dump({"root": root, "next": steps}, sys.stdout, indent=2)
        print()
        return 0

    # the refresh suggestion is store-wide; keep it visible even when capped
    tail = [s for s in steps if s["feature"] is None and s["command"].endswith("refresh")]
    body = [s for s in steps if s not in tail]
    hidden = 0 if args.all else max(0, len(body) - 5)
    shown = (body if args.all else body[:5]) + tail
    for i, s in enumerate(shown, 1):
        who = f"[{s['feature']}] " if s["feature"] else ""
        flag = "! " if s["urgent"] else ""
        print(f"{i}. {flag}{who}{s['command']}")
        print(f"   {s['why']}")
    if hidden:
        print(f"   (+{hidden} more active feature{'s' if hidden != 1 else ''}; --all to list them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
