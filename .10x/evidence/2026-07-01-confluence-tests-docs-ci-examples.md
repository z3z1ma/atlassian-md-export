Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-add-confluence-tests-docs-ci-examples.md, .10x/specs/confluence-cli-config.md, .10x/specs/confluence-export-api-sync.md, .10x/specs/confluence-page-markdown-output.md, .10x/specs/confluence-attachments-index-clean-verify.md

# Confluence Tests, Docs, CI, And Examples Evidence

## What Was Observed

The Confluence-facing docs/examples/integration-test child ticket was completed in `atlassian-md-export`.

Observed changes:

- `README.md` now documents Confluence setup, authentication variables, examples, config keys, output layout, incremental sync, attachments, verify, clean, troubleshooting, limitations, tests, and sandbox integration opt-in.
- `examples/confluence-launch-readiness.md` is a generated Confluence page Markdown example with fictional `example.atlassian.net` content and no secrets/private data.
- `tests/test_integration_sandbox.py` keeps the existing Jira sandbox test and adds a real Confluence sandbox export mode controlled by `CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, and `CONFLUENCE_MD_EXPORT_SANDBOX_PAGE`.
- The Confluence sandbox test is skipped by default when any required variable is absent and therefore does not require live credentials in CI.
- Existing Confluence unit tests already cover ADF rendering, Markdown/frontmatter, filename safety, incremental sync decisions, API pagination, comments pagination, 429 retry, 401 auth failure, malformed payloads, partial failures, attachment safety, indexes, verify, clean, and the representative Markdown snapshot.
- `.github/workflows/ci.yml` was inspected and left unchanged because it already runs `uv run ruff check src tests`, `uv run mypy src tests`, and `uv run pytest` across the shared Jira and Confluence source/test paths.
- `pyproject.toml` integration marker text now names both Jira and Confluence sandbox tests.

## Procedure

Commands run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```text
uv run pytest tests/test_integration_sandbox.py tests/test_cli.py tests/test_confluence_client.py tests/test_confluence_operations.py tests/test_confluence_writer.py -q
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Observed results:

- Focused tests: `51 passed, 2 skipped`.
- Full pytest: `108 passed, 2 skipped`.
- Ruff: `All checks passed!`.
- Mypy: `Success: no issues found in 26 source files`.

## What This Supports

This supports closure of `.10x/tickets/done/2026-07-01-add-confluence-tests-docs-ci-examples.md` against its README, example, skipped integration mode, CI coverage, and existing Jira skip-behavior acceptance criteria.

## Limits

The real Confluence sandbox export was not executed because sandbox environment variables were not present. The local skipped test output verifies the default no-credentials behavior; live sandbox evidence remains conditional on configured credentials and page id.
