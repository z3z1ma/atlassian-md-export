Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-implement-confluence-cli-config-auth.md, .10x/specs/confluence-cli-config.md, .10x/decisions/generalize-atlassian-md-export.md

# Confluence CLI, Config, And Auth

## What Was Observed

- `pyproject.toml` exposes `confluence-md-export` as `atlassian_md_export.cli:confluence_app` beside the existing `jira-md-export` script.
- `confluence-md-export --help` lists `init`, `pull`, `page`, `comments`, `attachments`, `verify`, `index`, and `clean` without adding Confluence as a Jira subcommand.
- Focused CLI tests verify each Confluence stateful command requires explicit `--out`.
- `confluence-md-export init --out DIR` creates `manifest.json`, `state.sqlite`, `pages/_raw/`, `attachments/`, and `indexes/` without requiring Confluence credentials.
- Config loading reads `confluence-md-export.yaml`, `atlassian-md-export.yaml`, and `.confluence-md-export.yaml` with the ratified Confluence keys for `site`, `space`, `out`, `content`, `sync`, and `markdown`.
- Confluence auth resolves `CONFLUENCE_EMAIL`/`CONFLUENCE_API_TOKEN` first and supports `ATLASSIAN_EMAIL`/`ATLASSIAN_API_TOKEN` fallback.
- Confluence auth does not accept `JIRA_EMAIL`/`JIRA_API_TOKEN` fallback.
- `.env` loading supplies Confluence site/email/token values without overriding real environment variables.
- Missing Confluence credentials return a friendly message naming missing variable families without printing secret values.
- Confluence `--verbose` and `--json-logs` initialize logging for Confluence commands, and log redaction covers `CONFLUENCE_API_TOKEN` and `ATLASSIAN_API_TOKEN`.
- Confluence API, page writing, comments, attachments, indexes, verify, and cleanup semantics remain placeholders for later child tickets.

## Procedure

From `/Users/alexanderbut/code_projects/work/atlassian-md-export`, ran:

```sh
uv run pytest tests/test_cli.py
```

Observed:

```text
22 passed
```

Ran:

```sh
uv run ruff check src/atlassian_md_export/cli.py src/atlassian_md_export/config.py src/atlassian_md_export/log.py tests/test_cli.py
```

Observed:

```text
All checks passed!
```

Ran:

```sh
uv run mypy src/atlassian_md_export/cli.py src/atlassian_md_export/config.py src/atlassian_md_export/log.py
```

Observed:

```text
Success: no issues found in 3 source files
```

Ran:

```sh
uv run confluence-md-export --help
uv run jira-md-export --help
```

Observed:

```text
Both commands exited 0 and displayed their separate command surfaces.
```

## What This Supports

- The CLI/config/auth acceptance criteria in `.10x/tickets/done/2026-07-01-implement-confluence-cli-config-auth.md` are satisfied.
- The separate executable decision in `.10x/decisions/generalize-atlassian-md-export.md` is preserved.
- The implementation avoids Confluence network API behavior, matching the ticket exclusion.

## Limits

- No live Confluence site was contacted.
- Full repository tests were not run; verification was focused on CLI/config/auth plus targeted lint/type checks for touched modules.
- The Confluence local `verify`, `index`, and `clean` implementations are intentionally placeholders until the later Confluence child tickets implement page output, indexes, and cleanup semantics.
