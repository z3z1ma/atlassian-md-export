Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-scaffold-atlassian-md-export-python-package.md, .10x/tickets/done/2026-07-01-implement-jira-client-and-sync-state.md, .10x/tickets/done/2026-07-01-implement-adf-renderer-and-markdown-writer.md, .10x/tickets/done/2026-07-01-implement-attachments-index-clean-verify.md

# Add Tests, Documentation, CI, And Examples

## Scope

Complete the project quality bar with tests, README, example generated Markdown, integration-test mode, and minimal GitHub Actions workflow.

## Acceptance Criteria

- Test suite includes:
  - unit tests for ADF renderer
  - unit tests for Markdown escaping and YAML frontmatter
  - unit tests for filename safety
  - unit tests for incremental sync decisions
  - mocked HTTP tests for pagination, comments pagination, 429 retry, 401 auth failure, and partial failures
  - snapshot tests for representative issue Markdown output
  - integration-test mode using real Jira sandbox environment variables, skipped by default
- README includes setup, auth, examples, config, deterministic export behavior, cleanup semantics, troubleshooting, and explanation of the generalized `atlassian-md-export` repository with Jira-first `jira-md-export` CLI.
- Example generated Markdown file exists and matches the active Markdown output spec.
- Minimal GitHub Actions workflow runs lint, typecheck, and tests.
- The lockfile is committed.
- Type hints are present throughout source modules.
- Quality commands pass locally before ticket closure, or failures are recorded with explicit blockers.

## Blockers

None.

## Progress and Notes

- 2026-07-01: Ticket opened from ratified parent plan.
- 2026-07-01: Entered inner loop after integration ticket completed with evidence.
- 2026-07-01: Added README, real renderer-produced example Markdown, skipped-by-default Jira sandbox integration test, GitHub Actions workflow, CLI/help coverage for `--stable-exported-at`, public custom-field config coverage, deterministic stale-index coverage, and final quality evidence.

## Explicit Exclusions

- Do not require real Jira credentials for default tests.
- Do not include secrets in examples, snapshots, logs, or CI config.

## References

- `.10x/specs/atlassian-md-export-cli-config.md`
- `.10x/specs/jira-export-api-sync.md`
- `.10x/specs/jira-issue-markdown-output.md`
- `.10x/specs/adf-markdown-rendering.md`
- `.10x/specs/jira-attachments-index-clean-verify.md`

## Evidence Expectations

- Recorded output for lint/typecheck/tests.
- Recorded output proving integration tests are skipped by default without sandbox variables.
- Review record before parent closure.

## Evidence

- `.10x/evidence/2026-07-01-tests-docs-ci-examples.md`
- `.10x/reviews/2026-07-01-atlassian-md-export-implementation.md`

## Closure Review

- All acceptance criteria are satisfied by `.10x/evidence/2026-07-01-tests-docs-ci-examples.md`.
- The integration test is present and skipped by default; no real Jira sandbox run was possible without credentials.
- The final local gate passed: pytest, ruff, mypy, lockfile check, and locked sync.
- No follow-up ticket is required for this slice.

## Retrospective

- CLI flags that mirror config behavior should be checked from command help, not inferred from writer/config tests.
- Public config-shape tests are needed when orchestration adapts user-facing YAML into writer-internal mappings.
