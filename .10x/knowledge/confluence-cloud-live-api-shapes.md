Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Confluence Cloud Live API Shapes

## Summary

Confluence Cloud REST API v2 page payloads and related summary endpoints can be less redundant than Jira payloads. Do not assume every related object carries title, space key, or web path fields.

## Observed Shapes

Live page `4185325571` on `floqast.atlassian.net` showed:

- `/wiki/api/v2/pages/{id}` returned `spaceId` but no top-level raw `spaceKey`.
- `/wiki/api/v2/pages/{id}` returned `_links.base` as `https://floqast.atlassian.net/wiki`.
- The same page returned `_links.webui` as `/spaces/DP/pages/...`, so normal `urljoin("https://host/wiki", "/spaces/...")` drops `/wiki` unless handled deliberately.
- `/wiki/api/v2/pages/{id}/ancestors` returned objects with only `id` and `type`; one ancestor had `type: folder`.

## Exporter Implications

- Preserve raw page JSON exactly; store resolved fields separately as normalized export metadata.
- Resolve a missing page `spaceKey` from `spaceId` using `/wiki/api/v2/spaces/{spaceId}`.
- Treat ancestor and descendant summaries as summaries. Require stable identifiers, not titles.
- Preserve Confluence web context paths such as `/wiki` when composing page URLs.
- Local refresh commands should reuse saved normalized metadata when raw payloads are incomplete.
