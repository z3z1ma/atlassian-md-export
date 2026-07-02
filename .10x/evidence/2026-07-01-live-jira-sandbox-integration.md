Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-add-tests-docs-ci-examples.md, .10x/tickets/done/2026-07-01-build-atlassian-md-export.md, .10x/specs/jira-export-api-sync.md

# Live Jira Sandbox Integration Evidence

## What Was Observed

The real Jira sandbox integration test passed using the fish universal Jira credentials and `JIRA_MD_EXPORT_SANDBOX_ISSUE=DATA-4174`.

The first non-escalated attempt found all required environment variables but failed at DNS/connect time under the restricted network sandbox. The rerun with network escalation reached Jira Cloud and passed.

No credential values were printed or recorded.

## Procedure

Command run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```text
fish -lc 'set -gx JIRA_MD_EXPORT_SANDBOX_ISSUE DATA-4174; uv --cache-dir .uv-cache run pytest -m integration'
```

Escalated rerun result:

```text
collected 30 items / 29 deselected / 1 selected
tests/test_integration_sandbox.py . [100%]
1 passed, 29 deselected in 1.11s
```

## What This Supports

- Fish universal Jira variables are visible to the integration test when run through `fish`.
- The live Jira API path can read issue `DATA-4174` using `/rest/api/3/search/jql`.
- The live Jira comments path can fetch comments for `DATA-4174` using `/rest/api/3/issue/{issueIdOrKey}/comment`.

## Limits

This proves the current sandbox reference issue path works. It does not prove every Jira field shape, attachment download path, or destructive/local maintenance command against live Jira.
