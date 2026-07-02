Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Fix Live Confluence Minimal Ancestor Payloads

## Scope

Repair the Confluence client so live `/wiki/api/v2/pages/{id}/ancestors` payloads that contain only `id` and `type` are accepted. Full page hydration must remain strict.

During live CLI verification against page `4185325571`, the exporter also produced `space_key: null`, wrote the page under `pages/unknown-space/`, and emitted a page URL without the required `/wiki` Confluence context path. Those are live correctness defects in the same acceptance path and are in scope for this ticket.

## Acceptance Criteria

- Ancestor and descendant summary validators require a string id and, where relevant, type, but do not require title.
- Full page hydration through `/wiki/api/v2/pages/{id}` still requires id/title.
- Mocked tests cover minimal ancestor payloads.
- Exact page and pull exports resolve `spaceId` to `space_key` without mutating preserved raw page JSON.
- Confluence web URLs preserve the `/wiki` context path when Atlassian returns `_links.base` with `/wiki` and `_links.webui` beginning with `/spaces/...`.
- Live export of page `4185325571` succeeds through the integration and CLI paths.

## Blockers

None. Live testing against `https://floqast.atlassian.net/wiki/spaces/DP/pages/4185325571/Data+Engineer+Onboarding` exposed the issue.

## Evidence Expectations

- Focused Confluence client test.
- Live integration test with `CONFLUENCE_MD_EXPORT_SANDBOX_PAGE=4185325571`.
- CLI page export, comments refresh, index, and verify against a temporary output directory.

## Progress and Notes

- Reproduced the live failure against page `4185325571`: Confluence ancestors returned minimal `id`/`type` objects, including a folder ancestor.
- Loosened Confluence summary validation so ancestor/page summaries require `id` but not `title`; full page hydration remains strict on `id` and `title`.
- Added space-key hydration from `spaceId` through `/wiki/api/v2/spaces/{spaceId}` without mutating preserved `raw_page`.
- Added normalized page metadata in raw export JSON so stateful local commands can preserve resolved fields while keeping source JSON intact.
- Fixed Confluence URL composition so `_links.base` paths like `/wiki` are preserved when `_links.webui` starts with `/spaces/...`.
- Added normalized URL fallback for local comments/attachments/index/verify reconstruction when raw payloads are incomplete.
- Added regression tests for minimal ancestor payloads, space-key hydration, `/wiki` URL preservation, and stateful comments/attachments refresh from raw JSON lacking `spaceKey` and `_links`.
- Ran adversarial read-only review; review concerns were addressed before closure.

## Evidence

- `.10x/evidence/2026-07-01-live-confluence-page-4185325571.md`
- `.10x/reviews/2026-07-01-live-confluence-fix-adversarial-review.md`

Final verification:

```text
CONFLUENCE_MD_EXPORT_SANDBOX_PAGE=4185325571 live integration: 1 passed
Live CLI sequence at /tmp/confluence-md-export-live-final.nA6oI8: init, page, verify, comments --force, attachments, index, verify all exited 0
uv run pytest: 121 passed, 2 skipped
uv run ruff check src tests: All checks passed
uv run mypy src tests: Success, no issues found in 26 source files
```

## Retrospective

The key lesson is now captured in `.10x/knowledge/confluence-cloud-live-api-shapes.md`: Confluence v2 live payloads can omit redundant fields such as `spaceKey`, and Confluence web URLs require preserving `_links.base` context paths such as `/wiki`. Future Confluence work should treat summary endpoint fields as sparse and preserve raw API payloads separately from normalized metadata.
