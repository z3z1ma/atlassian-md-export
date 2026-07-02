Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-implement-confluence-cli-config-auth.md

# Implement Confluence Client And Sync State

## Scope

Implement Confluence API client behavior, discovery pagination, page hydration, comments/attachments/labels/hierarchy fetching seams, incremental sync decisions, retry/backoff handling, and SQLite state tracking.

## Acceptance Criteria

- Space resolution and full space discovery use Confluence REST API v2.
- Arbitrary CQL discovery uses `/wiki/rest/api/search` only for discovery and hydrates every page through v2 page detail.
- Ancestor subtree export includes the root page plus descendants from the v2 descendants endpoint.
- v2 pagination follows HTTP `Link` headers until complete.
- CQL pagination follows documented next links/cursors until complete.
- Page hydration requests `body-format=atlas_doc_format` by default.
- Footer comments, inline comments, labels, ancestors, descendants, and attachment metadata have client methods with strict payload validation.
- HTTP 200 malformed payloads fail the run and do not advance sync or cleanup state.
- Incremental CQL date literals use `yyyy-MM-dd HH:mm`, not ISO 8601.
- SQLite tracks page id, space id/key, title, status, parent id, updated timestamp, version, content hash, raw JSON hash, Markdown hash, last seen time, last exported time, and run metadata.
- Default incremental pull uses the last successful compatible run with a 10-minute overlap.
- `--force`, `--since`, exact page repulls, and representative cleanup state match `.10x/specs/confluence-export-api-sync.md`.
- HTTP 429 and 5xx responses retry with exponential backoff and jitter, respecting `Retry-After`.
- HTTP 401 fails fast with an actionable auth error and no secret leakage.
- Partial failures do not advance trusted sync cursor or representative cleanup state.

## Blockers

None.

## Progress And Notes

- 2026-07-01: Ticket opened from ratified Confluence parent plan.
- 2026-07-01: Implemented Confluence REST client support for v2 space/page/resource APIs, v1 CQL discovery with v2 hydration, v2 Link pagination, CQL next-link pagination, default `atlas_doc_format` hydration, strict success-payload validation, provider-specific auth/retry messaging, Confluence CQL date formatting, and provider-specific SQLite page/run state.
- 2026-07-01: Added mocked Confluence HTTP tests for v2 Link pagination, v1 CQL pagination, ancestor subtree hydration, footer/inline comment pagination, resource methods, 429/5xx retry, 401 fail-fast behavior, and malformed 200 payloads.
- 2026-07-01: Added Confluence state tests for page fields, compatible incremental cursor selection with 10-minute overlap, force/since/exact page semantics, representative cleanup authority, partial-failure non-advancement, and CQL date literal formatting.
- 2026-07-01: Verified with focused pytest, full pytest, package mypy, and full ruff. Evidence recorded in `.10x/evidence/2026-07-01-confluence-client-sync-state.md`.
- 2026-07-01: Retrospective: the existing Jira state table should not be overloaded for Confluence page semantics; provider-specific run/page tables kept cleanup authority and incremental cursor behavior legible for downstream Confluence writer/clean tickets. No new reusable skill was needed.

## Explicit Exclusions

- Do not implement Markdown rendering beyond normalized data structures required by downstream writer.
- Do not download attachment binaries in this ticket.
- Do not implement nested comment replies.

## References

- `.10x/specs/confluence-export-api-sync.md`
- `.10x/specs/confluence-cli-config.md`
- `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md`
- `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md`

## Evidence Expectations

- Mocked HTTP tests for v2 Link pagination.
- Mocked HTTP tests for v1 CQL pagination.
- Mocked HTTP tests for footer and inline comment pagination.
- Mocked HTTP tests for 429 retry, 401 auth failure, malformed 200 payloads, and partial failures.
- Unit tests for Confluence incremental sync decisions and CQL date literal formatting.

## Completion Evidence

- `.10x/evidence/2026-07-01-confluence-client-sync-state.md`
