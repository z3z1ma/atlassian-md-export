Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Target: /Users/alexanderbut/code_projects/work/atlassian-md-export
Verdict: fail

# Jira Exporter Deep Correctness Audit

## Target

`atlassian-md-export` Jira exporter implementation and tests after the live incremental JQL date-literal fix.

## Method

Sub-agent Volta performed a fresh read-only adversarial review under `.10x/tickets/done/2026-07-01-deep-correctness-audit-jira-exporter.md`. The parent reconciled the report against source, active specs, knowledge, and recent evidence.

## Findings

### Critical: Attachment download trusts arbitrary content URLs

Confirmed.

`src/atlassian_md_export/operations.py` passes `attachment.content_url` directly to `client.http.request_bytes(...)` during attachment download. `src/atlassian_md_export/client.py` uses an authenticated Jira `httpx.Client` for the request. If Jira source data or a mocked/malformed response contains an absolute external URL, the exporter can send Jira Basic Auth to a non-Jira host or download non-Jira content.

This violates `.10x/specs/jira-attachments-index-clean-verify.md`, which constrains binary attachment download to Jira attachment content handling.

Owner: `.10x/tickets/done/2026-07-01-restrict-jira-attachment-download-hosts.md`.

### Significant: Missing `issues` or `comments` in HTTP 200 payloads are treated as empty successful pages

Confirmed.

`src/atlassian_md_export/jira/client.py` uses `payload.get("issues", [])` and `payload.get("comments", [])`. A response missing those fields can become a successful zero-issue search or zero-comment page. This is the same failure class as the malformed-date incident: an unexpected HTTP 200 payload can be mistaken for a real empty result and advance state.

Owner: `.10x/tickets/done/2026-07-01-reject-malformed-jira-success-payloads.md`.

### Significant: Incremental sync cursor semantics conflict with active records

Confirmed as a record conflict and correctness risk.

`.10x/specs/jira-export-api-sync.md` currently says default `pull` MUST use the last successful representative pull. `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md` says incremental decisions SHOULD advance from the latest successful run for the same command/scope while cleanup authority remains representative-only. The implementation follows the knowledge record.

The recent malformed-date incident shows the risk: false-success incrementals can become the next cursor basis. Even after fixing known malformed payloads, this semantic needs explicit hardening or ratification before Confluence copies the pattern.

Owner: `.10x/tickets/done/2026-07-01-reconcile-incremental-sync-cursor-authority.md`.

### Significant: `ORDER BY` detection is not quote-aware

Confirmed.

`src/atlassian_md_export/jira/client.py` detects `ORDER BY` with a regex over the whole JQL string. A valid user JQL such as `summary ~ "order by"` can be misclassified as already ordered, and incremental splitting can cut inside the quoted literal.

Owner: `.10x/tickets/done/2026-07-01-harden-jql-order-by-parsing.md`.

### Minor: `content_hash` ignores attachment local-path rendering

Confirmed.

`src/atlassian_md_export/writer.py` `issue_content_hash(...)` includes raw issue JSON and comments, but not normalized attachment `local_path`. Markdown changes when a downloaded attachment link is rendered, while frontmatter `content_hash` can remain unchanged.

Owner: `.10x/tickets/done/2026-07-01-include-attachment-local-path-in-content-hash.md`.

## Residual Hardening

Volta also identified correctness hardening gaps that are not immediate blockers but should be fixed before the codebase becomes a template for Confluence:

- Negative `sync.overlap_minutes` can move incremental windows into the future.
- `verify` does not compare SQLite state hashes to current file hashes.
- Some whole-run exceptions lack per-issue attribution.

Owner: `.10x/tickets/done/2026-07-01-jira-exporter-validation-and-verify-hardening.md`.

## Verdict

Fail for proceeding to Confluence. The Jira exporter needs the critical/significant findings resolved or explicitly ratified before its patterns are generalized.

The sub-agent pass was valuable and found issues that prior local gates did not catch. The main lesson is that Jira Cloud enhanced search and source payloads must be treated as hostile enough that HTTP 200 and empty arrays are not sufficient evidence of correctness.
