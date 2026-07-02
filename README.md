# atlassian-md-export

Python 3.12 tooling for exporting Jira Cloud issues and Confluence Cloud pages to deterministic Markdown and raw JSON for AI-agent ingestion.

The package exposes two provider-specific CLIs:

```sh
uv run jira-md-export --help
uv run confluence-md-export --help
```

## Setup

```sh
uv sync --dev
```

## Jira Quick Start

Set Jira credentials in the environment or a local `.env` file:

```sh
JIRA_SITE=https://example.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your-api-token
```

Then initialize and export:

```sh
uv run jira-md-export init --out ./jira-export
uv run jira-md-export pull --site "$JIRA_SITE" --project PROJ --out ./jira-export
uv run jira-md-export pull --jql 'project = PROJ AND statusCategory != Done' --out ./jira-export
uv run jira-md-export issue PROJ-123 PROJ-456 --out ./jira-export
uv run jira-md-export comments PROJ-123 --out ./jira-export --force
uv run jira-md-export attachments PROJ-123 --out ./jira-export --attachment-include '*.log' --attachment-max-mb 5
```

Default Jira pulls are metadata-only for attachments. Use `--download-attachments` on `pull` or `issue` to download eligible binaries.

## Confluence Setup And Auth

Create an Atlassian API token for the account that can read the target Confluence site, spaces, pages, comments, labels, and attachments. Set Confluence credentials in the environment or a local `.env` file:

```sh
CONFLUENCE_SITE=https://example.atlassian.net
CONFLUENCE_EMAIL=you@example.com
CONFLUENCE_API_TOKEN=your-api-token
```

`ATLASSIAN_SITE`, `ATLASSIAN_EMAIL`, and `ATLASSIAN_API_TOKEN` are accepted as generic fallbacks. Confluence commands do not fall back to `JIRA_*` variables.

Secrets are never printed by the CLI. Existing environment variables override `.env` values.

## Confluence Examples

Initialize an export directory without contacting Confluence:

```sh
uv run confluence-md-export init --out ./confluence-export
```

Export all pages in a space:

```sh
uv run confluence-md-export pull --site "$CONFLUENCE_SITE" --space DOC --out ./confluence-export
```

Export by CQL, an ancestor subtree, or exact page IDs:

```sh
uv run confluence-md-export pull --cql 'space = "DOC" AND type = page' --out ./confluence-export
uv run confluence-md-export pull --ancestor 123456 --out ./confluence-export
uv run confluence-md-export page 123456 789012 --out ./confluence-export
```

Refresh comments or download attachments for already-exported pages:

```sh
uv run confluence-md-export comments 123456 --out ./confluence-export --force
uv run confluence-md-export attachments 123456 --out ./confluence-export --attachment-include '*.pdf' --attachment-max-mb 10
```

See `examples/confluence-launch-readiness.md` for a safe generated page Markdown example with fictional content.

## Confluence Config

Use `--config PATH`, or place `confluence-md-export.yaml`, `atlassian-md-export.yaml`, or `.confluence-md-export.yaml` in the current directory:

```yaml
site: https://example.atlassian.net
space: DOC
out: ./confluence-export
content:
  body_format: atlas_doc_format
  include_footer_comments: true
  include_inline_comments: true
  include_resolved_inline_comments: true
sync:
  overlap_minutes: 10
  concurrency: 4
  download_attachments: false
markdown:
  stable_exported_at: false
  include_raw_adf_on_unknown_nodes: true
```

CLI options override config values. `--out` is still required for every stateful command even when config contains `out`.

## Confluence Output Layout

`confluence-md-export init --out ./confluence-export` creates:

```text
confluence-export/
  manifest.json
  state.sqlite
  pages/
    _raw/
  attachments/
  indexes/
```

After export, page Markdown lives under `pages/SPACEKEY/PAGEID-safe-title.md`. Raw source JSON lives under `pages/_raw/PAGEID.json`; it includes raw page data, fetched footer and inline comments, attachment metadata, labels, ancestors, child references, and exporter metadata needed to regenerate Markdown.

Generated indexes live under `indexes/`:

```text
indexes/
  all.md
  by-space.md
  by-label.md
  by-parent.md
  stale.md
```

