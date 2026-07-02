Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Target: /Users/alexanderbut/code_projects/work/atlassian-md-export
Verdict: pass

# Jira Hardening Post-Fix Adversarial Review

## Target

Final Jira hardening changes made after `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`.

## Method

Sub-agent Bernoulli performed a read-only adversarial review focused on the six audit findings:

- attachment download URL safety
- strict Jira success payload validation
- incremental cursor versus cleanup authority
- quote-aware JQL `ORDER BY` parsing
- attachment `local_path` sensitivity in Markdown `content_hash`
- config and verify hardening

The parent then fixed the one review finding and asked Bernoulli for a read-only confirmation pass.

## Findings

### Minor: operation-level malformed-payload regression coverage was temporary

Resolved.

Bernoulli initially found that malformed HTTP 200 payload state handling was backed by client tests and temporary operation-path evidence, but not committed operation-level regression tests. This mattered because `.10x/tickets/done/2026-07-01-reject-malformed-jira-success-payloads.md` expected a mocked operation test proving malformed payloads do not mark the export run successful.

The parent added persistent tests in `atlassian-md-export/tests/test_operations.py`:

- `test_pull_malformed_search_payload_fails_run_and_preserves_cursor`
- `test_pull_malformed_comments_payload_fails_run_and_preserves_cursor`

These tests exercise `run_pull`, trigger missing search `issues` and missing comment `comments` payloads, assert the latest `export_runs` row has `succeeded = 0` and `partial_failure = 1`, and assert `decide_incremental_sync(...)` still selects the prior successful cursor.

Bernoulli confirmed this finding is fully addressed and found no new issues.

## Verification Referenced

- `.10x/evidence/2026-07-01-jira-hardening-final-verification.md`

## Verdict

Pass.

No unresolved findings block proceeding to Confluence scoping. The remaining stated limit is that live Jira integration reads issue discovery/comments for `DATA-4174` but does not download a real Jira attachment binary; attachment URL safety is covered by mocked tests that fail if unsafe URLs are requested.
