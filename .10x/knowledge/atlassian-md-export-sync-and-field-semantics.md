Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Atlassian Markdown Export Sync And Field Semantics

## Sync Runs Versus Cleanup Authority

For Jira exports, the state model separates latest successful scope sync from representative cleanup authority.

- Incremental pull decisions SHOULD advance from the latest successful run for the same command/scope.
- `clean --remove-missing` MUST only trust a successful full representative project/JQL pull.
- Incremental pulls, exact issue pulls, comment refreshes, attachment refreshes, and partial-failure runs MUST NOT replace the representative issue key set used for deletion.
- A full project/JQL pull that returns zero issues is still representative and may record an empty representative key set.
- Jira HTTP 200 payloads are not trusted by status code alone. Malformed search/comment payloads must fail the run, so they cannot become either a sync cursor or cleanup authority.

This keeps default incremental sync efficient while preventing `clean --remove-missing` from deleting local issues merely because an incremental query did not return unchanged issues.

## Custom Field Mapping

The public config shape maps friendly labels to Jira field IDs:

```yaml
custom_fields:
  story_points: customfield_10016
```

The writer normalization path expects the inverse internal shape, `field_id -> display label`. The CLI/orchestration boundary owns that conversion. Tests should cover the public config shape, not only the writer-internal shape.

## Deterministic Local Indexes

Local Markdown indexes should not use wall-clock time when identical Jira input should produce identical output. `stale.md` uses the latest issue `updated` timestamp in the local export as its default reference time. Tests may inject a clock explicitly, but production index generation should remain input-deterministic.
