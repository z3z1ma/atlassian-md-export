Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Atlassian Markdown Export CLI And Config

## Purpose and Scope

This specification defines the first Jira-facing CLI contract for `atlassian-md-export`. It covers command names, required output directory behavior, configuration loading, authentication, logging, and friendly errors.

The first production command exposed to users MUST be `jira-md-export`. Confluence commands are explicitly excluded.

## Product Boundary

- The repository MUST be named `atlassian-md-export`.
- The Python import package SHOULD be `atlassian_md_export`.
- The Jira CLI executable MUST be `jira-md-export`.
- The first implementation MUST target Python 3.12 and use `uv`.
- The project MUST include a lockfile.
- Required runtime libraries are `httpx`, `pydantic`, `typer`, `rich`, `PyYAML`, and the Python standard-library `sqlite3` unless implementation evidence proves SQLAlchemy materially reduces complexity.

## Commands

The CLI MUST expose:

- `jira-md-export init --out DIR`
- `jira-md-export pull --site URL --project KEY --out DIR`
- `jira-md-export pull --jql JQL --out DIR`
- `jira-md-export pull --issue KEY --out DIR`
- `jira-md-export issue KEY [KEY...] --out DIR`
- `jira-md-export comments KEY [KEY...] --out DIR --force`
- `jira-md-export attachments KEY [KEY...] --out DIR`
- `jira-md-export verify --out DIR`
- `jira-md-export index --out DIR`
- `jira-md-export clean --out DIR --remove-missing`

Every stateful command MUST require an explicit `--out DIR` option. A config file may contain `out`, but the CLI MUST NOT silently select state from config alone. If both `--out` and config `out` are present, `--out` is authoritative.

`init` MUST create the output directory structure, initialize SQLite state, write an initial manifest if absent, and MAY write an example config file. It MUST NOT require Jira credentials or contact Jira.

`verify` and `index` are stateful local commands because they read/write under `OUT`; they MUST still require `--out`.

## Configuration

The CLI MUST support `--config PATH` on commands where Jira or rendering options are relevant. When no config path is provided, the CLI MAY read `jira-md-export.yaml`, `atlassian-md-export.yaml`, or `.jira-md-export.yaml` from the current working directory if present.

Supported config keys MUST include at least:

```yaml
site: https://example.atlassian.net
project: PROJ
out: ./jira-export
fields:
  include:
    - summary
    - description
    - issuetype
    - status
    - priority
    - assignee
    - reporter
    - creator
    - created
    - updated
    - resolution
    - resolutiondate
    - labels
    - components
    - fixVersions
    - versions
    - parent
    - issuelinks
    - attachment
    - subtasks
    - project
custom_fields:
  story_points: customfield_10016
  sprint: customfield_10020
  epic_link: customfield_10014
sync:
  overlap_minutes: 10
  concurrency: 4
  download_attachments: false
markdown:
  stable_exported_at: false
  include_raw_adf_on_unknown_nodes: true
```

CLI options MUST override config values. Environment variables MUST override `.env` values. Secrets MUST never be written to config, manifest, logs, Markdown, or JSON except when present in Jira source content itself.

## Authentication

Authentication MUST support:

- `JIRA_SITE`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

The CLI MUST load `.env` files for local development. It MUST never print API tokens or Authorization headers. On missing credentials, it MUST return a friendly actionable error naming the missing variable(s) without echoing secret values.

`--site URL` or config `site` MAY provide the site instead of `JIRA_SITE`. Email and API token MUST come from environment or `.env`.

## Logging and Progress

The CLI MUST provide Rich progress output for network and write operations.

The CLI MUST support:

- `--verbose` for more diagnostic detail.
- `--json-logs` for one JSON object per log event.

Logs MUST be structured enough to identify command, site host, issue key, page/operation, status code, retry count, and output path where relevant. Logs MUST redact secrets.

## Friendly Errors

Errors MUST be actionable. At minimum:

- 401: explain that Jira credentials are invalid or lack access.
- 403: explain that the user lacks permission for the issue/project/resource.
- 404: explain that an issue, attachment, or site path was not found.
- Invalid JQL: show Jira's non-secret error text.
- Partial failure: identify failed issue keys/resources and confirm existing exports were not corrupted.

## Exclusions

- No Confluence commands or Confluence API calls in the first Jira implementation.
- No hidden global state outside `OUT` except optional `.env`/config reads.
- No printing of secrets, tokens, or Authorization headers.
