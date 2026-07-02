from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlassian_md_export.writer import CONFLUENCE_PAGE_FRONTMATTER_FIELDS
from atlassian_md_export.writer import STABLE_EXPORTED_AT
from atlassian_md_export.writer import confluence_page_content_hash
from atlassian_md_export.writer import confluence_page_markdown_path
from atlassian_md_export.writer import confluence_page_raw_export_json
from atlassian_md_export.writer import normalize_confluence_page
from atlassian_md_export.writer import render_confluence_page_markdown
from atlassian_md_export.writer import safe_confluence_path_segment
from atlassian_md_export.writer import write_confluence_page_files


def test_representative_confluence_page_markdown_snapshot() -> None:
    root, page, child = _normalized_page_set()
    exported_pages = (root, page, child)
    content_hash = confluence_page_content_hash(page, exported_pages=exported_pages)

    markdown = render_confluence_page_markdown(
        page,
        stable_exported_at=True,
        exported_pages=exported_pages,
    )

    assert markdown == f"""---
schema_version: 1
source: confluence-cloud:example.atlassian.net
id: '123'
url: https://example.atlassian.net/wiki/spaces/DOC/pages/123/Launch+Plan
title: Launch *Plan* [Q3]
space_key: DOC
space_id: space-1
status: current
parent:
  id: '100'
  title: Root Page
  space_key: DOC
  url: https://example.atlassian.net/wiki/spaces/DOC/pages/100/Root
ancestors:
- id: '100'
  title: Root Page
  space_key: DOC
  url: https://example.atlassian.net/wiki/spaces/DOC/pages/100/Root
version: 7
author: user-1
owner: owner-1
created: 2026-07-01T08:00:00.000+0000
updated: 2026-07-01T10:00:00.000+0000
labels:
- global:alpha
- team:beta
child_count: 1
comment_count: 3
footer_comment_count: 2
inline_comment_count: 1
attachment_count: 1
exported_at: '1970-01-01T00:00:00Z'
content_hash: {content_hash}
---

# Launch \\*Plan\\* \\[Q3\\]

## Page Metadata

- Space: DOC / space-1
- Page ID: 123
- Status: current
- Parent: [Root Page](100-Root-Page.md)
- Author: user-1
- Owner: owner-1
- Created: 2026-07-01T08:00:00.000+0000
- Updated: 2026-07-01T10:00:00.000+0000
- Version: 7
- Labels: global:alpha, team:beta
- Comments: 3 total (2 footer, 1 inline)
- Attachments: 1

## Ancestors

- [Root Page](100-Root-Page.md) (id=100)

## Child Pages

- [Child Page](124-Child-Page.md) (id=124)

## Content

Hello **world**

## Attachments

- design.png (id=att-1, mime=image/png, size=42, created=2026-07-01T09:00:00.000+0000, author=File Person) - [local file](../../attachments/123/att-1-design.png)

## Labels

- global:alpha (id=label-1)
- team:beta (id=label-2)

## Comments

### Footer Comment 1 - Rae Reporter - 2026-07-01T12:00:00.000+0000

- Comment ID: 1
- Updated: 2026-07-01T12:05:00.000+0000
- Status: current

First footer

### Footer Comment 2 - Alex Agent - 2026-07-01T13:00:00.000+0000

- Comment ID: 2
- Status: current

Second footer

### Inline Comment 1 - Ivy Inline - 2026-07-01T14:00:00.000+0000

- Comment ID: 10
- Status: open
- Inline Resolution Status: open

Inline note

## Raw Field Notes

- Raw page field preserved but not rendered: `metadata`
"""


