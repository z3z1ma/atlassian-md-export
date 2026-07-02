Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/reviews/2026-07-01-confluence-production-readiness-adversarial.md

# Repair Confluence Review Blockers

## Scope

Address the adversarial review findings that block production readiness:

- Validate Confluence pagination next links before authenticated requests follow them.
- Keep stable Markdown timestamps from corrupting raw JSON exporter metadata and SQLite `last_exported_at`.
- Parse Confluence-style error payloads into actionable HTTP errors.
- Repair Confluence SQLite schema columns for existing pre-final local export databases.

## Acceptance Criteria

- Cross-origin absolute pagination links, scheme-relative pagination links, unsafe schemes, and ambiguous absolute URLs are rejected with clear client errors.
- Same-origin absolute pagination links are converted/followed safely; relative pagination links continue to work.
- `--stable-exported-at` freezes Markdown frontmatter only. Raw JSON exporter metadata and SQLite `last_exported_at` record the actual supplied/current export timestamp.
- Confluence/Jira HTTP error parsing includes `message`, `detail`, `title`, and `statusCode`-style payloads without leaking secrets.
- `initialize_state` repairs all current Confluence table columns on existing DBs.
- Focused tests cover each repaired behavior.

## Blockers

None.

## Progress And Notes

- 2026-07-01: Added Confluence pagination next-link safety for v2 `Link` headers and CQL `_links.next` / `next`.
- 2026-07-01: Split Markdown stable frontmatter timestamp behavior from raw/state actual export timestamps for Jira and Confluence writer paths.
- 2026-07-01: Expanded shared Atlassian HTTP error detail parsing for Confluence-style payloads.
- 2026-07-01: Added Confluence SQLite schema column repair and delayed index creation until after repair.
- 2026-07-01: Added focused tests for all repaired findings and recorded evidence in `.10x/evidence/2026-07-01-confluence-review-blockers-repaired.md`.

## Explicit Exclusions

- Do not implement the broader structured logging gap here unless it stays small and directly tied to the changed paths.
- Do not change Confluence API endpoint choices or output layout.

## References

- `.10x/reviews/2026-07-01-confluence-production-readiness-adversarial.md`
- `.10x/specs/confluence-cli-config.md`
- `.10x/specs/confluence-export-api-sync.md`
- `.10x/specs/confluence-page-markdown-output.md`

## Evidence Expectations

- Focused tests for pagination link safety, stable raw/state timestamps, error parsing, and Confluence schema repair.
- `uv run pytest`
- `uv run ruff check src tests`
- `uv run mypy src tests`

## Closure Evidence

- `.10x/evidence/2026-07-01-confluence-review-blockers-repaired.md`
