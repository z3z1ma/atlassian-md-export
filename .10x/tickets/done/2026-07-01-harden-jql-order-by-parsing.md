Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-deep-correctness-audit-jira-exporter.md

# Harden JQL Order By Parsing

## Scope

Make JQL `ORDER BY` detection and splitting quote-aware enough to avoid matching `order by` inside string literals.

## Acceptance Criteria

- `ordered_jql('summary ~ "order by"')` appends deterministic ordering.
- `updated_since_jql('summary ~ "order by"', ...)` wraps the full filter and appends the incremental constraint without splitting inside the literal.
- Existing JQL with a real trailing `ORDER BY` clause is preserved.
- Invalid or unsupported JQL shapes fail clearly rather than generating malformed incremental JQL.

## Blockers

None.

## References

- `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`
- `.10x/specs/jira-export-api-sync.md`

## Evidence Expectations

- Unit tests for quoted `order by`, escaped quotes, and real `ORDER BY`.
- Full pytest, ruff, and mypy.

## Progress and Evidence

- 2026-07-01: Replaced whole-string `ORDER BY` detection with quote-aware scanning in `atlassian-md-export/src/atlassian_md_export/jira/client.py`, including practical backslash-escaped quote handling.
- 2026-07-01: Added focused client tests in `atlassian-md-export/tests/test_jira_client.py` for quoted `order by`, escaped quotes, and real trailing `ORDER BY` preservation.
- 2026-07-01: Final parent verification passed with `uv run pytest`, `uv run ruff check .`, `uv run mypy src`, and live Jira sandbox integration for `DATA-4174`.
- Evidence: `.10x/evidence/2026-07-01-jira-client-strict-payload-and-order-by-verification.md`.
