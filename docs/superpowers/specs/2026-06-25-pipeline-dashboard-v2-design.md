# Design addendum: dashboard v2 — content, diagrams, tokens, drift

- **Date**: 2026-06-25
- **Status**: approved for planning
- **Builds on**: `2026-06-25-pipeline-dashboard-design.md` (v1 — the read-only scanner + rail + server). This addendum adds five capabilities; it does not change v1's constraints (read-only, no command changes, Python stdlib only, 127.0.0.1).

---

## 1. What this adds (and why)

The v1 dashboard shows *where* each feature is on the chain. v2 answers *what was promised, what got built, what it cost, and where it drifted* — the confidence layer.

| # | Capability | Source | New write? |
|---|---|---|---|
| 1 | **Inline content** — goal, constraints, failure conditions, expectations scenarios shown in the expanded row | parse intent + expectations markdown bodies | no |
| 2 | **Drift panel** — per-feature intentguard findings (OOS hits, constraint violations, expectation fails) | parse `docs/intents/<slug>.intentguard.md` body | no |
| 3 | **Live flowchart** — the 9-stage chain as a labeled flow, lit per selected feature | reuses scan stage states | no |
| 4 | **Static arch diagram** — how the read-only tool works | hand-built SVG, fixed | no |
| 5 | **Token usage** — input/output/cache tokens per session, attributed to features | parse `~/.claude/projects/<repo-slug>/*.jsonl` | no |

