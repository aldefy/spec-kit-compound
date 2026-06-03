# Upstream issue draft for github/spec-kit

**Status:** draft — review before filing. Copy the body below into a new issue at <https://github.com/github/spec-kit/issues/new>.

---

## Suggested title

> Hook executor under Claude Code integration silently no-ops agent-prompt hooks (only shell-script-wrapper hooks dispatch)

## Suggested labels

`bug` · `claude-code` · `extensions` · `hooks`

## Body

### Summary

Spec-kit's extension hook system dispatches **shell-script-wrapper** hooks correctly under the Claude Code integration (the bundled `git` extension's hooks are proof). However, **agent-prompt** hooks — command files that instruct the agent to do interactive work rather than invoke a script — silently no-op. They register correctly in `.specify/extensions.yml` and appear in the merged hooks list, but the agent never executes them when their phase fires.

This means third-party extensions whose value-add is in agent-driven prompts (interactive interviews, LLM-judged validations, etc.) cannot use the hook system at all, even though `extension.yml` accepts their hook declarations without error.

### Environment

- spec-kit version: latest as of June 2026 (`specify --version` for exact)
- Integration: `claude` (Claude Code)
- OS: macOS 15 (Darwin)
- Extension that surfaced the issue: [spec-kit-compound](https://github.com/aldefy/spec-kit-compound) v0.2.0

### Repro

1. Build an extension whose `extension.yml` registers a `before_specify` hook pointing at an agent-prompt command (one whose `commands/X.md` body asks the agent to do interactive work, not to run a shell script):

```yaml
hooks:
  before_specify:
    command: speckit.compound.intent
    optional: false
    description: "Run intent interview before /speckit-specify"
```

2. Install: `specify extension add /path/to/extension --dev`
3. Confirm `.specify/extensions.yml` now contains the hook entry under `before_specify` (yes, it does).
4. Run `/speckit-specify "some outcome"` in a Claude Code session.

### Observed

`/speckit-specify` runs to completion. The "Extension Hooks" block in its output only mentions other extensions' hooks (e.g., the bundled `git` extension's `speckit.git.commit` post-hook). Our `speckit.compound.intent` mandatory pre-hook is absent. No interactive interview starts. The spec is generated in vanilla shape.

### Expected

Either:
- The agent dispatches `/speckit-compound-intent` before continuing with `/speckit-specify` (treating `EXECUTE_COMMAND` directives in the `before_specify` pre-execution block as an instruction to actually invoke the named slash command), OR
- The install rejects the registration with a clear error explaining that only shell-script-wrapper command files are supported as hooks.

### Why this matters

The hook system is the natural extension point for third-party authors who want to *add* discipline to the SDD workflow (intent capture, expectations capture, validation gates, post-implementation review). With the current behavior, those authors have two options:

1. **Wrap their work in a shell script** — fine when the work is deterministic (a coverage check, a regex grep) but impossible when the work needs an agent (an interactive interview, LLM-judged scope validation).
2. **Document a manual chain** — works but loses the "drop in and it just runs" affordance the hook system advertises.

The bundled `git` extension's hooks fall into option 1 (deterministic scripts), so the limitation has been invisible. The first extension to try option 2 (ours) hit it head-on.

### Workaround we shipped

[spec-kit-compound v0.2.1](https://github.com/aldefy/spec-kit-compound/releases/tag/v0.2.1) removed the broken hook entries and made the chain manual (with `scripts/check-chain-fired.sh` as a post-flight eval). [v0.2.2](https://github.com/aldefy/spec-kit-compound/releases/tag/v0.2.2) added a shell-script-wrapper *gate* hook (`before_specify` → `speckit.compound.require-intent.sh`) that refuses to let `/speckit-specify` proceed if no intent doc exists. This works because the gate is a deterministic script.

The discipline is enforced through gating rather than chaining — workable, but the gate can only refuse, not run the interactive prompt the user actually needs.

### Suggested fix (in priority order)

1. **Make agent-prompt hook dispatch work.** When the hook executor encounters a hook command whose target file is an agent-prompt (no shell script invocation), have the harness actually dispatch that slash command in the user's session before resuming the parent command. This is the spirit of `EXECUTE_COMMAND` in the current `speckit-*` SKILL.md files.
2. **If (1) is infeasible**, reject agent-prompt hooks at install time with a clear error: *"hooks must be shell-script-wrappers; command X invokes interactive agent work, which is not supported."* This at least surfaces the constraint instead of silently no-op'ing.
3. **Document the constraint** in `extensions/EXTENSION-PUBLISHING-GUIDE.md`. The current guide does not mention this limitation; third-party authors learn it the hard way at first live install.

### Additional context

Happy to provide a minimal repro repo (the spec-kit-compound v0.2.0 tag, plus a fresh `specify init` project) if useful. CC: relevant Claude Code integration folks if there's a known handler for this on that side.

---

## Notes to self (do not include in upstream issue)

- The bundled `git` extension proves shell-script hooks dispatch. If the maintainers say "this is intended behavior, scripts only," then suggestion #1 is rejected and we lean on #2 + #3.
- The "in-prompt Phase 8 handoff" pattern (one slash command invokes the next at the end of its prompt) is the workaround we ship and it does work — so a path to fixing this might be: have the hook executor inject the same kind of "dispatch this slash command" instruction the in-prompt handoff uses, just at the hook trigger point instead of at the end of a sibling command.
- After filing, link the issue back in our README and CHANGELOG so future users tracking down "why is this manual" see the upstream conversation.
