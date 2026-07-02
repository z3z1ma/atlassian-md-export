Status: done
Created: 2026-07-01
Updated: 2026-07-01
Parent: .10x/tickets/done/2026-07-01-build-confluence-md-export.md
Depends-On: .10x/reviews/2026-07-01-confluence-production-readiness-adversarial.md

# Implement Structured Confluence Logging

## Scope

Add structured Confluence logging around network and write operations so `--verbose` and `--json-logs` identify command, site host, page id, space key, operation, status code/retry where available, and output path.

## Acceptance Criteria

- Confluence pull/page/comments/attachments emit useful structured logs without printing secrets or Authorization headers.
- Retry and HTTP failure logs include provider, status code, retry attempt, and safe path/resource context where feasible.
- Local file-write logs include page id and output paths.
- Tests verify JSON log redaction and representative Confluence operation context.

## Blockers

None. This is a production operability gap from adversarial review, but not required to safely repair data/auth correctness blockers.

## Progress And Notes

- 2026-07-01: Implementation started after reading the ticket, governing CLI/config spec, adversarial review, and parent plan. Current source inspection found existing JSON log formatting/redaction and incomplete Confluence operation/client context logging.
- 2026-07-01: Implemented stdlib structured logging for Confluence operation context, page/attachment file writes, and shared HTTP retry/failure status context. Evidence recorded in `.10x/evidence/2026-07-01-structured-confluence-logging.md`.

## Explicit Exclusions

- Do not log raw page/comment bodies, tokens, Authorization headers, or attachment binary content.
- Do not introduce a new logging dependency.

## References

- `.10x/specs/confluence-cli-config.md`
- `.10x/reviews/2026-07-01-confluence-production-readiness-adversarial.md`

## Evidence Expectations

- Focused logging tests.
- `uv run pytest`
- `uv run ruff check src tests`
- `uv run mypy src tests`

## Evidence

- `.10x/evidence/2026-07-01-structured-confluence-logging.md`
