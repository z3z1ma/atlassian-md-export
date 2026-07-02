Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Jira Cloud REST API v3 Export Facts

## Question

Which Jira Cloud REST API v3 endpoints and pagination mechanisms govern the Jira Markdown exporter?

## Sources and Methods

- Inspected Atlassian developer documentation for Jira Cloud REST API v3 issue search on 2026-07-01:
  - https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/
- Inspected Atlassian developer documentation for Jira Cloud REST API v3 issue comments on 2026-07-01:
  - https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-comments/
- Inspected Atlassian developer documentation for Jira Cloud REST API v3 issue attachments on 2026-07-01:
  - https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-attachments/

## Findings

- Jira Cloud REST API v3 exposes enhanced issue search at `/rest/api/3/search/jql`.
- The enhanced search endpoint accepts JQL, fields, max results, and `nextPageToken`; response examples include `isLast` and `issues`.
- Legacy `/rest/api/3/search` is present in the docs but marked as being removed. The exporter must not use it for issue discovery.
- Issue comments are fetched from `/rest/api/3/issue/{issueIdOrKey}/comment`.
- Comment pagination uses `startAt` and `maxResults`, with responses including `startAt`, `maxResults`, `total`, and a comments list.
- Attachment content download is exposed at `/rest/api/3/attachment/content/{id}` and may redirect unless redirect handling is controlled by query parameters/client behavior.
- Classic Jira API token usage requires Jira work-read permissions/scopes at the account/API level; unauthenticated or invalid credentials can return 401.

## Conclusions

- Issue discovery for pulls and exact issue-key repulls should use `/rest/api/3/search/jql`, not `/rest/api/3/search`.
- Comments must be fetched independently through the issue comments endpoint and paginated until complete; search-embedded comment fields are not authoritative.
- Attachment metadata can come from issue fields, while binary download should use the attachment content endpoint only when attachment download is explicitly enabled.

## Limits

- Atlassian APIs may change; revalidate this research before changing endpoint behavior or pagination assumptions.
- This research verifies endpoint shape only. It does not define product semantics for exported Markdown, cleanup, or Confluence.
