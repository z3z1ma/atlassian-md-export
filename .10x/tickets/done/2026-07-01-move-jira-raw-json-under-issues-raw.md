Status: done
Created: 2026-07-01
Updated: 2026-07-01
Depends-On: .10x/tickets/done/2026-07-01-implement-adf-renderer-and-markdown-writer.md, .10x/tickets/done/2026-07-01-implement-attachments-index-clean-verify.md

# Move Jira Raw JSON Under Issues Raw

## Scope

Move exported Jira raw issue JSON files from `issues/KEY.json` to `issues/_raw/KEY.json` while keeping issue Markdown at `issues/KEY.md`.

## Acceptance Criteria

- `init` creates `issues/_raw/`.
- New issue exports write Markdown to `issues/KEY.md` and raw JSON to `issues/_raw/KEY.json`.
- Index generation reads raw JSON from `issues/_raw/*.json` and continues linking to `../issues/KEY.md`.
- `comments` and `attachments` commands read existing local raw JSON from `issues/_raw/KEY.json`.
- `verify` checks raw issue JSON under `issues/_raw/`, manifest hashes, index links, and downloaded attachment references.
- `clean --remove-missing` removes `issues/KEY.md`, `issues/_raw/KEY.json`, and downloaded attachment directories for removed keys.
- README/example/test expectations reflect the new layout.
- Existing local tests, lint, and typecheck pass.
- A smoke export verifies the new layout in a temporary directory.

## Blockers

None.

## Progress and Notes

- 2026-07-01: User requested reducing clutter by moving raw JSON out of direct `issues/` siblings. User preferred amending active specs in place rather than superseding them.
- 2026-07-01: Before code changes, live incremental pull on `/private/tmp/jira-md-export-live-DATA-project` was tested. It used `sync_since=2026-07-01T18:24:35.976267+00:00`, exported 0 issues, preserved full representative run 1, and `verify` passed.
- 2026-07-01: Active specs were amended in place to make `issues/_raw/KEY.json` the canonical raw issue JSON path.
- 2026-07-01: Active specs were amended in place again to add one-way migration from legacy `issues/KEY.json` files to `issues/_raw/KEY.json` during stateful initialization.
- 2026-07-01: Implemented canonical path helpers, raw-directory initialization, one-way migration, writer path update, index/raw reader update, manifest/verify/clean/comments/attachments path updates, README update, and regression tests.
- 2026-07-01: Verified local gates and live smoke checks, including migration of the existing full DATA export to 4783 raw files under `issues/_raw/` with no direct `issues/*.json` files remaining.

## Explicit Exclusions

- Do not change Markdown file placement.
- Do not change raw JSON content or deterministic serialization.
- Do not add broad backwards-compatible dual-read behavior. A one-way migration from legacy `issues/KEY.json` to `issues/_raw/KEY.json` is in scope because existing export directories must remain safe on the next stateful command.
- Do not change attachment binary layout.

## References

- `.10x/specs/jira-issue-markdown-output.md`
- `.10x/specs/jira-export-api-sync.md`
- `.10x/specs/jira-attachments-index-clean-verify.md`

## Evidence Expectations

- `uv --cache-dir .uv-cache run pytest`
- `uv --cache-dir .uv-cache run ruff check src tests`
- `uv --cache-dir .uv-cache run mypy src tests`
- Local smoke export confirms `issues/_raw/KEY.json`, no direct `issues/KEY.json`, and `verify` passes.

## Evidence

- `.10x/evidence/2026-07-01-jira-raw-json-under-issues-raw.md`

## Closure Review

- `init` creates `issues/_raw/`; covered by `test_local_cli_commands_use_real_paths`.
- New exports write Markdown to `issues/KEY.md` and raw JSON to `issues/_raw/KEY.json`; covered by writer tests and live `DATA-4174` smoke export.
- Index generation, manifest hashing, comments/attachments refresh, verify, and clean use `issues/_raw/*.json`; covered by unit tests and full DATA export verification after migration.
- Existing old-layout exports are migrated during stateful initialization; covered by `test_initialize_output_migrates_legacy_issue_json_to_raw_dir` and the migrated full DATA export.
- Full gates passed: pytest, ruff, and mypy.

## Retrospective

- Layout changes that move source files need a migration check before implementation, even when the new layout is simple. Otherwise an incremental no-op can accidentally make indexes and manifests appear empty.
