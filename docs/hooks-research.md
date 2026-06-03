# Agentic CLI hooks — research findings (June 2026)

Research kicked off by the question: *do Claude Code, Codex, Cursor, Gemini CLI have hooks that intercept file read/write and run validation (complexity check, intent-justification, etc.) **before** the action completes? Goal: build pre-action quality hooks for spec-kit-compound v0.3+.*

**TL;DR:** yes, all four major agentic CLIs shipped hook systems in 2025–2026 with converged shape. Pre-action interception with blocking is idiomatic across vendors. The opportunity for spec-kit-compound v0.3 is to enforce discipline at the **tool level** (every Write/Edit) instead of only at the **spec-kit phase boundaries** (before /speckit-specify, after /speckit-implement) it currently uses.

---

## The four CLIs, side-by-side

| CLI | Pre-action event | Config location | Block mechanism | Released |
|---|---|---|---|---|
| **Claude Code** | `PreToolUse` (matcher: `Write\|Edit\|Bash`) | `.claude/settings.json` (project) or `~/.claude/settings.json` (user) | exit 2 → stderr message returned to model | Jan 2026 |
| **OpenAI Codex CLI** | `PreToolUse` + `PermissionRequest` + several others | `~/.codex/config` and plugin manifests | exit 2 + stderr reason; same Unix shell convention | v0.117.0 (2026) |
| **Cursor** | `beforeShellExecution`, `beforeReadFile`, `beforeMCPExecution`, `afterFileEdit`, `stop` | JSON config | Structured JSON output (decision: deny / allow) | Cursor 1.7 (Oct 2025) |
| **Gemini CLI** | `BeforeTool` / `AfterTool` (matcher regex for tool names) | `.gemini/settings.json` | JSON return: `{decision: "deny", reason: ...}` | 2026 |

### Convergent shape

Across all four, the contract is the same:

1. Hook is a **shell command** registered in a settings file
2. **Matcher** scopes which tool/action triggers it (e.g., `Write|Edit` to match file writes)
3. Hook receives **JSON via stdin** containing the tool name, the tool input (file path, content, command, etc.), and a tool-use ID
4. Hook returns control via **exit code** or **structured JSON output**
5. Exit 2 (or `decision: "deny"`) → action is blocked, reason fed back to the model
6. Exit 0 (or `decision: "allow"`) → action proceeds

The vendors copied each other. Codex CLI's hooks doc is structurally identical to Claude Code's; Gemini renamed events to `BeforeTool` but kept the JSON contract. This convergence means **one mental model + per-vendor config translation = full coverage.**

---

## Claude Code in depth (the 80% case)

Claude Code is the harness most spec-kit-compound users run, so this is where v0.3 hook investment pays back the most.

### Configuration

```jsonc
// .claude/settings.json  (project-level; commit this)
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/compound-oos-gate.sh"
          }
        ]
      }
    ]
  }
}
```

### What the script sees

When the agent calls `Write({"file_path": "src/foo.kt", "content": "..."})`:

```jsonc
// stdin to hook script
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/abs/path/src/foo.kt",
    "content": "..."
  },
  "tool_use_id": "toolu_01..."
}
```

The script can `jq` out fields:

```bash
file_path=$(jq -r '.tool_input.file_path')
content=$(jq -r '.tool_input.content')
```

### How to block

```bash
# Inside compound-oos-gate.sh
if echo "$file_path" | grep -qE "$(cat docs/intents/*.intent.md | grep -A20 'out-of-scope' | extract-paths)"; then
  echo "This file is declared out-of-scope in the active intent doc. Revise intent first or refactor proposed change." >&2
  exit 2
fi
exit 0
```

The stderr message becomes context the model reads — it knows *why* the action was blocked and can adjust its plan.

### Lifecycle events available (~12 total in current Claude Code)

- **`PreToolUse`** — before any tool invocation (Write, Edit, Bash, etc.) ← **the one we care about**
- **`PostToolUse`** — after a tool invocation, useful for cleanup (formatting, linting)
- `UserPromptSubmit` — before a user message is sent to the model
- `Notification` — when Claude needs user input
- `Stop` — when Claude finishes a response
- `SubagentStop` — when a sub-agent finishes
- `PreCompact` / `PostCompact` — around context compaction
- Plus session start/end events

