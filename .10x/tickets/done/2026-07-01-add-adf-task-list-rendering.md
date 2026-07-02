Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Add ADF Task List Rendering

## Scope

Add first-class Markdown rendering for Jira/Confluence ADF `taskList` and `taskItem` nodes.

## Acceptance Criteria

- `taskList` renders as deterministic Markdown task-list items.
- `taskItem` state maps to unchecked/checked Markdown syntax where possible.
- Nested rich inline content inside task items is preserved.
- Unknown or malformed task-list content still uses the explicit unsupported-node fallback and raw JSON preservation.
- Unit tests cover checked, unchecked, nested, and malformed task-list shapes.

## Blockers

None. This is not required to preserve data because unknown-node fallback already includes raw JSON, but live Jira issue `DATA-4174` demonstrated that task lists are common enough to deserve first-class rendering.

## Progress and Notes

- 2026-07-01: Ticket opened after live CLI export of `DATA-4174` showed an ADF `taskList` in acceptance criteria.
- 2026-07-01: Confluence scoping made task-list rendering a dependency for first-class Confluence page Markdown output.
- 2026-07-01: Renderer-only implementation completed in `atlassian-md-export/src/atlassian_md_export/renderer.py` with focused tests in `atlassian-md-export/tests/test_renderer.py`. Focused pytest, Ruff, and mypy verification passed; evidence recorded in `.10x/evidence/2026-07-01-adf-task-list-rendering.md`. At that point, the ticket remained open for parent closure/review because that child execution scope did not include writer snapshot or end-to-end export verification.
- 2026-07-01: Added focused Jira writer coverage in `atlassian-md-export/tests/test_writer.py` proving generated issue Markdown renders task lists in description and comment bodies. Focused writer/renderer pytest, Ruff, and mypy verification passed; evidence updated in `.10x/evidence/2026-07-01-adf-task-list-rendering.md`.

## Explicit Exclusions

- Do not change raw ADF preservation.
- Do not broaden into a full ADF renderer rewrite.

## References

- `.10x/specs/adf-markdown-rendering.md`
- `.10x/evidence/2026-07-01-live-jira-cli-export-default-fields.md`
- `.10x/specs/confluence-page-markdown-output.md`

## Evidence Expectations

- Renderer unit tests.
- Snapshot or focused writer test showing task list in issue Markdown.

## Evidence

- `.10x/evidence/2026-07-01-adf-task-list-rendering.md`
- `.10x/reviews/2026-07-01-adf-task-list-rendering-closure.md`