Confluence page Markdown uses `schema_version: 1`, stable frontmatter ordering, and these body sections: page metadata, ancestors, child pages, content, attachments, labels, comments, and raw field notes. Use `--stable-exported-at` or `markdown.stable_exported_at: true` to freeze Markdown frontmatter `exported_at` to `1970-01-01T00:00:00Z` for cleaner diffs. Raw JSON exporter metadata and SQLite `last_exported_at` still record the actual export time.

## Confluence Incremental Sync

Representative `pull --space`, `pull --cql`, and `pull --ancestor` runs use the last successful compatible run for the same output directory and scope, with a 10-minute overlap by default. Use:

```sh
uv run confluence-md-export pull --space DOC --out ./confluence-export --since 2026-07-01T00:00:00Z
uv run confluence-md-export pull --space DOC --out ./confluence-export --force
```

Incremental CQL uses Confluence date literals like `yyyy-MM-dd HH:mm`. Exact `page`, `comments`, and `attachments` commands do not replace the representative page set used by cleanup.

## Confluence Attachments

Attachment export is metadata-only by default. Use `--download-attachments` on `pull`, or the `attachments` command, to download eligible binaries:

```sh
uv run confluence-md-export pull --space DOC --out ./confluence-export --download-attachments --attachment-include '*.pdf' --attachment-max-mb 10
```

Downloaded attachments are stored at `attachments/PAGEID/ATTACHMENTID-safe_filename`. Downloads are limited to same-origin Confluence URLs or safe relative URLs; unsafe origins, path traversal, ambiguous URLs, and over-size files are skipped or reported without corrupting existing exports.

## Local Maintenance

Regenerate Confluence indexes:

```sh
uv run confluence-md-export index --out ./confluence-export
```

Verify local consistency without contacting Confluence:

```sh
uv run confluence-md-export verify --out ./confluence-export
```

Remove local page Markdown, raw JSON, and downloaded attachment directories for pages absent from the last successful representative pull:

```sh
uv run confluence-md-export clean --out ./confluence-export --remove-missing
```

`clean --remove-missing` refuses to delete files when no successful representative Confluence pull exists. SQLite page history is preserved.

## Jira Output And Maintenance

`jira-md-export init --out ./jira-export` creates:

```text
jira-export/
  manifest.json
  state.sqlite
  issues/
    _raw/
  attachments/
  indexes/
```

Jira `pull --project` and `pull --jql` use the last successful pull for the same scope, with a 10-minute updated-time overlap. Only full project/JQL refreshes replace the representative issue set used by cleanup.

```sh
uv run jira-md-export index --out ./jira-export
uv run jira-md-export verify --out ./jira-export
uv run jira-md-export clean --out ./jira-export --remove-missing
```

Raw issue JSON, fetched comments, raw comment ADF, and attachment metadata are preserved in `issues/_raw/KEY.json`.

## Troubleshooting

- `401`: check the provider email, API token, and site access.
- `403`: the account lacks permission for the project, issue, space, page, comment, label, or attachment.
- `404`: the site, issue, page, space, or attachment path was not found.
- Invalid JQL or CQL: the Atlassian error text is shown without secrets.
- Partial failures: completed file writes are atomic; rerun with `--force` or exact `issue`/`page` commands after fixing the cause.
- Missing Confluence credentials: set `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`, or the `ATLASSIAN_*` fallbacks.

## Limitations

- Confluence nested comment replies are not exported in the first implementation.
- Confluence storage-format-only bodies are preserved in raw JSON and rendered as explicit unsupported-body placeholders.
- Embedded media references inside Confluence page content are not rewritten; attachments are listed separately.
- Attachment downloads are opt-in and constrained to safe Confluence-origin targets.
- `verify` is local-only and does not prove that remote Atlassian content has not changed.

## Tests And CI

```sh
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

CI runs lint, typecheck, and the default test suite across the shared Jira and Confluence code paths. Real sandbox tests are skipped by default.

To opt into the Jira sandbox test:

```sh
JIRA_SITE=https://example.atlassian.net \
JIRA_EMAIL=you@example.com \
JIRA_API_TOKEN=token \
JIRA_MD_EXPORT_SANDBOX_ISSUE=PROJ-123 \
uv run pytest -m integration
```

To opt into the Confluence sandbox test:

```sh
CONFLUENCE_SITE=https://example.atlassian.net \
CONFLUENCE_EMAIL=you@example.com \
CONFLUENCE_API_TOKEN=token \
CONFLUENCE_MD_EXPORT_SANDBOX_PAGE=123456 \
uv run pytest -m integration
```
