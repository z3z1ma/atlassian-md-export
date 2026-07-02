Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Build Atlassian Markdown Exporter

## Scope

Create the new `/Users/alexanderbut/code_projects/work/atlassian-md-export` repository for a production-quality Jira Cloud Markdown exporter with a generalized Atlassian package boundary and a Jira-first CLI command named `jira-md-export`.

This is a parent plan, not an executable implementation ticket.

## Acceptance Criteria

- Child tickets complete the Jira-first CLI package, API sync, Markdown rendering/output, attachments/index/clean/verify behavior, tests, docs, lockfile, and CI.
- The implementation follows the active specs:
  - `.10x/specs/atlassian-md-export-cli-config.md`
  - `.10x/specs/jira-export-api-sync.md`
  - `.10x/specs/jira-issue-markdown-output.md`
  - `.10x/specs/adf-markdown-rendering.md`
  - `.10x/specs/jira-attachments-index-clean-verify.md`
- The project follows the active decision:
  - `.10x/decisions/generalize-atlassian-md-export.md`
- API behavior follows the current research:
  - `.10x/research/2026-07-01-jira-cloud-v3-export-api-facts.md`
- Parent closure maps every child acceptance criterion to evidence and review.

## Child Tickets

- `.10x/tickets/done/2026-07-01-scaffold-atlassian-md-export-python-package.md`
- `.10x/tickets/done/2026-07-01-implement-jira-client-and-sync-state.md`
- `.10x/tickets/done/2026-07-01-implement-adf-renderer-and-markdown-writer.md`
- `.10x/tickets/done/2026-07-01-implement-attachments-index-clean-verify.md`
- `.10x/tickets/done/2026-07-01-add-tests-docs-ci-examples.md`

## Blockers

None. The user ratified repository generalization, explicit output directory behavior, and cleanup semantics on 2026-07-01.

## Progress and Notes

- 2026-07-01: User requested a production Jira Cloud to Markdown exporter optimized for AI-agent ingestion, with detailed CLI, output, sync, rendering, attachment, index, test, and docs requirements.
- 2026-07-01: Inspected workspace root and found no existing `jira-md-export`, `atlassian-md-export`, or `*md-export*` directory.
- 2026-07-01: User ratified generalizing the repository immediately for future Confluence overlap while targeting Jira first.
- 2026-07-01: User ratified requiring explicit `--out` for stateful commands.
- 2026-07-01: User ratified liberal `clean --remove-missing` behavior when the last successful representative pull is authoritative.
- 2026-07-01: All child tickets completed. Final parent review corrected CLI stable timestamp exposure, clarified representative cleanup state semantics, and removed wall-clock drift from stale-index generation before closure.

## Explicit Exclusions

- Do not implement Confluence export behavior in this plan.
- Do not place the project inside an unrelated existing repository.
- Do not use legacy Jira `/rest/api/3/search`.

## Evidence Expectations

- Evidence records for package scaffold validation, unit/mocked/integration-skipped test results, lint/typecheck results, representative CLI smoke tests, deterministic snapshot behavior, and clean/verify behavior.
- Review record before parent closure.

## Dependencies

Child tickets must be executed in dependency order unless the parent updates this plan with evidence that a child can proceed independently.

## Evidence

- `.10x/evidence/2026-07-01-atlassian-md-export-scaffold.md`
- `.10x/evidence/2026-07-01-jira-client-sync-state.md`
- `.10x/evidence/2026-07-01-adf-renderer-markdown-writer.md`
- `.10x/evidence/2026-07-01-attachments-index-clean-verify-implementation.md`
- `.10x/evidence/2026-07-01-tests-docs-ci-examples.md`
- `.10x/evidence/2026-07-01-live-jira-sandbox-integration.md`
- `.10x/reviews/2026-07-01-atlassian-md-export-implementation.md`
- `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md`

## Closure Review

- Child tickets completed the package scaffold, Jira client/state, ADF renderer/writer, attachment/index/clean/verify orchestration, tests, docs, example, lockfile, and CI workflow.
- The active specs remain consistent with implemented behavior for the Jira-first scope.
- The active decision to generalize as `atlassian-md-export` while exposing `jira-md-export` is reflected in package naming, README, and CLI script.
- Current research-backed Jira API requirements are represented in tests for `/rest/api/3/search/jql`, `nextPageToken`, independent comment pagination, 429 retry, and 401 failure.
- Deterministic local output includes stable issue Markdown and deterministic `stale.md` index behavior for identical Jira input.
- The final implementation review passed with residual live-sandbox risk recorded.

## Retrospective

- Separate state concepts that look similar but have different safety consequences: latest sync checkpoint and cleanup deletion authority are not the same thing.
- For future Confluence support, reuse the package-level Atlassian boundary and keep provider-specific API clients behind focused modules rather than sharing Jira semantics.
