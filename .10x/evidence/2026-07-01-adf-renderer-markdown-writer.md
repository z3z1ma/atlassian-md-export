Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-implement-adf-renderer-and-markdown-writer.md

# ADF Renderer And Markdown Writer

## What Was Observed

- `AdfMarkdownRenderer` now renders required ADF blocks, inline nodes, and marks behind the repository-owned abstraction.
- Unknown ADF nodes emit explicit placeholders and can include deterministic sorted raw JSON.
- Issue Markdown rendering emits frontmatter in the exact order required by `.10x/specs/jira-issue-markdown-output.md`.
- Issue Markdown body sections render in the required order.
- Comments are normalized oldest-first and render with stable numbered headings, comment ID, changed updated timestamp, visibility, and converted body.
- Stable export timestamp mode emits `1970-01-01T00:00:00Z`.
- Content hashes are stable across `exported_at` changes.
- Raw issue JSON preservation includes canonical raw issue JSON, fetched comments, raw ADF for description and comments, attachment metadata, and non-secret exporter metadata.
- Issue Markdown and JSON writes use the existing temp-file plus `os.replace` atomic write path.
- Parent-side full-suite verification after cleanup observed pytest, ruff, and mypy all passing.

## Procedure

From `/Users/alexanderbut/code_projects/work/atlassian-md-export`, ran:

```sh
uv --cache-dir .uv-cache run python -m compileall src/atlassian_md_export
```

Observed successful compilation of the package modules.

Ran:

```sh
uv --cache-dir .uv-cache run pytest
```

Observed:

```text
19 passed in 0.20s
```

Ran ticket-scoped ruff:

```sh
uv --cache-dir .uv-cache run ruff check src/atlassian_md_export/renderer.py src/atlassian_md_export/writer.py src/atlassian_md_export/models.py tests/test_renderer.py tests/test_writer.py tests/test_cli.py tests/test_jira_client.py tests/test_state.py
```

Observed:

```text
All checks passed!
```

Ran:

```sh
uv --cache-dir .uv-cache run mypy src tests
```

Observed:

```text
Success: no issues found in 18 source files
```

Parent-side verification then removed one unused scaffold import in `src/atlassian_md_export/config.py` and re-ran:

```sh
uv --cache-dir .uv-cache run pytest
uv --cache-dir .uv-cache run ruff check src tests
uv --cache-dir .uv-cache run mypy src tests
```

Observed:

```text
19 passed in 0.21s
All checks passed!
Success: no issues found in 18 source files
```

## What This Supports

- The renderer and writer acceptance criteria for this ticket are satisfied by unit and representative snapshot-style tests.
- The implementation remains within renderer, writer, model, and test ownership and does not implement attachment downloads, indexes, verify, clean, or end-to-end CLI orchestration.

## Limits

- No live Jira instance was contacted.
- Future CLI orchestration is still required to call these writer helpers during real exports.
