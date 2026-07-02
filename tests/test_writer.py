from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlassian_md_export.models import NormalizedJiraIssue
from atlassian_md_export.renderer import AdfMarkdownRenderer
from atlassian_md_export.writer import FRONTMATTER_FIELDS
from atlassian_md_export.writer import STABLE_EXPORTED_AT
from atlassian_md_export.writer import initialize_output
from atlassian_md_export.writer import issue_content_hash
from atlassian_md_export.writer import issue_raw_export_json
from atlassian_md_export.writer import normalize_jira_issue
from atlassian_md_export.writer import render_issue_markdown
from atlassian_md_export.writer import write_issue_files


def test_representative_issue_markdown_snapshot() -> None:
    issue = _normalized_issue()
    renderer = AdfMarkdownRenderer()
    content_hash = issue_content_hash(issue, renderer=renderer)

    markdown = render_issue_markdown(issue, renderer=renderer, stable_exported_at=True)

    assert markdown == f"""---
schema_version: 1
source: jira-cloud:example.atlassian.net
key: ABC-1
id: issue-10001
url: https://example.atlassian.net/browse/ABC-1
project: ABC
issue_type: Story
status: In Progress
priority: null
assignee: Alex Agent
reporter: Rae Reporter
created: 2026-07-01T10:00:00.000+0000
updated: 2026-07-01T11:00:00.000+0000
resolution: null
resolutiondate: null
labels:
- alpha
- zeta
components:
- Backend
fix_versions:
- '2.0'
versions:
- '1.0'
parent: ABC-0
epic: EPIC-1
comment_count: 2
attachment_count: 1
exported_at: '1970-01-01T00:00:00Z'
content_hash: {content_hash}
---

# ABC-1: Export \\*bold\\* data

## Summary

Export \\*bold\\* data

## Description

Hello @Ada

## Key Fields

- Type: Story
- Status: In Progress
- Priority: null
- Assignee: Alex Agent
- Reporter: Rae Reporter
- Created: 2026-07-01T10:00:00.000+0000
- Updated: 2026-07-01T11:00:00.000+0000
- Resolution: null
- Resolution Date: null
- Labels: alpha, zeta
- Components: Backend
- Fix Versions: 2.0
- Versions: 1.0
- Parent: ABC-0
- Epic: EPIC-1
- Story Points: 8

## Links

- blocks: [ABC-2](https://example.atlassian.net/browse/ABC-2) - Other issue - To Do

## Subtasks

- ABC-3 - Subtask summary - Done

## Attachments

- debug.log (id=att-1, mime=text/plain, size=12, created=2026-07-01T09:00:00.000+0000, author=File Person)

## Raw Field Notes

- Story Points (`customfield_10016`): 8

## Comments

### Comment 1 — Rae Reporter — 2026-07-01T12:00:00.000+0000

- Comment ID: 1
- Updated: 2026-07-01T12:05:00.000+0000
- Visibility: role:Developers

First comment

### Comment 2 — Alex Agent — 2026-07-01T13:00:00.000+0000

- Comment ID: 2

Second comment
"""


def test_frontmatter_order_and_section_order_are_stable() -> None:
    markdown = render_issue_markdown(_normalized_issue(), stable_exported_at=True)
    frontmatter = markdown.split("---\n", 2)[1]
    payload = yaml.safe_load(frontmatter)
    assert tuple(payload) == FRONTMATTER_FIELDS

    body = markdown.split("---\n", 2)[2]
    expected_sections = [
        "# ABC-1: Export \\*bold\\* data",
        "## Summary",
        "## Description",
        "## Key Fields",
        "## Links",
        "## Subtasks",
        "## Attachments",
        "## Raw Field Notes",
        "## Comments",
    ]
    positions = [body.index(section) for section in expected_sections]
    assert positions == sorted(positions)


