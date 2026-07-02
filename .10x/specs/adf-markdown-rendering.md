Status: active
Created: 2026-07-01
Updated: 2026-07-01

# ADF Markdown Rendering

## Amendment Notes

- 2026-07-01: Broadened this spec from Jira-only use to Atlassian ADF rendering for Jira and Confluence. Confluence pages and comments use the same repository-owned `AdfMarkdownRenderer` abstraction.
- 2026-07-01: Added `taskList` and `taskItem` to required rendering support; implementation is tracked by `.10x/tickets/done/2026-07-01-add-adf-task-list-rendering.md`.

## Purpose and Scope

This specification defines Atlassian Document Format to Markdown rendering behavior for Jira issue descriptions/comments and Confluence page/comment bodies.

## Interface

The project MUST define an `AdfMarkdownRenderer` abstraction owned by this repository. Jira export code MUST depend on that abstraction, not directly on a third-party converter.

The implementation SHOULD use a maintained ADF parser/converter if one is available, compatible with Python 3.12, and simpler than maintaining equivalent local code. Even if a third-party converter is used, raw ADF preservation remains mandatory and unknown-node handling MUST satisfy this spec.

If no suitable maintained converter is found quickly, the project MUST implement a local renderer behind `AdfMarkdownRenderer`.

## Required Node and Mark Support

The renderer MUST support at least:

- paragraphs
- headings
- bullet lists
- ordered lists
- bold
- italic
- underline
- strike
- inline code
- code blocks
- blockquotes
- links
- mentions
- dates
- panels
- tables
- hard breaks
- rules
- media placeholders
- inline cards
- emojis
- task lists
- task items

Nested marks MUST compose in deterministic order. Markdown special characters MUST be escaped where required to preserve literal text.

## Unknown Nodes

Unknown ADF nodes MUST NOT be silently dropped.

When an unknown node or unsupported shape is encountered, the renderer MUST emit an explicit placeholder naming the node type when known. If `markdown.include_raw_adf_on_unknown_nodes` is true, it MUST include the raw node JSON in a fenced `json` block or HTML comment. The raw node serialization MUST be deterministic.

The renderer MUST preserve surrounding known content when an unknown node appears inside a larger document.

## Tables

Tables MUST render as GitHub-flavored Markdown tables when practical. Cell text MUST be escaped for pipes and newlines. Unsupported rich table content MUST degrade to readable inline Markdown plus an unknown-content note when necessary.

## Media and Cards

Media nodes MUST render as placeholders that identify available media id, collection, alt text, file name, or type. The renderer MUST NOT attempt to download media directly.

Inline cards MUST render as links when a URL is available and as explicit placeholders otherwise.

## Dates and Mentions

Date nodes MUST render deterministic human-readable text using the timestamp/date attributes available in ADF. Mentions MUST render display text when present and include the account id only when useful and non-secret.

## Validation

Unit tests MUST cover the required supported nodes and marks, unknown node preservation, Markdown escaping, nested lists, tables, and comments/descriptions representative of Jira Cloud ADF.

## Exclusions

- Perfect visual parity with Jira is not required.
- The renderer MUST NOT mutate raw ADF.
