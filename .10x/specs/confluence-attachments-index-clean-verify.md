Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Confluence Attachments, Indexes, Clean, And Verify

## Purpose And Scope

This specification defines local attachment handling, generated indexes, verification, and cleanup behavior for Confluence exports.

## Attachments

Attachment handling MUST be metadata-only by default.

The CLI MUST support:

- `--download-attachments`
- `--attachment-max-mb`
- `--attachment-include`

`--attachment-include` SHOULD be repeatable and SHOULD match attachment filenames with shell-style glob patterns. If no include pattern is provided, all attachments within size limits are eligible when download is enabled.

Downloaded attachments MUST be stored at:

```text
OUT/attachments/PAGEID/ATTACHMENTID-safe_filename
```

Attachment download URLs MUST be constrained to the authenticated Confluence site origin or safe relative URLs. The implementation MUST reject cross-origin absolute download URLs, path traversal, and ambiguous URL forms.

Filenames MUST be sanitized to prevent path traversal, hidden path segments, control characters, platform-invalid characters, and unstable Unicode/path normalization issues. If a filename becomes empty after sanitization, the exporter MUST use a deterministic fallback such as `attachment`.

`--attachment-max-mb` MUST prevent downloads larger than the configured size. Skipped downloads MUST remain visible in Markdown and raw JSON as metadata.

Attachment writes MUST be atomic.

## Indexes

The exporter MUST generate:

- `indexes/all.md`
- `indexes/by-space.md`
- `indexes/by-label.md`
- `indexes/by-parent.md`
- `indexes/stale.md`

Index entries MUST link relatively to page Markdown files. Sorting MUST be deterministic by grouping key, page title, and page id.

`stale.md` MUST identify pages by updated age using a deterministic threshold documented in README. If no threshold is configured, implementation SHOULD use 30 days as the default. The default reference time SHOULD be the latest page `updated` timestamp in the local export, not wall-clock time.

## Manifest

`manifest.json` MUST be deterministic and MUST include at least:

- schema version
- generator name/version
- Confluence site host
- output path metadata
- last successful representative run id/time/scope
- exported page ids
- counts for pages, footer comments, inline comments, and attachments
- stable hashes needed by verify

The manifest MUST NOT contain secrets.

## Verify

`confluence-md-export verify --out DIR` MUST validate local export consistency without contacting Confluence.

It MUST check at least:

- required directories/files exist
- manifest JSON is parseable
- SQLite state is parseable
- page Markdown files listed by manifest exist
- raw page JSON files listed by manifest exist under `pages/_raw/`
- stored Markdown and raw JSON hashes match current file contents
- index links point to existing page Markdown files
- downloaded attachment paths referenced by Markdown/JSON exist

Verification failures MUST be reported with actionable paths and reasons.

## Clean

`confluence-md-export clean --out DIR --remove-missing` MUST remove local page Markdown files, `pages/_raw/PAGEID.json` files, and downloaded attachment directories for page ids absent from the last successful representative `pull --space`, `pull --cql`, or `pull --ancestor` run recorded in `OUT`.

If no successful representative run exists, clean MUST fail without deleting files.

`clean --remove-missing` MAY also regenerate indexes and manifest after deletion. It MUST preserve SQLite history for removed pages so future repulls can compare state.

Because `--remove-missing` is explicit, no additional interactive confirmation is required.

## Exclusions

- Clean MUST NOT infer missing pages from exact `page`, `comments`, or `attachments` command runs.
- Clean MUST NOT delete SQLite history.
- Verify MUST NOT contact Confluence.
