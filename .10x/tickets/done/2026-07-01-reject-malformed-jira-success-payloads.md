Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-deep-correctness-audit-jira-exporter.md

# Reject Malformed Jira Success Payloads

## Scope

Fail fast when Jira HTTP 200 search/comment responses omit required payload fields instead of treating missing arrays as empty successful pages.

## Acceptance Criteria

- Search responses missing `issues` fail with `AtlassianClientError`.
- Comment responses missing `comments` fail with `AtlassianClientError`.
- A failed malformed search/comment response does not mark the export run successful.
- Existing pagination behavior remains intact for valid empty arrays.

## Blockers

None.

## References

- `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`
- `.10x/specs/jira-export-api-sync.md`

## Evidence Expectations

- Mocked client tests for missing `issues` and missing `comments`.
- Mocked operation test proving malformed success payload does not advance successful run state.
- Full pytest, ruff, and mypy.

## Progress and Evidence

- 2026-07-01: Implemented strict required-field validation in `atlassian-md-export/src/atlassian_md_export/jira/client.py`; missing search `issues` and missing comment `comments` now raise `AtlassianClientError`, while valid empty arrays remain accepted.
- 2026-07-01: Added focused client tests in `atlassian-md-export/tests/test_jira_client.py` for missing `issues`, missing `comments`, and empty comments.
- 2026-07-01: Verified malformed search/comment payloads through persistent `run_pull` regression tests in `atlassian-md-export/tests/test_operations.py`; failed payloads finalize export runs as failed and preserve the prior successful incremental cursor.
- 2026-07-01: Final parent verification passed with `uv run pytest`, `uv run ruff check .`, `uv run mypy src`, and live Jira sandbox integration for `DATA-4174`.
- Evidence: `.10x/evidence/2026-07-01-jira-client-strict-payload-and-order-by-verification.md`.
