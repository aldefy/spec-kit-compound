# Correction-note schema (v0.3+)

For corrections to be enforceable at the tool level (the v0.3+ active-corrections feature), they need machine-readable frontmatter that tells the `PreToolUse` hook *what to look for* and *where to look for it*.

Pre-v0.3 corrections (markdown body only) are still loaded as agent context by `/speckit-compound-load` — they just aren't actively enforced. Upgrade them to the v0.3+ schema when convenient.

---

## Schema

```markdown
---
slug: 2026-06-03-no-css-img-filters
paths:
  - "**/*.css"
  - "**/*.scss"
match: "filter:\\s*(brightness|invert|grayscale)\\("
rule: "Do not apply CSS `filter` properties to image-affecting selectors."
context: "Past mistake: filter: brightness(0.8) on img was used to dim images in dark mode; this broke image rendering on certain GPUs and caused color inaccuracy."
---

# Correction: 2026-06-03 — no CSS image filters

## What happened

…the human-readable correction note body, unchanged from pre-v0.3 format…

## Derived rule

…the long-form rule, optional in v0.3+ because the frontmatter `rule:` field is what the hook cites…
```

---

## Field reference

| Field | Required | Type | Meaning |
|---|---|---|---|
| `slug` | yes | string | Unique identifier. Used in the bypass comment `// compound-allow: <slug>` and in stderr citations. Typically `{YYYY-MM-DD}-{short-name}` matching the filename without `.md`. |
| `paths` | yes | array of glob strings | The hook only runs the regex on writes whose target file path matches at least one of these globs. Use `**/*.ext` for "any file with extension". Empty array = never matches. |
| `match` | yes | string (regex) | Extended POSIX regex (`grep -E` syntax). If this regex matches anywhere in the proposed file content, the correction fires. **Three gotchas**: (1) **POSIX ERE only** — use `[[:space:]]` not `\s`, `[[:digit:]]` not `\d`, `[[:alpha:]]` not `\w`. PCRE shortcuts don't work (`\s` matches literal `s`). (2) **Avoid backslashes inside double-quoted YAML strings** — the YAML→bash→grep pipeline doesn't process YAML escapes, so `\\(` becomes literal `\\(` which grep parses as backslash + unbalanced paren. Use single-quoted YAML (`'...\(...'`) or just drop unnecessary escapes. (3) Test with `echo "<content>" \| grep -E "<regex>"` before committing the correction. |
| `rule` | yes | string | One-line directive shown in the hook's stderr block message under "Rule:". This is what the agent will read and adjust its plan around. Keep it imperative and short. |
| `context` | yes | string | One-line background shown under "Context:". Tell the agent *why* the rule exists — past incident, performance trap, policy reason. |

**All four frontmatter fields are required for the correction to be enforced.** A correction missing any field will be loaded as context (for human readers) but skipped by the hook with a warning to stderr (failure condition F12 of the active-corrections intent).

---

## How matching works (mental model)

For each Write or Edit the agent attempts:

```
for correction in docs/compound/corrections/*.md:
    if correction lacks frontmatter:
        skip (it's a pre-v0.3 context-only correction)

    if any field is missing:
        warn to stderr; skip

    if file_path matches none of correction.paths globs:
        skip

    if proposed content does not match correction.match regex:
        skip

    if content contains "// compound-allow: {correction.slug}":
        skip (per-file escape hatch acknowledged)

    record match

if any matches survive:
    block Write/Edit with stderr block message citing each match
else:
    let Write/Edit proceed
```

---

## Writing a good `match:` regex

Three rules of thumb:

1. **Anchor where you can.** If the mistake is always a function call like `dangerouslySetInnerHTML(...)`, write `\bdangerouslySetInnerHTML\s*\(` not just `dangerouslySetInnerHTML`. Reduces false positives in unrelated mentions (comments, docs, variable names containing the substring).
2. **Target the syntactic form, not the surrounding code.** If the rule is "no console.log in production code", match `console\.log\s*\(` — don't try to also exclude tests in the regex; use the `paths:` glob to exclude `**/*.test.{js,ts}` and similar instead. Path scoping is faster and clearer than negative regex.
3. **Test against your own corpus before committing.** A correction whose regex matches innocuous code is worse than no correction at all — it teaches developers to bypass the hook reflexively. Use `grep -E "your-regex" path/to/sample-file` to dry-run.

