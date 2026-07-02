Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-restrict-jira-attachment-download-hosts.md, .10x/tickets/done/2026-07-01-reject-malformed-jira-success-payloads.md, .10x/tickets/done/2026-07-01-reconcile-incremental-sync-cursor-authority.md, .10x/tickets/done/2026-07-01-harden-jql-order-by-parsing.md, .10x/tickets/done/2026-07-01-include-attachment-local-path-in-content-hash.md, .10x/tickets/done/2026-07-01-jira-exporter-validation-and-verify-hardening.md

# Jira Hardening Final Verification

## What Was Observed

All Jira hardening tickets opened from the deep correctness audit are closed and their focused regression coverage is present.

Parent-side follow-up after the adversarial review added persistent operation-level tests for malformed HTTP 200 search/comment payloads through `run_pull`. The tests assert the failed export run is persisted with `succeeded = 0` and `partial_failure = 1`, and that the prior successful same-scope cursor remains the selected incremental cursor.

Attachment download validation was also tightened from same-host to same-origin for absolute attachment URLs, so scheme and port downgrades are rejected before the Jira-authenticated HTTP client makes a binary request.

## Procedure

Commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`.

```text
uv run pytest tests/test_operations.py::test_pull_malformed_search_payload_fails_run_and_preserves_cursor tests/test_operations.py::test_pull_malformed_comments_payload_fails_run_and_preserves_cursor
```

Result: passed, `2 passed in 0.23s`.

```text
uv run pytest
```

Result: passed, `52 passed, 1 skipped in 0.70s`.

```text
uv run ruff check .
```

Result: passed, `All checks passed!`.

```text
uv run mypy src
```

Result: passed, `Success: no issues found in 14 source files`.

```text
fish -lc 'set -gx JIRA_MD_EXPORT_SANDBOX_ISSUE DATA-4174; uv run pytest tests/test_integration_sandbox.py'
```

Result: passed, `1 passed in 0.68s`.

## What This Supports Or Challenges

This supports proceeding to Confluence scoping from a Jira exporter baseline where the known audit defects have durable fixes, tests, and evidence.

The full pytest run still reports the sandbox integration as skipped because `JIRA_MD_EXPORT_SANDBOX_ISSUE` is intentionally not a persistent environment variable; the explicit fish invocation above supplies `DATA-4174` and passes.

## Limits

The live integration reads issue discovery and comments for `DATA-4174`. It does not download a real Jira attachment binary. Attachment URL safety is covered by mocked tests that fail if external or same-host wrong-scheme absolute URLs are requested.
