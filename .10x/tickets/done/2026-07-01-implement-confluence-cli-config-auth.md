Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: None

# Implement Confluence CLI, Config, And Auth

## Scope

Add the `confluence-md-export` console command, Typer command surface, Confluence config parsing, environment authentication resolution, safe logging, and output-directory initialization.

## Acceptance Criteria

- `pyproject.toml` exposes `confluence-md-export` beside `jira-md-export`.
- Commands required by `.10x/specs/confluence-cli-config.md` exist with explicit `--out DIR` on every stateful command.
- `init --out DIR` creates the Confluence output directory skeleton, SQLite state, and initial manifest without requiring credentials or contacting Confluence.
- Config loading supports Confluence config filenames and keys from `.10x/specs/confluence-cli-config.md`.
- Auth resolution supports `CONFLUENCE_*` variables with `ATLASSIAN_*` fallback and never falls back to `JIRA_*`.
- `.env` loading works for Confluence variables.
- Missing credentials produce friendly actionable errors without printing secrets.
- `--verbose` and `--json-logs` work for Confluence commands without leaking tokens.

## Blockers

None.

## Progress And Notes

- 2026-07-01: Ticket opened from ratified Confluence parent plan.
- 2026-07-01: Implemented separate `confluence-md-export` Typer entry point, Confluence config candidates/keys, Confluence credential resolution with Atlassian fallback and no Jira fallback, Confluence output initialization, token redaction, and focused CLI/config/auth tests.
- 2026-07-01: Verified with focused CLI tests, targeted ruff/mypy checks, and console-script help smoke tests. Evidence recorded in `.10x/evidence/2026-07-01-confluence-cli-config-auth.md`.
- 2026-07-01: Retrospective: no new reusable knowledge or operational skill was needed beyond the active Confluence specs and the existing provider-separation decision; later API/local behavior remains owned by the existing downstream Confluence child tickets.

## Explicit Exclusions

- Do not implement Confluence network client behavior beyond wiring placeholders needed for command dispatch.
- Do not change Jira command semantics.

## References

- `.10x/specs/confluence-cli-config.md`
- `.10x/decisions/generalize-atlassian-md-export.md`

## Evidence Expectations

- CLI unit tests for command availability and required `--out`.
- Config/auth unit tests covering `CONFLUENCE_*`, `ATLASSIAN_*`, `.env`, and no `JIRA_*` fallback.
- Log redaction test or focused assertion that Authorization/API tokens are not emitted.

## Completion Evidence

- `.10x/evidence/2026-07-01-confluence-cli-config-auth.md`
