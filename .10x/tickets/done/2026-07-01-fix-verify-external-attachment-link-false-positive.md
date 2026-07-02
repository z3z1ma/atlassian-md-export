Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-implement-attachments-index-clean-verify.md

# Fix Verify External Attachment Link False Positive

## Scope

Fix `jira-md-export verify` so issue Markdown links to external URLs containing the substring `attachments/` are not treated as local downloaded attachment references.

## Acceptance Criteria

- `verify_export` continues to fail when a local downloaded attachment referenced by issue Markdown is missing.
- `verify_export` passes when issue Markdown contains an external URL such as `https://github.com/user-attachments/...`.
- The DATA project test export at `/private/tmp/jira-md-export-live-DATA-project` verifies successfully after the fix.

## Blockers

None.

## Progress and Notes

- 2026-07-01: Ticket opened after live DATA export produced 4783 issues but verifier failed on `DATA-2182.md` because a GitHub `user-attachments` comment link was resolved as a local attachment file.
- 2026-07-01: Patched `src/atlassian_md_export/operations.py` so issue Markdown attachment-reference verification skips external and anchor links before checking for local `attachments/` targets.
- 2026-07-01: Added a regression to `tests/test_operations.py` covering an external `https://github.com/user-attachments/...` comment link while preserving the missing local downloaded attachment failure check.

## Explicit Exclusions

- Do not change attachment download behavior.
- Do not loosen validation for relative local attachment links.
- Do not contact Jira from verify.

## References

- `.10x/specs/jira-attachments-index-clean-verify.md`
- `.10x/tickets/done/2026-07-01-implement-attachments-index-clean-verify.md`

## Evidence Expectations

- Focused regression test for external attachment-like URLs in issue Markdown.
- `uv --cache-dir .uv-cache run pytest tests/test_operations.py`
- `uv --cache-dir .uv-cache run ruff check src tests`
- `uv --cache-dir .uv-cache run mypy src tests`
- `jira-md-export verify --out /private/tmp/jira-md-export-live-DATA-project`

## Evidence

- `.10x/evidence/2026-07-01-live-data-project-export.md`

## Closure Review

- `verify_export` continues to fail when a local downloaded attachment referenced by issue Markdown is missing; the existing assertion remained in `test_pull_downloads_eligible_attachments_and_verify_checks_local_refs`.
- `verify_export` now passes when issue Markdown contains an external URL with `user-attachments`; the focused regression writes that link through the normal export path.
- The live DATA project export at `/private/tmp/jira-md-export-live-DATA-project` verified successfully after the fix.
- Full gates passed: operations tests, full pytest, ruff, and mypy.

## Retrospective

- Link validation should classify external, anchor, and local paths before substring-based checks. Substrings such as `attachments/` are not enough to prove local export ownership.