def test_issue_markdown_renders_description_and_comment_task_lists() -> None:
    issue = _normalized_issue()
    description_adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "taskList",
                "attrs": {"localId": "description-list"},
                "content": [
                    {
                        "type": "taskItem",
                        "attrs": {"localId": "description-todo", "state": "TODO"},
                        "content": [{"type": "text", "text": "Document acceptance"}],
                    },
                    {
                        "type": "taskItem",
                        "attrs": {"localId": "description-done", "state": "DONE"},
                        "content": [
                            {"type": "text", "text": "Review "},
                            {
                                "type": "text",
                                "text": "ADF",
                                "marks": [{"type": "strong"}],
                            },
                        ],
                    },
                ],
            }
        ],
    }
    comment_adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "taskList",
                "attrs": {"localId": "comment-list"},
                "content": [
                    {
                        "type": "taskItem",
                        "attrs": {"localId": "comment-done", "state": "DONE"},
                        "content": [{"type": "text", "text": "Confirm export"}],
                    }
                ],
            }
        ],
    }
    issue = issue.model_copy(
        update={
            "description_adf": description_adf,
            "comments": [issue.comments[0].model_copy(update={"body_adf": comment_adf})],
        }
    )

    markdown = render_issue_markdown(issue, stable_exported_at=True)

    assert (
        "## Description\n\n"
        "- [ ] Document acceptance\n"
        "- [x] Review **ADF**\n\n"
        "## Key Fields"
    ) in markdown
    assert (
        "### Comment 1 — Rae Reporter — 2026-07-01T12:00:00.000+0000\n\n"
        "- Comment ID: 1\n"
        "- Updated: 2026-07-01T12:05:00.000+0000\n"
        "- Visibility: role:Developers\n\n"
        "- [x] Confirm export"
    ) in markdown


def test_stable_exported_at_and_content_hash_ignore_export_timestamp() -> None:
    issue = _normalized_issue()
    first = render_issue_markdown(
        issue,
        exported_at="2026-07-01T00:00:00Z",
    )
    second = render_issue_markdown(
        issue,
        exported_at="2026-07-02T00:00:00Z",
    )
    stable_first = render_issue_markdown(
        issue,
        stable_exported_at=True,
        exported_at="2026-07-01T00:00:00Z",
    )
    stable_second = render_issue_markdown(
        issue,
        stable_exported_at=True,
        exported_at="2026-07-02T00:00:00Z",
    )

    first_frontmatter = yaml.safe_load(first.split("---\n", 2)[1])
    second_frontmatter = yaml.safe_load(second.split("---\n", 2)[1])
    assert first_frontmatter["exported_at"] == "2026-07-01T00:00:00Z"
    assert second_frontmatter["exported_at"] == "2026-07-02T00:00:00Z"
    assert first_frontmatter["content_hash"] == second_frontmatter["content_hash"]
    assert stable_first == stable_second
    assert yaml.safe_load(stable_first.split("---\n", 2)[1])["exported_at"] == STABLE_EXPORTED_AT


def test_attachment_local_path_changes_markdown_content_hash() -> None:
    issue_without_download = _normalized_issue()
    issue_with_download = issue_without_download.model_copy(
        update={
            "attachments": [
                attachment.model_copy(
                    update={"local_path": "../attachments/ABC-1/att-1-debug.log"}
                )
                for attachment in issue_without_download.attachments
            ]
        },
    )

    without_download = render_issue_markdown(
        issue_without_download,
        stable_exported_at=True,
    )
    with_download = render_issue_markdown(
        issue_with_download,
        stable_exported_at=True,
    )
    without_frontmatter = yaml.safe_load(without_download.split("---\n", 2)[1])
    with_frontmatter = yaml.safe_load(with_download.split("---\n", 2)[1])

    assert issue_without_download.raw_issue == issue_with_download.raw_issue
    assert " - [local file](../attachments/ABC-1/att-1-debug.log)" not in without_download
    assert " - [local file](../attachments/ABC-1/att-1-debug.log)" in with_download
    assert without_frontmatter["content_hash"] != with_frontmatter["content_hash"]
    assert issue_content_hash(issue_without_download) != issue_content_hash(issue_with_download)


def test_raw_issue_export_json_preserves_required_source_material() -> None:
    issue = _normalized_issue()
    exported_at = "2026-07-01T12:00:00Z"

    raw_json = issue_raw_export_json(
        issue,
        stable_exported_at=True,
        exported_at=exported_at,
    )
    payload = json.loads(raw_json)

    assert raw_json.endswith("\n")
    assert payload["raw_issue"] == _raw_issue()
    assert [comment["id"] for comment in payload["fetched_comments"]] == ["1", "2"]
    assert payload["raw_adf"]["description"] == _raw_issue()["fields"]["description"]
    assert payload["raw_adf"]["comments"][0]["body"] == _comments()[1]["body"]
    assert payload["attachment_metadata"][0]["raw"] == _raw_issue()["fields"]["attachment"][0]
    assert payload["exporter"] == {
        "exported_at": exported_at,
        "name": "atlassian-md-export",
        "site_host": "example.atlassian.net",
        "source": "jira-cloud:example.atlassian.net",
        "version": "0.1.0",
    }


