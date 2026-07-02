Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-fix-verify-external-attachment-link-false-positive.md, .10x/specs/jira-attachments-index-clean-verify.md, .10x/specs/jira-export-api-sync.md, .10x/specs/jira-issue-markdown-output.md

# Live DATA Project Export Evidence

## What Was Observed

A live full-project Jira export for project `DATA` completed successfully to `/private/tmp/jira-md-export-live-DATA-project`.

The initial `verify` run failed on `issues/DATA-2182.md` because the verifier treated an external GitHub `user-attachments` URL in a Jira comment as a local downloaded attachment path. Inspection showed `DATA-2182` has `attachment_count: 0`; the failing link was ordinary comment content, not Jira attachment metadata.

The verifier was corrected to skip external and anchor links before checking issue Markdown links for local `attachments/` targets. A regression test was added so external URLs containing `user-attachments` do not fail verification while missing local downloaded attachments still do.

After the fix, the live DATA export verified successfully.

## Procedure

Commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`.

Full DATA export:

```text
fish -lc 'uv --cache-dir .uv-cache run jira-md-export pull --project DATA --out /private/tmp/jira-md-export-live-DATA-project --stable-exported-at --force --concurrency 4'
```

Result:

```text
Exported 4783 issue(s).
```

Initial verify:

```text
fish -lc 'uv --cache-dir .uv-cache run jira-md-export verify --out /private/tmp/jira-md-export-live-DATA-project'
```

Result: failed with one false positive:

```text
Markdown attachment link target missing: /private/tmp/jira-md-export-live-DATA-project/issues/DATA-2182.md -> https://github.com/user-attachments/files/.../redacted.xlsx
```

Focused regression and gates after fixing verifier external-link handling:

```text
uv --cache-dir .uv-cache run pytest tests/test_operations.py
```

Result: 7 passed in 0.32s.

```text
uv --cache-dir .uv-cache run pytest
```

Result: 29 passed, 1 skipped in 0.81s.

```text
uv --cache-dir .uv-cache run ruff check src tests
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src tests
```

Result: Success, no issues found in 21 source files.

Post-fix verify:

```text
uv --cache-dir .uv-cache run jira-md-export verify --out /private/tmp/jira-md-export-live-DATA-project
```

Result:

```text
Verified Jira Markdown export at /private/tmp/jira-md-export-live-DATA-project
```

Manifest and local file/state counts:

```text
jq '{jira_site_host, counts, last_successful_representative_run: {id: .last_successful_representative_run.id, command: .last_successful_representative_run.command, scope_type: .last_successful_representative_run.scope_type, scope_value: .last_successful_representative_run.scope_value, issue_count: (.last_successful_representative_run.issue_keys | length)}}' /private/tmp/jira-md-export-live-DATA-project/manifest.json
```

Observed:

```json
{
  "jira_site_host": "floqast.atlassian.net",
  "counts": {
    "attachments": 1734,
    "comments": 5130,
    "issues": 4783
  },
  "last_successful_representative_run": {
    "id": 1,
    "command": "pull",
    "scope_type": "project",
    "scope_value": "DATA",
    "issue_count": 4783
  }
}
```

```text
sqlite3 /private/tmp/jira-md-export-live-DATA-project/state.sqlite 'select count(*) as issue_rows from issues; select id, command, scope_type, scope_value, succeeded, partial_failure, failure_message from export_runs order by id desc limit 1;'
```

Observed:

```text
4783
1|pull|project|DATA|1|0|
```

File counts:

```text
find /private/tmp/jira-md-export-live-DATA-project -type f | wc -l
find /private/tmp/jira-md-export-live-DATA-project/issues -maxdepth 1 -type f -name '*.md' | wc -l
find /private/tmp/jira-md-export-live-DATA-project/issues -maxdepth 1 -type f -name '*.json' | wc -l
find /private/tmp/jira-md-export-live-DATA-project/indexes -maxdepth 1 -type f -name '*.md' | wc -l
```

Observed:

```text
9573 total files
4783 issue Markdown files
4783 issue JSON files
5 index Markdown files
```

## What This Supports

- Live Jira Cloud REST API v3 project export works for the full `DATA` project using `/rest/api/3/search/jql`, authoritative comment fetches, pagination, rendering, state, manifest, and index generation.
- The export directory is locally self-consistent according to `jira-md-export verify`.
- The last successful representative run is recorded for `pull` scope `project:DATA` with 4783 issue keys.
- The verifier now distinguishes external comment links containing `attachments/` from local downloaded Jira attachment references.

## Limits

Attachment binary download was not enabled; the 1734 attachment count is Jira attachment metadata, not downloaded files. The export used `--stable-exported-at`, so Markdown `exported_at` values are frozen for deterministic output. The live Jira project can change after this run, so the counts are evidence for the July 1, 2026 run only.
