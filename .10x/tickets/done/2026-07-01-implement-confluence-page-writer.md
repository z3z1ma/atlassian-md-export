Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-implement-confluence-client-and-sync-state.md, .10x/tickets/done/2026-07-01-add-adf-task-list-rendering.md

# Implement Confluence Page Writer

## Scope

Implement deterministic Confluence page Markdown rendering, YAML frontmatter normalization, raw JSON preservation under `pages/_raw/`, safe page filenames, relative links, and page content hashing.

## Acceptance Criteria

- Page Markdown files are written under `pages/SPACEKEY/PAGEID-safe-title.md`.
- Raw page source files are written under `pages/_raw/PAGEID.json` with deterministic JSON serialization.
- YAML frontmatter fields and order match `.10x/specs/confluence-page-markdown-output.md`.
- Markdown section order matches `.10x/specs/confluence-page-markdown-output.md`.
- Page content uses the `AdfMarkdownRenderer` abstraction for `atlas_doc_format` bodies.
- Missing or storage-only bodies render an explicit unsupported-body placeholder while preserving raw data.
- Ancestor and child-page links are relative when target pages are part of the export.
- Filename safety prevents path traversal, hidden path segments, control characters, platform-invalid characters, and unstable Unicode/path normalization issues.
- `content_hash` excludes `exported_at` and includes source/rendering inputs that affect Markdown.
- Writes are atomic and never corrupt existing complete exports on partial failure.

## Blockers

None. First-class ADF task-list rendering is tracked separately and is a dependency for this ticket.

## Progress And Notes

- 2026-07-01: Ticket opened from ratified Confluence parent plan.
- 2026-07-01: Implemented Confluence page normalization, deterministic page Markdown rendering, canonical raw JSON preservation under `pages/_raw/`, safe page path segments, relative generated-page links, content hashing, and atomic Markdown/JSON writes in `atlassian-md-export/src/atlassian_md_export/models.py` and `atlassian-md-export/src/atlassian_md_export/writer.py`.
- 2026-07-01: Added focused writer tests in `atlassian-md-export/tests/test_confluence_writer.py` for frontmatter order/escaping, section order, representative Markdown snapshot, filename safety, raw JSON placement/preservation, stable `content_hash`, unsupported storage-only bodies, and atomic writes.
- 2026-07-01: Verified with focused Confluence writer pytest, shared writer pytest, Ruff on changed files, and mypy on changed source modules. Evidence recorded in `.10x/evidence/2026-07-01-confluence-page-writer.md`.
- 2026-07-01: Retrospective: the Confluence writer could reuse the existing Jira writer's canonical JSON, YAML ordering, timestamp, hash, and atomic write mechanics; no new reusable skill or knowledge record was needed.

## Explicit Exclusions

- Do not implement attachment binary download behavior in this ticket.
- Do not rewrite arbitrary embedded media references inside page content.
- Do not implement nested comment replies.

## References

- `.10x/specs/confluence-page-markdown-output.md`
- `.10x/specs/adf-markdown-rendering.md`
- `.10x/tickets/done/2026-07-01-add-adf-task-list-rendering.md`

## Evidence Expectations

- Unit tests for Confluence YAML frontmatter ordering and Markdown escaping.
- Unit tests for page filename safety.
- Snapshot tests for representative Confluence page Markdown output.
- Tests showing raw JSON placement under `pages/_raw/`.
- Tests showing stable `content_hash` behavior with stable and non-stable `exported_at`.

## Completion Evidence

- `.10x/evidence/2026-07-01-confluence-page-writer.md`