---

## Writing a good `rule:` and `context:`

The agent reads these. Write for the agent:

- **`rule:`** is *what to do or not do*. Imperative tense, present tense. *"Do not apply CSS filter properties to image-affecting selectors"* — not *"This rule prohibits..."*
- **`context:`** is *why this rule exists*. One short sentence. *"Past mistake: filter: brightness(0.8) on img caused image rendering issues on certain GPUs"* — gives the agent enough background to suggest an alternative (e.g., "use a darker overlay div instead").

If the rule is more than one line, the correction is probably trying to do too much. Split into two corrections.

---

## Bypass mechanisms

Two ways to get past a correction the agent is otherwise about to be blocked on:

### Per-file (audit trail in code)

Add a comment anywhere in the file being written:

```css
/* compound-allow: 2026-06-03-no-css-img-filters */
img.intentional-dim { filter: brightness(0.85); }
```

The hook scans the proposed content for the literal string `compound-allow: <slug>`. If found, that specific correction is bypassed for this write. The override appears in the diff for PR review.

### Per-session (no audit trail)

Set the environment variable before starting the agent:

```bash
export COMPOUND_BYPASS=1
```

While set, the hook exits 0 immediately for every Write/Edit. No corrections are checked. Use sparingly — leaves no record in the codebase that the discipline was disabled.

---

## Example: full correction file

`docs/compound/corrections/2026-06-03-no-css-img-filters.md`:

```markdown
---
slug: 2026-06-03-no-css-img-filters
paths:
  - "**/*.css"
  - "**/*.scss"
  - "content/themes/**/*.css"
match: "filter:[[:space:]]*(brightness|invert|grayscale)"
rule: "Do not apply CSS filter properties (brightness/invert/grayscale) to img selectors."
context: "Past mistake (Ghost dark mode v1, March 2026): filter: brightness(0.8) on .post img caused color shifts on macOS Safari and a 12% drop in image quality on AMD GPUs. Use a darker page background or overlay div instead."
---

# Correction: 2026-06-03 — no CSS image filters

## What happened

During Ghost dark mode v1, the agent applied `filter: brightness(0.8)` to all `img` elements inside `.post` to "dim" images. This produced visible color shifts in macOS Safari and pixel-diff failures on AMD GPUs.

## Derived rule

The rule in frontmatter (`rule:` field) is the canonical short form. This longer note documents the incident for future readers.

## How to satisfy this rule when you need darkening

Use one of:
- Lower the body background luminance (the perceptual darkening is the same)
- Add a semi-transparent overlay `div` above images for hero shots specifically
- Serve a pre-darkened image variant from the CDN

## Related ADRs

- `docs/compound/adr/008-images-render-at-native-brightness.md` (codified this rule as an architecture decision)
```

When the agent later tries to Write a CSS file containing `img { filter: brightness(0.9) }` to this codebase, the hook fires and blocks with:

```
Blocked by compound-store correction(s). Proposed Write on styles.css matches:

  • docs/compound/corrections/2026-06-03-no-css-img-filters.md
    Rule:    Do not apply CSS filter properties (brightness/invert/grayscale) to img selectors.
    Context: Past mistake (Ghost dark mode v1, March 2026): filter: brightness(0.8) on .post img caused color shifts on macOS Safari and a 12% drop in image quality on AMD GPUs. Use a darker page background or overlay div instead.

To override for this file: add a comment '// compound-allow: <correction-slug>' referencing the correction's basename (without .md).
To bypass for the session: set COMPOUND_BYPASS=1 in the shell environment.
```

The agent reads this stderr and either revises its approach (background darkening, overlay div) or asks the user whether the override is intentional.
