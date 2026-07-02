Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-implement-confluence-comments-attachments-index-verify.md, .10x/specs/confluence-attachments-index-clean-verify.md, .10x/specs/confluence-page-markdown-output.md, .10x/specs/confluence-export-api-sync.md, .10x/specs/confluence-cli-config.md

# Confluence Comments, Attachments, Indexes, Clean, And Verify Evidence

## What Was Observed

The Confluence operations/local behavior ticket was implemented in `atlassian-md-export` with mocked unit coverage and full local verification.

Implemented behavior observed in tests:

- Confluence `pull` fetches pages, footer comments, inline comments, labels, ancestors, descendants, and attachment metadata through the existing Confluence client seams.
- Footer and inline comments render through the existing Confluence page writer oldest-first with stable metadata headings; inline resolution metadata is preserved when present.
- Attachment handling is metadata-only unless download behavior is requested.
- Attachment downloads honor include globs and max-size options, write under `attachments/PAGEID/ATTACHMENTID-safe_filename`, and render local relative paths in Markdown/raw JSON.
- Confluence attachment download URL validation accepts same-origin absolute URLs and safe relative URLs, and rejects cross-origin, scheme-relative, traversal, and unsupported-scheme forms before HTTP requests.
- Confluence indexes `all.md`, `by-space.md`, `by-label.md`, `by-parent.md`, and `stale.md` are generated with relative links and deterministic stale-page reference time.
- Confluence manifest JSON includes page/comment/attachment counts, exported page ids, last successful representative run information, and file hashes.
- Confluence `verify` detects missing downloaded attachment targets and checks manifest/state hashes without a Confluence client.
- Confluence `clean --remove-missing` removes only page Markdown, raw JSON, and attachment directories absent from the latest successful representative Confluence pull while preserving SQLite page history.
- Attachment partial failure does not advance trusted Confluence representative cleanup authority.
- Confluence CLI placeholders were replaced by real operation calls, and required options are exposed.

## Procedure

Commands run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```text
uv run pytest tests/test_confluence_operations.py
uv run pytest tests/test_cli.py
uv run pytest tests/test_operations.py tests/test_confluence_operations.py
uv run ruff check src/atlassian_md_export/operations.py src/atlassian_md_export/indexes.py src/atlassian_md_export/attachments.py src/atlassian_md_export/cli.py tests/test_confluence_operations.py tests/test_cli.py
uv run mypy src/atlassian_md_export/operations.py src/atlassian_md_export/indexes.py src/atlassian_md_export/attachments.py src/atlassian_md_export/cli.py
uv run pytest tests/test_confluence_writer.py tests/test_confluence_client.py tests/test_state.py tests/test_cli.py tests/test_operations.py tests/test_confluence_operations.py
uv run pytest
uv run ruff check .
uv run mypy src/atlassian_md_export
```

Final verification results:

- `uv run pytest`: 108 passed, 1 skipped.
- `uv run ruff check .`: all checks passed.
- `uv run mypy src/atlassian_md_export`: success, no issues in 16 source files.

## What This Supports

This supports closure of `.10x/tickets/done/2026-07-01-implement-confluence-comments-attachments-index-verify.md` against its acceptance criteria for Confluence operations, attachment download safety, indexes, manifest, local verify, cleanup authority, partial-failure run state, and CLI wiring.

## Limits

Verification used mocked HTTP/unit tests and local filesystem checks. It did not run live Confluence integration, docs/examples, or CI workflows, which are excluded from this ticket.
