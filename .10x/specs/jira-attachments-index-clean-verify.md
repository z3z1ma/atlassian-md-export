Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Jira Attachments, Indexes, Clean, And Verify

## Amendment Notes

- 2026-07-01: Amended raw issue JSON placement in place from `issues/KEY.json` to `issues/_raw/KEY.json`; verify and clean requirements now refer to that canonical raw path.
- 2026-07-01: Clarified that stateful commands MAY migrate legacy direct raw JSON files into `issues/_raw/` before manifest, index, clean, or write behavior uses raw files.

## Purpose and Scope

This specification defines local attachment handling, generated indexes, verification, and cleanup behavior for Jira exports.

## Attachments

Attachment handling MUST be metadata-only by default.

The CLI MUST support:

- `--download-attachments`
- `--attachment-max-mb`
- `--attachment-include`

`--attachment-include` SHOULD be repeatable and SHOULD match attachment filenames with shell-style glob patterns. If no include pattern is provided, all attachments within size limits are eligible when download is enabled.

Downloaded attachments MUST be stored at:

```text
OUT/attachments/ISSUE_KEY/ATTACHMENT_ID-safe_filename
```

Filenames MUST be sanitized to prevent path traversal, hidden path segments, control characters, platform-invalid characters, and unstable Unicode/path normalization issues. If a filename becomes empty after sanitization, the exporter MUST use a deterministic fallback such as `attachment`.

`--attachment-max-mb` MUST prevent downloads larger than the configured size. Skipped downloads MUST remain visible in Markdown and raw JSON as metadata.

Attachment writes MUST be atomic.

## Indexes

The exporter MUST generate:

- `indexes/by-status.md`
- `indexes/by-assignee.md`
- `indexes/by-epic.md`
- `indexes/stale.md`

It SHOULD also generate `indexes/all.md`.

Index entries MUST link relatively to issue Markdown files. Sorting MUST be deterministic by grouping key and issue key.

`stale.md` MUST identify issues by updated age using a deterministic threshold documented in README. If no threshold is configured, implementation SHOULD use 30 days as the default.

## Manifest

`manifest.json` MUST be deterministic and MUST include at least:

- schema version
- generator name/version
- Jira site host
- output path metadata
- last successful representative run id/time/scope
- exported issue keys
- counts for issues, comments, and attachments
- stable hashes needed by verify

The manifest MUST NOT contain secrets.

## Verify

`jira-md-export verify --out DIR` MUST validate local export consistency without contacting Jira.

It MUST check at least:

- required directories/files exist
- manifest JSON is parseable
- SQLite state is parseable
- issue Markdown files listed by manifest exist
- raw issue JSON files listed by manifest exist under `issues/_raw/`
- stored Markdown and raw JSON hashes match current file contents
- index links point to existing issue Markdown files
- downloaded attachment paths referenced by Markdown/JSON exist

Verification failures MUST be reported with actionable paths and reasons.

## Clean

`jira-md-export clean --out DIR --remove-missing` MUST remove local issue Markdown files, `issues/_raw/KEY.json` files, and downloaded attachment directories for issue keys absent from the last successful representative `pull --project` or `pull --jql` run recorded in `OUT`.

If no successful representative run exists, clean MUST fail without deleting files.

`clean --remove-missing` MAY also regenerate indexes and manifest after deletion. It MUST preserve SQLite history for removed issues so future repulls can compare state.

Because `--remove-missing` is explicit, no additional interactive confirmation is required.

## Exclusions

- Clean MUST NOT infer missing issues from exact `issue`, `comments`, or `attachments` command runs.
- Clean MUST NOT delete SQLite history.
- Verify MUST NOT contact Jira.
