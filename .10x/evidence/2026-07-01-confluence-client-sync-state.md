Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-implement-confluence-client-and-sync-state.md, .10x/specs/confluence-export-api-sync.md, .10x/specs/confluence-cli-config.md

# Confluence Client And Sync State Evidence

## What Was Observed

The Confluence API client and provider-specific SQLite state were implemented in `/Users/alexanderbut/code_projects/work/atlassian-md-export` without adding Confluence writer, attachment binary download, indexes, verify, clean, docs, or live integration behavior.

Implemented source surfaces:

- `src/atlassian_md_export/confluence/client.py`
- `src/atlassian_md_export/confluence/__init__.py`
- `src/atlassian_md_export/state.py`
- `src/atlassian_md_export/client.py`

Focused test surfaces:

- `tests/test_confluence_client.py`
- `tests/test_state.py`

## Procedure

From `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

- `uv run pytest tests/test_confluence_client.py tests/test_state.py`
  - Result: `22 passed in 0.20s`.
- `uv run ruff check src tests`
  - Result: `All checks passed!`
- `uv run mypy src/atlassian_md_export`
  - Result: `Success: no issues found in 16 source files`.
- `uv run pytest`
  - Result: `88 passed, 1 skipped in 0.74s`.

## What This Supports

- Space resolution and space page discovery use Confluence REST API v2.
- Arbitrary CQL discovery uses `/wiki/rest/api/search` for discovery and hydrates pages through v2 page detail.
- Ancestor subtree export includes the root page and hydrates page descendants from the v2 descendants endpoint.
- v2 pagination follows HTTP `Link` headers.
- CQL pagination follows next links carrying cursors.
- Page and comment hydration request `body-format=atlas_doc_format` by default.
- Client methods exist and validate payloads for footer comments, inline comments, labels, ancestors, descendants, and attachment metadata.
- HTTP 200 malformed payloads raise `AtlassianClientError` rather than being treated as empty success.
- HTTP 429 and 5xx retry behavior and HTTP 401 fail-fast behavior are covered by mocked tests.
- Confluence CQL incremental date literals are formatted as `yyyy-MM-dd HH:mm` without seconds, ISO `T`, or timezone suffixes.
- SQLite tracks Confluence page id, space id/key, title, status, parent id, updated timestamp, version, content hash, raw JSON hash, Markdown hash, last seen/exported times, and Confluence run metadata.
- Confluence incremental state uses the latest successful compatible same-scope run with a 10-minute overlap, while force, explicit since, exact page, partial failure, and representative cleanup state follow the active spec.

## Limits

The HTTP verification is mocked; no live Confluence sandbox request was made. Markdown rendering, raw file writing, attachment binary download, indexes, verify, clean, docs, and live integration remain owned by downstream Confluence child tickets. The full test suite still contains one skipped sandbox integration test by design.
