"""Local filesystem writer helpers for export output."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
import unicodedata
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.parse import quote
import uuid

import yaml

from atlassian_md_export import __version__
from atlassian_md_export.models import ConfluencePageWriteResult
from atlassian_md_export.models import GeneratorInfo
from atlassian_md_export.models import InitResult
from atlassian_md_export.models import IssueWriteResult
from atlassian_md_export.models import Manifest
from atlassian_md_export.models import NormalizedConfluenceAttachment
from atlassian_md_export.models import NormalizedConfluenceComment
from atlassian_md_export.models import NormalizedConfluenceLabel
from atlassian_md_export.models import NormalizedConfluencePage
from atlassian_md_export.models import NormalizedConfluencePageReference
from atlassian_md_export.models import NormalizedCustomField
from atlassian_md_export.models import NormalizedJiraAttachment
from atlassian_md_export.models import NormalizedJiraComment
from atlassian_md_export.models import NormalizedJiraIssue
from atlassian_md_export.models import NormalizedJiraIssueLink
from atlassian_md_export.models import NormalizedJiraSubtask
from atlassian_md_export.models import OutputMetadata
from atlassian_md_export.renderer import AdfMarkdownRenderer
from atlassian_md_export.renderer import escape_markdown_text
from atlassian_md_export.state import initialize_state

ISSUES_DIR = "issues"
RAW_ISSUES_DIR = "_raw"
OUTPUT_DIRECTORIES = (ISSUES_DIR, f"{ISSUES_DIR}/{RAW_ISSUES_DIR}", "attachments", "indexes")
ISSUE_MARKDOWN_SCHEMA_VERSION = 1
PAGES_DIR = "pages"
RAW_PAGES_DIR = "_raw"
CONFLUENCE_PAGE_MARKDOWN_SCHEMA_VERSION = 1
STABLE_EXPORTED_AT = "1970-01-01T00:00:00Z"
FRONTMATTER_FIELDS = (
    "schema_version",
    "source",
    "key",
    "id",
    "url",
    "project",
    "issue_type",
    "status",
    "priority",
    "assignee",
    "reporter",
    "created",
    "updated",
    "resolution",
    "resolutiondate",
    "labels",
    "components",
    "fix_versions",
    "versions",
    "parent",
    "epic",
    "comment_count",
    "attachment_count",
    "exported_at",
    "content_hash",
)
CONFLUENCE_PAGE_FRONTMATTER_FIELDS = (
    "schema_version",
    "source",
    "id",
    "url",
    "title",
    "space_key",
    "space_id",
    "status",
    "parent",
    "ancestors",
    "version",
    "author",
    "owner",
    "created",
    "updated",
    "labels",
    "child_count",
    "comment_count",
    "footer_comment_count",
    "inline_comment_count",
    "attachment_count",
    "exported_at",
    "content_hash",
)
_RENDERED_FIELD_IDS = {
    "summary",
    "description",
    "project",
    "issuetype",
    "status",
    "priority",
    "assignee",
    "reporter",
    "created",
    "updated",
    "resolution",
    "resolutiondate",
    "labels",
    "components",
    "fixVersions",
    "versions",
    "parent",
    "issuelinks",
    "subtasks",
    "attachment",
    "comment",
}
_CONFLUENCE_RENDERED_RAW_FIELDS = {
    "_links",
    "ancestors",
    "author",
    "authorId",
    "body",
    "createdAt",
    "createdBy",
    "id",
    "owner",
    "ownerId",
    "parent",
    "parentId",
    "space",
    "spaceId",
    "spaceKey",
    "status",
    "title",
    "updatedAt",
    "version",
}
_SAFE_SEGMENT_INVALID_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")
_SAFE_SEGMENT_DASHES = re.compile(r"-{2,}")
_WINDOWS_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_MAX_PAGE_SEGMENT_CHARS = 180


def initialize_output(out_dir: Path) -> InitResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_out = out_dir.resolve()

    directories = [resolved_out / name for name in OUTPUT_DIRECTORIES]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_raw_issue_files(resolved_out)

    state_path = resolved_out / "state.sqlite"
    initialize_state(state_path)

    manifest_path = resolved_out / "manifest.json"
    manifest_created = False
    if not manifest_path.exists():
        manifest = Manifest(
            generator=GeneratorInfo(name="atlassian-md-export", version=__version__),
            output=OutputMetadata(path=str(resolved_out)),
        )
        atomic_write_text(manifest_path, manifest_json(manifest))
        manifest_created = True

    return InitResult(
        out_dir=resolved_out,
        directories=directories,
        manifest_path=manifest_path,
        state_path=state_path,
        manifest_created=manifest_created,
    )


def manifest_json(manifest: Manifest) -> str:
    payload = manifest.model_dump(mode="json")
    return canonical_json(payload)


def issue_markdown_path(out_dir: Path, key: str) -> Path:
    return out_dir / ISSUES_DIR / f"{key}.md"


def issue_raw_dir(out_dir: Path) -> Path:
    return out_dir / ISSUES_DIR / RAW_ISSUES_DIR


def issue_raw_path(out_dir: Path, key: str) -> Path:
    return issue_raw_dir(out_dir) / f"{key}.json"


def confluence_page_markdown_path(out_dir: Path, page: NormalizedConfluencePage) -> Path:
    return out_dir / _confluence_page_markdown_relative_path(page)


def confluence_page_raw_dir(out_dir: Path) -> Path:
    return out_dir / PAGES_DIR / RAW_PAGES_DIR


def confluence_page_raw_path(out_dir: Path, page_id: str) -> Path:
    safe_id = safe_confluence_path_segment(page_id, fallback="page")
    return confluence_page_raw_dir(out_dir) / f"{safe_id}.json"


def safe_confluence_path_segment(value: str | None, *, fallback: str = "untitled") -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join("-" if character.isspace() else character for character in ascii_value)
    cleaned = _SAFE_SEGMENT_INVALID_CHARS.sub("-", cleaned)
    cleaned = _SAFE_SEGMENT_DASHES.sub("-", cleaned).strip(" .-_")
    cleaned = cleaned.lstrip(".").strip(" .-_")
    if cleaned in {"", ".", ".."}:
        cleaned = fallback

    stem = cleaned.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED_BASENAMES:
        cleaned = f"_{cleaned}"

    if len(cleaned) <= _MAX_PAGE_SEGMENT_CHARS:
        return cleaned

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    suffix = Path(cleaned).suffix
    suffix_budget = min(len(suffix), 24)
    suffix = suffix[-suffix_budget:] if suffix_budget else ""
    prefix_budget = _MAX_PAGE_SEGMENT_CHARS - len(digest) - len(suffix) - 1
    return f"{cleaned[:prefix_budget].rstrip(' .-_')}-{digest}{suffix}"


def _migrate_legacy_raw_issue_files(out_dir: Path) -> None:
    legacy_issue_dir = out_dir / ISSUES_DIR
    raw_dir = issue_raw_dir(out_dir)
    for legacy_path in sorted(legacy_issue_dir.glob("*.json")):
        target = raw_dir / legacy_path.name
        if target.exists():
            continue
        os.replace(legacy_path, target)


def normalize_jira_issue(
    raw_issue: Mapping[str, Any],
    *,
    comments: Sequence[Mapping[str, Any]] = (),
    site_url: str | None = None,
    custom_fields: Mapping[str, str] | None = None,
) -> NormalizedJiraIssue:
    raw = _json_object(raw_issue)
    fields = _mapping(raw.get("fields"))
    key = _required_string(raw.get("key"), "Jira issue key")
    issue_id = _required_string(raw.get("id"), "Jira issue id")
    site_base = _site_base(site_url, raw)
    site_host = _site_host(site_base)
    normalized_custom_fields = _normalize_custom_fields(fields, custom_fields or {})

    return NormalizedJiraIssue(
        key=key,
        id=issue_id,
        source=f"jira-cloud:{site_host}" if site_host else "jira-cloud",
        site_host=site_host,
        url=f"{site_base}/browse/{key}" if site_base else None,
        project=_display_value(fields.get("project"), preferred_keys=("key", "name")),
        summary=_optional_string(fields.get("summary")) or "",
        issue_type=_display_value(fields.get("issuetype")),
        status=_display_value(fields.get("status")),
        priority=_display_value(fields.get("priority")),
        assignee=_display_value(fields.get("assignee")),
        reporter=_display_value(fields.get("reporter")),
        created=_optional_string(fields.get("created")),
        updated=_optional_string(fields.get("updated")),
        resolution=_display_value(fields.get("resolution")),
        resolutiondate=_optional_string(fields.get("resolutiondate")),
        labels=_sorted_display_list(fields.get("labels")),
        components=_sorted_display_list(fields.get("components")),
        fix_versions=_sorted_display_list(fields.get("fixVersions")),
        versions=_sorted_display_list(fields.get("versions")),
        parent=_parent_key(fields.get("parent")),
        epic=_epic_value(fields, normalized_custom_fields),
        description_adf=_optional_mapping(fields.get("description")),
        comments=_sorted_comments(comments),
        attachments=_normalize_attachments(fields.get("attachment")),
        links=_normalize_issue_links(fields.get("issuelinks"), site_base),
        subtasks=_normalize_subtasks(fields.get("subtasks")),
        custom_fields=normalized_custom_fields,
        raw_issue=raw,
    )


def normalize_confluence_page(
    raw_page: Mapping[str, Any],
    *,
    footer_comments: Sequence[Mapping[str, Any]] = (),
    inline_comments: Sequence[Mapping[str, Any]] = (),
    attachments: Sequence[Mapping[str, Any]] = (),
    labels: Sequence[Mapping[str, Any]] = (),
    ancestors: Sequence[Mapping[str, Any]] = (),
    child_pages: Sequence[Mapping[str, Any]] = (),
    site_url: str | None = None,
    space_key: str | None = None,
    url: str | None = None,
) -> NormalizedConfluencePage:
    raw = _json_object(raw_page)
    page_id = _required_string(raw.get("id"), "Confluence page id")
    site_base = _confluence_site_base(site_url, raw, fallback_url=url)
    site_host = _site_host(site_base)
    normalized_space_key = _confluence_space_key(raw) or space_key
    normalized_ancestors = _normalize_confluence_page_refs(
        ancestors,
        site_base=site_base,
        fallback_space_key=normalized_space_key,
    )
    parent = _confluence_parent(
        raw,
        normalized_ancestors,
        site_base,
        fallback_space_key=normalized_space_key,
    )
    body_adf, body_representation = _confluence_body_adf(raw.get("body"))

    return NormalizedConfluencePage(
        id=page_id,
        source=f"confluence-cloud:{site_host}" if site_host else "confluence-cloud",
        site_host=site_host,
        url=_confluence_web_url(site_base, raw) or url,
        title=_optional_string(raw.get("title")) or "",
        space_key=normalized_space_key,
        space_id=_confluence_space_id(raw),
        status=_optional_string(raw.get("status")),
        parent=parent,
        ancestors=normalized_ancestors,
        version=_confluence_version(raw.get("version")),
        author=_confluence_actor(raw.get("author"))
        or _confluence_actor(raw.get("createdBy"))
        or _optional_string(raw.get("authorId")),
        owner=_confluence_actor(raw.get("owner")) or _optional_string(raw.get("ownerId")),
        created=_optional_string(raw.get("createdAt")),
        updated=_confluence_updated(raw),
        labels=_normalize_confluence_labels(labels),
        child_pages=_normalize_confluence_page_refs(
            child_pages,
            site_base=site_base,
            pages_only=True,
            fallback_space_key=normalized_space_key,
        ),
        footer_comments=_sorted_confluence_comments(footer_comments),
        inline_comments=_sorted_confluence_comments(inline_comments),
        attachments=_normalize_confluence_attachments(attachments),
        body_adf=body_adf,
        body_representation=body_representation,
        raw_page=raw,
    )


def render_issue_markdown(
    issue: NormalizedJiraIssue,
    *,
    renderer: AdfMarkdownRenderer | None = None,
    stable_exported_at: bool = False,
    exported_at: str | None = None,
) -> str:
    active_renderer = renderer or AdfMarkdownRenderer()
    resolved_exported_at = _exported_at(stable=stable_exported_at, exported_at=exported_at)
    content_hash = issue_content_hash(issue, renderer=active_renderer)
    frontmatter = _frontmatter_yaml(
        _frontmatter_payload(
            issue,
            exported_at=resolved_exported_at,
            content_hash=content_hash,
        )
    )
    body = _issue_body(issue, active_renderer).rstrip()
    return f"---\n{frontmatter}---\n\n{body}\n"


def issue_content_hash(
    issue: NormalizedJiraIssue,
    *,
    renderer: AdfMarkdownRenderer | None = None,
) -> str:
    active_renderer = renderer or AdfMarkdownRenderer()
    payload = {
        "schema_version": ISSUE_MARKDOWN_SCHEMA_VERSION,
        "source": issue.source,
        "site_host": issue.site_host,
        "url": issue.url,
        "raw_issue": issue.raw_issue,
        "fetched_comments": [comment.raw for comment in issue.comments],
        "rendered_attachments": [
            _attachment_hash_metadata(attachment) for attachment in issue.attachments
        ],
        "custom_fields": [field.model_dump(mode="json") for field in issue.custom_fields],
        "renderer": {
            "include_raw_adf_on_unknown_nodes": (active_renderer.include_raw_adf_on_unknown_nodes),
        },
    }
    return _sha256_text(canonical_json(payload))


def issue_raw_export_json(
    issue: NormalizedJiraIssue,
    *,
    stable_exported_at: bool = False,
    exported_at: str | None = None,
) -> str:
    del stable_exported_at
    resolved_exported_at = _exported_at(stable=False, exported_at=exported_at)
    payload = {
        "schema_version": ISSUE_MARKDOWN_SCHEMA_VERSION,
        "exporter": {
            "name": "atlassian-md-export",
            "version": __version__,
            "source": issue.source,
            "site_host": issue.site_host,
            "exported_at": resolved_exported_at,
        },
        "raw_issue": issue.raw_issue,
        "fetched_comments": [comment.raw for comment in issue.comments],
        "raw_adf": {
            "description": issue.description_adf,
            "comments": [
                {"id": comment.id, "body": comment.body_adf} for comment in issue.comments
            ],
        },
        "attachment_metadata": [
            attachment.model_dump(mode="json") for attachment in issue.attachments
        ],
    }
    return canonical_json(payload)


def write_issue_files(
    out_dir: Path,
    issue: NormalizedJiraIssue,
    *,
    renderer: AdfMarkdownRenderer | None = None,
    stable_exported_at: bool = False,
    exported_at: str | None = None,
) -> IssueWriteResult:
    resolved_exported_at = _exported_at(stable=False, exported_at=exported_at)
    markdown = render_issue_markdown(
        issue,
        renderer=renderer,
        stable_exported_at=stable_exported_at,
        exported_at=resolved_exported_at,
    )
    raw_json = issue_raw_export_json(
        issue,
        stable_exported_at=stable_exported_at,
        exported_at=resolved_exported_at,
    )

    markdown_path = issue_markdown_path(out_dir, issue.key)
    json_path = issue_raw_path(out_dir, issue.key)
    atomic_write_text(markdown_path, markdown)
    atomic_write_text(json_path, raw_json)

    return IssueWriteResult(
        markdown_path=markdown_path,
        json_path=json_path,
        content_hash=issue_content_hash(issue, renderer=renderer),
        markdown_hash=_sha256_text(markdown),
        raw_json_hash=_sha256_text(raw_json),
        exported_at=resolved_exported_at,
    )


def render_confluence_page_markdown(
    page: NormalizedConfluencePage,
    *,
    renderer: AdfMarkdownRenderer | None = None,
    stable_exported_at: bool = False,
    exported_at: str | None = None,
    exported_pages: Sequence[NormalizedConfluencePage] = (),
) -> str:
    active_renderer = renderer or AdfMarkdownRenderer()
    resolved_exported_at = _exported_at(stable=stable_exported_at, exported_at=exported_at)
    content_hash = confluence_page_content_hash(
        page,
        renderer=active_renderer,
        exported_pages=exported_pages,
    )
    frontmatter = _frontmatter_yaml(
        _confluence_frontmatter_payload(
            page,
            exported_at=resolved_exported_at,
            content_hash=content_hash,
        )
    )
    body = _confluence_page_body(page, active_renderer, exported_pages).rstrip()
    return f"---\n{frontmatter}---\n\n{body}\n"


def confluence_page_content_hash(
    page: NormalizedConfluencePage,
    *,
    renderer: AdfMarkdownRenderer | None = None,
    exported_pages: Sequence[NormalizedConfluencePage] = (),
) -> str:
    active_renderer = renderer or AdfMarkdownRenderer()
    payload = {
        "schema_version": CONFLUENCE_PAGE_MARKDOWN_SCHEMA_VERSION,
        "source": page.source,
        "site_host": page.site_host,
        "url": page.url,
        "raw_page": page.raw_page,
        "normalized_page": {
            "space_key": page.space_key,
            "space_id": page.space_id,
            "url": page.url,
        },
        "fetched_footer_comments": [comment.raw for comment in page.footer_comments],
        "fetched_inline_comments": [comment.raw for comment in page.inline_comments],
        "labels": [label.raw for label in page.labels],
        "ancestors": [ancestor.raw for ancestor in page.ancestors],
        "child_page_references": [child.raw for child in page.child_pages],
        "attachment_metadata": [
            _attachment_hash_metadata(attachment) for attachment in page.attachments
        ],
        "exported_page_links": _confluence_exported_page_hash_inputs(exported_pages),
        "renderer": {
            "include_raw_adf_on_unknown_nodes": (active_renderer.include_raw_adf_on_unknown_nodes),
        },
    }
    return _sha256_text(canonical_json(payload))


def confluence_page_raw_export_json(
    page: NormalizedConfluencePage,
    *,
    stable_exported_at: bool = False,
    exported_at: str | None = None,
) -> str:
    del stable_exported_at
    resolved_exported_at = _exported_at(stable=False, exported_at=exported_at)
    payload = {
        "schema_version": CONFLUENCE_PAGE_MARKDOWN_SCHEMA_VERSION,
        "exporter": {
            "name": "atlassian-md-export",
            "version": __version__,
            "source": page.source,
            "site_host": page.site_host,
            "exported_at": resolved_exported_at,
        },
        "raw_page": page.raw_page,
        "normalized_page": {
            "space_key": page.space_key,
            "space_id": page.space_id,
            "url": page.url,
        },
        "fetched_footer_comments": [comment.raw for comment in page.footer_comments],
        "fetched_inline_comments": [comment.raw for comment in page.inline_comments],
        "raw_adf": {
            "page": page.body_adf,
            "footer_comments": [
                {"id": comment.id, "body": comment.body_adf} for comment in page.footer_comments
            ],
            "inline_comments": [
                {"id": comment.id, "body": comment.body_adf} for comment in page.inline_comments
            ],
        },
        "attachment_metadata": [
            attachment.model_dump(mode="json") for attachment in page.attachments
        ],
        "labels": [label.raw for label in page.labels],
        "ancestors": [ancestor.raw for ancestor in page.ancestors],
        "child_page_references": [child.raw for child in page.child_pages],
    }
    return canonical_json(payload)


def write_confluence_page_files(
    out_dir: Path,
    page: NormalizedConfluencePage,
    *,
    renderer: AdfMarkdownRenderer | None = None,
    stable_exported_at: bool = False,
    exported_at: str | None = None,
    exported_pages: Sequence[NormalizedConfluencePage] = (),
) -> ConfluencePageWriteResult:
    resolved_exported_at = _exported_at(stable=False, exported_at=exported_at)
    markdown = render_confluence_page_markdown(
        page,
        renderer=renderer,
        stable_exported_at=stable_exported_at,
        exported_at=resolved_exported_at,
        exported_pages=exported_pages,
    )
    raw_json = confluence_page_raw_export_json(
        page,
        stable_exported_at=stable_exported_at,
        exported_at=resolved_exported_at,
    )

    markdown_path = confluence_page_markdown_path(out_dir, page)
    json_path = confluence_page_raw_path(out_dir, page.id)
    atomic_write_text(markdown_path, markdown)
    atomic_write_text(json_path, raw_json)

    return ConfluencePageWriteResult(
        markdown_path=markdown_path,
        json_path=json_path,
        content_hash=confluence_page_content_hash(
            page,
            renderer=renderer,
            exported_pages=exported_pages,
        ),
        markdown_hash=_sha256_text(markdown),
        raw_json_hash=_sha256_text(raw_json),
        exported_at=resolved_exported_at,
    )


def canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, canonical_json(payload))


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_bytes(content)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _frontmatter_payload(
    issue: NormalizedJiraIssue,
    *,
    exported_at: str,
    content_hash: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": ISSUE_MARKDOWN_SCHEMA_VERSION,
        "source": issue.source,
        "key": issue.key,
        "id": issue.id,
        "url": issue.url,
        "project": issue.project,
        "issue_type": issue.issue_type,
        "status": issue.status,
        "priority": issue.priority,
        "assignee": issue.assignee,
        "reporter": issue.reporter,
        "created": issue.created,
        "updated": issue.updated,
        "resolution": issue.resolution,
        "resolutiondate": issue.resolutiondate,
        "labels": issue.labels,
        "components": issue.components,
        "fix_versions": issue.fix_versions,
        "versions": issue.versions,
        "parent": issue.parent,
        "epic": issue.epic,
        "comment_count": len(issue.comments),
        "attachment_count": len(issue.attachments),
        "exported_at": exported_at,
        "content_hash": content_hash,
    }
    if tuple(payload) != FRONTMATTER_FIELDS:
        raise RuntimeError("Jira Markdown frontmatter field order drifted.")
    return payload


def _confluence_frontmatter_payload(
    page: NormalizedConfluencePage,
    *,
    exported_at: str,
    content_hash: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": CONFLUENCE_PAGE_MARKDOWN_SCHEMA_VERSION,
        "source": page.source,
        "id": page.id,
        "url": page.url,
        "title": page.title,
        "space_key": page.space_key,
        "space_id": page.space_id,
        "status": page.status,
        "parent": _confluence_reference_payload(page.parent),
        "ancestors": [_confluence_reference_payload(ancestor) for ancestor in page.ancestors],
        "version": page.version,
        "author": page.author,
        "owner": page.owner,
        "created": page.created,
        "updated": page.updated,
        "labels": [_confluence_label_text(label) for label in page.labels],
        "child_count": len(page.child_pages),
        "comment_count": len(page.footer_comments) + len(page.inline_comments),
        "footer_comment_count": len(page.footer_comments),
        "inline_comment_count": len(page.inline_comments),
        "attachment_count": len(page.attachments),
        "exported_at": exported_at,
        "content_hash": content_hash,
    }
    if tuple(payload) != CONFLUENCE_PAGE_FRONTMATTER_FIELDS:
        raise RuntimeError("Confluence page Markdown frontmatter field order drifted.")
    return payload


def _frontmatter_yaml(payload: Mapping[str, object]) -> str:
    return yaml.safe_dump(
        dict(payload),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def _confluence_page_body(
    page: NormalizedConfluencePage,
    renderer: AdfMarkdownRenderer,
    exported_pages: Sequence[NormalizedConfluencePage],
) -> str:
    title = escape_markdown_text(page.title)
    parts = [
        f"# {title}",
        "## Page Metadata",
        _confluence_page_metadata(page, exported_pages),
        "## Ancestors",
        _confluence_ancestors(page, exported_pages),
        "## Child Pages",
        _confluence_child_pages(page, exported_pages),
        "## Content",
        _confluence_content(page, renderer),
        "## Attachments",
        _confluence_attachments(page),
        "## Labels",
        _confluence_labels(page),
        "## Comments",
        _confluence_comments(page, renderer),
        "## Raw Field Notes",
        _confluence_raw_field_notes(page),
    ]
    return "\n\n".join(parts)


def _confluence_page_metadata(
    page: NormalizedConfluencePage,
    exported_pages: Sequence[NormalizedConfluencePage],
) -> str:
    fields: list[tuple[str, object]] = [
        ("Space", _compact_join([page.space_key, page.space_id], separator=" / ")),
        ("Page ID", page.id),
        ("Status", page.status),
        ("Parent", _confluence_reference_value(page, page.parent, exported_pages)),
        ("Author", page.author),
        ("Owner", page.owner),
        ("Created", page.created),
        ("Updated", page.updated),
        ("Version", page.version),
        ("Labels", [_confluence_label_text(label) for label in page.labels]),
        (
            "Comments",
            (
                f"{len(page.footer_comments) + len(page.inline_comments)} total "
                f"({len(page.footer_comments)} footer, {len(page.inline_comments)} inline)"
            ),
        ),
        ("Attachments", len(page.attachments)),
    ]
    lines = []
    for label, value in fields:
        rendered = str(value) if label == "Parent" else _markdown_value(value)
        lines.append(f"- {label}: {rendered}")
    return "\n".join(lines)


def _confluence_ancestors(
    page: NormalizedConfluencePage,
    exported_pages: Sequence[NormalizedConfluencePage],
) -> str:
    if not page.ancestors:
        return "_No ancestors._"
    lines = []
    for ancestor in page.ancestors:
        label = _confluence_reference_value(page, ancestor, exported_pages)
        lines.append(f"- {label} (id={escape_markdown_text(ancestor.id)})")
    return "\n".join(lines)


def _confluence_child_pages(
    page: NormalizedConfluencePage,
    exported_pages: Sequence[NormalizedConfluencePage],
) -> str:
    if not page.child_pages:
        return "_No child pages._"
    lines = []
    for child in sorted(page.child_pages, key=_confluence_reference_sort_key):
        label = _confluence_reference_value(page, child, exported_pages)
        lines.append(f"- {label} (id={escape_markdown_text(child.id)})")
    return "\n".join(lines)


def _confluence_content(
    page: NormalizedConfluencePage,
    renderer: AdfMarkdownRenderer,
) -> str:
    if page.body_adf is None:
        return _unsupported_body_placeholder("page", page.id, page.body_representation)
    rendered = renderer.render(page.body_adf)
    return rendered or "_No page content._"


def _confluence_attachments(page: NormalizedConfluencePage) -> str:
    if not page.attachments:
        return "_No attachments._"
    return "\n".join(
        _attachment_line(
            filename=attachment.filename,
            attachment_id=attachment.id,
            mime_type=attachment.mime_type,
            size=attachment.size,
            created=attachment.created,
            author_display_name=attachment.author_display_name,
            local_path=attachment.local_path,
        )
        for attachment in page.attachments
    )


def _confluence_labels(page: NormalizedConfluencePage) -> str:
    if not page.labels:
        return "_No labels._"
    lines = []
    for label in page.labels:
        suffix = f" (id={escape_markdown_text(label.id)})" if label.id else ""
        lines.append(f"- {escape_markdown_text(_confluence_label_text(label))}{suffix}")
    return "\n".join(lines)


def _confluence_comments(page: NormalizedConfluencePage, renderer: AdfMarkdownRenderer) -> str:
    footer = _render_confluence_comment_group(
        "Footer",
        page.id,
        page.footer_comments,
        renderer,
    )
    inline = _render_confluence_comment_group(
        "Inline",
        page.id,
        page.inline_comments,
        renderer,
    )
    rendered = [section for section in (footer, inline) if section]
    return "\n\n".join(rendered) if rendered else "_No comments._"


def _render_confluence_comment_group(
    comment_type: str,
    page_id: str,
    comments: Sequence[NormalizedConfluenceComment],
    renderer: AdfMarkdownRenderer,
) -> str:
    rendered_comments: list[str] = []
    for index, comment in enumerate(comments, start=1):
        author = comment.author_display_name or "Unknown Author"
        created = comment.created or "Unknown Created Timestamp"
        lines = [
            f"### {comment_type} Comment {index} - {escape_markdown_text(author)} - "
            f"{escape_markdown_text(created)}",
            "",
            f"- Comment ID: {_markdown_value(comment.id)}",
        ]
        if comment.updated and comment.updated != comment.created:
            lines.append(f"- Updated: {escape_markdown_text(comment.updated)}")
        if comment.status:
            lines.append(f"- Status: {escape_markdown_text(comment.status)}")
        if comment.resolution_status:
            lines.append(
                f"- Inline Resolution Status: {escape_markdown_text(comment.resolution_status)}"
            )
        if comment.body_adf is None:
            body = _unsupported_body_placeholder("comment", page_id, comment.body_representation)
        else:
            body = renderer.render(comment.body_adf) or "_No comment body._"
        lines.extend(["", body])
        rendered_comments.append("\n".join(lines))
    return "\n\n".join(rendered_comments)


def _confluence_raw_field_notes(page: NormalizedConfluencePage) -> str:
    fields = sorted(set(page.raw_page) - _CONFLUENCE_RENDERED_RAW_FIELDS)
    if not fields:
        return "_No additional raw field notes._"
    return "\n".join(f"- Raw page field preserved but not rendered: `{field}`" for field in fields)


def _issue_body(issue: NormalizedJiraIssue, renderer: AdfMarkdownRenderer) -> str:
    summary = escape_markdown_text(issue.summary)
    parts = [
        f"# {escape_markdown_text(issue.key)}: {summary}",
        "## Summary",
        summary,
        "## Description",
        renderer.render(issue.description_adf) or "_No description._",
        "## Key Fields",
        _key_fields(issue),
        "## Links",
        _links(issue),
        "## Subtasks",
        _subtasks(issue),
        "## Attachments",
        _attachments(issue),
        "## Raw Field Notes",
        _raw_field_notes(issue),
        "## Comments",
        _comments(issue, renderer),
    ]
    return "\n\n".join(parts)


def _key_fields(issue: NormalizedJiraIssue) -> str:
    fields: list[tuple[str, object]] = [
        ("Type", issue.issue_type),
        ("Status", issue.status),
        ("Priority", issue.priority),
        ("Assignee", issue.assignee),
        ("Reporter", issue.reporter),
        ("Created", issue.created),
        ("Updated", issue.updated),
        ("Resolution", issue.resolution),
        ("Resolution Date", issue.resolutiondate),
        ("Labels", issue.labels),
        ("Components", issue.components),
        ("Fix Versions", issue.fix_versions),
        ("Versions", issue.versions),
        ("Parent", issue.parent),
        ("Epic", issue.epic),
    ]
    fields.extend((field.label, field.value) for field in issue.custom_fields)
    return "\n".join(f"- {label}: {_markdown_value(value)}" for label, value in fields)


def _links(issue: NormalizedJiraIssue) -> str:
    if not issue.links:
        return "_No links._"
    lines = []
    for link in issue.links:
        target = _linked_key(link.key, link.url) if link.key else _markdown_value(link.url)
        details = _compact_join([link.summary, link.status], separator=" - ")
        suffix = f" - {escape_markdown_text(details)}" if details else ""
        lines.append(f"- {escape_markdown_text(link.relationship)}: {target}{suffix}")
    return "\n".join(lines)


def _subtasks(issue: NormalizedJiraIssue) -> str:
    if not issue.subtasks:
        return "_No subtasks._"
    lines = []
    for subtask in issue.subtasks:
        details = _compact_join([subtask.summary, subtask.status], separator=" - ")
        suffix = f" - {escape_markdown_text(details)}" if details else ""
        lines.append(f"- {escape_markdown_text(subtask.key)}{suffix}")
    return "\n".join(lines)


def _attachments(issue: NormalizedJiraIssue) -> str:
    if not issue.attachments:
        return "_No attachments._"
    return "\n".join(
        _attachment_line(
            filename=attachment.filename,
            attachment_id=attachment.id,
            mime_type=attachment.mime_type,
            size=attachment.size,
            created=attachment.created,
            author_display_name=attachment.author_display_name,
            local_path=attachment.local_path,
        )
        for attachment in issue.attachments
    )


def _attachment_line(
    *,
    filename: str | None,
    attachment_id: str | None,
    mime_type: str | None,
    size: int | None,
    created: str | None,
    author_display_name: str | None,
    local_path: str | None,
) -> str:
    suffix = _compact_join(
        [
            f"id={attachment_id}" if attachment_id else None,
            f"mime={mime_type}" if mime_type else None,
            f"size={size}" if size is not None else None,
            f"created={created}" if created else None,
            f"author={author_display_name}" if author_display_name else None,
        ],
        separator=", ",
    )
    line = f"- {escape_markdown_text(filename or 'unnamed attachment')}"
    if suffix:
        line += f" ({escape_markdown_text(suffix)})"
    if local_path:
        line += f" - [local file]({_escape_url(local_path)})"
    return line


def _attachment_hash_metadata(
    attachment: NormalizedJiraAttachment | NormalizedConfluenceAttachment,
) -> dict[str, object]:
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "size": attachment.size,
        "created": attachment.created,
        "author_display_name": attachment.author_display_name,
        "local_path": attachment.local_path,
    }


def _confluence_exported_page_hash_inputs(
    exported_pages: Sequence[NormalizedConfluencePage],
) -> list[dict[str, object]]:
    return [
        {
            "id": page.id,
            "title": page.title,
            "space_key": page.space_key,
            "relative_path": _path_as_posix(_confluence_page_markdown_relative_path(page)),
        }
        for page in sorted(exported_pages, key=lambda item: item.id)
    ]


def _confluence_page_markdown_relative_path(page: NormalizedConfluencePage) -> Path:
    safe_space = safe_confluence_path_segment(page.space_key, fallback="unknown-space")
    safe_id = safe_confluence_path_segment(page.id, fallback="page")
    safe_title = safe_confluence_path_segment(page.title, fallback="untitled")
    return Path(PAGES_DIR) / safe_space / f"{safe_id}-{safe_title}.md"


def _confluence_reference_payload(
    reference: NormalizedConfluencePageReference | None,
) -> dict[str, object] | None:
    if reference is None:
        return None
    return {
        "id": reference.id,
        "title": reference.title,
        "space_key": reference.space_key,
        "url": reference.url,
    }


def _confluence_label_text(label: NormalizedConfluenceLabel) -> str:
    if label.prefix:
        return f"{label.prefix}:{label.name}"
    return label.name


def _confluence_reference_value(
    current_page: NormalizedConfluencePage,
    reference: NormalizedConfluencePageReference | None,
    exported_pages: Sequence[NormalizedConfluencePage],
) -> str:
    if reference is None:
        return "null"
    label = escape_markdown_text(reference.title or reference.id)
    exported_index = {page.id: page for page in exported_pages}
    target = exported_index.get(reference.id)
    if target is not None:
        url = _relative_page_url(current_page, target)
        return f"[{label}]({_escape_url(url)})"
    if reference.url:
        return f"[{label}]({_escape_url(reference.url)})"
    return label


def _relative_page_url(
    current_page: NormalizedConfluencePage,
    target_page: NormalizedConfluencePage,
) -> str:
    current_path = _confluence_page_markdown_relative_path(current_page)
    target_path = _confluence_page_markdown_relative_path(target_page)
    relative = os.path.relpath(target_path, start=current_path.parent)
    return relative.replace(os.sep, "/")


def _confluence_reference_sort_key(
    reference: NormalizedConfluencePageReference,
) -> tuple[str, str]:
    return ((reference.title or "").casefold(), reference.id)


def _unsupported_body_placeholder(
    body_owner: str,
    page_id: str,
    representation: str | None,
) -> str:
    found = representation or "none"
    safe_id = safe_confluence_path_segment(page_id, fallback="page")
    raw_path = _path_as_posix(Path(PAGES_DIR) / RAW_PAGES_DIR / f"{safe_id}.json")
    return (
        f"[Unsupported Confluence {body_owner} body: atlas_doc_format body not available; "
        f"found {escape_markdown_text(found)}; raw preserved in {raw_path}]"
    )


def _path_as_posix(path: Path) -> str:
    return path.as_posix()


def _raw_field_notes(issue: NormalizedJiraIssue) -> str:
    if not issue.custom_fields:
        return "_No additional raw field notes._"
    return "\n".join(
        f"- {escape_markdown_text(field.label)} (`{field.field_id}`): "
        f"{_markdown_value(field.value)}"
        for field in issue.custom_fields
    )


def _comments(issue: NormalizedJiraIssue, renderer: AdfMarkdownRenderer) -> str:
    if not issue.comments:
        return "_No comments._"

    rendered_comments: list[str] = []
    for index, comment in enumerate(issue.comments, start=1):
        author = comment.author_display_name or "Unknown Author"
        created = comment.created or "Unknown Created Timestamp"
        lines = [
            f"### Comment {index} — {escape_markdown_text(author)} — "
            f"{escape_markdown_text(created)}",
            "",
            f"- Comment ID: {_markdown_value(comment.id)}",
        ]
        if comment.updated and comment.updated != comment.created:
            lines.append(f"- Updated: {escape_markdown_text(comment.updated)}")
        if comment.visibility:
            lines.append(f"- Visibility: {escape_markdown_text(comment.visibility)}")
        body = renderer.render(comment.body_adf) or "_No comment body._"
        lines.extend(["", body])
        rendered_comments.append("\n".join(lines))
    return "\n\n".join(rendered_comments)


def _markdown_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return ", ".join(escape_markdown_text(item) for item in value) if value else "[]"
    return escape_markdown_text(value)


def _linked_key(key: str | None, url: str | None) -> str:
    label = escape_markdown_text(key or "link")
    if url:
        return f"[{label}]({_escape_url(url)})"
    return label


def _normalize_confluence_page_refs(
    raw_refs: Sequence[Mapping[str, Any]],
    *,
    site_base: str | None,
    pages_only: bool = False,
    fallback_space_key: str | None = None,
) -> list[NormalizedConfluencePageReference]:
    refs: list[NormalizedConfluencePageReference] = []
    for raw_ref in _mapping_list(raw_refs):
        if pages_only and raw_ref.get("type") not in (None, "page"):
            continue
        ref_id = _optional_string(raw_ref.get("id"))
        if not ref_id:
            continue
        refs.append(
            NormalizedConfluencePageReference(
                id=ref_id,
                title=_optional_string(raw_ref.get("title")),
                space_key=_confluence_space_key(raw_ref) or fallback_space_key,
                url=_confluence_web_url(site_base, raw_ref, fallback_space_key=fallback_space_key),
                raw=raw_ref,
            )
        )
    return refs


def _confluence_parent(
    raw_page: Mapping[str, Any],
    ancestors: Sequence[NormalizedConfluencePageReference],
    site_base: str | None,
    *,
    fallback_space_key: str | None = None,
) -> NormalizedConfluencePageReference | None:
    raw_parent = _mapping(raw_page.get("parent"))
    parent_id = _optional_string(raw_page.get("parentId")) or _optional_string(raw_parent.get("id"))
    if not parent_id:
        return None
    for ancestor in reversed(ancestors):
        if ancestor.id == parent_id:
            return ancestor
    return NormalizedConfluencePageReference(
        id=parent_id,
        title=_optional_string(raw_parent.get("title")),
        space_key=_confluence_space_key(raw_parent)
        or _confluence_space_key(raw_page)
        or fallback_space_key,
        url=_confluence_web_url(site_base, raw_parent, fallback_space_key=fallback_space_key),
        raw=raw_parent,
    )


def _normalize_confluence_labels(
    raw_labels: Sequence[Mapping[str, Any]],
) -> list[NormalizedConfluenceLabel]:
    labels: list[NormalizedConfluenceLabel] = []
    for raw_label in _mapping_list(raw_labels):
        name = _optional_string(raw_label.get("name"))
        if not name:
            continue
        labels.append(
            NormalizedConfluenceLabel(
                id=_optional_string(raw_label.get("id")),
                prefix=_optional_string(raw_label.get("prefix")),
                name=name,
                raw=raw_label,
            )
        )
    return sorted(labels, key=_confluence_label_sort_key)


def _normalize_confluence_attachments(
    raw_attachments: Sequence[Mapping[str, Any]],
) -> list[NormalizedConfluenceAttachment]:
    attachments: list[NormalizedConfluenceAttachment] = []
    for raw_attachment in _mapping_list(raw_attachments):
        size = raw_attachment.get("fileSize", raw_attachment.get("size"))
        attachments.append(
            NormalizedConfluenceAttachment(
                id=_optional_string(raw_attachment.get("id")),
                filename=_optional_string(raw_attachment.get("title"))
                or _optional_string(raw_attachment.get("filename")),
                mime_type=_optional_string(raw_attachment.get("mediaType"))
                or _optional_string(raw_attachment.get("mimeType")),
                size=size if isinstance(size, int) else None,
                created=_optional_string(raw_attachment.get("createdAt"))
                or _optional_string(raw_attachment.get("created")),
                author_display_name=_confluence_actor(raw_attachment.get("author"))
                or _confluence_actor(raw_attachment.get("createdBy")),
                download_url=_optional_string(raw_attachment.get("downloadLink"))
                or _optional_string(_mapping(raw_attachment.get("_links")).get("download")),
                local_path=_optional_string(raw_attachment.get("local_path"))
                or _optional_string(raw_attachment.get("localPath")),
                raw=raw_attachment,
            )
        )
    return sorted(attachments, key=lambda item: (item.id or "", item.filename or ""))


def _normalize_confluence_comments(
    raw_comments: Sequence[Mapping[str, Any]],
) -> list[NormalizedConfluenceComment]:
    comments: list[NormalizedConfluenceComment] = []
    for raw_comment in _mapping_list(raw_comments):
        body_adf, body_representation = _confluence_body_adf(raw_comment.get("body"))
        comments.append(
            NormalizedConfluenceComment(
                id=_optional_string(raw_comment.get("id")),
                author_display_name=_confluence_actor(raw_comment.get("author"))
                or _confluence_actor(raw_comment.get("createdBy"))
                or _optional_string(raw_comment.get("authorId")),
                created=_optional_string(raw_comment.get("createdAt"))
                or _optional_string(raw_comment.get("created")),
                updated=_optional_string(raw_comment.get("updatedAt"))
                or _optional_string(raw_comment.get("updated")),
                status=_optional_string(raw_comment.get("status")),
                resolution_status=_optional_string(raw_comment.get("resolutionStatus"))
                or _display_value(raw_comment.get("resolution")),
                body_adf=body_adf,
                body_representation=body_representation,
                raw=raw_comment,
            )
        )
    return comments


def _sorted_confluence_comments(
    raw_comments: Sequence[Mapping[str, Any]],
) -> list[NormalizedConfluenceComment]:
    return sorted(_normalize_confluence_comments(raw_comments), key=_confluence_comment_sort_key)


def _confluence_comment_sort_key(
    comment: NormalizedConfluenceComment,
) -> tuple[str, tuple[int, int | str]]:
    return (comment.created or "", _id_sort_key(comment.id))


def _confluence_label_sort_key(label: NormalizedConfluenceLabel) -> tuple[str, str]:
    return (label.prefix or "", label.name)


def _confluence_body_adf(value: object) -> tuple[dict[str, Any] | None, str | None]:
    body = _mapping(value)
    if not body:
        return None, None

    if "atlas_doc_format" in body:
        adf = _adf_from_body_representation(body.get("atlas_doc_format"))
        return adf, "atlas_doc_format"

    for representation in sorted(str(key) for key in body):
        if representation:
            return None, representation
    return None, None


def _adf_from_body_representation(value: object) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        if value.get("type") == "doc":
            return _json_object(value)
        raw_value = value.get("value")
        if isinstance(raw_value, Mapping):
            return _json_object(raw_value)
        if isinstance(raw_value, str):
            return _json_string_object(raw_value)
        return None
    if isinstance(value, str):
        return _json_string_object(value)
    return None


def _json_string_object(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, Mapping):
        return None
    return _json_object(parsed)


def _confluence_space_key(raw: Mapping[str, Any]) -> str | None:
    return _optional_string(raw.get("spaceKey")) or _optional_string(
        _mapping(raw.get("space")).get("key")
    )


def _confluence_space_id(raw: Mapping[str, Any]) -> str | None:
    return _optional_string(raw.get("spaceId")) or _optional_string(
        _mapping(raw.get("space")).get("id")
    )


def _confluence_version(value: object) -> int | None:
    if isinstance(value, int):
        return value
    version = _mapping(value)
    number = version.get("number")
    return number if isinstance(number, int) else None


def _confluence_updated(raw: Mapping[str, Any]) -> str | None:
    updated = _optional_string(raw.get("updatedAt"))
    if updated:
        return updated
    return _optional_string(_mapping(raw.get("version")).get("createdAt"))


def _confluence_actor(value: object) -> str | None:
    return _display_value(
        value,
        preferred_keys=("displayName", "publicName", "name", "accountId", "id"),
    )


def _confluence_web_url(
    site_base: str | None,
    raw: Mapping[str, Any],
    *,
    fallback_space_key: str | None = None,
) -> str | None:
    links = _mapping(raw.get("_links"))
    base = _optional_string(links.get("base")) or site_base
    for key in ("webui", "tinyui"):
        candidate = _optional_string(links.get(key))
        if candidate:
            return _absolute_url(base, candidate)
    direct_url = _optional_string(raw.get("url"))
    if direct_url:
        return _absolute_url(base, direct_url)
    self_url = _optional_string(raw.get("self"))
    if self_url:
        return _absolute_url(site_base, self_url)
    page_id = _optional_string(raw.get("id"))
    space_key = _confluence_space_key(raw) or fallback_space_key
    if base and page_id and space_key:
        return _absolute_url(
            base,
            f"/spaces/{quote(space_key, safe='')}/pages/{quote(page_id, safe='')}",
        )
    return None


def _absolute_url(site_base: str | None, value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return value
    if not site_base:
        return None
    base = site_base.rstrip("/")
    base_path = urlparse(base).path.rstrip("/")
    if value.startswith("/") and base_path and not value.startswith(base_path + "/"):
        return urljoin(base + "/", value.lstrip("/"))
    return urljoin(site_base.rstrip("/") + "/", value)


def _normalize_comments(raw_comments: Sequence[Mapping[str, Any]]) -> list[NormalizedJiraComment]:
    comments = []
    for raw_comment in raw_comments:
        raw = _json_object(raw_comment)
        author = _mapping(raw.get("author"))
        comments.append(
            NormalizedJiraComment(
                id=_optional_string(raw.get("id")),
                author_display_name=_display_value(author),
                created=_optional_string(raw.get("created")),
                updated=_optional_string(raw.get("updated")),
                visibility=_visibility(raw.get("visibility")),
                body_adf=_optional_mapping(raw.get("body")),
                raw=raw,
            )
        )
    return comments


def _sorted_comments(raw_comments: Sequence[Mapping[str, Any]]) -> list[NormalizedJiraComment]:
    return sorted(_normalize_comments(raw_comments), key=_comment_sort_key)


def _comment_sort_key(comment: NormalizedJiraComment) -> tuple[str, tuple[int, int | str]]:
    return (comment.created or "", _id_sort_key(comment.id))


def _id_sort_key(value: str | None) -> tuple[int, int | str]:
    if value is not None and value.isdecimal():
        return (0, int(value))
    return (1, value or "")


def _normalize_attachments(value: object) -> list[NormalizedJiraAttachment]:
    attachments = []
    for raw_attachment in _mapping_list(value):
        author = _mapping(raw_attachment.get("author"))
        size = raw_attachment.get("size")
        attachments.append(
            NormalizedJiraAttachment(
                id=_optional_string(raw_attachment.get("id")),
                filename=_optional_string(raw_attachment.get("filename")),
                mime_type=_optional_string(raw_attachment.get("mimeType")),
                size=size if isinstance(size, int) else None,
                created=_optional_string(raw_attachment.get("created")),
                author_display_name=_display_value(author),
                content_url=_optional_string(raw_attachment.get("content")),
                local_path=_optional_string(raw_attachment.get("local_path")),
                raw=raw_attachment,
            )
        )
    return sorted(attachments, key=lambda item: (item.id or "", item.filename or ""))


def _normalize_issue_links(
    value: object,
    site_base: str | None,
) -> list[NormalizedJiraIssueLink]:
    links = []
    for raw_link in _mapping_list(value):
        link_type = _mapping(raw_link.get("type"))
        if isinstance(raw_link.get("outwardIssue"), Mapping):
            relationship = _optional_string(link_type.get("outward")) or "outward"
            target = _mapping(raw_link.get("outwardIssue"))
        elif isinstance(raw_link.get("inwardIssue"), Mapping):
            relationship = _optional_string(link_type.get("inward")) or "inward"
            target = _mapping(raw_link.get("inwardIssue"))
        else:
            relationship = _display_value(link_type) or "linked"
            target = {}
        target_key = _optional_string(target.get("key"))
        target_fields = _mapping(target.get("fields"))
        links.append(
            NormalizedJiraIssueLink(
                relationship=relationship,
                key=target_key,
                url=f"{site_base}/browse/{target_key}" if site_base and target_key else None,
                summary=_optional_string(target_fields.get("summary")),
                status=_display_value(target_fields.get("status")),
            )
        )
    return sorted(links, key=lambda item: (item.relationship, item.key or "", item.url or ""))


def _normalize_subtasks(value: object) -> list[NormalizedJiraSubtask]:
    subtasks = []
    for raw_subtask in _mapping_list(value):
        key = _optional_string(raw_subtask.get("key"))
        if key is None:
            continue
        fields = _mapping(raw_subtask.get("fields"))
        subtasks.append(
            NormalizedJiraSubtask(
                key=key,
                summary=_optional_string(fields.get("summary")),
                status=_display_value(fields.get("status")),
            )
        )
    return sorted(subtasks, key=lambda item: item.key)


def _normalize_custom_fields(
    fields: Mapping[str, Any],
    configured_fields: Mapping[str, str],
) -> list[NormalizedCustomField]:
    custom_fields = []
    for field_id, label in sorted(configured_fields.items(), key=lambda item: (item[1], item[0])):
        if field_id in _RENDERED_FIELD_IDS or field_id not in fields:
            continue
        value = fields[field_id]
        rendered_value = _display_value(value)
        if rendered_value is None:
            continue
        custom_fields.append(
            NormalizedCustomField(field_id=field_id, label=label, value=rendered_value)
        )
    return custom_fields


def _epic_value(
    fields: Mapping[str, Any],
    custom_fields: Sequence[NormalizedCustomField],
) -> str | None:
    explicit = _display_value(fields.get("epic"))
    if explicit:
        return explicit
    for field in custom_fields:
        if field.label.lower() in {"epic", "epic link", "epic name"}:
            return field.value
    return _display_value(fields.get("customfield_10014"))


def _parent_key(value: object) -> str | None:
    parent = _mapping(value)
    return _optional_string(parent.get("key")) if parent else None


def _sorted_display_list(value: object) -> list[str]:
    values: list[str] = []
    if not isinstance(value, list):
        return values
    for item in value:
        rendered = _display_value(item)
        if rendered is not None:
            values.append(rendered)
    return sorted(values)


def _display_value(
    value: object,
    *,
    preferred_keys: Sequence[str] = ("displayName", "name", "value", "key", "id"),
) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    if isinstance(value, list):
        return _display_list_value(value)
    if isinstance(value, Mapping):
        return _display_mapping_value(value, preferred_keys)
    return str(value)


def _display_list_value(value: Sequence[object]) -> str:
    rendered = [_display_value(item) for item in value]
    return ", ".join(sorted(item for item in rendered if item))


def _display_mapping_value(value: Mapping[Any, Any], preferred_keys: Sequence[str]) -> str:
    for key in preferred_keys:
        rendered_field = _display_value(value.get(key))
        if rendered_field:
            return rendered_field
    return canonical_json(_json_object(value)).strip()


def _visibility(value: object) -> str | None:
    visibility = _mapping(value)
    if not visibility:
        return None
    visibility_type = _optional_string(visibility.get("type"))
    visibility_value = _optional_string(visibility.get("value")) or _optional_string(
        visibility.get("identifier")
    )
    return _compact_join([visibility_type, visibility_value], separator=":")


def _compact_join(values: Sequence[str | None], *, separator: str) -> str:
    return separator.join(value for value in values if value)


def _json_object(value: Mapping[Any, Any]) -> dict[str, Any]:
    return {str(key): _jsonable(item) for key, item in value.items()}


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _optional_mapping(value: object) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return _json_object(value)


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_json_object(item) for item in value if isinstance(item, Mapping)]


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    return None


def _required_string(value: object, label: str) -> str:
    text = _optional_string(value)
    if not text:
        raise ValueError(f"{label} is required.")
    return text


def _site_base(site_url: str | None, raw_issue: Mapping[str, Any]) -> str | None:
    candidate = site_url or _optional_string(raw_issue.get("self"))
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.hostname:
        return None
    netloc = parsed.hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return f"{parsed.scheme}://{netloc}"


def _confluence_site_base(
    site_url: str | None,
    raw_page: Mapping[str, Any],
    *,
    fallback_url: str | None = None,
) -> str | None:
    links_base = _optional_string(_mapping(raw_page.get("_links")).get("base"))
    if links_base:
        return _confluence_base_from_url(links_base) or _site_base(site_url, raw_page)
    if fallback_url:
        fallback_base = _confluence_base_from_url(fallback_url, trim_page_path=True)
        if fallback_base is not None:
            return fallback_base
    return _site_base(site_url, raw_page)


def _confluence_base_from_url(value: str, *, trim_page_path: bool = False) -> str | None:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        return None
    netloc = parsed.hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    path = parsed.path.rstrip("/")
    if trim_page_path:
        for marker in ("/spaces/", "/pages/", "/x/", "/display/"):
            if marker in path:
                path = path.split(marker, 1)[0].rstrip("/")
                break
    return f"{parsed.scheme}://{netloc}{path}"


def _site_host(site_base: str | None) -> str | None:
    if site_base is None:
        return None
    return urlparse(site_base).hostname


def _escape_url(url: str) -> str:
    return url.replace("\\", "%5C").replace(" ", "%20").replace(")", "%29")


def _exported_at(*, stable: bool, exported_at: str | None) -> str:
    if stable:
        return STABLE_EXPORTED_AT
    if exported_at is not None:
        return exported_at
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
