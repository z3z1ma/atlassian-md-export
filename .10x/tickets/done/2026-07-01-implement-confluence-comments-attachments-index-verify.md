Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-implement-confluence-page-writer.md

# Implement Confluence Comments, Attachments, Indexes, Clean, And Verify

## Scope

Implement Confluence footer/inline comment rendering, attachment metadata and optional downloads, local indexes, manifest updates, `verify`, and `clean --remove-missing`.

## Acceptance Criteria

- Footer comments and inline comments are rendered oldest-first with stable headings and metadata from `.10x/specs/confluence-page-markdown-output.md`.
- Inline comment status/resolution metadata is included when present.
- Attachment handling is metadata-only by default.
- Optional attachment downloads support `--download-attachments`, `--attachment-max-mb`, and repeatable `--attachment-include`.
- Attachment download URLs are constrained to same-origin or safe relative Confluence URLs.
- Downloaded attachments are stored at `attachments/PAGEID/ATTACHMENTID-safe_filename`.
- Downloaded attachment local paths participate in content/state hashing where they affect Markdown.
- Indexes generated match `.10x/specs/confluence-attachments-index-clean-verify.md`.
- Manifest fields and counts match `.10x/specs/confluence-attachments-index-clean-verify.md`.
- `verify --out DIR` validates local consistency without contacting Confluence.
- `clean --out DIR --remove-missing` deletes pages, raw JSON, and downloaded attachment directories only from the last successful representative scope.
- Exact `page`, `comments`, and `attachments` commands do not update cleanup authority.

## Blockers

None.

## Progress And Notes

- 2026-07-01: Ticket opened from ratified Confluence parent plan.
- 2026-07-01: Began implementation. Existing Confluence client/state/page writer records and source were inspected; implementation will add provider-specific operations, attachment handling, indexes, local verify/clean, CLI wiring, and focused tests within the ticket write scope.
- 2026-07-01: Implemented Confluence operation orchestration, provider-specific attachment download safety, Confluence indexes, manifest generation, local verify, cleanup authority, CLI wiring, and focused mocked/unit tests in `atlassian-md-export`.
- 2026-07-01: Verified with focused Confluence operation/CLI tests, existing Jira operation regression tests, Confluence writer/client/state tests, full pytest, full Ruff, and package mypy. Evidence recorded in `.10x/evidence/2026-07-01-confluence-comments-attachments-index-verify.md`.
- 2026-07-01: Retrospective: the Confluence client returns tuple resources while the existing writer normalization path consumes list-shaped raw resource collections; the operation layer now converts fetched resource tuples to lists before normalization, and mocked operation tests cover the boundary. No new reusable skill was needed.
- 2026-07-01: Record path repaired into `.10x/tickets/done/`; implementation and evidence unchanged.

## Explicit Exclusions

- Do not implement nested comment replies.
- Do not contact Confluence from `verify`.
- Do not delete SQLite history during clean.

## References

- `.10x/specs/confluence-attachments-index-clean-verify.md`
- `.10x/specs/confluence-page-markdown-output.md`
- `.10x/specs/confluence-export-api-sync.md`

## Evidence Expectations

- Unit tests for comment ordering and formatting.
- Unit tests for attachment filename and URL safety.
- Mocked tests for optional attachment download skip/download behavior.
- Unit tests for all generated indexes.
- Unit tests for verify failures with actionable paths.
- Unit tests for clean behavior and representative cleanup authority.

## Completion Evidence

- `.10x/evidence/2026-07-01-confluence-comments-attachments-index-verify.md`
