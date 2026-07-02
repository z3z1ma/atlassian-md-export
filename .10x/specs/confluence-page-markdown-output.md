Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Confluence Page Markdown Output

## Purpose And Scope

This specification defines deterministic files produced by `confluence-md-export` for Confluence pages. The output is optimized for AI-agent ingestion and reproducible Git diffs.

## Output Layout

Exports MUST use this layout under `OUT`:

```text
OUT/
  manifest.json
  state.sqlite
  pages/
    SPACEKEY/
      PAGEID-safe-title.md
    _raw/
      PAGEID.json
  attachments/
    PAGEID/
      ATTACHMENTID-safe_filename
  indexes/
    all.md
    by-space.md
    by-label.md
    by-parent.md
    stale.md
```

Raw JSON MUST live under `pages/_raw/`, not beside Markdown files inside the human-browsable space folders.

The Markdown filename MUST include the immutable page id and a sanitized title slug. Links between generated files MUST be relative.

## Markdown Frontmatter

Every page Markdown file MUST start with YAML frontmatter. Fields MUST appear in this exact order:

1. `schema_version`
2. `source`
3. `id`
4. `url`
5. `title`
6. `space_key`
7. `space_id`
8. `status`
9. `parent`
10. `ancestors`
11. `version`
12. `author`
13. `owner`
14. `created`
15. `updated`
16. `labels`
17. `child_count`
18. `comment_count`
19. `footer_comment_count`
20. `inline_comment_count`
21. `attachment_count`
22. `exported_at`
23. `content_hash`

Missing scalar values MUST be emitted as `null`. Lists MUST be emitted as YAML lists in deterministic order unless Confluence source order is semantically meaningful. Labels MUST be sorted by prefix/name.

`schema_version` MUST be a stable integer or string chosen by implementation and documented in README.

`source` MUST identify Confluence Cloud and the site host without secrets.

`url` MUST link to the Confluence page web URL when available.

`parent` MUST be either `null` or a stable object containing at least the parent page id and title when known.

`ancestors` MUST preserve Confluence hierarchy order from root to immediate parent when known.

`content_hash` MUST be a stable hash of canonical source content and renderer-relevant options. It MUST NOT change solely because `exported_at` changed.

## Export Timestamp

By default, `exported_at` MUST be the current UTC export timestamp in ISO 8601 format.

When `--stable-exported-at` or config `markdown.stable_exported_at: true` is enabled, `exported_at` MUST be frozen to `1970-01-01T00:00:00Z` for cleaner Git diffs. The field MUST still be present.

## Markdown Body

The Markdown body MUST use this exact section order:

1. H1 title: `# Title`
2. `## Page Metadata`
3. `## Ancestors`
4. `## Child Pages`
5. `## Content`
6. `## Attachments`
7. `## Labels`
8. `## Comments`
9. `## Raw Field Notes`

The H1 MUST use Markdown-escaped page title text. Missing title MUST render as an empty string after `#`.

`## Page Metadata` MUST include stable normalized fields useful to agents: space, page id, status, parent, author, owner, created, updated, version, labels, comments, and attachments.

`## Ancestors` MUST include ancestor links in root-to-parent order. If no ancestors are known, it MUST render a clear empty-state marker.

`## Child Pages` MUST include known child or descendant references in deterministic order with relative links when those pages are part of the export.

`## Content` MUST contain converted Confluence ADF Markdown or a clear empty-state marker. If no renderable ADF body is available, it MUST emit an explicit unsupported-body placeholder and preserve raw body JSON in `pages/_raw/PAGEID.json`.

`## Attachments` MUST include metadata for every attachment and the local relative path when downloaded.

`## Labels` MUST list page labels in deterministic order.

`## Comments` MUST include all fetched footer comments and inline comments oldest-first within each comment type. When timestamps tie, comments MUST sort by numeric/string comment id.

`## Raw Field Notes` MUST list included fields that were present in raw Confluence data but not rendered elsewhere.

## Comments Format

Footer comments MUST use stable headings:

```md
### Footer Comment N - Author Display Name - Created Timestamp
```

Inline comments MUST use stable headings:

```md
### Inline Comment N - Author Display Name - Created Timestamp
```

Below each heading, each comment MUST include:

- comment ID
- updated timestamp if different from created
- status if present
- inline resolution status if present
- converted Markdown body or explicit unsupported-body placeholder

Comment numbering MUST start at 1 separately for footer comments and inline comments after oldest-first sorting.

## Determinism

For identical Confluence source input and identical configuration, generated Markdown MUST be byte-identical except for `exported_at` when stable timestamp mode is disabled.

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

- Markdown conversion quality does not need to be perfect, but raw page and comment body preservation is mandatory.
- Do not rewrite arbitrary embedded media references inside page content in the first implementation. ADF media nodes may render as placeholders while attachments are listed separately.
- Do not emit secrets from environment variables.
