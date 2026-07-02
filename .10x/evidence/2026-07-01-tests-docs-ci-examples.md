Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Relates-To: .10x/tickets/done/2026-07-01-add-tests-docs-ci-examples.md, .10x/tickets/done/2026-07-01-build-atlassian-md-export.md, .10x/specs/atlassian-md-export-cli-config.md, .10x/specs/jira-export-api-sync.md, .10x/specs/jira-issue-markdown-output.md, .10x/specs/adf-markdown-rendering.md, .10x/specs/jira-attachments-index-clean-verify.md

# Tests, Documentation, CI, And Examples Evidence

## What Was Observed

The `atlassian-md-export` package contains a Jira-first `jira-md-export` CLI, README, real renderer-produced example Markdown, skipped-by-default real Jira integration test, lockfile, and GitHub Actions workflow.

During final review, the CLI was amended to expose `--stable-exported-at` on rendering commands and to show Rich indeterminate progress for Jira-touching commands. A public-path regression test was added for the documented `custom_fields` config shape, state tests confirm incremental sync can advance without becoming cleanup deletion authority, and `stale.md` index generation was made deterministic from issue data rather than wall-clock time.

## Procedure

Commands were run from `/Users/alexanderbut/code_projects/work/atlassian-md-export`:

```text
uv --cache-dir .uv-cache run pytest
```

Result: 29 passed, 1 skipped in 0.46s. The skipped test is the real Jira sandbox integration test, skipped because sandbox environment variables were not provided.

```text
uv --cache-dir .uv-cache run ruff check src tests
```

Result: All checks passed.

```text
uv --cache-dir .uv-cache run mypy src tests
```

Result: Success, no issues found in 21 source files.

```text
uv --cache-dir .uv-cache lock --check
```

Result: Resolved 32 packages in 3ms.

```text
uv --cache-dir .uv-cache sync --dev --locked
```

Result: Resolved 32 packages and checked 31 packages.

```text
uv --cache-dir .uv-cache run jira-md-export --help
```

Result: command list includes `init`, `pull`, `issue`, `comments`, `attachments`, `verify`, `index`, and `clean`.

```text
uv --cache-dir .uv-cache run jira-md-export pull --help
```

Result: `pull` exposes `--out`, `--site`, `--project`, `--jql`, `--issue`, `--since`, `--force`, `--concurrency`, `--download-attachments`, `--attachment-max-mb`, repeatable `--attachment-include`, and `--stable-exported-at`.

Inspected files:

- `README.md` documents setup, auth, examples, config, deterministic output, cleanup semantics, troubleshooting, and integration test opt-in.
- `examples/ABC-1.md` is renderer-produced Markdown with stable frontmatter order, required section order, oldest-first comments, and a real `content_hash`.
- `.github/workflows/ci.yml` runs `uv sync --dev --locked`, ruff, mypy, and pytest on Python 3.12.
- `tests/test_integration_sandbox.py` requires `JIRA_SITE`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and `JIRA_MD_EXPORT_SANDBOX_ISSUE`; otherwise it skips.

## What This Supports

- The requested testing categories are covered by unit, mocked HTTP, snapshot, state, CLI, and skipped integration tests.
- The package has a lockfile and reproducible CI workflow.
- The CLI surface exposes the stable timestamp option required for cleaner diffs.
- Local index generation avoids wall-clock drift for `stale.md` under identical Jira input.
- The final local quality gate passed after all review fixes.

## Limits

The real Jira sandbox integration test was not run because no sandbox credentials or issue key were present in the environment. The workspace root is not a Git repository, so no repository status diff could be recorded from `git status`.
