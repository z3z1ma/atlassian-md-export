Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-implement-structured-confluence-logging.md, .10x/specs/confluence-cli-config.md, .10x/reviews/2026-07-01-confluence-production-readiness-adversarial.md

# Structured Confluence Logging

## What Was Observed

- Confluence export operations now emit structured stdlib logging extras for `provider`, `command`, `site_host`, `operation`, scope context, page id, space key, and output paths where applicable.
- Confluence pull/page/comment/attachment write paths log page file writes with page id, space key, Markdown path, and raw JSON path.
- Confluence attachment download and local attachment write paths log safe resource/output paths without logging attachment bytes.
- Shared Atlassian HTTP retry and failure logging now records provider, method, safe path without query values, status code, retry attempt, and retry count.
- JSON log formatting still redacts secret-like keys, configured API token environment values, and Authorization text.
- No new logging dependency was added.

## Procedure

From `/Users/alexanderbut/code_projects/work/atlassian-md-export`, ran focused logging tests:

```text
uv run pytest tests/test_cli.py::test_json_log_formatter_redacts_nested_confluence_context tests/test_confluence_operations.py::test_confluence_pull_logs_safe_structured_context tests/test_confluence_client.py::test_retry_handles_429_and_5xx tests/test_confluence_client.py::test_confluence_http_error_uses_message_payload
```

Observed:

```text
5 passed
```

Ran the required full verification:

```text
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

Observed:

```text
117 passed, 2 skipped
All checks passed!
Success: no issues found in 26 source files
```

## What This Supports

- The structured logging ticket acceptance criteria are satisfied for Confluence operation context, HTTP retry/failure context, local write paths, and JSON redaction coverage.
- The adversarial review residual finding for incomplete structured Confluence logging has a focused implementation and evidence owner.

## Limits

- Verification used mocked Confluence HTTP interactions; no live Confluence site was contacted.
- Log records intentionally omit raw CQL text, page/comment bodies, Authorization headers, tokens, and attachment content.
