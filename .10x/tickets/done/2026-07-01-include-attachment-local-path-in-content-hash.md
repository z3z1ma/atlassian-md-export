Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-deep-correctness-audit-jira-exporter.md

# Include Attachment Local Path In Content Hash

## Scope

Ensure issue Markdown `content_hash` changes when renderer-visible attachment local links change.

## Acceptance Criteria

- `content_hash` includes normalized attachment metadata that affects Markdown rendering, including `local_path`.
- A test proves Markdown with and without downloaded attachment local links produces different `content_hash` values.
- Raw JSON preservation remains unchanged.

## Blockers

None.

## Progress and Notes

- 2026-07-01: Added `rendered_attachments` to `issue_content_hash(...)`, using normalized metadata rendered in the Markdown attachment section: id, filename, MIME type, size, created timestamp, author display name, and `local_path`.
- 2026-07-01: Added a focused writer test proving an operations-style normalized `local_path` changes rendered Markdown and frontmatter `content_hash` while `raw_issue` remains identical.
- 2026-07-01: Closed after focused writer tests, full pytest, project-scoped Ruff, and mypy passed. Exact `uv run ruff check .` was run and failed because Ruff traversed `.uv-cache` third-party dependency sources under the package root; this was recorded as an evidence limit.
- 2026-07-01: Final parent verification passed with exact `uv run ruff check .` after project Ruff excludes were tightened, plus `uv run pytest`, `uv run mypy src`, and live Jira sandbox integration for `DATA-4174`.

## References

- `.10x/reviews/2026-07-01-jira-exporter-deep-correctness-audit.md`
- `.10x/specs/jira-issue-markdown-output.md`

## Evidence Expectations

- Writer unit test for attachment local path hash sensitivity.
- Full pytest, ruff, and mypy.

## Evidence

- `.10x/evidence/2026-07-01-attachment-local-path-content-hash-verification.md`
