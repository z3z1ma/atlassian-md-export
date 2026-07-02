Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Confluence Cloud Export API Facts

## Question

Which current official Confluence Cloud APIs should govern a deterministic Markdown exporter that mirrors the Jira exporter architecture while preserving raw source data?

## Sources And Methods

Inspected current official Atlassian documentation on 2026-07-01:

- Confluence Cloud REST API v2 reference: https://developer.atlassian.com/cloud/confluence/rest/v2/
- Page API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/
- Attachment API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-attachment/
- Comment API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comment/
- Ancestors API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-ancestors/
- Descendants API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-descendants/
- Children API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-children/
- Label API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-label/
- Space API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-space/
- Search API: https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-search/
- CQL guide: https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/
- CQL fields: https://developer.atlassian.com/cloud/confluence/cql-fields/

## Findings

Confluence REST API v2 is the current primary API surface for structured page export. It exposes separate groups for pages, spaces, labels, comments, attachments, ancestors, descendants, and children.

The Page API v2 supports `GET /wiki/api/v2/spaces/{id}/pages` for all pages in a space and `GET /wiki/api/v2/pages/{id}` for page hydration. Page list/detail endpoints are cursor-paginated through the HTTP `Link` header. Page responses include stable fields such as `id`, `status`, `title`, `spaceId`, `parentId`, `parentType`, `position`, `authorId`, `ownerId`, `createdAt`, `version`, `body`, `_links`, and optional labels/properties/operations.

The Page API v2 accepts a `body-format` query parameter. Current examples show body representations including `storage`, `atlas_doc_format`, `view`, `export_view`, `styled_view`, `anonymous_export_view`, and `editor`. For this exporter, `atlas_doc_format` is the best first-choice representation because the Jira exporter already has an ADF-to-Markdown abstraction. Raw bodies must still be preserved so conversion quality cannot destroy source fidelity.

Arbitrary CQL discovery is still documented on the v1 search/content-search APIs, not as a v2 page endpoint. The current official search group exposes `GET /wiki/rest/api/search`, and the CQL guide still documents CQL through content/search-style REST paths. Therefore, a Confluence exporter that supports arbitrary `--cql` should use official v1 CQL search for discovery and hydrate page details through v2 page APIs.

CQL date literals use Confluence-supported date formats such as `yyyy-MM-dd HH:mm`, `yyyy/MM/dd HH:mm`, `yyyy-MM-dd`, and `yyyy/MM/dd`. The `lastmodified` field supports range filtering. The Jira hardening lesson applies here: incremental CQL must not emit ISO 8601 timestamps with `T`, seconds, fractional seconds, or timezone offsets.

Comment data is not embedded authoritatively in page search results. Confluence v2 exposes separate page comment endpoints for footer comments and inline comments:

- `GET /wiki/api/v2/pages/{id}/footer-comments`
- `GET /wiki/api/v2/pages/{id}/inline-comments`

Both are cursor-paginated through the HTTP `Link` header and accept `body-format`, `status`, `sort`, `cursor`, and `limit` style parameters. Inline comments also expose resolution status filtering. Comment bodies can include `atlas_doc_format` and/or `storage` representations.

Attachment export should use Confluence v2 attachment APIs. Page-specific attachments are available through `GET /wiki/api/v2/pages/{id}/attachments`, paginated through the HTTP `Link` header. Attachment responses include stable metadata such as `id`, `status`, `title`, `createdAt`, `pageId`, `mediaType`, `fileSize`, `webuiLink`, `downloadLink`, `version`, and `_links.download`.

Hierarchy export should prefer descendants and ancestors APIs over the deprecated child pages endpoint. `GET /wiki/api/v2/pages/{id}/ancestors` returns ancestors for a page in top-to-bottom order. `GET /wiki/api/v2/pages/{id}/descendants` returns minimal descendant records and should be followed by page hydration through `GET /wiki/api/v2/pages/{id}`. The v2 child pages endpoint is explicitly deprecated.

Labels should be read from `GET /wiki/api/v2/pages/{id}/labels` when needed for authoritative pagination. Spaces can be resolved through `GET /wiki/api/v2/spaces`, including filtering by key, before calling space page endpoints.

All paginated Confluence v2 endpoints inspected use `Link` header pagination rather than Jira search's `nextPageToken`. The client abstraction must support both pagination styles without conflating them.

## Conclusions

The Confluence implementation should live in the generalized `atlassian-md-export` package beside Jira, with a separate `confluence-md-export` console command.

Use Confluence REST API v2 for authoritative page hydration, comments, attachments, labels, ancestors, descendants, and spaces. Use official v1 CQL search only for arbitrary CQL discovery, then hydrate every discovered page through v2.

Use `atlas_doc_format` as the primary body/comment representation for Markdown conversion because it reuses the Jira ADF renderer. Preserve raw page/comment/attachment/label/hierarchy JSON regardless of conversion success. If a page has only `storage`, preserve it and render an explicit unsupported-body placeholder rather than silently dropping content.

Implement incremental sync with `lastmodified >= "yyyy-MM-dd HH:mm"` CQL clauses and the same 10-minute overlap concept as Jira. Full representative scope and cleanup authority must be tracked separately from exact page repulls, matching the Jira sync-cursor fix.

Avoid deprecated child-page APIs. For hierarchy, use ancestors for breadcrumbs and descendants for subtree discovery.

## Limits

This research did not prove comment reply/thread behavior beyond root footer and inline comment endpoints. That is a remaining scoping choice: either explicitly exclude replies from the first Confluence implementation or inspect and specify reply pagination before implementation.

This research did not test a live Confluence sandbox. Live integration should be a separate opt-in evidence item once implementation exists and `CONFLUENCE_*` or `ATLASSIAN_*` sandbox variables are available.
