Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Target: /Users/alexanderbut/code_projects/work/atlassian-md-export live Confluence page fix
Verdict: pass

# Live Confluence Fix Adversarial Review

## Target

Review of the live Confluence repairs in:

- `src/atlassian_md_export/confluence/client.py`
- `src/atlassian_md_export/writer.py`
- `src/atlassian_md_export/operations.py`
- `src/atlassian_md_export/indexes.py`
- Confluence client/writer/operations tests

## Findings

No blocking or significant defects were found by read-only subagent review.

The reviewer verified by inspection that raw page payloads are preserved, missing raw `spaceKey` is resolved from `spaceId`, minimal ancestor objects are accepted, normalized `space_key` is carried through local reload paths, `/wiki` is preserved when `_links.base` contains it, and Jira URL behavior still uses the origin-only Jira helper.

The reviewer identified a coverage gap: `run_confluence_comments()` and `run_confluence_attachments()` did not have direct tests for existing raw JSON where `raw_page` lacks `spaceKey` and relies on `normalized_page.space_key`. The reviewer also identified a residual URL risk: local refresh consumed `normalized_page.space_key` but not `normalized_page.url`.

Both concerns were addressed after review:

- Added `test_confluence_refresh_commands_preserve_normalized_page_metadata`.
- Added normalized URL fallback through local Confluence page reloads and index reconstruction.
- Re-ran focused tests, live integration, live CLI sequence, full pytest, ruff, and mypy.

## Verdict

Pass. The reviewed live failure modes and the reviewer-raised gaps are repaired and covered by final evidence in `.10x/evidence/2026-07-01-live-confluence-page-4185325571.md`.

## Residual Risk

No known unresolved risk for the reported live page path. Live binary attachment download was not exercised because page `4185325571` currently has zero attachments; mocked tests exercise the binary attachment path.
