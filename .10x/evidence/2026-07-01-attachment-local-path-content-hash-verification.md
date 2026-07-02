Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-include-attachment-local-path-in-content-hash.md

# Attachment Local Path Content Hash Verification

## What Was Observed

The writer now includes rendered attachment metadata, including `local_path`, in `issue_content_hash(...)`. The focused unit test proves that adding an operations-style normalized attachment `local_path` changes both rendered Markdown and frontmatter `content_hash` while leaving `raw_issue` identical.

## Procedure

All commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`.

- `uv run pytest tests/test_writer.py`: passed, 7 passed in 0.16s.
- `uv run pytest`: passed, 42 passed and 1 skipped in 0.51s.
- `uv run ruff check .`: failed because Ruff traversed top-level `.uv-cache/archive-v0/...` third-party dependency sources and reported 2091 lint errors there.
- `uv run ruff check src tests`: passed, all checks passed.
- `uv run mypy src`: passed, no issues found in 14 source files.
- `uv run pytest tests/test_writer.py -q`: passed, 7 passed in 0.21s.

## What This Supports Or Challenges

This supports the ticket acceptance criteria that renderer-visible attachment local links affect Markdown `content_hash` and that raw Jira issue preservation semantics are not changed by the implementation.

The exact requested Ruff command is not a clean project-source signal while `.uv-cache` exists under the package root. The source/test-scoped Ruff command verifies the files in this slice.

## Limits

`uv run ruff check .` remains noisy because of top-level `.uv-cache`. No cache cleanup or Ruff configuration change was made because those paths are outside the write ownership for this slice.
