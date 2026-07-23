---
slug: feature-swimlane-triage
status: active
created: 2026-07-23
intent: ../intents/feature-swimlane-triage.intent.md
---

# Expectations: Developers can triage every feature on a branch by its pipeline progress — grouped, searchable, and sortable — so a teammate can pick up work someone else started.

> **Compartmentation note.** This file is consumed by `/speckit-compound-intentguard`. It is NOT consumed by `/speckit-implement`. Do not paste scenarios from this file into builder prompts.

## Positive scenarios
- **E1**: A developer opens the dashboard and the feature list appears grouped under lane headers (Needs attention, WIP, Review, Backlog, Done), each header showing a count of the features in it.
- **E2**: A developer types part of a feature's name into the search box; within a moment only matching features remain visible across the lanes, updating as they keep typing, with no button to press.
- **E3**: A developer searches a word that appears only inside a compound-store decision note — not in any feature name or goal — and the feature whose store text contains that word stays visible.
- **E4**: A developer changes the sort control to alphabetical; the features inside each lane reorder A–Z while the lanes themselves keep their fixed top-to-bottom order.
- **E5**: A developer toggles off every lane except WIP and only in-progress features remain, while any feature needing attention still shows regardless of the toggles.
- **E6**: A developer sets a search term and a sort mode, then closes and reopens the dashboard, and the same search term, sort mode, and collapsed lanes are still in effect.
- **E7**: A developer sees a distinct "in-progress" dot on a feature whose intent or expectation doc a teammate is still drafting, and a distinct attention badge on a blocked feature that stays on the card even when that feature is filtered into another lane.

## Edge / negative scenarios
- **E8**: A developer opens the dashboard on a branch with no intent docs yet and sees a clear empty state (or empty lanes with zero counts), never an error or a blank screen.
- **E9**: A developer searches a term that matches nothing; every lane reads zero with a clear "no matches" indication, and clearing the search restores all features.
- **E10**: A developer in private/incognito browsing uses search, sort, and lane toggles; everything works for the session and simply does not persist after a restart, with no error shown.
- **E11**: While a developer has a search typed and a lane collapsed, the 3-second background refresh brings in a teammate's newly added feature; the new feature appears in its correct lane without resetting the developer's search, sort, or collapse state.
- **E12**: A developer using only the keyboard can reach and operate the search box, the sort control, and each lane chip in order, and a screen reader announces every lane header and each chip's on/off state.

## Test record
- Total scenarios: 7 positive + 5 edge = 12
- All pass E1–E4

## Compound store refs
- Patterns reached for: none
- Corrections applied: none
