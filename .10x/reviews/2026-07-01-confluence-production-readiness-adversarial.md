Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Target: Confluence exporter implementation in /Users/alexanderbut/code_projects/work/atlassian-md-export
Verdict: fail

# Confluence Production Readiness Adversarial Review

## Target

Read-only adversarial review of the Confluence exporter implementation and repair patches against active Confluence specs.

## Findings

### Critical: Auth-bearing pagination followed untrusted links

Confluence v2 and CQL pagination reused raw `Link`, `_links.next`, or `next` values with the authenticated `httpx.Client` without same-origin validation or conversion to safe relative paths.

### Critical: Stable export timestamp leaked into raw/state export-time fields

`stable_exported_at` froze raw JSON exporter metadata and SQLite `last_exported_at`, which made raw/state export-time fields say `1970-01-01T00:00:00Z` instead of the actual export time.

### Significant: Confluence-style error messages were not parsed

The shared HTTP error parser understood Jira `errorMessages` and `errors`, but ignored common Confluence `message`/`statusCode` payloads.

### Significant: Structured Confluence logging is incomplete

JSON logging exists and init emits structured extras, but pull/page/comments/attachments do not yet log command/site/page/resource/retry/output details across network/write operations.

### Residual: Confluence schema repair for pre-final DBs was incomplete

Fresh databases were fine, but existing early Confluence export DBs might lack columns because `initialize_state` only repaired Jira `export_runs` columns.

## Verdict

Fail pending repair of the pagination, timestamp, error parsing, and schema issues. Structured logging requires either a focused implementation or an accepted residual-risk owner before parent closure.

## Residual Risk

The review was source/spec/test/docs only. The reviewer did not run tests or edit code.
