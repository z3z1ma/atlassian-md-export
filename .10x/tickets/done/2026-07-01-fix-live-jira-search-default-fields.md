Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md

# Fix Live Jira Search Default Fields

## Scope

Fix the live CLI failure where `/rest/api/3/search/jql` returns issue objects with only `id` when no `fields` parameter is provided, causing `jira-md-export issue DATA-4174` to fail before comment fetching or writing.

## Acceptance Criteria

- Default Jira export requests include the configured/spec default field set when no config file provides fields.
- Search requests also include configured custom field IDs.
- Existing validation requiring string issue `id` and `key` remains intact.
- A regression test covers that the orchestration layer sends non-empty default fields.
- The live CLI command `jira-md-export issue DATA-4174 --out /private/tmp/jira-md-export-live --stable-exported-at` succeeds.
- `jira-md-export verify --out /private/tmp/jira-md-export-live` succeeds after the live export.
- Local pytest, ruff, and mypy pass.

## Blockers

None. Live response-shape evidence established that omitting `fields` yields issue objects containing only `id`, while requesting fields yields `id`, `key`, `self`, and `fields`.

## Progress and Notes

- 2026-07-01: Ticket opened after live CLI reproduction failed with `Jira issue response lacked string id/key values.`
- 2026-07-01: Added default Jira field include list, merged configured custom field IDs into search requests, added orchestration regression coverage, reran local gates, live CLI export, live verify, and live integration.

## Explicit Exclusions

- Do not relax parser validation to accept missing issue keys.
- Do not add Confluence behavior in this ticket.

## References

- `.10x/specs/jira-export-api-sync.md`
- `.10x/specs/atlassian-md-export-cli-config.md`
- `.10x/evidence/2026-07-01-live-jira-sandbox-integration.md`

## Evidence Expectations

- Local test/lint/typecheck evidence.
- Live CLI export and verify evidence for `DATA-4174`.

## Evidence

- `.10x/evidence/2026-07-01-live-jira-cli-export-default-fields.md`

## Closure Review

- Acceptance criteria are satisfied by `.10x/evidence/2026-07-01-live-jira-cli-export-default-fields.md`.
- Parser validation remains strict for missing issue keys.
- Active spec `.10x/specs/jira-export-api-sync.md` now records the live enhanced-search behavior.
- No follow-up is needed for the default-fields failure.

## Retrospective

- Live smoke tests need to exercise the actual CLI path, not only a lower-level API integration test, because config/default behavior can diverge.
