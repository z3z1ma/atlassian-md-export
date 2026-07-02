Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-implement-jira-client-and-sync-state.md

# Fix Jira Incremental JQL Date Literals

## Scope

Fix incremental `pull` JQL generation so stored ISO instants are rendered as Jira-valid date literals, preventing invalid date filters from returning empty successful exports.

## Acceptance Criteria

- Incremental JQL uses `updated >= "yyyy-MM-dd HH:mm"` instead of ISO values such as `2026-07-01T18:46:21.362026+00:00`.
- Stored UTC instants are converted to the authenticated Jira user's timezone before formatting.
- Formatting truncates to minute precision rather than rounding up.
- A mocked test proves generated incremental JQL is Jira-valid for a UTC prior run and an `America/Los_Angeles` Jira user timezone.
- A mocked test documents the live API hazard where malformed date JQL can return HTTP 200 with zero issues.
- The live full DATA export incremental pull uses a Jira-valid date literal and verifies afterward.
- Local pytest, ruff, and mypy pass.

## Blockers

None.

## Progress and Notes

- 2026-07-01: User screenshot showed Jira UI rejecting generated JQL with `updated >= "2026-07-01T18:46:21.362026+00:00"`.
- 2026-07-01: Live API check confirmed `/rest/api/3/search/jql` returned HTTP 200 with `issues: []` and `isLast: true` for the malformed date literal, so this can be recorded as a successful no-op pull.
- 2026-07-01: Live API check confirmed the authenticated Jira user timezone is `America/Los_Angeles`.
- 2026-07-01: Active sync spec was amended in place to require Jira-valid date literals converted to the authenticated Jira user's timezone.
- 2026-07-01: Implemented Jira user timezone lookup, ISO-to-Jira-date literal formatting, incremental JQL wiring, and regression coverage. Live DATA incremental now used `updated >= "2026-07-01 11:47"` and exported 16 issue(s).

## Explicit Exclusions

- Do not change the 10-minute overlap policy.
- Do not change raw file layout.
- Do not add Confluence behavior.

## References

- `.10x/specs/jira-export-api-sync.md`

## Evidence Expectations

- `uv --cache-dir .uv-cache run pytest`
- `uv --cache-dir .uv-cache run ruff check src tests`
- `uv --cache-dir .uv-cache run mypy src tests`
- Live incremental DATA pull uses `updated >= "yyyy-MM-dd HH:mm"` and verify passes.

## Evidence

- `.10x/evidence/2026-07-01-jira-incremental-jql-date-literals.md`

## Closure Review

- Incremental JQL now emits `updated >= "yyyy-MM-dd HH:mm"`; local tests assert `2026-07-01T12:20:59.999999+00:00` becomes `2026-07-01 05:20` for `America/Los_Angeles`.
- Stored UTC instants are converted to the authenticated Jira user's timezone via `/rest/api/3/myself`.
- Formatting truncates to minute precision, preserving conservative overlap.
- Mocked tests cover timezone lookup, date formatting, the 200-empty malformed-date hazard, and orchestration-generated incremental JQL.
- Live DATA incremental used Jira-valid date syntax, exported 16 issue(s), and verify passed.
- Full gates passed: pytest, ruff, and mypy.

## Retrospective

- Do not assume HTTP 200 plus empty `issues` proves a valid JQL query for enhanced search. Generated JQL needs local validation for known brittle literal formats before the request is sent.
