Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Fix GitHub Actions CLI Help Test Failures

## Scope

Repair the failing GitHub Actions `quality` job for commit `5034afb` by addressing the pytest failures in `tests/test_cli.py`.

## Acceptance Criteria

- The root cause of the Actions failure is identified from GitHub job logs.
- The fix preserves coverage that the relevant Jira and Confluence CLI commands expose their intended options.
- The test assertions are not dependent on terminal-width-sensitive Rich/Typer help rendering.
- Local `uv run pytest`, `uv run ruff check src tests`, and `uv run mypy src tests` pass.
- The fix is pushed and the GitHub Actions run for the new commit passes.

## Explicit Exclusions

- Do not change CLI user-facing behavior unless metadata inspection proves the implementation is wrong.
- Do not alter authentication, export, state, or renderer behavior.

## References

- GitHub Actions run: `28550802907`
- Failed job: `quality` / `Test`
- Failed test file: `tests/test_cli.py`

## Progress and Notes

- 2026-07-01: GitHub job logs show 11 failures, all from assertions scraping rendered Typer/Rich help output for option names such as `--stable-exported-at`, `--out`, and `--site`.
- 2026-07-01: Replaced width-sensitive rendered-help assertions with Typer command metadata assertions in `tests/test_cli.py`.
- 2026-07-01: Local `uv run pytest`, `uv run ruff check src tests`, and `uv run mypy src tests` pass.
- 2026-07-01: GitHub Actions run `28556843264` passed for pushed commit `5d2a74694fc18acec46b988cb3af9117068c5f94`.

## Blockers

None.

## Evidence Expectations

- Recorded in `.10x/evidence/2026-07-01-github-actions-cli-help-test-fix.md`.
