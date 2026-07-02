Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-implement-attachments-index-clean-verify.md, .10x/specs/jira-attachments-index-clean-verify.md, .10x/specs/jira-export-api-sync.md, .10x/specs/jira-issue-markdown-output.md, .10x/specs/atlassian-md-export-cli-config.md

# Attachments, Indexes, Clean, Verify Implementation Evidence

## What Was Observed

Implementation and focused tests were added for attachment filename safety, metadata-only defaults, explicit attachment download, deterministic indexes, deterministic manifest hashes, local verify, clean removal based on representative state, comments refresh, real CLI local command paths, and `--concurrency` wiring for pull comment fetching.

The reported duplicate `def manifest_json(manifest: Manifest) -> str:` concern was checked in `src/atlassian_md_export/writer.py`; the current file contains one definition at line 120 and compiles successfully.

## Procedure

Commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```text
uv --cache-dir .uv-cache run pytest
```

Result: 25 passed in 0.35s.

```text
uv --cache-dir .uv-cache run ruff check src tests
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src tests
```

Result: Success, no issues found in 20 source files.

```text
rg -n "def manifest_json" src/atlassian_md_export/writer.py
```

Result: one match, `120:def manifest_json(manifest: Manifest) -> str:`.

```text
uv --cache-dir .uv-cache run python -m compileall src/atlassian_md_export/writer.py
```

Result: exit code 0.

Parent-side verification re-ran:

```text
uv --cache-dir .uv-cache run pytest
```

Result: 25 passed in 0.35s.

```text
uv --cache-dir .uv-cache run ruff check src tests
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src tests
```

Result: Success, no issues found in 20 source files.

```text
rg -n "def manifest_json" src/atlassian_md_export/writer.py
```

Result: one match, `120:def manifest_json(manifest: Manifest) -> str:`.

Parent-side local CLI smoke used `/private/tmp/jira-md-export-integration-smoke`:

```text
uv --cache-dir .uv-cache run jira-md-export init --out /private/tmp/jira-md-export-integration-smoke
```

Result: initialized the export directory.

```text
uv --cache-dir .uv-cache run jira-md-export index --out /private/tmp/jira-md-export-integration-smoke
```

Result: regenerated 5 index files.

```text
uv --cache-dir .uv-cache run jira-md-export verify --out /private/tmp/jira-md-export-integration-smoke
```

Result: verified the export directory.

```text
uv --cache-dir .uv-cache run jira-md-export clean --out /private/tmp/jira-md-export-integration-smoke --remove-missing
```

Result: failed safely with `No successful representative pull exists; clean refused to delete local files.`

## What This Supports

- Filename safety is covered by tests for traversal-like names, hidden names, reserved names, control characters, and deterministic truncation.
- Mocked Jira pull tests cover explicit attachment download, include filters, metadata-visible skipped attachments, manifest hashes/counts, generated index links, verify pass, verify fail after deleting a referenced attachment, and partial attachment failure not advancing representative state.
- Local clean behavior is covered for removing issue Markdown/JSON and downloaded attachment directories absent from the last successful representative pull while preserving SQLite issue history.
- Local CLI smoke coverage confirms `init`, `index`, `verify`, and `clean --remove-missing` call real paths rather than placeholders.

## Limits

Tests use `httpx.MockTransport` and local temporary export directories. They do not contact a real Jira site and do not prove network permissions or live Jira data-shape compatibility beyond the mocked REST API v3 shapes used by the suite.
