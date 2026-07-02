Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-repair-confluence-review-blockers.md, .10x/reviews/2026-07-01-confluence-production-readiness-adversarial.md

# Confluence Review Blockers Repaired

## What Was Observed

The adversarial review blockers were repaired:

- Confluence pagination next links are validated before authenticated requests follow them. Same-origin absolute links are reduced to path/query form; cross-origin, scheme-relative, unsafe scheme, and ambiguous links fail with `AtlassianClientError`.
- `stable_exported_at` now freezes Markdown frontmatter only. Raw JSON exporter metadata and `write_*_files().exported_at`, which feeds SQLite `last_exported_at`, preserve the actual supplied/current export timestamp.
- Shared Atlassian HTTP errors now parse Confluence-style `message`, `detail`, `title`, `error`, and `statusCode` payloads.
- `initialize_state` now repairs current Confluence table columns and creates indexes after column repair, so early pre-final local DBs can upgrade.
- Clean preserves SQLite rows while clearing artifact hashes for deleted Jira issues and Confluence pages, allowing local `verify` to pass after cleanup.

## Procedure

Commands run in `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```sh
uv run pytest tests/test_confluence_client.py tests/test_confluence_writer.py tests/test_writer.py tests/test_state.py -q
uv run ruff check src/atlassian_md_export/confluence/client.py src/atlassian_md_export/client.py src/atlassian_md_export/writer.py src/atlassian_md_export/state.py tests/test_confluence_client.py tests/test_confluence_writer.py tests/test_writer.py tests/test_state.py
uv run mypy src/atlassian_md_export/confluence/client.py src/atlassian_md_export/client.py src/atlassian_md_export/writer.py src/atlassian_md_export/state.py
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

## Results

- Focused blocker tests: `46 passed in 0.41s`.
- Focused ruff: all checks passed.
- Focused mypy: success, no issues in 4 source files.
- Full test suite after blocker repairs: `115 passed, 2 skipped in 1.45s`.
- Full ruff: all checks passed.
- Full mypy: success, no issues in 26 source files.

## Limits

The live Confluence sandbox integration still requires `CONFLUENCE_MD_EXPORT_SANDBOX_PAGE`; it was not present in the fish environment during this run.
