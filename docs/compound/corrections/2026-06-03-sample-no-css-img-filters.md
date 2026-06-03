---
slug: 2026-06-03-sample-no-css-img-filters
paths:
  - "**/*.css"
  - "**/*.scss"
match: "filter:[[:space:]]*(brightness|invert|grayscale)"
rule: "Do not apply CSS filter properties (brightness/invert/grayscale) to img selectors."
context: "Past mistake (Ghost dark mode v1, March 2026): filter: brightness(0.8) on .post img caused color shifts on macOS Safari and a 12% drop in image quality on AMD GPUs. Use a darker page background or overlay div instead."
---

# Correction: 2026-06-03 — no CSS image filters (sample)

> **This is a sample correction shipped with spec-kit-compound v0.3+ to demonstrate the v0.3+ schema and to act as a smoke test.** If you install the extension and run `/speckit-compound-install-hooks`, asking the agent to Write a CSS file containing `img { filter: brightness(...) }` should produce a hook block citing this correction.
>
> Real corrections in your own project should be derived from real incidents via `/speckit-compound-writeback`, not copied from this template.

## What happened

During Ghost dark mode v1 (March 2026), the agent applied `filter: brightness(0.8)` to all `img` elements inside `.post` containers to "dim" images for dark theme. This produced visible color shifts in macOS Safari and pixel-diff failures on AMD GPUs.

## Derived rule

The rule in frontmatter (`rule:` field) is the canonical short form. This longer note documents the incident for future readers.

## How to satisfy this rule when you need darkening

Use one of:
- Lower the body background luminance (the perceptual darkening is the same)
- Add a semi-transparent overlay `div` above images for hero shots specifically
- Serve a pre-darkened image variant from the CDN

## Related

- See `docs/compound/CORRECTIONS-SCHEMA.md` for the full v0.3+ frontmatter spec
- See `docs/intents/active-corrections.intent.md` for the v0.3 design that introduced active enforcement
