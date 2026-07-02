Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-reconcile-incremental-sync-cursor-authority.md, .10x/tickets/done/2026-07-01-jira-exporter-validation-and-verify-hardening.md, .10x/specs/jira-export-api-sync.md, .10x/specs/jira-attachments-index-clean-verify.md

# Jira Cursor Validation Verify Hardening

## What Was Observed

The final Jira correctness hardening slice was implemented in `atlassian-md-export`.

Observed behavior:

- Default incremental cursor selection uses the latest successful non-partial run for the same command/scope.
- Failed and partial runs do not advance the cursor.
- Incremental successes do not replace full representative cleanup authority.
- `sync.overlap_minutes` rejects negative values through Pydantic validation while allowing `0`.
- `verify` compares SQLite issue hash columns against current Markdown/raw JSON files.
- `verify` reports missing Markdown/raw JSON files for state rows that have corresponding stored hashes.
- Historical SQLite issue rows without stored hashes remain allowed, preserving the active clean spec requirement that `clean --remove-missing` keeps SQLite history.
- Exact `uv run ruff check .` is now a project-source signal because generated/local dependency/cache directories are excluded in Ruff config.

## Procedure

Focused tests were run first:

```text
uv run pytest tests/test_state.py tests/test_operations.py::test_verify_compares_state_hashes_against_current_issue_files tests/test_operations.py::test_verify_reports_state_rows_missing_issue_files tests/test_cli.py::test_config_rejects_negative_sync_overlap_and_allows_zero
```

Result:

```text
10 passed in 0.33s
```

The first full pytest run exposed a conflict between the new state-row verify check and the clean spec's preserved historical rows:

```text
uv run pytest
```

Result:

```text
1 failed, 48 passed, 1 skipped in 0.67s
```

The failure was `test_clean_remove_missing_uses_representative_run_and_preserves_state`; it used a preserved SQLite row with no stored hashes. Verify was narrowed to require current files only for state rows that actually have stored hash values.

The focused regression for that adjustment was run:

```text
uv run pytest tests/test_operations.py::test_clean_remove_missing_uses_representative_run_and_preserves_state tests/test_operations.py::test_verify_reports_state_rows_missing_issue_files
```

Result:

```text
2 passed in 0.21s
```

Full verification was then run:

```text
uv run pytest
uv run ruff check .
uv run mypy src
```

Results:

```text
49 passed, 1 skipped in 0.63s
All checks passed!
Success: no issues found in 14 source files
```

Before the Ruff exclusion, exact `uv run ruff check .` produced 2091 errors from `.uv-cache` vendored dependencies. After adding `extend-exclude` for `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.uv-cache`, `.venv`, and `__pycache__`, the exact command passed.

## What This Supports Or Challenges

This supports closing `.10x/tickets/done/2026-07-01-reconcile-incremental-sync-cursor-authority.md`: implementation and tests match the reconciled cursor contract in `.10x/specs/jira-export-api-sync.md`.

This supports closing `.10x/tickets/done/2026-07-01-jira-exporter-validation-and-verify-hardening.md`: the remaining validation and verify hardening bullets are implemented and verified. The earlier per-issue attribution slice was already recorded in `.10x/evidence/2026-07-01-jira-operations-correctness-verification.md`.

## Limits

The verification is local/unit/mocked. The Jira sandbox integration test was skipped because sandbox environment variables were not supplied. No Confluence implementation or shaping was performed.
