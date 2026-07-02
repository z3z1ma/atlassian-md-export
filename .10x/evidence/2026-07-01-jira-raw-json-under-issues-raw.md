Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-move-jira-raw-json-under-issues-raw.md, .10x/specs/jira-issue-markdown-output.md, .10x/specs/jira-export-api-sync.md, .10x/specs/jira-attachments-index-clean-verify.md

# Jira Raw JSON Under Issues Raw Evidence

## What Was Observed

Raw Jira issue JSON placement was changed from direct `issues/KEY.json` siblings to `issues/_raw/KEY.json`, while issue Markdown remains at `issues/KEY.md`.

The active specs were amended in place, not superseded. Amendment notes were added to:

- `.10x/specs/jira-issue-markdown-output.md`
- `.10x/specs/jira-export-api-sync.md`
- `.10x/specs/jira-attachments-index-clean-verify.md`

Before code changes, the existing full DATA export was tested with an incremental pull. It used the previous successful run plus the configured 10-minute overlap, exported 0 issues, preserved the representative full run, and verified successfully.

The implementation also added a one-way local migration during `initialize_output`: legacy direct `issues/KEY.json` files move to `issues/_raw/KEY.json` when the new destination does not already exist. This prevents existing export directories from being treated as empty by new-code incremental pulls, index generation, manifest generation, or clean/verify workflows.

## Procedure

Pre-change incremental test against the existing full DATA export:

```text
fish -lc 'uv --cache-dir .uv-cache run jira-md-export pull --project DATA --out /private/tmp/jira-md-export-live-DATA-project --stable-exported-at --concurrency 4'
```

Observed JQL included:

```text
(project = "DATA") AND updated >= "2026-07-01T18:24:35.976267+00:00" ORDER BY updated ASC, key ASC
```

Result:

```text
Exported 0 issue(s).
```

State/manifest/verify after pre-change incremental:

```text
run 1: pull project DATA, representative issue keys length 56319
run 2: pull project DATA, sync_since 2026-07-01T18:24:35.976267+00:00, representative issue keys length 0
manifest counts: 4783 issues, 5130 comments, 1734 attachments
verify: passed
```

Local gates after implementation:

```text
uv --cache-dir .uv-cache run pytest
```

Result: 30 passed, 1 skipped in 0.50s.

```text
uv --cache-dir .uv-cache run ruff check src tests
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src tests
```

Result: Success, no issues found in 21 source files.

Fresh live one-issue smoke export:

```text
fish -lc 'set -l dir (mktemp -d /private/tmp/jira-md-export-raw-layout-smoke.XXXXXX); uv --cache-dir .uv-cache run jira-md-export issue DATA-4174 --out $dir --stable-exported-at; test -f $dir/issues/DATA-4174.md; test -f $dir/issues/_raw/DATA-4174.json; test ! -e $dir/issues/DATA-4174.json; uv --cache-dir .uv-cache run jira-md-export verify --out $dir; echo $dir'
```

Result:

```text
Repulled 1 issue(s).
Verified Jira Markdown export at /private/tmp/jira-md-export-raw-layout-smoke.WKNeSd
```

New-code incremental test against the existing full DATA export:

```text
fish -lc 'uv --cache-dir .uv-cache run jira-md-export pull --project DATA --out /private/tmp/jira-md-export-live-DATA-project --stable-exported-at --concurrency 4'
```

Observed JQL included:

```text
(project = "DATA") AND updated >= "2026-07-01T18:37:30.186195+00:00" ORDER BY updated ASC, key ASC
```

Result:

```text
Exported 0 issue(s).
```

Post-migration full DATA export checks:

```text
uv --cache-dir .uv-cache run jira-md-export verify --out /private/tmp/jira-md-export-live-DATA-project
```

Result:

```text
Verified Jira Markdown export at /private/tmp/jira-md-export-live-DATA-project
```

File layout counts:

```text
0 direct issues/*.json files
4783 issues/_raw/*.json files
4783 issues/*.md files
```

Manifest counts after migration:

```json
{
  "attachments": 1734,
  "comments": 5130,
  "issues": 4783
}
```

State after new-code incremental:

```text
run 1: pull project DATA, representative issue keys length 56319
run 2: pull project DATA, sync_since 2026-07-01T18:24:35.976267+00:00, representative issue keys length 0
run 3: pull project DATA, sync_since 2026-07-01T18:37:30.186195+00:00, representative issue keys length 0
```

## What This Supports

- `issues/_raw/KEY.json` is now the canonical raw issue JSON path.
- `init`, issue writes, indexes, manifest hashes, comments/attachments refreshes, verify, and clean all use the new raw path.
- Existing old-layout exports are migrated on their next stateful command instead of losing manifest/index visibility.
- The existing full DATA export was migrated without losing issue/comment/attachment counts and still verifies.

## Limits

The migration moves legacy direct raw JSON only when `issues/_raw/KEY.json` does not already exist. It intentionally does not provide broad dual-read compatibility for arbitrary mixed layouts.
