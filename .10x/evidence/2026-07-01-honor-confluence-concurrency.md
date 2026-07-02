Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-honor-confluence-concurrency.md, .10x/specs/confluence-export-api-sync.md

# Honor Confluence Concurrency Evidence

## What Was Observed

`run_confluence_pull(..., concurrency=N)` now normalizes `N` to at least one worker and passes it into the Confluence page export path. Per-page Confluence resource hydration and attachment byte fetching are prepared through a bounded `ThreadPoolExecutor`; local attachment writes, page Markdown/JSON writes, state updates, index generation, and manifest writes remain serial and deterministic.

The focused regression test `test_confluence_pull_honors_concurrency_and_preserves_export_order` forces page 1 to wait while page 2 completes an attachment download. It observes a maximum of two active per-page network requests when `concurrency=2`, confirms the page 2 download is fetched before page 1, and then verifies SQLite page-state insertion order remains the discovery order `1, 2, 3`. The existing end-to-end Confluence pull test now passes `concurrency=0`, proving defensive normalization at the operations boundary.

Partial-failure behavior remains routed through the existing failure list and failed-run finalization path: page-specific hydration failures return a prepared failure entry without stopping other page workers, attachment download validation/fetch/write failures are recorded with page/resource context, and representative state is still advanced only after the failure list is empty.

## Procedure

Ran these commands from `/Users/alexanderbut/code_projects/work/atlassian-md-export` after implementation:

```text
uv run pytest tests/test_confluence_operations.py
uv run ruff check src tests
uv run mypy src tests
```

## Results

```text
uv run pytest tests/test_confluence_operations.py
6 passed in 0.36s

uv run ruff check src tests
All checks passed!

uv run mypy src tests
Success: no issues found in 26 source files
```

## What This Supports

- `run_confluence_pull(..., concurrency=N)` no longer ignores the concurrency argument.
- Per-page Confluence resource hydration and optional attachment byte downloads use the configured bounded worker count.
- Local writes remain serial after concurrent preparation.
- Output/state ordering remains deterministic even when worker completion order differs from discovery order.
- `concurrency < 1` is normalized defensively.
- Focused Confluence operation tests, Ruff, and mypy pass.

## Limits

This evidence is based on mocked Confluence HTTP behavior and local file/state verification. It does not contact a live Confluence site.