All five remain read-only and dependency-free. No Mermaid / no CDN — diagrams are hand-built SVG/CSS (a CDN script would violate v1's self-contained constraint).

## 2. Non-goals (YAGNI)

- No per-message token timeline / graphs. A total + per-feature attribution is enough.
- No editing of intent/expectations from the UI. Still read-only.
- No changes to the 8 chain commands. Token data comes from transcripts that already exist, not from new command writes.
- No exact token attribution guarantees. Attribution is heuristic and labeled as such (see §6).
- No historical token tracking across machines — transcripts are local; that's accepted.

## 3. Content parsing (capability 1)

Extend the scanner to read section bodies. New pure helpers:

- `extract_goal(intent_text) -> str` — the text after `# Intent:` on that line (`"An agent cannot make a mistake the team already documented."`). `""` if absent.
- `extract_section(md_text, header) -> list[str]` — returns the list-item lines (`- ...` / `**Cn**: ...`) under a `## <header>` heading until the next `##`. Used for intent `## Constraints`, `## Failure conditions`, `## Out of scope`, and expectations `## Positive scenarios` / `## Edge / negative scenarios`.

Scanner adds to each feature dict a `content` key:

```json
"content": {
  "goal": "An agent cannot make a mistake the team already documented.",
  "constraints": ["**C1**: p95 hook execution time < 250ms ...", "..."],
  "failures": ["**F1**: Build fails", "..."],
  "out_of_scope": ["Multi-CLI support ...", "..."],
  "expectations_positive": ["**E1**: A developer with at least one matchable correction ...", "..."],
  "expectations_edge": ["**E7**: An agent attempts a Write ...", "..."]
}
```

Each list is best-effort; a missing file or section yields `[]` / `""`. The expanded row renders these as labeled blocks (Goal prominent; Constraints / Failure conditions / Expectations as collapsible sub-lists). This is the confidence layer — the promise is visible next to the progress.

## 4. Drift panel (capability 2)

The intentguard report (`docs/intents/<slug>.intentguard.md`) already encodes the L3 drift check. Parse its body:

- `parse_intentguard(md_text) -> dict` returns:
```json
{
  "verdict": "BLOCKED" | "REVIEW NEEDED" | "PASS" | null,
  "drift": [
    {"level": "L3a", "kind": "out-of-scope", "text": "<item>: matched at file:line → BLOCKED", "severity": "blocked"},
    {"level": "L3b", "kind": "constraint",   "text": "**C1**: BLOCKED — <rationale>", "severity": "blocked"},
    {"level": "L3d", "kind": "expectation",  "text": "**E2**: REVIEW NEEDED — <rationale>", "severity": "review"}
  ]
}
```
- A drift item is any L3a/L3b/L3d body line containing `BLOCKED` or `REVIEW` (case-insensitive). `severity` = `blocked` if the line says BLOCKED, else `review`. Lines that are clean (`PASS`) are not drift and are omitted.
- `verdict` comes from frontmatter `verdict:` (already parsed in v1) — kept authoritative; the body scan only populates the itemized drift list.

This attaches to the feature's `stages.intentguard` dict as `drift: [...]`. The UI shows a **Drift** panel in the expanded row: verdict badge + the itemized list, red for blocked, amber for review. No intentguard file → "not validated yet."

## 5. Diagrams (capabilities 3 + 4)

**Flowchart (live).** A dedicated section above the feature list, or inside the expanded row (decision: inside the expanded row, so it reflects the *selected* feature). Nine stage boxes left→right with arrowheads and a one-line description under each (e.g. `01 INTENT — goal + constraints + failure conditions`). Boxes colored by the selected feature's stage states (done/current/pending/blocked) reusing the rail color tokens. Pure CSS flex + a small inline SVG arrowhead. Horizontally scrollable on narrow widths.

**Arch diagram (static).** An "About" panel (toggle in the header) holding a fixed inline SVG:
`filesystem [docs/ · specs/ · ~/.claude transcripts] → scan_state() → GET /api/state → page (polls every 3s)`.
A one-paragraph caption stating the read-only, no-deps, localhost design. This is reference; it does not change with scan results.

Stage descriptions (constant, drawn once):

```
01 INTENT       goal + constraints + failure conditions
02 EXPECTATIONS success + edge scenarios (validator-only)
03 SPECIFY      spec.md from intent
04 PLAN         design + architecture
05 TASKS        dependency-ordered task list
06 GAPFILL      add missing constraint/failure/OOS tests
07 IMPLEMENT    build (tasks checked off)
08 INTENTGUARD  L3 validation → PASS / REVIEW / BLOCKED
09 WRITEBACK    persist ADRs / corrections / patterns
```

## 6. Token usage (capability 5)

**Source.** `~/.claude/projects/<repo-slug>/*.jsonl`, where `<repo-slug>` is the repo path with `/` → `-` (confirmed format: `-Users-adit-StudioProjects-spec-kit-compound`). Each line is a JSON message; lines with a `message.usage` (or top-level `usage`) block carry token fields: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`. Each line also has `sessionId` and `timestamp` (ISO).

**Helper.** `scan_tokens(home, repo_root) -> dict`:
```json
{
  "available": true,
  "total": {"input": N, "output": N, "cache_creation": N, "cache_read": N, "billable": N},
  "sessions": [
    {"session": "<id>", "first": "<iso>", "last": "<iso>",
     "tokens": {"input": N, "output": N, "cache_creation": N, "cache_read": N, "billable": N}}
  ]
}
```
- `billable = input + output + cache_creation` (cache_read shown separately, not summed into billable — it's discounted).
- `available: false` (and empty totals) when the project log dir is absent — degrades silently, the token panel shows "no local transcripts found."
- Robust to schema drift: each line wrapped in try/except; a line without usage is skipped; an unexpected field is ignored.

**Attribution (heuristic, labeled).** v2 scope keeps attribution simple and honest:
- The header shows the **repo-wide billable total** ("⌁ 1.2M tokens across N sessions") — exact, no guessing.
- Per-feature attribution is **deferred to a later round** unless cheap: if a session's messages reference a feature slug (the slug string appears in the transcript line), tally those sessions to that feature and show it on the row marked `~` (inferred). If that proves noisy in live testing, it stays header-only. The spec does not promise per-feature token accuracy; it promises an exact repo total plus a best-effort, clearly-marked per-feature hint.

## 7. Data model delta

`scan_state(repo_root, now=None, home=None)` gains a `home` arg (defaults to `os.path.expanduser("~")`, overridable for tests). Top-level adds:
```json
"tokens": { ...scan_tokens output... },
"stage_descriptions": { "intent": "goal + constraints + failure conditions", ... }
```
Each feature gains `content` (§3) and `stages.intentguard.drift` (§4).

## 8. Error handling

- Every body parse is defensive: missing file → `""`/`[]`; malformed section → skipped, never raised.
- Token scan: missing dir → `available:false`; unreadable/garbled line → skipped; never crashes the `/api/state` response.
- The page renders each new panel independently — a feature with no content still shows its rail; a repo with no transcripts still shows everything else.

## 9. Testing

- `extract_goal` / `extract_section`: fixture intent/expectations text → expected lists; missing-section → `[]`.
- `parse_intentguard`: a BLOCKED report fixture → verdict + drift items with correct severities; a PASS report → empty drift; a missing file → `{verdict:null, drift:[]}`.
- `scan_tokens`: a temp `home/.claude/projects/<slug>/x.jsonl` fixture with two sessions → correct per-session and total sums; missing dir → `available:false`; a line with no usage → skipped; a garbled line → skipped without raising.
- `scan_state` integration: a feature with intent+expectations+intentguard present → `content` populated, `drift` populated, `tokens` merged.
- `PAGE_HTML`: assert the new panels' anchors exist (flowchart, drift, About/arch, token total) and still self-contained (no `<script src=`, no external stylesheet beyond the font import).
- Existing v1 tests must still pass.

## 10. Open questions

None blocking. Per-feature token attribution accuracy is explicitly scoped as best-effort/labeled (§6); if live testing shows it's noisy, it degrades to header-only with no spec change.