### Known caveats

- **Exit code 2 had a regression in early 2026** ([issue #24327](https://github.com/anthropics/claude-code/issues/24327)) where Claude would stop instead of replanning. Verify current behavior before shipping.
- **Hooks run synchronously and block the agent loop** — keep them fast. >5 seconds becomes annoying; >30 seconds breaks the UX.
- **Project-level hooks (`.claude/settings.json`) and user-level hooks (`~/.claude/settings.json`) merge.** Be defensive about not stomping the user's existing hooks when installing.

---

## What this enables for spec-kit-compound v0.3+

Today the discipline fires only when the user types a spec-kit slash command:
- `before_specify`: our require-intent gate hook (v0.2.2)
- `after_implement`: user manually runs `/speckit-compound-intentguard`

If the user just opens Claude and starts coding without spec-kit at all, our extension is invisible. With `PreToolUse` hooks, we can enforce discipline **at the moment the agent attempts a tool call** — regardless of whether spec-kit is in the loop.

Four concrete hook designs:

### (a) OOS write-gate — highest leverage

**Trigger:** `PreToolUse` on `Write|Edit`

**Logic:** read the active intent doc (`docs/intents/{active-slug}.intent.md`), parse its `## Out of scope` section, check whether the file path the agent wants to touch matches any declared OOS pattern.

**Block:** exit 2 with *"This file is declared out-of-scope in `docs/intents/{slug}.intent.md`. If this is intentional, revise the intent doc first."*

**Value:** today, `/speckit-compound-intentguard` catches OOS violations **post-hoc** — after the diff is already written and the agent has burned tokens. With this hook, the violation is caught **at the moment the agent attempts the Write** — zero wasted code generation, no revert needed.

### (b) Complexity gate

**Trigger:** `PreToolUse` on `Write` matching `*.kt`, `*.ts`, `*.py`, etc.

**Logic:** quick static analysis on the proposed file content. If any function exceeds cyclomatic complexity threshold (configurable, e.g. 10), block.

**Block:** exit 2 with *"Function X has complexity Y > 10. Either refactor before writing, or add a `// complexity-exempt: <reason>` justification."*

**Value:** stops "AI ships bloated mega-function" failure mode at write time.

### (c) Correction-pattern match

**Trigger:** `PreToolUse` on `Write|Edit`

**Logic:** scan `docs/compound/corrections/` for known correction rules. If the proposed change matches a known anti-pattern (regex over the file content + path), block.

**Block:** exit 2 with *"This matches correction `2026-05-14-no-css-filters`: <derived rule>. See `docs/compound/corrections/2026-05-14-no-css-filters.md` for context."*

**Value:** turns the compound store from passive context into **active enforcement**. Today the agent reads correction notes during `/speckit-compound-load` but may forget or ignore them. With this hook, repeating a known correction is impossible — the write is blocked at the tool level.

### (d) Intent existence check (extends v0.2.2's gate)

**Trigger:** `PreToolUse` on `Write` matching `src/**` or `app/**`

**Logic:** check whether any active intent doc exists. If not, block.

**Block:** exit 2 with *"No active intent doc found in `docs/intents/`. Run `/speckit-compound-intent` to capture goal, constraints, and failure conditions before writing source code."*

**Value:** today the v0.2.2 `before_specify` gate enforces the discipline when the user types `/speckit-specify`. With this hook, the discipline is enforced even when the user **skips spec-kit entirely and just starts coding** — the agent literally cannot write source files without an intent doc on disk.

---

## v0.3 architecture sketch

The Claude Code hooks live in `.claude/settings.json` — that's a **project file**, not part of our extension's `.specify/extensions/compound/`. So shipping these as part of spec-kit-compound means:

```
spec-kit-compound/
├── .claude/                               ← NEW in v0.3
│   ├── settings.template.json             ← hook registrations template
│   └── hooks/                             ← bash hook scripts
│       ├── compound-oos-gate.sh
│       ├── compound-complexity-gate.sh
│       ├── compound-correction-match.sh
│       └── compound-require-intent.sh
├── commands/
│   └── speckit.compound.install-hooks.md  ← NEW one-time installer
└── scripts/
    └── install-claude-hooks.sh            ← does the merge into user's settings.json
```

**One-time installer flow:**

1. User invokes `/speckit-compound-install-hooks` in their project
2. The install script reads `.claude/settings.template.json` from our extension
3. Merges hook entries into the user's existing `.claude/settings.json` (preserving any pre-existing hooks)
4. Copies the bash scripts to `.claude/hooks/`
5. Makes them executable
6. Confirms

After install, every Write/Edit the agent attempts in that project goes through our four gates. Discipline enforced at the tool level.

**Two-layer enforcement:**

| Layer | Mechanism | Trigger | Today | v0.3 |
|---|---|---|---|---|
| **L1 — Phase boundaries** | spec-kit hooks (`before_specify`) | User types `/speckit-specify` | ✓ (v0.2.2) | ✓ (unchanged) |
| **L2 — Tool calls** | Claude Code `PreToolUse` hooks | Agent attempts Write/Edit | — | ✓ (v0.3+) |

L2 catches everything L1 catches, plus everything L1 misses (raw agent sessions without spec-kit).

---

## Per-CLI portability

If we want spec-kit-compound to enforce at the tool level across all four CLIs, we need a per-CLI installer:

- **Claude Code**: write `.claude/settings.json` entries + `.claude/hooks/` scripts (as designed above)
- **Codex CLI**: write `.codex/config` entries pointing at the same bash scripts (Codex's hook contract is identical)
- **Cursor**: write Cursor 1.7 hooks config (slightly different event names: `beforeReadFile`, `afterFileEdit`)
- **Gemini CLI**: write `.gemini/settings.json` entries with `BeforeTool` matcher and a structured-JSON-returning script wrapper (since Gemini wants JSON output, not just exit codes)

The bash scripts themselves can be **CLI-agnostic** if they only consume the stdin JSON and emit stderr + exit code. The settings translation is the only per-CLI work.

For v0.3, ship Claude Code support only. Add the other CLIs in v0.4+ as users ask.

---

## Server-side caveat

These are all **client-side** hooks. They don't fire if someone runs the agent without the harness's hook system (e.g., raw API calls, custom orchestrators, CI bots). For belt-and-braces enforcement:

- **`.git/hooks/pre-commit`** — reject commits that violate intent/compound rules (final safety net)
- **CI checks** — `scripts/check-chain-fired.sh` already gives us this in v0.2.1+; could be wired as a required GitHub Action
- **Server-side commit-time validators** — push-time checks that reject pushes lacking valid `docs/intents/{slug}.intent.md` for the touched files

These are orthogonal to the hook system. Multi-layer defense.

---

## Sources

- [Claude Code Hooks Reference (canonical)](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks 2026 Complete Reference (32+ events)](https://thepromptshelf.dev/blog/claude-code-hooks-complete-reference-2026/)
- [How to Configure Claude Code Hooks (Anthropic blog)](https://claude.com/blog/how-to-configure-hooks)
- [Hooks Complete Guide — 12 Lifecycle Events](https://claudefa.st/blog/tools/hooks/hooks-guide)
- [Block Tool Commands Before Execution with PreToolUse Hooks](https://egghead.io/block-tool-commands-before-execution-with-pre-tool-use-hooks~erv55)
- [Known issue: PreToolUse exit code 2 stop bug](https://github.com/anthropics/claude-code/issues/24327)
- [Codex CLI Hooks (canonical)](https://developers.openai.com/codex/hooks)
- [Codex CLI Hooks Complete Guide](https://codex.danielvaughan.com/2026/04/15/codex-cli-hooks-complete-guide-events-policy-patterns/)
- [Cursor Hooks Docs](https://cursor.com/docs/hooks)
- [Cursor 1.7 Hooks Guide](https://skywork.ai/blog/how-to-cursor-1-7-hooks-guide/)
- [Cursor 1.7 Adds Hooks (InfoQ)](https://www.infoq.com/news/2025/10/cursor-hooks/)
- [Gemini CLI Hooks (canonical)](https://geminicli.com/docs/hooks/)
- [Gemini CLI Hooks Reference](https://geminicli.com/docs/hooks/reference/)
