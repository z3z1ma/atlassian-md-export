Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-scaffold-atlassian-md-export-python-package.md

# Implement Jira Client And Sync State

## Scope

Implement Jira Cloud REST API v3 client behavior, issue discovery via `/rest/api/3/search/jql`, comment pagination, incremental sync decisions, retry/backoff handling, and SQLite state tracking.

## Acceptance Criteria

- Issue discovery uses `/rest/api/3/search/jql` and paginates with `nextPageToken`.
- No implementation path uses legacy `/rest/api/3/search`.
- Comments for each exported issue are fetched from `/rest/api/3/issue/{issueIdOrKey}/comment` and paginated until complete.
- Search-embedded comments are ignored as authoritative comments.
- Exact issue repulls use the same normalized discovery/fetch path where practical.
- SQLite tracks issue key, id, updated timestamp, content hash, raw JSON hash, Markdown hash, last seen time, last exported time, and run metadata.
- Default incremental pull uses the last successful representative run with a 10-minute overlap.
- `--force`, `--since`, and `--issue` behavior matches `.10x/specs/jira-export-api-sync.md`.
- HTTP 429 and 5xx responses retry with exponential backoff and jitter, respecting `Retry-After`.
- HTTP 401 fails fast with an actionable auth error and no secret leakage.
- Partial failures do not advance the last successful representative run.

## Blockers

None.

## Progress and Notes

- 2026-07-01: Ticket opened from ratified parent plan.
- 2026-07-01: Entered inner loop after scaffold ticket completed with evidence.
- 2026-07-01: Implemented Jira v3 enhanced search, comment pagination, exact-key JQL, retry/auth error handling, SQLite run/issue state, and incremental sync decisions.
- 2026-07-01: Verified with pytest, scoped ruff, mypy, and source-only legacy endpoint grep.

## Explicit Exclusions

- Do not implement Markdown formatting beyond data structures required by downstream writer.
- Do not download attachment binaries in this ticket except through mocked client seams if needed for tests.
- Do not implement Confluence API calls.

## References

- `.10x/specs/jira-export-api-sync.md`
- `.10x/specs/atlassian-md-export-cli-config.md`
- `.10x/research/2026-07-01-jira-cloud-v3-export-api-facts.md`

## Evidence Expectations

- Unit tests for incremental sync decisions.
- Mocked HTTP tests for search pagination, comments pagination, 429 retry, 401 auth failure, and partial failure.
- Evidence that legacy `/rest/api/3/search` is absent from implementation except tests/docs warning against it.

## Evidence

- `.10x/evidence/2026-07-01-jira-client-sync-state.md`

## Closure Review

- All acceptance criteria are satisfied by `.10x/evidence/2026-07-01-jira-client-sync-state.md`.
- The ticket intentionally does not implement Markdown rendering, attachment binary download, or Confluence calls.
- No follow-up ticket is required for this slice.

## Retrospective

- Use `httpx.MockTransport` for Jira API behavior tests; it avoids adding a mocking dependency and keeps endpoint assertions direct.
- Source-only endpoint grep avoids treating defensive tests that mention legacy `/rest/api/3/search` as implementation usage.
