Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-restrict-jira-attachment-download-hosts.md, .10x/tickets/done/2026-07-01-jira-exporter-validation-and-verify-hardening.md

# Jira Operations Correctness Verification

## What Was Observed

The Jira operations correctness slice was implemented in `atlassian-md-export/src/atlassian_md_export/operations.py` with focused coverage in `atlassian-md-export/tests/test_operations.py`.

## Procedure

- `uv run pytest tests/test_operations.py` from `atlassian-md-export`: passed, 10 tests.
- `uv run pytest` from `atlassian-md-export`: passed, 44 passed and 1 skipped.
- `uv run mypy src` from `atlassian-md-export`: passed, no issues in 14 source files.
- `uv run ruff check src/atlassian_md_export/operations.py tests/test_operations.py` from `atlassian-md-export`: passed.
- `uv run ruff check . --exclude .uv-cache --exclude .venv` from `atlassian-md-export`: passed.
- `uv run ruff check .` from `atlassian-md-export`: failed because Ruff linted dependency/cache directories under `.uv-cache/archive-v0/...`; the output reported third-party-package findings such as unused imports in cached `h11`.
- `uv run ruff check . --exclude .uv-cache` from `atlassian-md-export`: failed because Ruff then linted `.venv/lib/python3.12/site-packages/...`; the output again reported third-party-package findings.

## What This Supports Or Challenges

This supports that attachment downloads now reject absolute non-Jira-site content URL hosts before issuing a binary request, that the rejected attachment remains a per-attachment partial failure with no local file, and that whole-run per-issue write failures in `_run_search_export` include the issue key in the raised and persisted failure message. Parent follow-up tightened absolute attachment URL validation from same-host to same-origin and added focused coverage for scheme downgrade rejection.

The literal project-root Ruff command is not currently a useful project-source signal because dependency/cache directories are inside the lint target. The source and test files changed by this slice, and the project tree excluding those dependency/cache directories, pass Ruff.

## Limits

No live Jira request was made. The external attachment host behavior is proven with `httpx.MockTransport`; the test fails if the external absolute URL is requested. The larger validation hardening ticket remains open for its other acceptance criteria.