def test_confluence_frontmatter_order_and_section_order_are_stable() -> None:
    root, page, child = _normalized_page_set()
    markdown = render_confluence_page_markdown(
        page,
        stable_exported_at=True,
        exported_pages=(root, page, child),
    )
    frontmatter = markdown.split("---\n", 2)[1]
    payload = yaml.safe_load(frontmatter)
    assert tuple(payload) == CONFLUENCE_PAGE_FRONTMATTER_FIELDS

    body = markdown.split("---\n", 2)[2]
    expected_sections = [
        "# Launch \\*Plan\\* \\[Q3\\]",
        "## Page Metadata",
        "## Ancestors",
        "## Child Pages",
        "## Content",
        "## Attachments",
        "## Labels",
        "## Comments",
        "## Raw Field Notes",
    ]
    positions = [body.index(section) for section in expected_sections]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    ("title", "expected_slug"),
    [
        ("../Secrets", "Secrets"),
        (".hidden", "hidden"),
        ('bad/name\\\\:*?"<>|', "bad-name"),
        ("   ", "untitled"),
        ("CON", "_CON"),
    ],
)
def test_confluence_page_filename_safety(title: str, expected_slug: str) -> None:
    page = normalize_confluence_page(
        {"id": "123", "title": title, "spaceKey": "../DOC"},
        site_url="https://example.atlassian.net",
    )

    path = confluence_page_markdown_path(Path("/export"), page)

    assert path == Path("/export/pages/DOC") / f"123-{expected_slug}.md"
    assert all(part not in {"", ".", ".."} for part in path.parts)
    assert not any(part.startswith(".") for part in path.relative_to("/export").parts)


def test_confluence_page_filename_normalizes_unicode_stably() -> None:
    assert safe_confluence_path_segment("Cafe\u0301 Roadmap") == "Cafe-Roadmap"
    assert safe_confluence_path_segment("Café Roadmap") == "Cafe-Roadmap"


def test_confluence_raw_json_is_under_pages_raw_and_preserves_source(
    tmp_path: Path,
) -> None:
    _root, page, _child = _normalized_page_set()
    exported_at = "2026-07-01T12:00:00Z"

    raw_json = confluence_page_raw_export_json(
        page,
        stable_exported_at=True,
        exported_at=exported_at,
    )
    payload = json.loads(raw_json)
    result = write_confluence_page_files(
        tmp_path,
        page,
        stable_exported_at=True,
        exported_at=exported_at,
    )

    assert raw_json.endswith("\n")
    assert result.exported_at == exported_at
    assert result.json_path == tmp_path / "pages" / "_raw" / "123.json"
    assert result.json_path.read_text(encoding="utf-8") == raw_json
    assert payload["raw_page"] == _raw_page()
    assert payload["normalized_page"] == {
        "space_id": "space-1",
        "space_key": "DOC",
        "url": "https://example.atlassian.net/wiki/spaces/DOC/pages/123/Launch+Plan",
    }
    assert [comment["id"] for comment in payload["fetched_footer_comments"]] == ["1", "2"]
    assert [comment["id"] for comment in payload["fetched_inline_comments"]] == ["10"]
    assert payload["raw_adf"]["page"] == _adf_doc("Hello ", "world")
    assert payload["attachment_metadata"][0]["raw"] == _attachments()[0]
    assert payload["labels"] == _labels_sorted_raw()
    assert payload["ancestors"] == [_ancestor_ref()]
    assert payload["child_page_references"] == [_child_ref()]
    assert payload["exporter"] == {
        "exported_at": exported_at,
        "name": "atlassian-md-export",
        "site_host": "example.atlassian.net",
        "source": "confluence-cloud:example.atlassian.net",
        "version": "0.1.0",
    }


def test_confluence_normalization_uses_resolved_space_key_and_wiki_base() -> None:
    raw_page = _raw_page()
    raw_page.pop("spaceKey")
    raw_page["_links"] = {
        "base": "https://example.atlassian.net/wiki",
        "webui": "/spaces/DOC/pages/123/Launch+Plan",
    }

    page = normalize_confluence_page(
        raw_page,
        ancestors=[{"id": "100", "type": "page"}],
        child_pages=[{"id": "124", "type": "page"}],
        site_url="https://example.atlassian.net",
        space_key="DOC",
    )
    payload = json.loads(confluence_page_raw_export_json(page))

    assert page.space_key == "DOC"
    assert page.url == "https://example.atlassian.net/wiki/spaces/DOC/pages/123/Launch+Plan"
    assert page.ancestors[0].space_key == "DOC"
    assert page.ancestors[0].url == "https://example.atlassian.net/wiki/spaces/DOC/pages/100"
    assert confluence_page_markdown_path(Path("/tmp/export"), page) == (
        Path("/tmp/export") / "pages" / "DOC" / "123-Launch-Plan-Q3.md"
    )
    assert payload["normalized_page"]["space_key"] == "DOC"
    assert "spaceKey" not in payload["raw_page"]


