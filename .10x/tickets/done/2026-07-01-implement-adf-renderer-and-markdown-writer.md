Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-scaffold-atlassian-md-export-python-package.md, .10x/tickets/done/2026-07-01-implement-jira-client-and-sync-state.md

# Implement ADF Renderer And Markdown Writer

## Scope

Implement `AdfMarkdownRenderer`, normalized Jira issue/comment models, deterministic YAML frontmatter, deterministic issue Markdown body, raw JSON preservation, Markdown escaping, content hashing, and atomic writes.

## Acceptance Criteria

- `AdfMarkdownRenderer` abstraction exists and all Jira rendering code depends on it.
- Renderer supports required ADF nodes/marks in `.10x/specs/adf-markdown-rendering.md`.
- Unknown ADF nodes emit explicit placeholders and deterministic raw JSON when configured.
- Markdown frontmatter fields and order match `.10x/specs/jira-issue-markdown-output.md`.
- Markdown body section order exactly matches `.10x/specs/jira-issue-markdown-output.md`.
- Comments render oldest-first with stable headings, comment ID, updated timestamp when changed, visibility when present, and converted body.
- `--stable-exported-at` freezes `exported_at` to `1970-01-01T00:00:00Z`.
- `content_hash` does not change solely because default `exported_at` changes.
- `issues/KEY.json` preserves canonical raw issue JSON, fetched comments, raw comment ADF, attachment metadata, and non-secret exporter metadata.
- Markdown and JSON writes are atomic.

## Blockers

None.

## Progress and Notes

- 2026-07-01: Ticket opened from ratified parent plan.
- 2026-07-01: Entered inner loop after Jira client/state ticket completed with evidence.
- 2026-07-01: Implemented local ADF Markdown renderer, normalized Jira issue/comment models, deterministic Markdown/frontmatter/body rendering, stable content hashing, canonical raw JSON preservation, and atomic issue Markdown/JSON writes.
- 2026-07-01: Added renderer unit tests, writer unit tests, and a representative snapshot-style Markdown test.
- 2026-07-01: Verified package compile, pytest, ticket-scoped ruff, and mypy.
- 2026-07-01: Parent-side verification removed a stale unused scaffold import and confirmed full pytest, ruff, and mypy pass.

## Explicit Exclusions

- Do not attempt perfect Jira visual parity.
- Do not drop unknown ADF nodes.
- Do not print or persist environment secrets.

## References

- `.10x/specs/adf-markdown-rendering.md`
- `.10x/specs/jira-issue-markdown-output.md`
- `.10x/specs/jira-export-api-sync.md`

## Evidence Expectations

- Unit tests for ADF renderer required nodes and unknown nodes.
- Unit tests for Markdown escaping and YAML frontmatter.
- Snapshot tests for representative issue Markdown output.
- Test proving byte-identical Markdown with stable exported timestamp for identical source input.

## Evidence

- `.10x/evidence/2026-07-01-adf-renderer-markdown-writer.md`

## Closure Review

- All acceptance criteria are supported by `.10x/evidence/2026-07-01-adf-renderer-markdown-writer.md`.
- The implementation intentionally leaves attachment downloads, indexes, verify, clean, and end-to-end CLI orchestration for `.10x/tickets/done/2026-07-01-implement-attachments-index-clean-verify.md` and later integration work.
- No follow-up ticket is required for the renderer/writer slice.

## Retrospective

- Keep the ADF converter behind `AdfMarkdownRenderer`; the local implementation is small enough for the required Jira Cloud node set and avoids adding a speculative converter dependency.
- Use representative Markdown string snapshots with computed content hash interpolation so snapshot tests remain exact without hard-coding hash internals.
- Keep broad ruff in the normal quality loop now that scaffold lint is clean.
