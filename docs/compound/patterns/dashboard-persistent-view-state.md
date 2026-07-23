# Pattern: Dashboard persistent view state (survives the poll and a restart)

## When to use
Any dashboard view control whose state must survive both the 3-second `/api/state`
poll re-render AND a dashboard restart — e.g. a search box, sort mode, filter chips,
or collapsed/expanded sections. The trap this avoids: the poll replaces the global
`STATE` every 3s and re-renders, so any view state stored on `STATE` (or re-derived
from it) is silently reset while the user is interacting.

## How
1. Hold each piece of view state in a **module-level JS variable**, hydrated from
   localStorage on load with a try/catch fallback (so private/incognito browsing
   degrades to session-only with no error):
   ```js
   function lsGet(k,d){ try{ const v=localStorage.getItem(k); return v==null?d:v; }catch(e){ return d; } }
   function lsSet(k,v){ try{ localStorage.setItem(k,v); }catch(e){} }
   let MQ = lsGet("skc-mq","");            // scalar
   let MCHIPS = /* JSON.parse(lsGet(...)) with Array.isArray guard */;
   function persistView(){ lsSet("skc-mq",MQ); /* ...all keys... */ }
   ```
2. On every change, update the module var, call `persistView()`, then re-render.
3. **The render function reads the module vars, never `STATE`**, for view state. The
   poll's `renderMaster()` call then naturally preserves the user's view.
4. For a live-typed input, preserve focus + caret across the re-render:
   `const pos=el.selectionStart; render(); newEl.focus(); newEl.setSelectionRange(pos,pos);`

## Why this works here
The poll owns `STATE`; view state must live *outside* `STATE` to survive it, and in
localStorage to survive a restart. See ADR-001 (derived views are client-side over the
poll) — this pattern is how such a view keeps user state stable across polls.

## Examples in this repo
- `dashboard.py` — `MQ` / `MSORT` / `MCHIPS` / `MCOLLAPSE`, `persistView()`, `wireControls()`
- `docs/intents/feature-swimlane-triage.intent.md` (feature feature-swimlane-triage)
