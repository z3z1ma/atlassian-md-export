Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-fix-live-jira-search-default-fields.md, .10x/specs/jira-export-api-sync.md, .10x/specs/atlassian-md-export-cli-config.md

# Live Jira CLI Export Default Fields Evidence

## What Was Observed

The live CLI export initially failed for `DATA-4174` because `/rest/api/3/search/jql` was called without a `fields` parameter. Jira Cloud returned issue objects containing only `id`, so the client correctly rejected the response because `key` was missing.

Shape inspection showed:

```text
payload_keys: isLast, issues
first issue keys: id
id type: str
key type: NoneType
fields type: NoneType
```

When an explicit fields list was supplied, Jira returned `id`, `key`, `self`, and `fields`. The implementation now sends the default field list and any configured custom field IDs for export searches.

No credential values were printed or recorded.

## Procedure

Commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`.

Local verification after the fix:

```text
uv --cache-dir .uv-cache run pytest
```

Result: 29 passed, 1 skipped in 0.46s.

```text
uv --cache-dir .uv-cache run ruff check src tests
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src tests
```

Result: Success, no issues found in 21 source files.

Live CLI export:

```text
fish -lc 'uv --cache-dir .uv-cache run jira-md-export issue DATA-4174 --out /private/tmp/jira-md-export-live-4174 --stable-exported-at'
```

Result: `Repulled 1 issue(s).`

The logged search URL included a non-empty `fields=` parameter containing the default issue field set.

Local verification of the live export:

```text
fish -lc 'uv --cache-dir .uv-cache run jira-md-export verify --out /private/tmp/jira-md-export-live-4174'
```

Result: `Verified Jira Markdown export at /private/tmp/jira-md-export-live-4174`.

Live integration rerun:

```text
fish -lc 'set -gx JIRA_MD_EXPORT_SANDBOX_ISSUE DATA-4174; uv --cache-dir .uv-cache run pytest -m integration'
```

Result: 1 passed, 29 deselected in 0.66s.

Generated artifacts observed:

```text
/private/tmp/jira-md-export-live-4174/indexes/all.md
/private/tmp/jira-md-export-live-4174/indexes/by-assignee.md
/private/tmp/jira-md-export-live-4174/indexes/by-epic.md
/private/tmp/jira-md-export-live-4174/indexes/by-status.md
/private/tmp/jira-md-export-live-4174/indexes/stale.md
/private/tmp/jira-md-export-live-4174/issues/DATA-4174.json
/private/tmp/jira-md-export-live-4174/issues/DATA-4174.md
/private/tmp/jira-md-export-live-4174/manifest.json
/private/tmp/jira-md-export-live-4174/state.sqlite
```

## What This Supports

- Live CLI export now reaches Jira, fetches issue fields and comments, writes Markdown/JSON/state/manifest/index files, and verifies locally.
- Default Jira export field behavior matches the active config/spec field list.
- Configured custom field IDs are included in search field requests.
- Validation for missing `key` remains intact.

## Limits

The live export used one reference issue, `DATA-4174`, and did not download attachments. The issue contained a Jira `taskList` ADF node; the renderer preserved it as an explicit unsupported-node placeholder plus raw JSON, which is correct fallback behavior but not polished task-list Markdown.
