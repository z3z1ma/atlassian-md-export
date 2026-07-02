Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-implement-confluence-comments-attachments-index-verify.md

# Honor Confluence Pull Concurrency

## Scope

Repair the Confluence exporter so `confluence-md-export pull --concurrency N` and `sync.concurrency` are honored during page hydration/resource fetching/download work instead of being accepted and ignored.

## Acceptance Criteria

- `run_confluence_pull(..., concurrency=N)` uses `N` as a bounded maximum worker count for per-page hydration/resource fetching and optional attachment downloads.
- Discovery pagination may remain sequential, but hydration/resource/download work for discovered pages must not be hard-coded to one page at a time.
- Output ordering, Markdown/JSON bytes, state updates, manifest, and indexes remain deterministic for identical Confluence input.
- Partial failures still fail the run, identify failed page ids/resources, and do not advance successful/representative run state.
- `concurrency < 1` is normalized defensively at the operations boundary even though the CLI already validates it.
- Tests prove that Confluence pull submits per-page work through the configured concurrency and preserves deterministic output.

## Blockers

None. This is a discovered implementation gap against `.10x/specs/confluence-export-api-sync.md`.

## Progress And Notes

- 2026-07-01: Implemented Confluence pull concurrency at the operations boundary. `run_confluence_pull(..., concurrency=N)` now normalizes `N` to at least one worker, prepares per-page resource hydration and attachment byte downloads through a bounded worker pool, and keeps attachment/page/state/index/manifest writes serial and deterministic.
- 2026-07-01: Added focused mocked coverage proving `concurrency=2` allows two active per-page network requests, attachment byte fetches can complete out of discovery order, and SQLite state writes remain in discovery order. Existing Confluence pull coverage now passes `concurrency=0` to prove defensive normalization.
- 2026-07-01: Verified with the ticket evidence commands. Evidence recorded in `.10x/evidence/2026-07-01-honor-confluence-concurrency.md`.

## Explicit Exclusions

- Do not parallelize local file writes.
- Do not change Jira concurrency behavior.
- Do not add new dependencies.

## References

- `.10x/specs/confluence-export-api-sync.md`
- `.10x/tickets/done/2026-07-01-build-confluence-md-export.md`

## Evidence Expectations

- Focused Confluence operations test covering the configured worker count and deterministic export order.
- `uv run pytest tests/test_confluence_operations.py`
- `uv run ruff check src tests`
- `uv run mypy src tests`

## Completion Evidence

- `.10x/evidence/2026-07-01-honor-confluence-concurrency.md`
