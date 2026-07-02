Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md, .10x/tickets/done/2026-07-01-fix-live-jira-search-default-fields.md, .10x/tickets/done/2026-07-01-move-jira-raw-json-under-issues-raw.md, .10x/tickets/done/2026-07-01-fix-jira-incremental-jql-date-literals.md

# Deep Correctness Audit Jira Exporter

## Scope

Perform an adversarial correctness audit of `atlassian-md-export` before starting Confluence export work.

## Acceptance Criteria

- A sub-agent performs a fresh read-only review of Jira exporter correctness.
- The review prioritizes bugs, data-loss risk, missed-update risk, silent-success paths, partial failure behavior, state drift, pagination, JQL generation, auth/error handling, raw JSON preservation, raw-layout migration, attachment verification, indexes, and deterministic output.
- Findings include severity, exact file/function references, why the bug matters, and a suggested reproduction or test.
- Parent agent reconciles the sub-agent report against source and records a durable review.
- Any confirmed unresolved defect that should survive this workstream gets a durable owner ticket.

## Blockers

None.

## Progress and Notes

- 2026-07-01: Ticket opened after live incremental JQL date-literal bug caused missed updates because Jira enhanced search returned HTTP 200 with empty issues for malformed date JQL.
- 2026-07-01: Spawned sub-agent Volta for a read-only adversarial pass over Jira exporter correctness before Confluence work.
- 2026-07-01: Parent reconciled Volta's report against source, active specs, knowledge, and recent evidence, then recorded `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`.
- 2026-07-01: Opened durable owners for confirmed issues: `.10x/tickets/done/2026-07-01-restrict-jira-attachment-download-hosts.md`, `.10x/tickets/done/2026-07-01-reject-malformed-jira-success-payloads.md`, `.10x/tickets/done/2026-07-01-reconcile-incremental-sync-cursor-authority.md`, `.10x/tickets/done/2026-07-01-harden-jql-order-by-parsing.md`, `.10x/tickets/done/2026-07-01-include-attachment-local-path-in-content-hash.md`, and `.10x/tickets/done/2026-07-01-jira-exporter-validation-and-verify-hardening.md`.

## Explicit Exclusions

- Do not implement Confluence behavior in this audit.
- Do not make code changes as part of the read-only sub-agent pass.
- Do not treat sub-agent claims as evidence until the parent reconciles them against source or commands.

## References

- `.10x/specs/jira-export-api-sync.md`
- `.10x/specs/jira-issue-markdown-output.md`
- `.10x/specs/jira-attachments-index-clean-verify.md`
- `.10x/specs/atlassian-md-export-cli-config.md`
- `.10x/evidence/2026-07-01-live-data-project-export.md`
- `.10x/evidence/2026-07-01-jira-raw-json-under-issues-raw.md`
- `.10x/evidence/2026-07-01-jira-incremental-jql-date-literals.md`

## Evidence Expectations

- Sub-agent report.
- Parent-authored review record under `.10x/reviews/`.
- Follow-up tickets for confirmed unresolved defects, if any.

## Closure Review

- Acceptance criteria satisfied: a fresh sub-agent review was performed, parent reconciliation was completed, a durable review was recorded, and every confirmed unresolved defect mentioned in the final report has a durable owner.
- The review verdict is `fail` for proceeding to Confluence until critical/significant Jira exporter issues are fixed or explicitly accepted.
- No code changes were made as part of this audit ticket; implementation belongs to the follow-up tickets.
