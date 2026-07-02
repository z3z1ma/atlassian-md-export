Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-implement-jira-client-and-sync-state.md

# Jira Client And Sync State

## What Was Observed

- Jira client code uses `/rest/api/3/search/jql` for issue discovery.
- Search pagination follows `nextPageToken`.
- Comments are fetched from `/rest/api/3/issue/{issueIdOrKey}/comment` using `startAt` and `maxResults`.
- `fetch_issues_with_comments` ignores search-embedded comments and fetches authoritative comments independently.
- Exact issue repulls use key-constrained JQL through the same search client path.
- HTTP 429 and 5xx retry through bounded retry logic; `Retry-After` is respected.
- HTTP 401 raises an authentication error without retrying.
- SQLite state tracks issue key/id/update/hash/seen/export fields and export run metadata.
- Incremental sync decisions cover previous representative runs with 10-minute overlap, explicit `--since`, `--force`, exact issue refreshes, and partial-failure non-advancement.
- Source-only grep found no exact legacy endpoint string `"/rest/api/3/search"` in `src/atlassian_md_export`.

## Procedure

From `/Users/alexanderbut/code_projects/work/atlassian-md-export`, ran:

```sh
uv --cache-dir .uv-cache run pytest
```

Observed:

```text
11 passed in 0.16s
```

Ran:

```sh
uv --cache-dir .uv-cache run ruff check src/atlassian_md_export/client.py src/atlassian_md_export/jira src/atlassian_md_export/state.py src/atlassian_md_export/cli.py tests
```

Observed:

```text
All checks passed!
```

Ran:

```sh
uv --cache-dir .uv-cache run mypy src tests
```

Observed:

```text
Success: no issues found in 16 source files
```

Ran:

```sh
rg -F '"/rest/api/3/search"' src/atlassian_md_export
```

Observed exit code 1 with no output, meaning no source match.

## What This Supports

- The Jira client and SQLite sync-state acceptance criteria are satisfied for mocked API behavior and local state decisions.
- Legacy issue search is not used in implementation source.
- Partial failures do not advance representative sync state.

## Limits

- No live Jira sandbox was contacted.
- End-to-end pull rendering/writing is still owned by later tickets.
- Attachment binary download is still owned by the attachment ticket.
