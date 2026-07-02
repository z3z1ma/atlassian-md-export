Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-fix-github-actions-cli-help-tests.md

# GitHub Actions CLI Help Test Fix Evidence

## What Was Observed

GitHub Actions run `28550802907` failed in the `quality` job during `uv run pytest`.
The failing tests were all in `tests/test_cli.py` and asserted that option names appeared in rendered Typer/Rich help output. The runner output showed 11 failures for strings such as `--stable-exported-at`, `--out`, and `--site` missing from terminal-rendered help text.

After replacing width-sensitive rendered-help assertions with Typer command metadata assertions, local quality gates passed and the pushed GitHub Actions run passed.

## Procedure

- Inspected GitHub Actions run `28550802907` and job `84647261617` logs with `gh`.
- Ran `uv run pytest tests/test_cli.py`: `25 passed`.
- Ran `uv run pytest`: `121 passed, 2 skipped`.
- Ran `uv run ruff check src tests`: passed.
- Ran `uv run mypy src tests`: passed.
- Pushed commit `5d2a74694fc18acec46b988cb3af9117068c5f94`.
- Watched GitHub Actions run `28556843264` with `gh run watch --exit-status`: `quality` passed in 23 seconds.

## What This Supports

The CI failure was caused by brittle help-output scraping, not by missing CLI options. The replacement tests cover registered command metadata and no longer depend on terminal width.

## Limits

This evidence covers the CI failure observed on 2026-07-01 and the follow-up GitHub Actions run for commit `5d2a74694fc18acec46b988cb3af9117068c5f94`. It does not evaluate unrelated future GitHub runner deprecation warnings.

