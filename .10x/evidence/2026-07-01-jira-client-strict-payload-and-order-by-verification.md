Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-reject-malformed-jira-success-payloads.md, .10x/tickets/done/2026-07-01-harden-jql-order-by-parsing.md

# Jira Client Strict Payload And Order By Verification

## What Was Observed

The Jira client rejects HTTP 200 search payloads without `issues` and comment payloads without `comments`.
Valid empty arrays still succeed.
JQL `ORDER BY` detection ignores `order by` inside quoted string literals, including backslash-escaped quotes, while preserving a real trailing `ORDER BY`.

Malformed search and comment payloads raise through the public `run_pull` operation path and finalize the corresponding export run as failed (`succeeded = 0`, `partial_failure = 1`, non-null `finished_at`, non-empty `failure_message`). Persistent regression tests now also prove those failed runs do not supersede the prior successful incremental cursor.

## Procedure

Commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`.

```text
uv run pytest tests/test_jira_client.py
```

Result: passed, `16 passed in 0.06s`.

```text
uv run pytest
```

Result: passed, `42 passed, 1 skipped in 0.97s`.

```text
uv run mypy src
```

Result: passed, `Success: no issues found in 14 source files`.

```text
uv run ruff check .
```

Result: failed because Ruff traversed vendored dependency cache files under `.uv-cache/archive-v0`, reporting 2091 third-party-source lint errors. The observed failures were outside the changed source and tests.

```text
uv run ruff check src tests
```

Result: passed, `All checks passed!`.

Persistent operation-level regression tests were added after adversarial review found the temporary check insufficient:

```text
uv run pytest tests/test_operations.py::test_pull_malformed_search_payload_fails_run_and_preserves_cursor tests/test_operations.py::test_pull_malformed_comments_payload_fails_run_and_preserves_cursor
```

Result: passed, `2 passed in 0.23s`.

## What This Supports Or Challenges

Supports closing `.10x/tickets/done/2026-07-01-reject-malformed-jira-success-payloads.md` for the bounded client slice and operation-failure propagation.

Supports closing `.10x/tickets/done/2026-07-01-harden-jql-order-by-parsing.md` for quote-aware `ORDER BY` detection and splitting.

Challenges the usefulness of the exact repository-wide command `uv run ruff check .` until `.uv-cache/` is excluded or the cache is moved outside the project directory.

## Limits

The live Jira sandbox integration reads a real issue/comments path but does not exercise malformed HTTP 200 payloads; those remain mocked regression coverage by design.
