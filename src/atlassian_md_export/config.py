"""Configuration and .env loading for Atlassian Markdown export commands."""

from __future__ import annotations

from collections.abc import Mapping
import os
import shlex
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr

JIRA_CONFIG_CANDIDATES = (
    "jira-md-export.yaml",
    "atlassian-md-export.yaml",
    ".jira-md-export.yaml",
)
CONFLUENCE_CONFIG_CANDIDATES = (
    "confluence-md-export.yaml",
    "atlassian-md-export.yaml",
    ".confluence-md-export.yaml",
)
CONFIG_CANDIDATES = JIRA_CONFIG_CANDIDATES
DEFAULT_FIELD_INCLUDE = (
    "summary",
    "description",
    "issuetype",
    "status",
    "priority",
    "assignee",
    "reporter",
    "creator",
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
    "attachment",
    "subtasks",
    "project",
)


class FieldsConfig(BaseModel):
    include: list[str] = Field(default_factory=lambda: list(DEFAULT_FIELD_INCLUDE))


class SyncConfig(BaseModel):
    overlap_minutes: int = Field(default=10, ge=0)
    concurrency: int = 4
    download_attachments: bool = False


class MarkdownConfig(BaseModel):
    stable_exported_at: bool = False
    include_raw_adf_on_unknown_nodes: bool = True


class ContentConfig(BaseModel):
    body_format: str = "atlas_doc_format"
    include_footer_comments: bool = True
    include_inline_comments: bool = True
    include_resolved_inline_comments: bool = True


class ExportConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    site: str | None = None
    project: str | None = None
    space: str | None = None
    out: Path | None = None
    content: ContentConfig = Field(default_factory=ContentConfig)
    fields: FieldsConfig = Field(default_factory=FieldsConfig)
    custom_fields: dict[str, str] = Field(default_factory=dict)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    markdown: MarkdownConfig = Field(default_factory=MarkdownConfig)


class MissingConfluenceCredentialsError(ValueError):
    """Raised when required Confluence credential values are absent."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing required environment variable(s): {', '.join(missing)}")


class ConfluenceCredentials(BaseModel):
    email: str
    api_token: SecretStr

    @classmethod
    def from_environment(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> "ConfluenceCredentials":
        values = env if env is not None else os.environ
        email = values.get("CONFLUENCE_EMAIL") or values.get("ATLASSIAN_EMAIL")
        api_token = values.get("CONFLUENCE_API_TOKEN") or values.get("ATLASSIAN_API_TOKEN")
        missing: list[str] = []
        if not email:
            missing.append("CONFLUENCE_EMAIL or ATLASSIAN_EMAIL")
        if not api_token:
            missing.append("CONFLUENCE_API_TOKEN or ATLASSIAN_API_TOKEN")
        if missing:
            raise MissingConfluenceCredentialsError(missing)
        assert email is not None
        assert api_token is not None
        return cls(email=email, api_token=SecretStr(api_token))


def load_config(
    path: Path | None = None,
    cwd: Path | None = None,
    candidates: tuple[str, ...] = CONFIG_CANDIDATES,
) -> ExportConfig:
    """Load YAML config from an explicit path or the first default candidate present."""

    config_path = _find_config_path(path, cwd or Path.cwd(), candidates)
    if config_path is None:
        return ExportConfig()

    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {config_path}")

    return ExportConfig.model_validate(raw)


def load_confluence_config(path: Path | None = None, cwd: Path | None = None) -> ExportConfig:
    """Load Confluence YAML config from an explicit path or default candidates."""

    return load_config(path, cwd, CONFLUENCE_CONFIG_CANDIDATES)


def load_dotenv(path: Path | None = None) -> set[str]:
    """Load a local .env file without overriding real environment variables."""

    dotenv_path = path or Path.cwd() / ".env"
    if not dotenv_path.exists():
        return set()

    loaded: set[str] = set()
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if key not in os.environ:
            os.environ[key] = value
            loaded.add(key)
    return loaded


def _find_config_path(path: Path | None, cwd: Path, candidates: tuple[str, ...]) -> Path | None:
    if path is not None:
        return path
    for candidate in candidates:
        candidate_path = cwd / candidate
        if candidate_path.exists():
            return candidate_path
    return None


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    if "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None

    value = _parse_dotenv_value(raw_value.strip())
    return key, value


def _parse_dotenv_value(raw_value: str) -> str:
    if not raw_value:
        return ""
    try:
        values = shlex.split(raw_value, comments=True, posix=True)
    except ValueError:
        return raw_value.strip("\"'")
    if not values:
        return ""
    return values[0]
