Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-preserve-confluence-local-link-context.md

# Treat Confluence Ancestor Pulls As Full Scope

## Scope

Repair Confluence sync state so `pull --ancestor PAGE_ID` is always treated as a full-scope representative pull, because the required descendants endpoint is authoritative for subtree discovery and does not support the same updated-time filter used by CQL-backed space/CQL incremental pulls.

## Acceptance Criteria

- `decide_confluence_incremental_sync(... scope_type="ancestor" ...)` returns a full-refresh decision with no `since` value unless `--since` semantics are explicitly unsupported or ignored at the operations boundary with an actionable error.
- Successful ancestor pulls refresh the representative page id set used by `clean --remove-missing`.
- Failed/partial ancestor pulls still do not advance successful/representative run state.
- Tests prove that a prior successful ancestor run does not cause a later default ancestor pull to be marked incremental, and that representative cleanup authority is refreshed.
- The implementation matches the amended `.10x/specs/confluence-export-api-sync.md`.

## Blockers

None.

## Progress And Notes

- 2026-07-01: Amended `.10x/specs/confluence-export-api-sync.md` to make ancestor pulls full-scope representative pulls because the descendants endpoint has no updated-time filter.
- 2026-07-01: Updated Confluence sync decision logic so default ancestor pulls do not become incremental and do not carry `since`.
- 2026-07-01: Added mocked regression coverage proving a later ancestor pull refreshes cleanup authority and `verify_confluence_export` passes after clean.
- 2026-07-01: Fixed shared clean-state handling so preserved Jira/Confluence SQLite rows clear artifact hashes after local files are deleted.
- 2026-07-01: Evidence recorded in `.10x/evidence/2026-07-01-confluence-ancestor-full-scope-clean.md`.

## Explicit Exclusions

- Do not replace descendant endpoint discovery with CQL.
- Do not change space or arbitrary CQL incremental behavior.

## References

- `.10x/specs/confluence-export-api-sync.md`
- `.10x/tickets/done/2026-07-01-build-confluence-md-export.md`

## Evidence Expectations

- Focused state and operations tests for ancestor full-scope behavior.
- `uv run pytest tests/test_state.py tests/test_confluence_operations.py`
- `uv run ruff check src tests`
- `uv run mypy src tests`

## Closure Evidence

- `.10x/evidence/2026-07-01-confluence-ancestor-full-scope-clean.md`
