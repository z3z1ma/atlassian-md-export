Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-fix-jira-incremental-jql-date-literals.md, .10x/specs/jira-export-api-sync.md

# Jira Incremental JQL Date Literals Evidence

## What Was Observed

The exporter generated invalid incremental JQL date literals such as:

```text
updated >= "2026-07-01T18:46:21.362026+00:00"
```

Jira's UI rejects that format. A live API check against `/rest/api/3/search/jql` showed the enhanced search endpoint can return HTTP 200 with an empty result for that malformed date literal:

```json
{
  "issues": [],
  "isLast": true
}
```

That means the exporter could record a successful no-op incremental pull while missing real updates. This was not an exception-swallowing path in Python; it was an invalid query shape that Jira's enhanced endpoint accepted as an empty successful response.

The authenticated Jira user timezone was checked through `/rest/api/3/myself` and returned `America/Los_Angeles`. The fix converts stored UTC instants into that Jira user timezone and formats them as Jira-valid `yyyy-MM-dd HH:mm` literals before inserting them into JQL.

## Procedure

Safe live API metadata check for malformed date JQL:

```text
GET /rest/api/3/search/jql?jql=(project = "DATA") AND updated >= "2026-07-01T18:46:21.362026+00:00" ORDER BY updated ASC, key ASC
```

Observed: HTTP 200, empty `issues`, `isLast: true`.

Safe live API metadata check for authenticated user timezone:

```text
GET /rest/api/3/myself
```

Observed:

```json
{
  "timeZone": "America/Los_Angeles",
  "locale": "en_US"
}
```

Local gates after implementation:

```text
uv --cache-dir .uv-cache run pytest
```

Result: 34 passed, 1 skipped in 0.56s.

```text
uv --cache-dir .uv-cache run ruff check src tests
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src tests
```

Result: Success, no issues found in 21 source files.

Live DATA incremental after implementation:

```text
fish -lc 'uv --cache-dir .uv-cache run jira-md-export pull --project DATA --out /private/tmp/jira-md-export-live-DATA-project --stable-exported-at --concurrency 4'
```

Observed JQL used a Jira-valid date literal:

```text
(project = "DATA") AND updated >= "2026-07-01 11:47" ORDER BY updated ASC, key ASC
```

Result:

```text
Exported 16 issue(s).
```

Post-run verification:

```text
uv --cache-dir .uv-cache run jira-md-export verify --out /private/tmp/jira-md-export-live-DATA-project
```

Result:

```text
Verified Jira Markdown export at /private/tmp/jira-md-export-live-DATA-project
```

Recently updated issues captured by the fixed incremental included:

```text
DATA-5039 updated 2026-07-01T11:47:10.886-0700
DATA-5037 updated 2026-07-01T11:48:23.387-0700
DATA-4662 updated 2026-07-01T11:57:53.777-0700
DATA-4826 updated 2026-07-01T11:57:54.626-0700
DATA-5038 updated 2026-07-01T12:01:39.872-0700
```

## What This Supports

- Incremental JQL now uses Jira-valid date literals instead of ISO timestamps.
- Stored UTC state timestamps are converted to the authenticated Jira user's timezone before JQL insertion.
- The previous successful no-op behavior was capable of missing updates; the fixed live incremental captured 16 updates.
- The export remains locally consistent after the fixed incremental pull.

## Limits

The live timezone observation applies to the authenticated Jira user used on July 1, 2026. The code now fetches the user timezone dynamically for incremental pulls rather than assuming this value.
