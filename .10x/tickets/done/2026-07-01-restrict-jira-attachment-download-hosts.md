Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-deep-correctness-audit-jira-exporter.md

# Restrict Jira Attachment Download Hosts

## Scope

Prevent Jira attachment download from requesting arbitrary external URLs with Jira-authenticated HTTP clients.

## Acceptance Criteria

- Attachment binary download only requests URLs that belong to the configured Jira site host or Jira-relative attachment paths.
- Absolute attachment URLs with a non-site host fail the command as a partial failure and do not write a local attachment file.
- Tests prove no external attachment URL is requested when `content` points outside the Jira site.
- Existing Jira attachment download tests still pass.

## Blockers

None.

## References

- `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`
- `.10x/specs/jira-attachments-index-clean-verify.md`

## Evidence Expectations

- Mocked attachment download test with an external `content` URL.
- Full pytest, ruff, and mypy.

## Progress and Notes

- 2026-07-01: Implemented attachment content URL validation in `atlassian-md-export/src/atlassian_md_export/operations.py`. Jira-relative URLs remain allowed. Absolute `http` or `https` URLs are allowed only when scheme, host, and port match the configured Jira client base URL. Other absolute or authority-bearing URLs become per-attachment partial failures and are not requested.
- 2026-07-01: Added focused mocked coverage in `atlassian-md-export/tests/test_operations.py` proving an external absolute attachment URL is not requested, produces a partial failure, records no local attachment path, and writes no local attachment file.
- 2026-07-01: Parent review tightened the implementation from same-host to same-origin so same-host scheme downgrades such as `http://...` are rejected when the Jira site is `https://...`.

## Evidence

- `.10x/evidence/2026-07-01-jira-operations-correctness-verification.md`

## Closure Notes

- Acceptance criteria are satisfied by the implementation and tests.
- Final verification passed with `uv run pytest`, `uv run ruff check .`, `uv run mypy src`, and live Jira sandbox integration for `DATA-4174`.
