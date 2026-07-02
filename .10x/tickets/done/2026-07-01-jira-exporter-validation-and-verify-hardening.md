Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-deep-correctness-audit-jira-exporter.md

# Jira Exporter Validation And Verify Hardening

## Scope

Address residual validation and verification hardening gaps identified during the deep correctness audit.

## Acceptance Criteria

- Negative `sync.overlap_minutes` is rejected by config validation.
- `verify` compares SQLite issue hash columns against current Markdown/raw JSON files or records why manifest-only verification remains intentional.
- Whole-run failures during per-issue normalization/write include enough issue context to act on the failure where practical.
- Tests cover any changed behavior.

## Blockers

None.

## References

- `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`

## Evidence Expectations

- Focused tests for config validation and verify/state hash behavior.
- Full pytest, ruff, and mypy.

## Progress and Notes

- 2026-07-01: Completed the per-issue attribution slice owned by the current operations task. `_run_search_export` now raises and records issue-key-prefixed messages for per-issue write and normalization failures where the Jira issue key is available. The other acceptance criteria remain open.
- 2026-07-01: Completed remaining validation and verify hardening. `sync.overlap_minutes` is constrained to non-negative values with `0` allowed. `verify` now compares SQLite issue hash columns against current Markdown/raw JSON files and reports hash mismatches or missing files for state rows with stored hash values while preserving clean's historical no-hash rows. Exact `uv run ruff check .` was made useful by excluding local generated dependency/cache directories.
- 2026-07-01: Closed with evidence in `.10x/evidence/2026-07-01-jira-cursor-validation-verify-hardening.md`.

## Closure

Acceptance criteria are satisfied:

- Negative `sync.overlap_minutes` is rejected by Pydantic config validation; zero remains valid.
- `verify` compares SQLite issue `markdown_hash`, `raw_json_hash`, and stable content hash authority against current local files/frontmatter.
- Whole-run per-issue attribution was completed in the earlier operations slice.
- Focused tests and full verification passed.

Retrospective: state rows can be historical because clean must preserve SQLite history. Verify should treat stored hash values as authority, not merely row existence, so historical rows without hashes do not conflict with clean semantics.

## Evidence

- `.10x/evidence/2026-07-01-jira-operations-correctness-verification.md`
- `.10x/evidence/2026-07-01-jira-cursor-validation-verify-hardening.md`
