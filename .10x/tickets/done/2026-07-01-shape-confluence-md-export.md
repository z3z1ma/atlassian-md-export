Status: done
Created: 2026-07-01
Updated: 2026-07-01

# Shape Confluence Markdown Export

## Scope

Scope the Confluence companion exporter for `atlassian-md-export`, reusing shared package foundations where appropriate while defining Confluence-specific behavior before implementation.

## Acceptance Criteria

- Identify Confluence Cloud REST API version and endpoints for content discovery, page retrieval, comments, attachments, ancestors/children, labels, spaces, and incremental sync.
- Decide CLI surface and output layout for the first Confluence exporter.
- Define Markdown/frontmatter schema and section order for Confluence pages.
- Define raw JSON/storage preservation requirements.
- Define incremental sync, cleanup, verify, and index semantics for Confluence.
- Split focused active specs and executable implementation tickets after user ratification.

## Blockers

None. The user ratified the recommended contract on 2026-07-01. Nested comment replies are explicitly excluded from the first implementation unless a later ratified spec supersedes that exclusion.

## Progress and Notes

- 2026-07-01: Ticket opened after completing Jira live CLI export fix. User indicated Confluence export should be scoped next and similar in nature.
- 2026-07-01: Inspected current official Confluence Cloud REST/CQL documentation and recorded `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md`.
- 2026-07-01: Recommended a Jira-parallel Confluence exporter with a separate `confluence-md-export` console command inside the generalized package, REST API v2 page hydration, v1 CQL discovery only where CQL is required, raw-first preservation, Confluence-specific incremental CQL formatting, and Jira-hardened safety rules for cleanup, downloads, payload validation, and verification.
- 2026-07-01: User ratified the recommended contract.
- 2026-07-01: Opened active focused Confluence specs and a parent/child implementation ticket graph.

## Recommended Contract For Ratification

Use these as the proposed first Confluence scope unless corrected:

1. CLI shape: add `confluence-md-export` beside `jira-md-export`, not a subcommand nested under Jira.
2. Discovery scope: support `pull --space KEY --out DIR`, `pull --cql CQL --out DIR`, `pull --ancestor PAGE_ID --out DIR`, and exact `page PAGE_ID [PAGE_ID...] --out DIR`.
3. API strategy: use Confluence REST API v2 for pages, comments, attachments, labels, ancestors, descendants, and spaces; use official v1 CQL search only for arbitrary CQL discovery and hydrate results through v2 page detail endpoints.
4. Body strategy: request `atlas_doc_format` first and render through the existing ADF abstraction; preserve raw body JSON always; if only storage-format content is available, preserve it and emit an explicit unsupported-body placeholder until storage-to-Markdown support is specified.
5. Comment strategy: fetch both footer comments and inline comments oldest-first, with stable headings and inline resolution metadata; exclude nested comment replies from the first implementation unless API inspection proves a simple authoritative pagination path before specs are activated.
6. Output layout: keep raw JSON under the content type, mirroring the Jira raw-directory amendment:

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

7. Markdown shape: deterministic YAML frontmatter plus body sections in this order:

   ```text
   # Title
   ## Page Metadata
   ## Ancestors
   ## Child Pages
   ## Content
   ## Attachments
   ## Labels
   ## Comments
   ## Raw Field Notes
   ```

8. Auth variables: support `CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, with optional generic fallback to `ATLASSIAN_SITE`, `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`. Do not fall back to `JIRA_*` automatically.
9. Incremental sync: use CQL `lastmodified >= "yyyy-MM-dd HH:mm"` with a 10-minute overlap for incremental representative scopes. Track cleanup authority separately from exact page repulls, following the Jira cursor fix.
10. Attachments: default metadata-only; optional downloads must enforce same-origin/relative download safety and max-size/include filters.
11. Verification: validate raw file presence, markdown hash state, attachment local path hash participation when downloads are enabled, representative-scope cleanup state, and strict success-payload schemas.

After ratification, split this into focused active specs before opening executable implementation tickets:

- Confluence CLI/config/auth.
- Confluence API discovery, pagination, hydration, and incremental sync.
- Confluence Markdown/frontmatter/raw output.
- Confluence comments/attachments/index/clean/verify behavior.

## Explicit Exclusions

- Do not implement Confluence API calls before the focused specs are ratified.
- Do not assume Jira issue semantics apply directly to Confluence page hierarchy, comments, or attachments.

## References

- `.10x/decisions/generalize-atlassian-md-export.md`
- `.10x/specs/atlassian-md-export-cli-config.md`
- `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md`
- `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md`
- `.10x/specs/confluence-cli-config.md`
- `.10x/specs/confluence-export-api-sync.md`
- `.10x/specs/confluence-page-markdown-output.md`
- `.10x/specs/confluence-attachments-index-clean-verify.md`
- `.10x/tickets/done/2026-07-01-build-confluence-md-export.md`

## Evidence Expectations

- Research record with current official Confluence Cloud API facts.
- Ratified focused specs before implementation tickets.

## Evidence

- `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md`
- `.10x/evidence/2026-07-01-confluence-scoping-ratification.md`
- `.10x/specs/confluence-cli-config.md`
- `.10x/specs/confluence-export-api-sync.md`
- `.10x/specs/confluence-page-markdown-output.md`
- `.10x/specs/confluence-attachments-index-clean-verify.md`
- `.10x/tickets/done/2026-07-01-build-confluence-md-export.md`

## Closure Review

- Confluence Cloud API version and endpoint choices are captured in `.10x/research/2026-07-01-confluence-cloud-export-api-facts.md` and `.10x/specs/confluence-export-api-sync.md`.
- CLI surface and output layout are captured in `.10x/specs/confluence-cli-config.md` and `.10x/specs/confluence-page-markdown-output.md`.
- Markdown frontmatter, raw JSON preservation, section order, and deterministic output rules are captured in `.10x/specs/confluence-page-markdown-output.md`.
- Incremental sync, cleanup, verify, and index semantics are captured in `.10x/specs/confluence-export-api-sync.md` and `.10x/specs/confluence-attachments-index-clean-verify.md`.
- Focused active specs and executable implementation tickets were opened after user ratification.
- No implementation was performed as part of shaping.

## Retrospective

- Confluence should reuse the Atlassian package boundary and ADF renderer, but the API and sync semantics are not Jira clones: v2 resource APIs use `Link` pagination, while arbitrary CQL discovery remains on the documented v1 search surface.
- Explicitly excluding nested comment replies prevents a quiet scope leak while still preserving a clear supersession path if comment-thread export becomes important.
