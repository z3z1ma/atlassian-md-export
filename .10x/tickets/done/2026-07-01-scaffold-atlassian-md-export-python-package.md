Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md
Depends-On: None

# Scaffold Atlassian Markdown Export Python Package

## Scope

Create the new `atlassian-md-export` Python 3.12 project scaffold with `uv`, package metadata, lockfile, source tree, CLI entrypoint, logging/config foundations, and repository documentation skeleton.

## Acceptance Criteria

- `/Users/alexanderbut/code_projects/work/atlassian-md-export` exists as a Git repository or Git-ready project directory.
- `pyproject.toml` defines a Python 3.12 package with dependencies required by `.10x/specs/atlassian-md-export-cli-config.md`.
- `uv.lock` exists.
- Console script `jira-md-export` points at the Typer CLI.
- Source layout includes the required module boundaries at minimum:
  - `client.py`
  - `models.py`
  - `renderer.py`
  - `state.py`
  - `writer.py`
  - `cli.py`
  - `indexes.py`
  - `attachments.py`
- The package layout leaves a minimal Jira provider boundary consistent with `.10x/decisions/generalize-atlassian-md-export.md`.
- Config loading supports YAML and `.env` without printing secrets.
- Logging foundations support `--verbose` and `--json-logs` with secret redaction.
- `jira-md-export init --out DIR` can initialize local output structure without contacting Jira.

## Blockers

None.

## Progress and Notes

- 2026-07-01: Ticket opened from ratified parent plan.
- 2026-07-01: Entered inner loop for scaffold implementation after user authorized implementation.
- 2026-07-01: Created the `atlassian-md-export` project scaffold with Python package metadata, CLI entrypoint, source module boundaries, config/logging foundations, SQLite initialization, and output initialization.
- 2026-07-01: Generated `uv.lock` using `uv --cache-dir .uv-cache lock` after sandboxed home-cache and network attempts failed; network access was approved for PyPI dependency resolution.
- 2026-07-01: Added `.python-version` pin `3.12` after local `uv` initially selected Python 3.14.
- 2026-07-01: Verified `jira-md-export --help` and `jira-md-export init --out /private/tmp/jira-md-export-scaffold-smoke` under Python 3.12.

## Explicit Exclusions

- Do not implement Jira network sync beyond placeholders needed for CLI wiring.
- Do not implement Confluence commands.

## References

- `.10x/decisions/generalize-atlassian-md-export.md`
- `.10x/specs/atlassian-md-export-cli-config.md`

## Evidence Expectations

- Command output showing `uv lock` or equivalent lockfile creation.
- Command output showing `jira-md-export --help` and `jira-md-export init --out <tmpdir>` succeed.
- Evidence that no secrets are logged by default-path commands.

## Evidence

- `.10x/evidence/2026-07-01-atlassian-md-export-scaffold.md`

## Closure Review

- All acceptance criteria are satisfied by `.10x/evidence/2026-07-01-atlassian-md-export-scaffold.md`.
- The scaffold intentionally leaves Jira network sync and Confluence commands unimplemented per explicit exclusions.
- No follow-up ticket is required for the scaffold slice.

## Retrospective

- Use `uv --cache-dir .uv-cache ...` in this workspace to avoid sandbox writes to the home uv cache.
- Keep `.python-version` pinned to `3.12` so local `uv` does not select a newer interpreter.
