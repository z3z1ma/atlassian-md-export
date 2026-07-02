Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Build Confluence Markdown Exporter

## Scope

Add a Confluence companion exporter to `/Users/alexanderbut/code_projects/work/atlassian-md-export`, reusing the generalized Atlassian package boundary and Jira hardening lessons while exposing a separate `confluence-md-export` CLI.

This is a parent plan, not an executable implementation ticket.

## Acceptance Criteria

- Child tickets complete the Confluence CLI/config/auth surface, API sync/state behavior, page Markdown/raw output, comments/attachments/index/clean/verify behavior, tests, docs, examples, and CI updates.
- The implementation follows the active specs:
  - `.10x/specs/confluence-cli-config.md`
  - `.10x/specs/confluence-export-api-sync.md`
  - `.10x/specs/confluence-page-markdown-output.md`
  - `.10x/specs/confluence-attachments-index-clean-verify.md`
  - `.10x/specs/adf-markdown-rendering.md`
- The project follows the active decision:
  - `.10x/decisions/generalize-atlassian-md-export.md`
- API behavior follows the current research:
  - `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md`
- Parent closure maps every child acceptance criterion to evidence and review.

## Child Tickets

- `.10x/tickets/done/2026-07-01-implement-confluence-cli-config-auth.md`
- `.10x/tickets/done/2026-07-01-implement-confluence-client-and-sync-state.md`
- `.10x/tickets/done/2026-07-01-implement-confluence-page-writer.md`
- `.10x/tickets/done/2026-07-01-implement-confluence-comments-attachments-index-verify.md`
- `.10x/tickets/done/2026-07-01-add-confluence-tests-docs-ci-examples.md`
- `.10x/tickets/done/2026-07-01-honor-confluence-concurrency.md`
- `.10x/tickets/done/2026-07-01-preserve-confluence-local-link-context.md`
- `.10x/tickets/done/2026-07-01-treat-confluence-ancestor-pulls-as-full-scope.md`
- `.10x/tickets/done/2026-07-01-repair-confluence-review-blockers.md`
- `.10x/tickets/done/2026-07-01-implement-structured-confluence-logging.md`

## Blockers

None. The user ratified the Confluence scope on 2026-07-01. Nested comment replies are explicitly excluded from the first implementation unless a later ratified spec supersedes that exclusion.

## Progress And Notes

- 2026-07-01: User asked to proceed to Confluence scoping and requested latest docs.
- 2026-07-01: Current official Confluence docs were researched and captured in `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md`.
- 2026-07-01: User ratified the recommended Confluence contract.
- 2026-07-01: Opened focused specs and child implementation tickets.
- 2026-07-01: CLI/config/auth child completed with evidence in `.10x/evidence/2026-07-01-confluence-cli-config-auth.md`.
- 2026-07-01: API client/sync-state child completed with evidence in `.10x/evidence/2026-07-01-confluence-client-sync-state.md`.
- 2026-07-01: Page Markdown/raw writer child completed with evidence in `.10x/evidence/2026-07-01-confluence-page-writer.md`.
- 2026-07-01: Comments/attachments/index/clean/verify child record was repaired into `tickets/done` after it was already marked done with evidence in `.10x/evidence/2026-07-01-confluence-comments-attachments-index-verify.md`.
- 2026-07-01: Tests/docs/examples/CI child completed with evidence in `.10x/evidence/2026-07-01-confluence-tests-docs-ci-examples.md`.
- 2026-07-01: Confluence concurrency repair completed with evidence in `.10x/evidence/2026-07-01-honor-confluence-concurrency.md`.
- 2026-07-01: Local link context repair completed with evidence in `.10x/evidence/2026-07-01-confluence-local-link-context.md`.
- 2026-07-01: Ancestor full-scope cleanup repair completed with evidence in `.10x/evidence/2026-07-01-confluence-ancestor-full-scope-clean.md`.
- 2026-07-01: First adversarial review failed; findings recorded in `.10x/reviews/2026-07-01-confluence-production-readiness-adversarial.md`.
- 2026-07-01: Review blockers repaired with evidence in `.10x/evidence/2026-07-01-confluence-review-blockers-repaired.md`.
- 2026-07-01: Structured Confluence logging residual from adversarial review completed with evidence in `.10x/evidence/2026-07-01-structured-confluence-logging.md`.
- 2026-07-01: Final verification recorded in `.10x/evidence/2026-07-01-confluence-final-verification.md`.
- 2026-07-01: Final adversarial review passed in `.10x/reviews/2026-07-01-confluence-final-adversarial-review.md`.

## Closure Evidence

- `.10x/evidence/2026-07-01-confluence-cli-config-auth.md`
- `.10x/evidence/2026-07-01-confluence-client-sync-state.md`
- `.10x/evidence/2026-07-01-confluence-page-writer.md`
- `.10x/evidence/2026-07-01-confluence-comments-attachments-index-verify.md`
- `.10x/evidence/2026-07-01-confluence-tests-docs-ci-examples.md`
- `.10x/evidence/2026-07-01-honor-confluence-concurrency.md`
- `.10x/evidence/2026-07-01-confluence-local-link-context.md`
- `.10x/evidence/2026-07-01-confluence-ancestor-full-scope-clean.md`
- `.10x/evidence/2026-07-01-confluence-review-blockers-repaired.md`
- `.10x/evidence/2026-07-01-structured-confluence-logging.md`
- `.10x/evidence/2026-07-01-confluence-final-verification.md`
- `.10x/reviews/2026-07-01-confluence-final-adversarial-review.md`

## Explicit Exclusions

- Do not merge Confluence behavior into `jira-md-export`.
- Do not rely on Jira issue semantics for Confluence page hierarchy, comments, attachments, or cleanup state.
- Do not implement nested comment replies in the first Confluence cut.

## Evidence Expectations

- Evidence records for each completed child ticket.
- Mocked HTTP tests for pagination, comments pagination, attachment safety, 429 retry, 401 auth failure, malformed success payloads, and partial failures.
- Snapshot tests for representative Confluence page Markdown output.
- Skipped-by-default live Confluence sandbox integration evidence when credentials/page id are configured.
- Final adversarial review before parent closure.

## Dependencies

Child tickets must be executed in dependency order unless the parent updates this plan with evidence that a child can proceed independently.
