"""Shared data models for local export state and manifest files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class GeneratorInfo(BaseModel):
    name: str
    version: str


class OutputMetadata(BaseModel):
    path: str
    layout_version: int = 1


class ExportCounts(BaseModel):
    issues: int = 0
    comments: int = 0
    attachments: int = 0


class Manifest(BaseModel):
    schema_version: int = 1
    generator: GeneratorInfo
    jira_site_host: str | None = None
    output: OutputMetadata
    last_successful_representative_run: dict[str, Any] | None = None
    exported_issue_keys: list[str] = Field(default_factory=list)
    counts: ExportCounts = Field(default_factory=ExportCounts)
    hashes: dict[str, str] = Field(default_factory=dict)


class InitResult(BaseModel):
    out_dir: Path
    directories: list[Path]
    manifest_path: Path
    state_path: Path
    manifest_created: bool


class NormalizedJiraComment(BaseModel):
    id: str | None = None
    author_display_name: str | None = None
    created: str | None = None
    updated: str | None = None
    visibility: str | None = None
    body_adf: dict[str, Any] | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NormalizedJiraAttachment(BaseModel):
    id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    created: str | None = None
    author_display_name: str | None = None
    content_url: str | None = None
    local_path: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NormalizedJiraIssueLink(BaseModel):
    relationship: str
    key: str | None = None
    url: str | None = None
    summary: str | None = None
    status: str | None = None


class NormalizedJiraSubtask(BaseModel):
    key: str
    summary: str | None = None
    status: str | None = None


class NormalizedCustomField(BaseModel):
    field_id: str
    label: str
    value: str


class NormalizedJiraIssue(BaseModel):
    key: str
    id: str
    source: str
    site_host: str | None = None
    url: str | None = None
    project: str | None = None
    summary: str = ""
    issue_type: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    created: str | None = None
    updated: str | None = None
    resolution: str | None = None
    resolutiondate: str | None = None
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    fix_versions: list[str] = Field(default_factory=list)
    versions: list[str] = Field(default_factory=list)
    parent: str | None = None
    epic: str | None = None
    description_adf: dict[str, Any] | None = None
    comments: list[NormalizedJiraComment] = Field(default_factory=list)
    attachments: list[NormalizedJiraAttachment] = Field(default_factory=list)
    links: list[NormalizedJiraIssueLink] = Field(default_factory=list)
    subtasks: list[NormalizedJiraSubtask] = Field(default_factory=list)
    custom_fields: list[NormalizedCustomField] = Field(default_factory=list)
    raw_issue: dict[str, Any] = Field(default_factory=dict)


class IssueWriteResult(BaseModel):
    markdown_path: Path
    json_path: Path
    content_hash: str
    markdown_hash: str
    raw_json_hash: str
    exported_at: str


class NormalizedConfluencePageReference(BaseModel):
    id: str
    title: str | None = None
    space_key: str | None = None
    url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NormalizedConfluenceLabel(BaseModel):
    id: str | None = None
    prefix: str | None = None
    name: str
    raw: dict[str, Any] = Field(default_factory=dict)


class NormalizedConfluenceAttachment(BaseModel):
    id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    created: str | None = None
    author_display_name: str | None = None
    download_url: str | None = None
    local_path: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NormalizedConfluenceComment(BaseModel):
    id: str | None = None
    author_display_name: str | None = None
    created: str | None = None
    updated: str | None = None
    status: str | None = None
    resolution_status: str | None = None
    body_adf: dict[str, Any] | None = None
    body_representation: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class NormalizedConfluencePage(BaseModel):
    id: str
    source: str
    site_host: str | None = None
    url: str | None = None
    title: str = ""
    space_key: str | None = None
    space_id: str | None = None
    status: str | None = None
    parent: NormalizedConfluencePageReference | None = None
    ancestors: list[NormalizedConfluencePageReference] = Field(default_factory=list)
    version: int | None = None
    author: str | None = None
    owner: str | None = None
    created: str | None = None
    updated: str | None = None
    labels: list[NormalizedConfluenceLabel] = Field(default_factory=list)
    child_pages: list[NormalizedConfluencePageReference] = Field(default_factory=list)
    footer_comments: list[NormalizedConfluenceComment] = Field(default_factory=list)
    inline_comments: list[NormalizedConfluenceComment] = Field(default_factory=list)
    attachments: list[NormalizedConfluenceAttachment] = Field(default_factory=list)
    body_adf: dict[str, Any] | None = None
    body_representation: str | None = None
    raw_page: dict[str, Any] = Field(default_factory=dict)


class ConfluencePageWriteResult(BaseModel):
    markdown_path: Path
    json_path: Path
    content_hash: str
    markdown_hash: str
    raw_json_hash: str
    exported_at: str
