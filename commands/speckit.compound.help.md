---
description: "Tell the user which command to run next (v0.9+): reads each active feature's stage state (intent, expectations, spec, plan, tasks, verdicts) plus the store's refresh findings, and names the next command, blocked features first. Read-only."
---

# What to run next

## User input

```text
$ARGUMENTS
```

You answer one question: **which command should the user run next?** You do not run that command, edit files, or start any work.

## What to do

**1. Run the scanner** from the project root and show its output verbatim:

```bash
python3 .specify/extensions/compound/scripts/compound_next.py
```

(Inside the spec-kit-compound repo itself, the path is `scripts/compound_next.py`.) If the user input contains `all`, add `--all` to list every active feature instead of the first five.

The scanner reuses the dashboard's stage logic, so its answer matches what `/speckit-compound-dashboard` shows. Lines marked `!` are blocked features (intentguard BLOCKED or planverify BLOCKED_DRIFT); they always come first.

**2. Add one sentence of judgement**, only where the scan can't see it:

- If the user described what they want to do next, say whether the **lite path** fits: it does only if the change touches 3 files or fewer, adds no dependency, changes no schema / API contract / persisted format, and adds no module or screen. If so, suggest `/speckit-compound-intent lite`.
- If several features are active, name the one the user seems to be working on (from this conversation), or ask which.
- If the scanner fails (no python3, missing script), fall back to reading `docs/intents/*.intent.md` and the files the stages need, and give your best answer, saying it was not computed.

**3. Stop.** End with the single command to type next, in a code block.

## The chain, for reference

| Stage | Command | Skipped on the lite path |
|---|---|---|
| intent | `/speckit-compound-intent` (`lite` for small work) | |
| expectations | `/speckit-compound-expectations` | yes |
| specify / plan / tasks | `/speckit-specify`, `/speckit-plan`, `/speckit-tasks` | yes |
| gapfill | `/speckit-compound-gapfill` | yes |
| planverify | `/speckit-compound-planverify` | yes |
| implement | `/speckit-implement` (lite: edit directly) | |
| intentguard | `/speckit-compound-intentguard` | |
| writeback | `/speckit-compound-writeback` | |

## What you do NOT do

- **Run the next command yourself.** The user decides when to start it.
- **Edit any file.** This command is read-only.
