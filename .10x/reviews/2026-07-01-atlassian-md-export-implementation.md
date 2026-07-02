Status: recorded
Created: 2026-07-01
Updated: 2026-07-01
Target: .10x/tickets/done/2026-07-01-build-atlassian-md-export.md
Verdict: pass

# Atlassian Markdown Export Implementation Review

## Target

Review of the Jira-first `atlassian-md-export` implementation under `/Users/alexanderbut/code_projects/work/atlassian-md-export` against the active specs, parent ticket, and user request.

## Findings

No blocking findings remain.

Review surfaced and corrected three issues before closure:

- `--stable-exported-at` was supported in config and writer code but not exposed as a CLI flag on rendering commands. It is now exposed on `pull`, `issue`, `comments`, and `attachments`, with CLI test coverage.
- The final state review clarified that incremental sync advancement and cleanup deletion authority are distinct. State now records representative issue keys only for successful full representative project/JQL refreshes while incremental decisions use the latest successful scope run.
- `stale.md` initially used wall-clock time. It now uses the latest issue `updated` timestamp as the default reference time so local indexes remain deterministic for identical Jira input.

## Assumptions Tested

- Jira issue discovery uses `/rest/api/3/search/jql` with `nextPageToken`, not `/rest/api/3/search`.
- Comments are fetched from `/rest/api/3/issue/{issueIdOrKey}/comment` and paginated independently of search-embedded comment data.
- Raw issue JSON, fetched comments, raw comment ADF, and attachment metadata are preserved.
- Markdown frontmatter and body section order are stable and snapshot-tested.
- Attachment downloads are opt-in, safe-named, and atomically written.
- `clean --remove-missing` refuses deletion without representative state and preserves SQLite history.
- `stale.md` index generation is deterministic from local issue data by default.
- Default tests skip live Jira integration without credentials.

## Residual Risk

Live Jira compatibility is now smoke-tested for reference issue `DATA-4174` in `.10x/evidence/2026-07-01-live-jira-sandbox-integration.md`. Broader Jira field-shape coverage, attachment downloads, and destructive/local maintenance commands are still proven by mocked/local tests rather than live Jira. The ADF renderer is local and intentionally wrapped behind `AdfMarkdownRenderer`; it covers the required minimum nodes but is not a full Atlassian editor implementation.

## Verdict

Pass. The implementation satisfies the active Jira-first scope with the live-sandbox limitation recorded in evidence.
