Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Confluence Export API And Sync

## Purpose And Scope

This specification defines Confluence Cloud page discovery, page hydration, comments fetching, attachment metadata fetching, hierarchy fetching, rate-limit handling, incremental sync, and raw source preservation for `confluence-md-export`.

## API Contract

The exporter MUST use Confluence Cloud REST API v2 for authoritative page hydration and page-related resources.

The exporter MUST use Confluence REST API v2 endpoints for:

- spaces: `/wiki/api/v2/spaces`
- page listing by space: `/wiki/api/v2/spaces/{id}/pages`
- page hydration: `/wiki/api/v2/pages/{id}`
- ancestors: `/wiki/api/v2/pages/{id}/ancestors`
- descendants: `/wiki/api/v2/pages/{id}/descendants`
- labels: `/wiki/api/v2/pages/{id}/labels`
- footer comments: `/wiki/api/v2/pages/{id}/footer-comments`
- inline comments: `/wiki/api/v2/pages/{id}/inline-comments`
- attachments: `/wiki/api/v2/pages/{id}/attachments`

The exporter MUST NOT use deprecated child-page APIs for subtree discovery. Descendant export MUST use the descendants endpoint and hydrate each discovered page through the page detail endpoint.

Arbitrary CQL discovery MUST use the current official Confluence search/CQL API, `/wiki/rest/api/search`, and then hydrate every discovered page through `/wiki/api/v2/pages/{id}`. CQL search results MUST NOT be treated as authoritative page bodies, comments, attachments, or labels.

Page and comment hydration MUST request `body-format=atlas_doc_format` by default. If Confluence returns only another body representation, raw data MUST still be preserved and Markdown rendering MUST emit an explicit unsupported-body placeholder rather than silently dropping content.

## Pagination

Confluence REST API v2 paginated endpoints MUST follow the HTTP `Link` header until complete.

Confluence CQL search pagination MUST follow the documented next cursor/next link until complete.

For HTTP 200 responses, the client MUST validate the success payload shape expected by the endpoint. Missing `results` lists or missing required id/title fields MUST fail the run instead of being treated as empty results.

## Discovery Behavior

`pull --space KEY` MUST resolve the space key to a Confluence space id through the spaces API before using space page endpoints.

If there is no trusted prior run for a space scope, `pull --space KEY` SHOULD perform a full space page listing through `/wiki/api/v2/spaces/{id}/pages` and hydrate every listed page.

Incremental space pulls SHOULD use CQL discovery constrained to the same space and `lastmodified` overlap window, then hydrate discovered pages through v2. This keeps incremental behavior aligned with Confluence's documented date filtering.

`pull --cql CQL` MUST preserve caller filter semantics. If an incremental constraint is added, the implementation MUST wrap the original CQL as needed rather than changing its meaning.

`pull --ancestor PAGE_ID` MUST export the ancestor root page plus descendants from `/wiki/api/v2/pages/{id}/descendants`, hydrating each page through v2 page detail.

`pull --page PAGE_ID` and `page PAGE_ID...` MUST fetch exact page ids directly through page hydration. Exact page commands MUST NOT replace representative cleanup state.

## CQL Date Behavior

Incremental `lastmodified >= ...` literals MUST use Confluence-valid CQL date syntax. The exporter MUST NOT emit ISO 8601 timestamp strings with `T`, seconds, microseconds, or timezone offsets inside CQL date literals.

When the incremental source value is a stored UTC instant, the exporter MUST convert it to a Confluence-compatible date literal formatted as `yyyy-MM-dd HH:mm`. The conversion MUST floor/truncate to minute precision, not round upward, so the overlap window remains conservative.

## Incremental Sync

SQLite state MUST track at least:

- page id
- space id
- space key
- title
- status
- parent id
- normalized updated timestamp
- version number
- stable content hash
- raw JSON hash
- Markdown hash
- last seen time
- last exported time

SQLite state MUST also track export runs, including:

- run id
- command/scope type
- space key, CQL, ancestor id, or exact page ids where applicable
- started at
- finished at
- success/failure
- representative page ids for successful full-scope pulls

Default `pull` behavior for `space` and `cql` scopes MUST use the latest successful non-partial pull run for the same output directory and compatible scope as the trusted sync cursor. It MUST apply a 10-minute overlap window by default. `--since` MUST override the default incremental timestamp. `--force` MUST refetch and rerender every page in scope.

Ancestor pulls MUST be treated as full-scope representative pulls in this implementation because the required descendants endpoint does not provide an updated-time filter. A successful `pull --ancestor PAGE_ID` MUST refresh the representative cleanup page id set.

A representative pull is a successful `pull --space`, `pull --cql`, or `pull --ancestor` run that completed discovery, page hydration, comments fetching, attachment metadata fetching, rendering, atomic writes, state updates, manifest update, and index refresh.

Exact `page`, `comments`, and `attachments` commands MUST NOT replace the representative page set used by `clean --remove-missing`.

Only successful full-scope representative pulls MUST update the representative page id set used by `clean --remove-missing`. Successful incremental pulls MAY advance the trusted sync cursor for future incremental fetches, but MUST NOT replace the representative cleanup page id set.

Failed runs, partial-failure runs, malformed success payloads, and runs that fail validation MUST NOT advance either the trusted sync cursor or representative cleanup state.

If there is no prior trusted successful run for the scope, `pull` MUST fetch the full scope.

## Concurrency And Retries

The exporter MUST support `--concurrency`; the default MUST be 4.

On HTTP 429 or 5xx responses, the client MUST retry with exponential backoff and jitter. If `Retry-After` is present, the client MUST respect it. Retry behavior MUST be bounded and surface a clear failure after exhaustion.

HTTP 401 MUST fail fast with an authentication error and MUST NOT retry as a rate-limit failure.

## Partial Failure And Atomicity

The exporter MUST use atomic writes for every Markdown, JSON, manifest, index, and downloaded attachment file. It MUST write temporary files in the destination filesystem and rename into place.

On partial failure:

- Existing complete exports MUST remain readable and uncorrupted.
- The run MUST NOT be marked successful.
- The last successful representative run MUST NOT advance.
- Successfully written individual page files MAY remain in place if their writes completed atomically and their state is internally consistent.
- The final CLI error MUST identify failed resources.

## Raw Source Preservation

For every exported page, `pages/_raw/PAGEID.json` MUST preserve canonical raw source data needed to regenerate Markdown later:

- raw page JSON from Confluence
- raw footer and inline comments fetched from comment endpoints
- raw attachment metadata
- raw labels
- raw ancestors and child/descendant references collected for rendering
- exporter metadata needed to understand source site and fetch time

The JSON file MUST be deterministic: UTF-8, sorted object keys, stable indentation, and final newline.

## Exclusions

- Do not rely on CQL search results as authoritative page bodies.
- Do not use deprecated child-page endpoints for subtree discovery.
- Do not advance representative cleanup state from exact page, comments, or attachments command runs.
