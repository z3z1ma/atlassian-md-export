Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/tickets/done/2026-07-01-implement-confluence-comments-attachments-index-verify.md

# Add Confluence Tests, Docs, CI, And Examples

## Scope

Complete Confluence-facing tests, README documentation, example generated Markdown, skipped-by-default live integration mode, and CI coverage.

## Acceptance Criteria

- README documents Confluence setup, auth, examples, config, output layout, incremental sync, attachments, verify, clean, troubleshooting, and limitations.
- Example generated Confluence Markdown file is included without secrets or private data.
- Test suite covers Confluence ADF rendering paths, Markdown/frontmatter, filename safety, incremental sync decisions, API pagination, comments pagination, 429 retry, 401 auth failure, malformed payloads, partial failures, attachment safety, indexes, verify, and clean.
- Snapshot tests cover representative Confluence page Markdown output.
- Integration-test mode exists for a real Confluence sandbox and is skipped by default.
- Integration mode is controlled by environment variables such as `CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, and `CONFLUENCE_MD_EXPORT_SANDBOX_PAGE`.
- CI runs lint, typecheck, and tests for both Jira and Confluence code paths.
- Existing Jira tests and live-sandbox skip behavior remain intact.

## Blockers

None.

## Progress And Notes

- 2026-07-01: Ticket opened from ratified Confluence parent plan.
- 2026-07-01: Updated `README.md` with Confluence setup, auth, examples, config, output layout, incremental sync, attachment handling, verify, clean, troubleshooting, limitations, tests, and sandbox integration documentation.
- 2026-07-01: Added `examples/confluence-launch-readiness.md`, a generated fictional Confluence Markdown page with no secrets/private content.
- 2026-07-01: Added skipped-by-default real Confluence sandbox export coverage to `tests/test_integration_sandbox.py` using `CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, and `CONFLUENCE_MD_EXPORT_SANDBOX_PAGE` while preserving the existing Jira sandbox skip behavior.
- 2026-07-01: Inspected `.github/workflows/ci.yml`; no workflow change was necessary because CI already runs lint, typecheck, and tests over `src tests`, covering both Jira and Confluence paths.
- 2026-07-01: Verified with focused integration/docs-adjacent tests, full pytest, full Ruff, and mypy over `src tests`. Evidence recorded in `.10x/evidence/2026-07-01-confluence-tests-docs-ci-examples.md`.
- 2026-07-01: Retrospective: previous Confluence child tickets already supplied the substantive mocked/unit coverage for API, sync, writer, attachments, verify, and clean behavior; this ticket only needed to close the remaining documentation, example, live-sandbox opt-in, and CI-scope surfaces. No new reusable skill or knowledge record was needed.

## Explicit Exclusions

- Do not require live Confluence credentials in CI.
- Do not include real private Confluence content in examples or snapshots.

## References

- `.10x/specs/confluence-cli-config.md`
- `.10x/specs/confluence-export-api-sync.md`
- `.10x/specs/confluence-page-markdown-output.md`
- `.10x/specs/confluence-attachments-index-clean-verify.md`
- `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md`

## Evidence Expectations

- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy src`
- Skipped-by-default integration test output.
- Live Confluence sandbox evidence if sandbox variables are provided.

## Completion Evidence

- `.10x/evidence/2026-07-01-confluence-tests-docs-ci-examples.md`
