# planverify fixtures

Three minimal feature snapshots whose surface analysis deterministically
drives each verdict. To verify end-to-end, copy a fixture into a scratch
spec-kit project as `docs/intents/foo.intent.md`,
`docs/expectations/foo.expectations.md`, `specs/foo/plan.md`,
`specs/foo/tasks.md`, then run `/speckit-compound-planverify` and confirm the
verdict:

| Fixture   | Expected verdict | Why |
|-----------|------------------|-----|
| pass/     | PASS             | surface ⊆ in-scope, full coverage |
| replan/   | REPLAN_ALLOWED   | one bounded `requested_surface` for a sibling file |
| blocked/  | BLOCKED_DRIFT    | touches out-of-scope `src/auth/**` + `src/db/schema.ts`, unrequested |

The surface-analysis layer (Phase 1) is deterministic and shell-extractable;
the checker's LLM judgment (P3a–P3d) is exercised by running the command
against these fixtures.
