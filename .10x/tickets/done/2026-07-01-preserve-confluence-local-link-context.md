Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-honor-confluence-concurrency.md

# Preserve Confluence Local Link Context On Repulls

## Scope

Repair Confluence page rendering so incremental pulls and exact page repulls render relative links using the existing local export plus the newly fetched replacement pages, not only the subset fetched in the current run.

## Acceptance Criteria

- `pull` and `page` exports pass an export context containing existing local pages plus all newly fetched replacement pages into `write_confluence_page_files`.
- Newly fetched pages win over older local raw JSON when the same page id appears in both sets.
- Relative links between generated page Markdown files remain stable during incremental pulls and exact page repulls.
- Existing comments and attachments commands continue to preserve local context.
- Tests cover an exact or incremental repull where the fetched page links relatively to an already-exported local page that was not fetched in the current run.

## Blockers

None. This is a discovered implementation gap against `.10x/specs/confluence-page-markdown-output.md`.

## Progress And Notes

- 2026-07-01: Implemented `_confluence_export_context` so pull/page writes use existing local Confluence pages plus fetched replacements.
- 2026-07-01: Added mocked regression coverage for exact page repull linking to an already-exported parent.
- 2026-07-01: Evidence recorded in `.10x/evidence/2026-07-01-confluence-local-link-context.md`.

## Explicit Exclusions

- Do not change Confluence Markdown section order or filename rules.
- Do not contact Confluence during local context loading beyond the pages already fetched for the command.

## References

- `.10x/specs/confluence-page-markdown-output.md`
- `.10x/tickets/done/2026-07-01-build-confluence-md-export.md`

## Evidence Expectations

- Focused Confluence operations or writer test proving local link context survives a one-page repull.
- `uv run pytest tests/test_confluence_operations.py tests/test_confluence_writer.py`
- `uv run ruff check src tests`
- `uv run mypy src tests`

## Closure Evidence

- `.10x/evidence/2026-07-01-confluence-local-link-context.md`