def test_confluence_content_hash_ignores_exported_at_and_tracks_links() -> None:
    root, page, child = _normalized_page_set()
    first = render_confluence_page_markdown(
        page,
        exported_at="2026-07-01T00:00:00Z",
        exported_pages=(root, page, child),
    )
    second = render_confluence_page_markdown(
        page,
        exported_at="2026-07-02T00:00:00Z",
        exported_pages=(root, page, child),
    )
    without_link_targets = render_confluence_page_markdown(
        page,
        exported_at="2026-07-01T00:00:00Z",
        exported_pages=(),
    )

    first_frontmatter = yaml.safe_load(first.split("---\n", 2)[1])
    second_frontmatter = yaml.safe_load(second.split("---\n", 2)[1])
    without_link_frontmatter = yaml.safe_load(without_link_targets.split("---\n", 2)[1])

    assert first_frontmatter["exported_at"] == "2026-07-01T00:00:00Z"
    assert second_frontmatter["exported_at"] == "2026-07-02T00:00:00Z"
    assert first_frontmatter["content_hash"] == second_frontmatter["content_hash"]
    assert first_frontmatter["content_hash"] != without_link_frontmatter["content_hash"]
    assert "[Root Page](100-Root-Page.md)" in first
    assert "[Root Page](https://example.atlassian.net/wiki/spaces/DOC/pages/100/Root)" in (
        without_link_targets
    )


def test_storage_only_confluence_body_renders_unsupported_placeholder() -> None:
    page = normalize_confluence_page(
        {
            "id": "999",
            "title": "Storage Only",
            "spaceKey": "DOC",
            "body": {"storage": {"value": "<p>legacy</p>", "representation": "storage"}},
        },
        site_url="https://example.atlassian.net",
    )

    markdown = render_confluence_page_markdown(page, stable_exported_at=True)
    raw_payload = json.loads(confluence_page_raw_export_json(page, stable_exported_at=True))

    assert (
        "[Unsupported Confluence page body: atlas_doc_format body not available; "
        "found storage; raw preserved in pages/_raw/999.json]"
    ) in markdown
    assert raw_payload["raw_page"]["body"]["storage"]["value"] == "<p>legacy</p>"


def test_write_confluence_page_files_uses_atomic_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _root, page, _child = _normalized_page_set()
    original_replace = os.replace
    replaced: list[tuple[str, str]] = []

    def recording_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replaced.append((Path(src).name, Path(dst).name))
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", recording_replace)

    result = write_confluence_page_files(
        tmp_path,
        page,
        stable_exported_at=True,
        exported_at="2026-07-01T12:00:00Z",
    )

    assert result.exported_at == "2026-07-01T12:00:00Z"
    frontmatter = yaml.safe_load(result.markdown_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert frontmatter["exported_at"] == STABLE_EXPORTED_AT
    assert result.markdown_path == tmp_path / "pages" / "DOC" / "123-Launch-Plan-Q3.md"
    assert result.json_path == tmp_path / "pages" / "_raw" / "123.json"
    assert result.markdown_path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(result.json_path.read_text(encoding="utf-8"))["raw_page"]["id"] == "123"
    assert [destination for _source, destination in replaced] == [
        "123-Launch-Plan-Q3.md",
        "123.json",
    ]
    assert not list((tmp_path / "pages" / "DOC").glob(".*.tmp"))
    assert not list((tmp_path / "pages" / "_raw").glob(".*.tmp"))


def _normalized_page_set() -> tuple[Any, Any, Any]:
    root = normalize_confluence_page(
        _raw_page(
            page_id="100",
            title="Root Page",
            parent_id=None,
            body_text=("Root", None),
            webui="/wiki/spaces/DOC/pages/100/Root",
        ),
        site_url="https://example.atlassian.net",
    )
    page = normalize_confluence_page(
        _raw_page(),
        footer_comments=_footer_comments(),
        inline_comments=_inline_comments(),
        attachments=_attachments(),
        labels=_labels(),
        ancestors=[_ancestor_ref()],
        child_pages=[_child_ref(), _whiteboard_ref()],
        site_url="https://example.atlassian.net",
    )
    child = normalize_confluence_page(
        _raw_page(
            page_id="124",
            title="Child Page",
            parent_id="123",
            body_text=("Child", None),
            webui="/wiki/spaces/DOC/pages/124/Child",
        ),
        ancestors=[_ancestor_ref(), _child_parent_ref()],
        site_url="https://example.atlassian.net",
    )
    return root, page, child


def _raw_page(
    *,
    page_id: str = "123",
    title: str = "Launch *Plan* [Q3]",
    parent_id: str | None = "100",
    body_text: tuple[str, str | None] = ("Hello ", "world"),
    webui: str = "/wiki/spaces/DOC/pages/123/Launch+Plan",
) -> dict[str, Any]:
    first, strong = body_text
    return {
        "id": page_id,
        "title": title,
        "status": "current",
        "spaceId": "space-1",
        "spaceKey": "DOC",
        "parentId": parent_id,
        "authorId": "user-1",
        "ownerId": "owner-1",
        "createdAt": "2026-07-01T08:00:00.000+0000",
        "updatedAt": "2026-07-01T10:00:00.000+0000",
        "version": {"number": 7, "createdAt": "2026-07-01T10:00:00.000+0000"},
        "body": {"atlas_doc_format": {"value": _adf_doc(first, strong)}},
        "_links": {"webui": webui},
        "metadata": {"properties": {"owner": "ai"}},
    }


def _adf_doc(first: str, strong: str | None) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": first}]
    if strong:
        content.append({"type": "text", "text": strong, "marks": [{"type": "strong"}]})
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": content}],
    }


