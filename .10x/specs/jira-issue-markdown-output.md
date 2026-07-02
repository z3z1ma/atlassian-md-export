Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Jira Issue Markdown Output

## Amendment Notes

- 2026-07-01: Amended raw JSON placement in place from `issues/KEY.json` to `issues/_raw/KEY.json` to reduce clutter in the issue Markdown directory while keeping raw issue data issue-scoped.
- 2026-07-01: Added migration expectation for existing exports: commands that initialize or write an export directory SHOULD move legacy direct `issues/KEY.json` files into `issues/_raw/KEY.json` when the destination does not already exist.

## Purpose and Scope

This specification defines deterministic files produced by `jira-md-export` for Jira issues. The output is optimized for AI-agent ingestion and reproducible Git diffs.

## Output Layout

Exports MUST use this layout under `OUT`:

```text
OUT/
  manifest.json
  state.sqlite
  issues/
    PROJ-123.md
    _raw/
      PROJ-123.json
  attachments/
    PROJ-123/
      10001-debug.log
  indexes/
    by-status.md
    by-assignee.md
    by-epic.md
    stale.md
```

`indexes/all.md` MAY also be generated.

## Markdown Frontmatter

Every issue Markdown file MUST start with YAML frontmatter. Fields MUST appear in this exact order:

1. `schema_version`
2. `source`
3. `key`
4. `id`
5. `url`
6. `project`
7. `issue_type`
8. `status`
9. `priority`
10. `assignee`
11. `reporter`
12. `created`
13. `updated`
14. `resolution`
15. `resolutiondate`
16. `labels`
17. `components`
18. `fix_versions`
19. `versions`
20. `parent`
21. `epic`
22. `comment_count`
23. `attachment_count`
24. `exported_at`
25. `content_hash`

Missing scalar values MUST be emitted as `null`. Lists MUST be emitted as YAML lists in deterministic sorted order unless Jira source order is semantically meaningful; labels, components, fix versions, and versions MUST be sorted by display name/value.

`schema_version` MUST be a stable integer or string chosen by implementation and documented in README.

`source` MUST identify Jira Cloud and the site host without secrets.

`url` MUST link to the Jira browse URL for the issue.

`content_hash` MUST be a stable hash of canonical source content and renderer-relevant options. It MUST NOT change solely because `exported_at` changed.

## Export Timestamp

By default, `exported_at` MUST be the current UTC export timestamp in ISO 8601 format.

When `--stable-exported-at` or config `markdown.stable_exported_at: true` is enabled, `exported_at` MUST be frozen to `1970-01-01T00:00:00Z` for cleaner Git diffs. The field MUST still be present.

## Markdown Body

The Markdown body MUST use this exact section order:

1. H1 title: `# KEY: Summary`
2. `## Summary`
3. `## Description`
4. `## Key Fields`
5. `## Links`
6. `## Subtasks`
7. `## Attachments`
8. `## Raw Field Notes`
9. `## Comments`

The H1 MUST use Markdown-escaped issue key and summary text. Missing summary MUST render as an empty string after the colon.

`## Summary` MUST contain the issue summary as plain Markdown text.

`## Description` MUST contain converted Jira ADF Markdown or a clear empty-state marker such as `_No description._`.

`## Key Fields` MUST include stable normalized fields useful to agents: type, status, priority, assignee, reporter, created, updated, resolution, labels, versions, parent, epic, and configured custom field values when present.

`## Links` MUST include issue links from Jira in deterministic order, grouped or listed with relationship labels and target issue keys/URLs where present.

`## Subtasks` MUST include subtasks in deterministic key order.

`## Attachments` MUST include metadata for every attachment and the local relative path when downloaded.

`## Raw Field Notes` MUST list included fields that were present in raw Jira data but not rendered elsewhere, especially configured custom fields.

`## Comments` MUST include all fetched comments oldest-first. When timestamps tie, comments MUST sort by numeric/string comment id.

## Comments Format

Each comment MUST have a stable heading:

```md
### Comment N <U+2014 em dash> Author Display Name <U+2014 em dash> Created Timestamp
```

The implementation MUST use the U+2014 em dash character surrounded by single spaces in generated Markdown, exactly matching the user-supplied heading contract. The heading text, order, and components MUST remain stable.

Below the heading, each comment MUST include:

- comment ID
- updated timestamp if different from created
- visibility if present
- converted Markdown body

Comment numbering MUST start at 1 after oldest-first sorting.

## Determinism

For identical Jira source input and identical configuration, generated Markdown MUST be byte-identical except for `exported_at` when stable timestamp mode is disabled.

Deterministic output requires:

- UTF-8
- `\n` line endings
- final newline
- stable YAML key order
- stable section order
- stable list sorting
- stable JSON serialization for raw files
- stable relative links
- stable escaping of Markdown metacharacters in headings, table cells, and links

## Exclusions

- Markdown conversion quality does not need to be perfect, but raw JSON and raw comment ADF preservation is mandatory.
- Do not emit secrets from environment variables.
- Do not use search-embedded comments as the authoritative comments body.
