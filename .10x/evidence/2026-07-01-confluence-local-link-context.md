Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-preserve-confluence-local-link-context.md, .10x/specs/confluence-page-markdown-output.md

# Confluence Local Link Context Repair Evidence

## What Was Observed

Confluence `pull` and exact `page` exports now render pages with an export context built from newly fetched pages plus existing local raw page exports. Newly fetched pages override older local raw JSON by page id. Existing comments and attachments commands already used local context and continue to do so through the shared helper.

## Procedure

Commands run in `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```sh
uv run pytest tests/test_confluence_operations.py tests/test_state.py -q
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

## Results

- Focused Confluence/state tests: `20 passed in 0.55s`.
- Full test suite: `111 passed, 2 skipped in 1.24s`.
- Ruff: all checks passed.
- Mypy: success, no issues in 26 source files.

The focused regression `test_confluence_page_repull_uses_existing_local_link_context` proves that a one-page Confluence repull links to an already-exported parent as `[Root](100-Root.md)` in both page metadata and ancestors.

## Limits

This evidence uses mocked Confluence HTTP responses. The live Confluence sandbox integration was not run because `CONFLUENCE_MD_EXPORT_SANDBOX_PAGE` was not present in the fish environment.
