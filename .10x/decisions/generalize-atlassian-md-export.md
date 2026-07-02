Status: active
Created: 2026-07-01
Updated: 2026-07-01

# Generalize Markdown Exporter As Atlassian Project

## Context

The requested deliverable is a production-quality Jira Cloud exporter named `jira-md-export` that writes deterministic Markdown and raw JSON for AI-agent ingestion. The user also expects a future Confluence exporter and explicitly approved generalizing the project immediately.

The workspace root is a parent directory containing many repositories and no root Git repository. No existing `jira-md-export`, `atlassian-md-export`, or `*md-export*` directory was found under `/Users/alexanderbut/code_projects/work`.

## Decision

Create a new top-level repository directory named `atlassian-md-export`.

The Python distribution and import package SHOULD be generalized:

- Distribution/repository: `atlassian-md-export`
- Python package: `atlassian_md_export`
- Jira provider modules: `atlassian_md_export/jira/`
- Shared infrastructure modules: renderer, writer, state, logging, config, indexing, and attachments where provider-neutral

The first shipped command MUST include `jira-md-export` and MUST implement Jira Cloud export behavior only. Confluence commands and Confluence API behavior are out of scope for the first implementation unless a later ticket/spec adds them.

The implementation MUST avoid speculative framework layers beyond this named generalization. A thin provider boundary is enough: common deterministic Markdown writing, atomic file operations, state storage, logging, and ADF rendering can be shared; Jira-specific search, comments, fields, and issue normalization stay in Jira modules.

## Alternatives Considered

- Jira-only repository and package named `jira-md-export`.
  - Rejected because the user explicitly approved generalizing now due to expected Confluence overlap.
- Fully generic Atlassian exporter with both Jira and Confluence commands in the first version.
  - Rejected because Confluence behavior, API contracts, output schema, and cleanup semantics are not specified or ratified. Building it now would invent product behavior.
- Put the tool inside an existing repository.
  - Rejected because inspection found no existing owner for this exact tool, and the workspace root already functions as a multi-repo parent.

## Consequences

- Future Confluence work can reuse package layout, config/loading, atomic writer, structured logging, and state conventions without renaming the repository.
- The public Jira command remains `jira-md-export`, satisfying the Jira-first deliverable.
- Package naming must be kept legible in docs so users understand why a Jira command lives in an Atlassian-named project.
- Confluence behavior remains blocked until a focused Confluence specification and ticket exist.
