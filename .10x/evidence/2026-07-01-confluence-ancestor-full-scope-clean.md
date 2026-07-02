Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-treat-confluence-ancestor-pulls-as-full-scope.md, .10x/specs/confluence-export-api-sync.md, .10x/specs/confluence-attachments-index-clean-verify.md

# Confluence Ancestor Full-Scope And Clean-State Evidence

## What Was Observed

Confluence ancestor pulls are now full-scope representative pulls. Successful later ancestor pulls refresh the representative page id set used by `clean --remove-missing`, so pages removed from a subtree can be deleted locally.

Cleaning now clears artifact hashes from preserved SQLite rows for deleted Jira issues and Confluence pages. This preserves history while keeping `verify` truthful after local Markdown/raw JSON/attachment files are removed.

## Procedure

Commands run in `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```sh
uv run pytest tests/test_confluence_operations.py tests/test_state.py -q
uv run pytest tests/test_operations.py::test_clean_remove_missing_uses_representative_run_and_preserves_state -q
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

## Results

- Focused Confluence/state tests: `20 passed in 0.55s`.
- Focused Jira clean-state regression: `1 passed in 0.18s`.
- Full test suite: `111 passed, 2 skipped in 1.24s`.
- Ruff: all checks passed.
- Mypy: success, no issues in 26 source files.

The focused regression `test_confluence_ancestor_pull_refreshes_cleanup_authority` proves that a second ancestor pull with a smaller subtree records the smaller representative page set, `clean --remove-missing` removes the stale page Markdown/raw JSON, and `verify_confluence_export` passes afterward.

## Limits

This evidence uses mocked HTTP responses for Confluence behavior. The live Confluence sandbox integration was not run because `CONFLUENCE_MD_EXPORT_SANDBOX_PAGE` was not present in the fish environment.