def test_initialize_output_migrates_legacy_issue_json_to_raw_dir(tmp_path: Path) -> None:
    legacy_path = tmp_path / "issues" / "ABC-1.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text('{"raw_issue":{"key":"ABC-1"}}\n', encoding="utf-8")

    initialize_output(tmp_path)

    migrated_path = tmp_path / "issues" / "_raw" / "ABC-1.json"
    assert migrated_path.read_text(encoding="utf-8") == '{"raw_issue":{"key":"ABC-1"}}\n'
    assert not legacy_path.exists()


def test_write_issue_files_uses_atomic_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    issue = _normalized_issue()
    original_replace = os.replace
    replaced: list[tuple[str, str]] = []

    def recording_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replaced.append((Path(src).name, Path(dst).name))
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", recording_replace)

    result = write_issue_files(
        tmp_path,
        issue,
        stable_exported_at=True,
        exported_at="2026-07-01T12:00:00Z",
    )

    assert result.exported_at == "2026-07-01T12:00:00Z"
    frontmatter = yaml.safe_load(result.markdown_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert frontmatter["exported_at"] == STABLE_EXPORTED_AT
    assert result.markdown_path == tmp_path / "issues" / "ABC-1.md"
    assert result.json_path == tmp_path / "issues" / "_raw" / "ABC-1.json"
    assert result.markdown_path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(result.json_path.read_text(encoding="utf-8"))["raw_issue"]["key"] == "ABC-1"
    assert not (tmp_path / "issues" / "ABC-1.json").exists()
    assert [destination for _source, destination in replaced] == ["ABC-1.md", "ABC-1.json"]
    assert not list((tmp_path / "issues").glob(".*.tmp"))
    assert not list((tmp_path / "issues" / "_raw").glob(".*.tmp"))


def _normalized_issue() -> NormalizedJiraIssue:
    return normalize_jira_issue(
        _raw_issue(),
        comments=_comments(),
        site_url="https://example.atlassian.net",
        custom_fields={"customfield_10016": "Story Points"},
    )


def _raw_issue() -> dict[str, Any]:
    return {
        "id": "issue-10001",
        "key": "ABC-1",
        "self": "https://example.atlassian.net/rest/api/3/issue/issue-10001",
        "fields": {
            "summary": "Export *bold* data",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Hello "},
                            {"type": "mention", "attrs": {"text": "Ada"}},
                        ],
                    }
                ],
            },
            "project": {"key": "ABC"},
            "issuetype": {"name": "Story"},
            "status": {"name": "In Progress"},
            "priority": None,
            "assignee": {"displayName": "Alex Agent"},
            "reporter": {"displayName": "Rae Reporter"},
            "created": "2026-07-01T10:00:00.000+0000",
            "updated": "2026-07-01T11:00:00.000+0000",
            "resolution": None,
            "resolutiondate": None,
            "labels": ["zeta", "alpha"],
            "components": [{"name": "Backend"}],
            "fixVersions": [{"name": "2.0"}],
            "versions": [{"name": "1.0"}],
            "parent": {"key": "ABC-0"},
            "customfield_10014": "EPIC-1",
            "customfield_10016": 8,
            "issuelinks": [
                {
                    "type": {"outward": "blocks"},
                    "outwardIssue": {
                        "key": "ABC-2",
                        "fields": {
                            "summary": "Other issue",
                            "status": {"name": "To Do"},
                        },
                    },
                }
            ],
            "subtasks": [
                {
                    "key": "ABC-3",
                    "fields": {
                        "summary": "Subtask summary",
                        "status": {"name": "Done"},
                    },
                }
            ],
            "attachment": [
                {
                    "id": "att-1",
                    "filename": "debug.log",
                    "mimeType": "text/plain",
                    "size": 12,
                    "created": "2026-07-01T09:00:00.000+0000",
                    "author": {"displayName": "File Person"},
                    "content": "https://example.atlassian.net/secure/attachment/att-1/debug.log",
                }
            ],
        },
    }


def _comments() -> list[dict[str, Any]]:
    return [
        {
            "id": "2",
            "author": {"displayName": "Alex Agent"},
            "created": "2026-07-01T13:00:00.000+0000",
            "updated": "2026-07-01T13:00:00.000+0000",
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Second comment"}],
                    }
                ],
            },
        },
        {
            "id": "1",
            "author": {"displayName": "Rae Reporter"},
            "created": "2026-07-01T12:00:00.000+0000",
            "updated": "2026-07-01T12:05:00.000+0000",
            "visibility": {"type": "role", "value": "Developers"},
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "First comment"}],
                    }
                ],
            },
        },
    ]
