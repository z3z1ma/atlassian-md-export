Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-add-adf-task-list-rendering.md, .10x/specs/adf-markdown-rendering.md

# ADF Task List Rendering Evidence

## What Was Observed

Renderer-only support for ADF `taskList` and `taskItem` nodes was added in
`atlassian-md-export/src/atlassian_md_export/renderer.py`.

Focused renderer tests now cover:

- `TODO` task items rendering as unchecked Markdown task-list items.
- `DONE` task items rendering as checked Markdown task-list items.
- Rich inline content in task items, including marks, links, mentions, and hard breaks.
- Nested `taskList` rendering with deterministic indentation.
- Malformed task-list shapes, including empty or non-list `taskList.content`, and unsupported child
  content preserving the explicit unsupported-node fallback plus deterministic raw JSON.

Focused writer coverage now proves generated Jira issue Markdown renders task lists in both:

- the issue description section; and
- a Jira comment body section.

The ADF state vocabulary was checked against Atlassian's linked JSON schema from
`https://go.atlassian.com/adf-json-schema`, which redirects to
`https://unpkg.com/@atlaskit/adf-schema@56.0.13/dist/json-schema/v1/full.json`.
That schema defines `taskItem.attrs.state` as `TODO` or `DONE`.

## Procedure

Commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`.

```text
uv --cache-dir .uv-cache run pytest tests/test_renderer.py
```

Result: 6 passed in 0.06s.

```text
uv --cache-dir .uv-cache run ruff check src/atlassian_md_export/renderer.py tests/test_renderer.py
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src/atlassian_md_export/renderer.py tests/test_renderer.py
```

Result: Success, no issues found in 2 source files.

Follow-up writer verification:

```text
uv --cache-dir .uv-cache run pytest tests/test_writer.py tests/test_renderer.py
```

Result: 14 passed in 0.16s.

```text
uv --cache-dir .uv-cache run ruff check tests/test_writer.py tests/test_renderer.py src/atlassian_md_export/renderer.py
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy tests/test_writer.py tests/test_renderer.py src/atlassian_md_export/renderer.py
```

Result: Success, no issues found in 3 source files.

## What This Supports

- The renderer maps known ADF task states to deterministic GitHub-style Markdown task-list
  syntax.
- Known inline renderer behavior is reused inside task items, preserving rich inline content.
- Unsupported or malformed task-list content still uses the existing explicit unknown-node
  fallback and raw JSON preservation path.
- Generated Jira issue Markdown includes rendered task-list syntax in issue description and comment
  body sections.

## Limits

Verification was intentionally focused on local renderer and writer unit tests. No live Jira export,
Confluence CLI/client/state path, or end-to-end export command was run.
