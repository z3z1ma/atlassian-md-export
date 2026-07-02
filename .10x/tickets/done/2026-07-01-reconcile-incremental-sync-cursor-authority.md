Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-deep-correctness-audit-jira-exporter.md

# Reconcile Incremental Sync Cursor Authority

## Scope

Resolve and implement the intended cursor authority for default Jira incremental pulls.

## Blocker

Resolved 2026-07-01. Active records previously conflicted:

- `.10x/specs/jira-export-api-sync.md` says default `pull` MUST use the last successful representative pull.
- `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md` says incremental pull decisions SHOULD advance from the latest successful run for the same command/scope.

The spec was amended in `.10x/specs/jira-export-api-sync.md` and the knowledge record was amended in `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md`. The intended contract is now: latest successful non-partial compatible pull advances the sync cursor; only full representative pulls advance cleanup authority; malformed success payloads and partial failures advance neither.

## Recommended Contract

Use a separate trusted incremental cursor concept rather than overloading cleanup representative state:

- Full representative pulls establish both cleanup authority and sync cursor.
- Incremental pulls may advance the sync cursor only after validated search/comment payloads, successful rendering/writes, and no partial failure.
- Cleanup deletion authority remains full representative pulls only.
- False-success or malformed payload responses MUST NOT advance either authority.

## Acceptance Criteria

- Active spec and knowledge records are reconciled.
- Implementation matches the reconciled contract.
- Tests cover full run, successful incremental advancement, malformed/partial incremental non-advancement, and cleanup representative preservation.

## Progress and Notes

- 2026-07-01: Reconciled active spec and knowledge records. Ticket unblocked for implementation/testing against the clarified contract.
- 2026-07-01: Implemented final hardening verification. Existing implementation already used `last_successful_scope_run(...)` for the incremental cursor and preserved representative cleanup authority for full representative runs only. Added regression tests for successful incremental advancement, failed-run non-advancement, same command/scope selection, partial-failure non-advancement, and representative cleanup preservation.
- 2026-07-01: Closed with evidence in `.10x/evidence/2026-07-01-jira-cursor-validation-verify-hardening.md`.

## Closure

Acceptance criteria are satisfied:

- Active spec and knowledge records were reconciled before implementation.
- Implementation matches the reconciled contract: latest successful non-partial same command/scope pull advances the cursor; partial/failed runs do not; cleanup authority remains full representative only.
- Focused state tests cover full run, successful incremental advancement, failed/partial non-advancement, same command/scope selection, and cleanup representative preservation.

Retrospective: keep cursor authority and cleanup deletion authority separate in both naming and tests. A future agent should treat "latest successful run" and "representative run" as intentionally different state concepts.

## References

- `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`
- `.10x/specs/jira-export-api-sync.md`
- `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md`

## Evidence Expectations

- Updated spec/knowledge records.
- State tests for the chosen cursor semantics.
- Full pytest, ruff, and mypy.

## Evidence

- `.10x/evidence/2026-07-01-jira-cursor-validation-verify-hardening.md`
