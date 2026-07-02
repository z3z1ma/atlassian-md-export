Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Jira Export API And Sync

## Amendment Notes

- 2026-07-01: Amended raw issue JSON placement in place from `issues/KEY.json` to `issues/_raw/KEY.json`; the raw preservation contract and deterministic serialization requirements are unchanged.
- 2026-07-01: Added a one-way local migration expectation so existing export directories with legacy direct `issues/KEY.json` raw files remain safe on the next stateful command.
- 2026-07-01: Amended incremental query behavior to require Jira-valid date literals for `updated >= ...`; stored UTC instants MUST be converted to the authenticated Jira user's timezone and formatted as `yyyy-MM-dd HH:mm` before insertion into JQL.
- 2026-07-01: Reconciled sync cursor authority with cleanup authority. Default incremental pulls use the latest successful non-partial pull for the same compatible scope as the trusted sync cursor; only full representative pulls update the issue-key set used by `clean --remove-missing`.

## Purpose and Scope

This specification defines Jira Cloud issue discovery, exact issue repull behavior, comments fetching, rate-limit handling, incremental sync, and raw source preservation for `jira-md-export`.

## API Contract

The exporter MUST use Jira Cloud REST API v3.

Issue discovery MUST use `/rest/api/3/search/jql`. It MUST NOT use legacy `/rest/api/3/search`.

Discovery pagination MUST follow `nextPageToken` until the result is complete. The client MUST treat either `isLast` or absence of a next token as completion, while preserving enough diagnostics to debug unexpected response shapes.

Discovery requests MUST include an explicit non-empty Jira field list. If the user has not configured fields, the exporter MUST request the default field list from `.10x/specs/atlassian-md-export-cli-config.md`. The exporter MUST also include configured custom field IDs in the request. This is required because Jira Cloud enhanced JQL search may return issue objects containing only `id` when `fields` is omitted.

Comments MUST be fetched for each exported issue with `/rest/api/3/issue/{issueIdOrKey}/comment`. The exporter MUST paginate comments using `startAt` and `maxResults` until all comments are fetched. It MUST NOT treat search-embedded comments as authoritative.

Exact issue commands (`pull --issue` and `issue KEY...`) SHOULD discover/fetch exact keys through `/rest/api/3/search/jql` with key-constrained JQL so one discovery path governs normalization.

Attachment metadata SHOULD come from issue fields. Binary attachment download MUST use Jira's attachment content endpoint only when explicitly enabled.

## Query Behavior

`pull --project KEY` MUST construct a project JQL query equivalent to:

```text
project = KEY ORDER BY updated ASC, key ASC
```

`pull --jql JQL` MUST preserve the caller's filtering semantics. If the JQL does not include an order clause, the exporter SHOULD add a deterministic order by updated and key. If the JQL includes an order clause, the exporter MUST NOT rewrite it except for incremental filtering.

Incremental filtering MUST be applied as an additional updated-time constraint when possible. The exporter MUST preserve user filter semantics by wrapping existing JQL as needed.

Incremental `updated >= ...` literals MUST use Jira-valid JQL date syntax. The exporter MUST NOT emit ISO 8601 timestamp strings with `T`, seconds, microseconds, or timezone offsets inside JQL date literals. When the incremental source value is a stored UTC instant, the exporter MUST convert it to the authenticated Jira user's timezone and format it as `yyyy-MM-dd HH:mm`. This conversion MUST floor/truncate to minute precision, not round upward, so the overlap window remains conservative.

## Incremental Sync

SQLite state MUST track at least:

- issue key
- issue id
- updated timestamp
- stable content hash
- raw JSON hash
- Markdown hash
- last seen time
- last exported time

SQLite state MUST also track export runs, including:

- run id
- command/scope type
- project or JQL where applicable
- started at
- finished at
- success/failure
- representative issue keys for successful project/JQL pulls

Default `pull` behavior MUST use the latest successful non-partial `pull` run for the same output directory and compatible scope as the trusted sync cursor. It MUST apply a 10-minute overlap window by default. `--since` MUST override the default incremental timestamp. `--force` MUST refetch and rerender every issue in scope.

A representative pull is a successful `pull --project` or `pull --jql` run that completed discovery, comments fetching, rendering, atomic writes, state updates, manifest update, and index refresh. Exact `issue`, `comments`, and `attachments` commands MUST NOT replace the representative issue set used by `clean --remove-missing`.

Only full-scope representative pulls MUST update the representative issue key set used by `clean --remove-missing`. Successful incremental pulls MAY advance the trusted sync cursor for future incremental fetches, but MUST NOT replace the representative cleanup key set.

Failed runs, partial-failure runs, malformed success payloads, and runs that fail validation MUST NOT advance either the trusted sync cursor or representative cleanup state.

If there is no prior trusted successful run for the scope, `pull` MUST fetch the full scope.

## Concurrency and Retries

The exporter MUST support `--concurrency`; the default MUST be 4.

On HTTP 429 or 5xx responses, the client MUST retry with exponential backoff and jitter. If `Retry-After` is present, the client MUST respect it. Retry behavior MUST be bounded and surface a clear failure after exhaustion.

HTTP 401 MUST fail fast with an authentication error and MUST NOT retry as a rate-limit failure.

## Partial Failure and Atomicity

The exporter MUST use atomic writes for every Markdown, JSON, manifest, index, and downloaded attachment file. It MUST write temporary files in the destination filesystem and rename into place.

On partial failure:

- Existing complete exports MUST remain readable and uncorrupted.
- The run MUST NOT be marked successful.
- The last successful representative run MUST NOT advance.
- Successfully written individual issue files MAY remain in place if their writes completed atomically and their state is internally consistent.
- The final CLI error MUST identify failed resources.

## Raw Source Preservation

For every exported issue, `issues/_raw/KEY.json` MUST preserve canonical raw source data needed to regenerate Markdown later:

- raw issue JSON from Jira
- raw comments fetched from the comments endpoint, including raw ADF bodies
- raw attachment metadata
- exporter metadata needed to understand source site and fetch time

The JSON file MUST be deterministic: UTF-8, sorted object keys, stable indentation, and final newline.

## Exclusions

- Do not rely on embedded comment snippets from issue search as the authoritative comments source.
- Do not advance representative cleanup state from exact issue repulls.
- Do not implement Confluence fetching in this Jira spec.