def _ancestor_ref() -> dict[str, Any]:
    return {
        "id": "100",
        "title": "Root Page",
        "spaceKey": "DOC",
        "_links": {"webui": "/wiki/spaces/DOC/pages/100/Root"},
    }


def _child_parent_ref() -> dict[str, Any]:
    return {
        "id": "123",
        "title": "Launch *Plan* [Q3]",
        "spaceKey": "DOC",
        "_links": {"webui": "/wiki/spaces/DOC/pages/123/Launch+Plan"},
    }


def _child_ref() -> dict[str, Any]:
    return {
        "id": "124",
        "title": "Child Page",
        "type": "page",
        "parentId": "123",
        "spaceKey": "DOC",
        "_links": {"webui": "/wiki/spaces/DOC/pages/124/Child"},
    }


def _whiteboard_ref() -> dict[str, Any]:
    return {"id": "board-1", "title": "Board", "type": "whiteboard"}


def _labels() -> list[dict[str, Any]]:
    return [
        {"id": "label-2", "prefix": "team", "name": "beta"},
        {"id": "label-1", "prefix": "global", "name": "alpha"},
    ]


def _labels_sorted_raw() -> list[dict[str, Any]]:
    return [
        {"id": "label-1", "prefix": "global", "name": "alpha"},
        {"id": "label-2", "prefix": "team", "name": "beta"},
    ]


def _attachments() -> list[dict[str, Any]]:
    return [
        {
            "id": "att-1",
            "title": "design.png",
            "mediaType": "image/png",
            "fileSize": 42,
            "createdAt": "2026-07-01T09:00:00.000+0000",
            "author": {"displayName": "File Person"},
            "local_path": "../../attachments/123/att-1-design.png",
        }
    ]


def _footer_comments() -> list[dict[str, Any]]:
    return [
        {
            "id": "2",
            "author": {"displayName": "Alex Agent"},
            "createdAt": "2026-07-01T13:00:00.000+0000",
            "updatedAt": "2026-07-01T13:00:00.000+0000",
            "status": "current",
            "body": {"atlas_doc_format": {"value": _adf_doc("Second footer", None)}},
        },
        {
            "id": "1",
            "author": {"displayName": "Rae Reporter"},
            "createdAt": "2026-07-01T12:00:00.000+0000",
            "updatedAt": "2026-07-01T12:05:00.000+0000",
            "status": "current",
            "body": {"atlas_doc_format": {"value": _adf_doc("First footer", None)}},
        },
    ]


def _inline_comments() -> list[dict[str, Any]]:
    return [
        {
            "id": "10",
            "author": {"displayName": "Ivy Inline"},
            "createdAt": "2026-07-01T14:00:00.000+0000",
            "status": "open",
            "resolutionStatus": "open",
            "body": {"atlas_doc_format": {"value": _adf_doc("Inline note", None)}},
        }
    ]
