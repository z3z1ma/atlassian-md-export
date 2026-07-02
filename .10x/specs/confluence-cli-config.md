Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Confluence CLI And Config

## Purpose And Scope

This specification defines the Confluence-facing CLI contract for `atlassian-md-export`. It covers command names, required output directory behavior, configuration loading, authentication, logging, progress, and user-facing errors.

## Product Boundary

The repository MUST remain `atlassian-md-export` and the Python import package SHOULD remain `atlassian_md_export`.

The Confluence CLI executable MUST be `confluence-md-export`. It MUST live beside `jira-md-export`; it MUST NOT be implemented as a Jira subcommand.

The Confluence implementation MUST target Python 3.12 and reuse the existing project dependencies unless a focused ticket and evidence justify a new dependency.

## Commands

The CLI MUST expose:

- `confluence-md-export init --out DIR`
- `confluence-md-export pull --site URL --space KEY --out DIR`
- `confluence-md-export pull --cql CQL --out DIR`
- `confluence-md-export pull --ancestor PAGE_ID --out DIR`
- `confluence-md-export pull --page PAGE_ID --out DIR`
- `confluence-md-export page PAGE_ID [PAGE_ID...] --out DIR`
- `confluence-md-export comments PAGE_ID [PAGE_ID...] --out DIR --force`
- `confluence-md-export attachments PAGE_ID [PAGE_ID...] --out DIR`
- `confluence-md-export verify --out DIR`
- `confluence-md-export index --out DIR`
- `confluence-md-export clean --out DIR --remove-missing`

Every stateful command MUST require an explicit `--out DIR` option. A config file may contain `out`, but the CLI MUST NOT silently select state from config alone. If both `--out` and config `out` are present, `--out` is authoritative.

`init` MUST create the output directory structure, initialize SQLite state, write an initial manifest if absent, and MAY write an example config file. It MUST NOT require Confluence credentials or contact Confluence.

`verify` and `index` are stateful local commands because they read/write under `OUT`; they MUST require `--out`.

## Configuration

The CLI MUST support `--config PATH` on commands where Confluence or rendering options are relevant. When no config path is provided, the CLI MAY read `confluence-md-export.yaml`, `atlassian-md-export.yaml`, or `.confluence-md-export.yaml` from the current working directory if present.

Supported config keys MUST include at least:

```yaml
site: https://example.atlassian.net
space: SPACE
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

CLI options MUST override config values. Environment variables MUST override `.env` values. Secrets MUST never be written to config, manifest, logs, Markdown, or JSON except when present in Confluence source content itself.

## Authentication

Authentication MUST support:

- `CONFLUENCE_SITE`
- `CONFLUENCE_EMAIL`
- `CONFLUENCE_API_TOKEN`

Authentication SHOULD also support generic Atlassian fallbacks:

- `ATLASSIAN_SITE`
- `ATLASSIAN_EMAIL`
- `ATLASSIAN_API_TOKEN`

The CLI MUST NOT automatically fall back to `JIRA_*` variables for Confluence commands.

`--site URL` or config `site` MAY provide the site instead of environment variables. Email and API token MUST come from environment or `.env`.

The CLI MUST load `.env` files for local development. It MUST never print API tokens or Authorization headers. On missing credentials, it MUST return a friendly actionable error naming the missing variable(s) without echoing secret values.

## Logging And Progress

The CLI MUST provide Rich progress output for network and write operations.

The CLI MUST support:

- `--verbose` for more diagnostic detail.
- `--json-logs` for one JSON object per log event.

Logs MUST be structured enough to identify command, site host, page id, space key, operation, status code, retry count, and output path where relevant. Logs MUST redact secrets.

## Friendly Errors

Errors MUST be actionable. At minimum:

- 401: explain that Confluence credentials are invalid or lack access.
- 403: explain that the user lacks permission for the space/page/resource.
- 404: explain that a page, attachment, space, or site path was not found.
- Invalid CQL: show Confluence's non-secret error text.
- Partial failure: identify failed page ids/resources and confirm existing exports were not corrupted.

## Exclusions

- Do not reuse Jira-specific environment variables for Confluence authentication.
- Do not hide state outside `OUT` except optional `.env`/config reads.
- Do not print secrets, tokens, or Authorization headers.
