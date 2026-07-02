"""Deterministic Markdown indexes for Jira export output."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
from pathlib import Path
from typing import Any

from atlassian_md_export.writer import atomic_write_text
from atlassian_md_export.writer import confluence_page_markdown_path
from atlassian_md_export.writer import confluence_page_raw_dir
from atlassian_md_export.writer import issue_raw_dir
from atlassian_md_export.writer import normalize_confluence_page

REQUIRED_INDEXES = (
    "by-status.md",
    "by-assignee.md",
    "by-epic.md",
    "stale.md",
)
OPTIONAL_INDEXES = ("all.md",)
CONFLUENCE_REQUIRED_INDEXES = (
    "all.md",
    "by-space.md",
    "by-label.md",
    "by-parent.md",
    "stale.md",
)


def index_dir(out_dir: Path) -> Path:
    return out_dir / "indexes"


def required_index_paths(out_dir: Path) -> list[Path]:
    return [index_dir(out_dir) / name for name in REQUIRED_INDEXES]


def confluence_required_index_paths(out_dir: Path) -> list[Path]:
    return [index_dir(out_dir) / name for name in CONFLUENCE_REQUIRED_INDEXES]


@dataclass(frozen=True)
class IndexIssue:
    key: str
    summary: str
    status: str | None
    assignee: str | None
    epic: str | None
    updated: str | None


@dataclass(frozen=True)
class IndexConfluencePage:
    page_id: str
    title: str
    space_key: str | None
    updated: str | None
    labels: tuple[str, ...]
    parent_id: str | None
    parent_title: str | None
    relative_markdown_path: str


def generate_indexes(
    out_dir: Path,
    *,
    stale_days: int = 30,
    now: datetime | None = None,
) -> list[Path]:
    issues = read_index_issues(out_dir)
    target_dir = index_dir(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    written = [
        _write_grouped_index(
            target_dir / "by-status.md",
            title="Issues by Status",
            issues=issues,
            group_for=lambda issue: issue.status or "Unspecified",
        ),
        _write_grouped_index(
            target_dir / "by-assignee.md",
            title="Issues by Assignee",
            issues=issues,
            group_for=lambda issue: issue.assignee or "Unassigned",
        ),
        _write_grouped_index(
            target_dir / "by-epic.md",
            title="Issues by Epic",
            issues=issues,
            group_for=lambda issue: issue.epic or "No Epic",
        ),
        _write_stale_index(
            target_dir / "stale.md",
            issues=issues,
            stale_days=stale_days,
            now=now,
        ),
        _write_all_index(target_dir / "all.md", issues),
    ]
    return written


def generate_confluence_indexes(
    out_dir: Path,
    *,
    stale_days: int = 30,
    now: datetime | None = None,
) -> list[Path]:
    pages = read_confluence_index_pages(out_dir)
    target_dir = index_dir(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    written = [
        _write_confluence_all_index(target_dir / "all.md", pages),
        _write_confluence_grouped_index(
            target_dir / "by-space.md",
            title="Confluence Pages by Space",
            pages=pages,
            groups_for=lambda page: (page.space_key or "Unknown Space",),
        ),
        _write_confluence_grouped_index(
            target_dir / "by-label.md",
            title="Confluence Pages by Label",
            pages=pages,
            groups_for=lambda page: page.labels or ("No Labels",),
        ),
        _write_confluence_grouped_index(
            target_dir / "by-parent.md",
            title="Confluence Pages by Parent",
            pages=pages,
            groups_for=lambda page: (_confluence_parent_group(page),),
        ),
        _write_confluence_stale_index(
            target_dir / "stale.md",
            pages=pages,
            stale_days=stale_days,
            now=now,
        ),
    ]
    return written


def read_index_issues(out_dir: Path) -> list[IndexIssue]:
    raw_dir = issue_raw_dir(out_dir)
    if not raw_dir.exists():
        return []
    issues: list[IndexIssue] = []
    for path in sorted(raw_dir.glob("*.json"), key=lambda item: item.name):
        issues.append(_issue_from_json(path))
    return sorted(issues, key=lambda issue: issue.key)


def read_confluence_index_pages(out_dir: Path) -> list[IndexConfluencePage]:
    raw_dir = confluence_page_raw_dir(out_dir)
    if not raw_dir.exists():
        return []
    pages: list[IndexConfluencePage] = []
    for path in sorted(raw_dir.glob("*.json"), key=lambda item: item.name):
        pages.append(_confluence_page_from_json(out_dir, path))
    return sorted(pages, key=_confluence_page_sort_key)


def _write_grouped_index(
    path: Path,
    *,
    title: str,
    issues: Iterable[IndexIssue],
    group_for: Callable[[IndexIssue], str],
) -> Path:
    groups: dict[str, list[IndexIssue]] = {}
    for issue in issues:
        group = group_for(issue)
        groups.setdefault(str(group), []).append(issue)

    lines = [f"# {title}", ""]
    if not groups:
        lines.append("_No issues._")
    for group in sorted(groups):
        lines.extend([f"## {group}", ""])
        for issue in sorted(groups[group], key=lambda item: item.key):
            lines.append(_issue_line(issue))
        lines.append("")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")
    return path


def _write_confluence_grouped_index(
    path: Path,
    *,
    title: str,
    pages: Iterable[IndexConfluencePage],
    groups_for: Callable[[IndexConfluencePage], tuple[str, ...]],
) -> Path:
    groups: dict[str, list[IndexConfluencePage]] = {}
    for page in pages:
        for group in groups_for(page):
            groups.setdefault(group, []).append(page)

    lines = [f"# {title}", ""]
    if not groups:
        lines.append("_No pages._")
    for group in sorted(groups, key=lambda value: value.casefold()):
        lines.extend([f"## {group}", ""])
        for page in sorted(groups[group], key=_confluence_page_sort_key):
            lines.append(_confluence_page_line(page))
        lines.append("")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")
    return path


def _write_stale_index(
    path: Path,
    *,
    issues: list[IndexIssue],
    stale_days: int,
    now: datetime | None,
) -> Path:
    active_now = now or _deterministic_reference_time(issues)
    cutoff = active_now - timedelta(days=stale_days)
    stale = [
        issue
        for issue in issues
        if issue.updated is not None and _parse_jira_datetime(issue.updated) < cutoff
    ]

    lines = ["# Stale Issues", "", f"Threshold: {stale_days} days", ""]
    if not stale:
        lines.append("_No stale issues._")
    for issue in sorted(stale, key=lambda item: (item.updated or "", item.key)):
        lines.append(f"- [{issue.key}](../issues/{issue.key}.md) - Updated {issue.updated} - {issue.summary}")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")
    return path


def _write_confluence_stale_index(
    path: Path,
    *,
    pages: list[IndexConfluencePage],
    stale_days: int,
    now: datetime | None,
) -> Path:
    active_now = now or _deterministic_confluence_reference_time(pages)
    cutoff = active_now - timedelta(days=stale_days)
    stale = [
        page
        for page in pages
        if page.updated is not None and _parse_atlassian_datetime(page.updated) < cutoff
    ]

    lines = ["# Stale Confluence Pages", "", f"Threshold: {stale_days} days", ""]
    if not stale:
        lines.append("_No stale pages._")
    for page in sorted(stale, key=lambda item: (item.updated or "", item.title.casefold(), item.page_id)):
        lines.append(
            f"- [{page.title}]({page.relative_markdown_path}) - "
            f"id={page.page_id} - Updated {page.updated}"
        )
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")
    return path


def _deterministic_reference_time(issues: list[IndexIssue]) -> datetime:
    updated_values = [
        _parse_atlassian_datetime(issue.updated)
        for issue in issues
        if issue.updated is not None
    ]
    if updated_values:
        return max(updated_values)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _deterministic_confluence_reference_time(pages: list[IndexConfluencePage]) -> datetime:
    updated_values = [
        _parse_atlassian_datetime(page.updated)
        for page in pages
        if page.updated is not None
    ]
    if updated_values:
        return max(updated_values)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _write_all_index(path: Path, issues: list[IndexIssue]) -> Path:
    lines = ["# All Issues", ""]
    if not issues:
        lines.append("_No issues._")
    for issue in sorted(issues, key=lambda item: item.key):
        lines.append(_issue_line(issue))
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")
    return path


def _write_confluence_all_index(path: Path, pages: list[IndexConfluencePage]) -> Path:
    lines = ["# All Confluence Pages", ""]
    if not pages:
        lines.append("_No pages._")
    for page in sorted(pages, key=_confluence_page_sort_key):
        lines.append(_confluence_page_line(page))
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")
    return path


def _issue_line(issue: IndexIssue) -> str:
    return f"- [{issue.key}](../issues/{issue.key}.md) - {issue.summary}"


def _confluence_page_line(page: IndexConfluencePage) -> str:
    details = [f"id={page.page_id}"]
    if page.space_key:
        details.append(f"space={page.space_key}")
    if page.updated:
        details.append(f"updated={page.updated}")
    return f"- [{page.title}]({page.relative_markdown_path}) - {', '.join(details)}"


def _issue_from_json(path: Path) -> IndexIssue:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Issue JSON is not an object: {path}")
    raw_issue = payload.get("raw_issue")
    if not isinstance(raw_issue, dict):
        raise ValueError(f"Issue JSON lacks raw_issue object: {path}")
    key = raw_issue.get("key")
    fields = raw_issue.get("fields")
    if not isinstance(key, str) or not isinstance(fields, dict):
        raise ValueError(f"Issue JSON lacks key/fields: {path}")
    return IndexIssue(
        key=key,
        summary=_string(fields.get("summary")) or "",
        status=_display(fields.get("status")),
        assignee=_display(fields.get("assignee")),
        epic=_display(fields.get("epic")) or _display(fields.get("customfield_10014")),
        updated=_string(fields.get("updated")),
    )


def _confluence_page_from_json(out_dir: Path, path: Path) -> IndexConfluencePage:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Confluence page JSON is not an object: {path}")
    raw_page = payload.get("raw_page")
    if not isinstance(raw_page, Mapping):
        raise ValueError(f"Confluence page JSON lacks raw_page object: {path}")

    page = normalize_confluence_page(
        raw_page,
        labels=_dict_list(payload.get("labels")),
        ancestors=_dict_list(payload.get("ancestors")),
        child_pages=_dict_list(payload.get("child_page_references")),
        space_key=_confluence_payload_space_key(payload),
        url=_confluence_payload_url(payload),
    )
    markdown_path = confluence_page_markdown_path(out_dir, page)
    return IndexConfluencePage(
        page_id=page.id,
        title=page.title,
        space_key=page.space_key,
        updated=page.updated,
        labels=tuple(_label_text(label) for label in page.labels),
        parent_id=page.parent.id if page.parent is not None else None,
        parent_title=page.parent.title if page.parent is not None else None,
        relative_markdown_path=_relative_index_link(out_dir, markdown_path),
    )


def _relative_index_link(out_dir: Path, markdown_path: Path) -> str:
    relative = os.path.relpath(markdown_path, start=index_dir(out_dir))
    return relative.replace(os.sep, "/")


def _label_text(label: Any) -> str:
    prefix = getattr(label, "prefix", None)
    name = getattr(label, "name", "")
    if prefix:
        return f"{prefix}:{name}"
    return str(name)


def _confluence_payload_space_key(payload: Mapping[str, Any]) -> str | None:
    normalized = payload.get("normalized_page")
    if isinstance(normalized, Mapping):
        normalized_space_key = normalized.get("space_key")
        if isinstance(normalized_space_key, str) and normalized_space_key:
            return normalized_space_key
    raw_page = payload.get("raw_page")
    if isinstance(raw_page, Mapping):
        raw_space_key = raw_page.get("spaceKey")
        if isinstance(raw_space_key, str) and raw_space_key:
            return raw_space_key
        raw_space = raw_page.get("space")
        if isinstance(raw_space, Mapping):
            embedded_space_key = raw_space.get("key")
            if isinstance(embedded_space_key, str) and embedded_space_key:
                return embedded_space_key
    return None


def _confluence_payload_url(payload: Mapping[str, Any]) -> str | None:
    normalized = payload.get("normalized_page")
    if isinstance(normalized, Mapping):
        normalized_url = normalized.get("url")
        if isinstance(normalized_url, str) and normalized_url:
            return normalized_url
    return None


def _confluence_parent_group(page: IndexConfluencePage) -> str:
    if page.parent_id is None:
        return "No Parent"
    if page.parent_title:
        return f"{page.parent_title} ({page.parent_id})"
    return page.parent_id


def _confluence_page_sort_key(page: IndexConfluencePage) -> tuple[str, str]:
    return (page.title.casefold(), page.page_id)


def _display(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    if isinstance(value, dict):
        for key in ("displayName", "name", "value", "key", "id"):
            rendered = _display(value.get(key))
            if rendered:
                return rendered
    return None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _parse_jira_datetime(value: str) -> datetime:
    return _parse_atlassian_datetime(value)


def _parse_atlassian_datetime(value: str) -> datetime:
    normalized = value
    if value.endswith("Z"):
        normalized = f"{value[:-1]}+00:00"
    elif len(value) >= 5 and value[-5] in {"+", "-"} and value[-3] != ":":
        normalized = f"{value[:-2]}:{value[-2:]}"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]
