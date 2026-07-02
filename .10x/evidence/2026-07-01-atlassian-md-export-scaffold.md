Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-scaffold-atlassian-md-export-python-package.md

# Atlassian Markdown Export Scaffold

## What Was Observed

- `/Users/alexanderbut/code_projects/work/atlassian-md-export` exists.
- `pyproject.toml` defines the `atlassian-md-export` Python package, Python `>=3.12`, required runtime dependencies, and the `jira-md-export` console script.
- `.python-version` pins local `uv` execution to Python 3.12.
- `uv.lock` exists.
- Required source module boundaries exist:
  - `src/atlassian_md_export/client.py`
  - `src/atlassian_md_export/models.py`
  - `src/atlassian_md_export/renderer.py`
  - `src/atlassian_md_export/state.py`
  - `src/atlassian_md_export/writer.py`
  - `src/atlassian_md_export/cli.py`
  - `src/atlassian_md_export/indexes.py`
  - `src/atlassian_md_export/attachments.py`
- `jira-md-export --help` runs under Python 3.12.
- `jira-md-export init --out /private/tmp/jira-md-export-scaffold-smoke` initializes the export layout without contacting Jira.
- The initialized smoke directory contains `manifest.json`, `state.sqlite`, `issues/`, `attachments/`, and `indexes/`.
- The initialized SQLite state contains `export_runs` and `issues` tables.

## Procedure

- Attempted `uv lock`; it failed because the sandbox could not create `/Users/alexanderbut/.cache/uv`.
- Re-ran with workspace-local cache:

```sh
uv --cache-dir .uv-cache lock
```

- The first workspace-cache lock attempt failed because sandboxed network could not resolve `pypi.org`.
- Re-ran the same command with approved network access; it resolved 32 packages and wrote `uv.lock`.
- Added `.python-version` with `3.12` after observing `uv` otherwise selected local Python 3.14.
- Ran CLI help smoke with approved network access for runtime dependency download:

```sh
uv --cache-dir .uv-cache run --no-dev --python 3.12 jira-md-export --help
```

- Ran init smoke:

```sh
uv --cache-dir .uv-cache run --no-dev --python 3.12 jira-md-export init --out /private/tmp/jira-md-export-scaffold-smoke
```

- Inspected generated layout with:

```sh
find /private/tmp/jira-md-export-scaffold-smoke -maxdepth 2 -type f -o -type d | sort
cat /private/tmp/jira-md-export-scaffold-smoke/manifest.json
sqlite3 /private/tmp/jira-md-export-scaffold-smoke/state.sqlite '.tables'
```

## What This Supports

- The scaffold ticket's package, lockfile, CLI, config/logging foundation, state initialization, and output initialization criteria are satisfied.
- `init` does not require Jira credentials and does not contact Jira.
- Dependency resolution and runtime execution are reproducible with a workspace-local `uv` cache path.

## Limits

- Jira network sync commands are placeholders by design for this ticket.
- The smoke test did not validate future sync, rendering, attachment, index, clean, or verify behavior.
- `.uv-cache/` and `.venv/` were created locally for verification and are ignored by `.gitignore`.
