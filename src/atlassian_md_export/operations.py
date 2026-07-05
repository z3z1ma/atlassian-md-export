"""Command orchestration for Jira Markdown exports."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import TypeGuard
from urllib.parse import unquote
from urllib.parse import urlparse

import yaml

from atlassian_md_export import __version__
from atlassian_md_export.attachments import attachment_path
from atlassian_md_export.attachments import attachment_relative_path
from atlassian_md_export.attachments import confluence_attachment_path
from atlassian_md_export.attachments import should_download_attachment
from atlassian_md_export.client import AtlassianClientError
from atlassian_md_export.client import AtlassianHttpClient
from atlassian_md_export.client import JiraCredentials
from atlassian_md_export.config import ConfluenceCredentials
from atlassian_md_export.config import DEFAULT_FIELD_INCLUDE
from atlassian_md_export.config import ExportConfig
from atlassian_md_export.confluence.client import ConfluenceClient
from atlassian_md_export.confluence.client import ConfluencePage
from atlassian_md_export.confluence.client import confluence_updated_since_cql
from atlassian_md_export.indexes import confluence_required_index_paths
from atlassian_md_export.indexes import generate_confluence_indexes
from atlassian_md_export.indexes import generate_indexes
from atlassian_md_export.indexes import required_index_paths
from atlassian_md_export.jira.client import JiraClient
from atlassian_md_export.jira.client import exact_issue_jql
from atlassian_md_export.jira.client import ordered_jql
from atlassian_md_export.jira.client import project_jql
from atlassian_md_export.jira.client import updated_since_jql
from atlassian_md_export.models import ExportCounts
from atlassian_md_export.models import GeneratorInfo
from atlassian_md_export.models import InitResult
from atlassian_md_export.models import Manifest
from atlassian_md_export.models import NormalizedConfluenceAttachment
from atlassian_md_export.models import NormalizedConfluencePage
from atlassian_md_export.models import NormalizedJiraAttachment
from atlassian_md_export.models import NormalizedJiraIssue
from atlassian_md_export.models import OutputMetadata
from atlassian_md_export.payloads import confluence_payload_space_key
from atlassian_md_export.payloads import confluence_payload_url
from atlassian_md_export.payloads import dict_list
from atlassian_md_export.renderer import AdfMarkdownRenderer
from atlassian_md_export.state import ConfluencePageState
from atlassian_md_export.state import ConfluenceSyncDecision
from atlassian_md_export.state import IssueState
from atlassian_md_export.state import SyncDecision
from atlassian_md_export.state import clear_confluence_page_export_artifacts
from atlassian_md_export.state import clear_issue_export_artifacts
from atlassian_md_export.state import confluence_representative_page_ids
from atlassian_md_export.state import decide_confluence_incremental_sync
from atlassian_md_export.state import decide_incremental_sync
from atlassian_md_export.state import finish_confluence_export_run
from atlassian_md_export.state import finish_export_run
from atlassian_md_export.state import initialize_state
from atlassian_md_export.state import latest_successful_confluence_representative_run
from atlassian_md_export.state import latest_successful_representative_run
from atlassian_md_export.state import now_iso
from atlassian_md_export.state import start_confluence_export_run
from atlassian_md_export.state import start_export_run
from atlassian_md_export.state import upsert_confluence_page_state
from atlassian_md_export.state import upsert_issue_state
from atlassian_md_export.writer import atomic_write_bytes
from atlassian_md_export.writer import atomic_write_text
from atlassian_md_export.writer import canonical_json
from atlassian_md_export.writer import confluence_page_markdown_path
from atlassian_md_export.writer import confluence_page_raw_dir
from atlassian_md_export.writer import confluence_page_raw_path
from atlassian_md_export.writer import initialize_output
from atlassian_md_export.writer import issue_markdown_path
from atlassian_md_export.writer import issue_raw_dir
from atlassian_md_export.writer import issue_raw_path
from atlassian_md_export.writer import manifest_json
from atlassian_md_export.writer import normalize_confluence_page
from atlassian_md_export.writer import normalize_jira_issue
from atlassian_md_export.writer import write_confluence_page_files
from atlassian_md_export.writer import write_issue_files

logger = logging.getLogger(__name__)

_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CONFLUENCE_OUTPUT_DIRECTORIES = ("pages", "pages/_raw", "attachments", "indexes")


class ExportCommandError(RuntimeError):
    """Raised for friendly CLI errors that do not need a traceback."""


@dataclass(frozen=True)
class AttachmentOptions:
    download: bool = False
    max_mb: float | None = None
    include_patterns: tuple[str, ...] = ()

    @property
    def max_bytes(self) -> int | None:
        if self.max_mb is None:
            return None
        return int(self.max_mb * 1024 * 1024)


@dataclass(frozen=True)
class ExportSummary:
    issue_keys: tuple[str, ...]
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConfluenceExportSummary:
    page_ids: tuple[str, ...]
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationResult:
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class CleanResult:
    removed_issue_keys: tuple[str, ...]


@dataclass(frozen=True)
class ConfluenceCleanResult:
    removed_page_ids: tuple[str, ...]


@dataclass(frozen=True)
class _PreparedConfluenceAttachmentDownload:
    attachment_index: int
    target_path: Path
    relative_path: str
    content: bytes


@dataclass(frozen=True)
class _PreparedConfluencePage:
    page: NormalizedConfluencePage | None
    attachment_downloads: tuple[_PreparedConfluenceAttachmentDownload, ...] = ()
    failures: tuple[str, ...] = ()


def build_jira_client(site_url: str) -> JiraClient:
    return JiraClient(
        AtlassianHttpClient(
            site_url,
            JiraCredentials.from_environment(),
        )
    )


def build_confluence_client(site_url: str) -> ConfluenceClient:
    return ConfluenceClient(
        AtlassianHttpClient(
            site_url,
            ConfluenceCredentials.from_environment(),
            provider_name="Confluence",
            auth_hint="Check CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN, and site access.",
        )
    )


def initialize_confluence_output(out_dir: Path) -> InitResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_out = out_dir.resolve()

    directories = [resolved_out / name for name in CONFLUENCE_OUTPUT_DIRECTORIES]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    state_path = resolved_out / "state.sqlite"
    initialize_state(state_path)

    manifest_path = resolved_out / "manifest.json"
    manifest_created = False
    if not manifest_path.exists():
        atomic_write_text(manifest_path, canonical_json(_confluence_manifest_payload(resolved_out)))
        manifest_created = True

    return InitResult(
        out_dir=resolved_out,
        directories=directories,
        manifest_path=manifest_path,
        state_path=state_path,
        manifest_created=manifest_created,
    )


def run_confluence_pull(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    site_url: str,
    config: ExportConfig,
    space: str | None = None,
    cql: str | None = None,
    ancestor: str | None = None,
    page: str | None = None,
    since: str | None = None,
    force: bool = False,
    concurrency: int = 4,
    attachment_options: AttachmentOptions = AttachmentOptions(),
) -> ConfluenceExportSummary:
    worker_count = max(1, concurrency)
    scope_type, scope_value, exact_page_ids = _confluence_pull_scope(
        space=space,
        cql=cql,
        ancestor=ancestor,
        page=page,
    )
    return _run_confluence_page_export(
        out_dir,
        client=client,
        site_url=site_url,
        config=config,
        command="pull",
        scope_type=scope_type,
        scope_value=scope_value,
        since=since,
        force=force,
        exact_page_ids=exact_page_ids,
        concurrency=worker_count,
        attachment_options=attachment_options,
    )


def run_confluence_page(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    site_url: str,
    config: ExportConfig,
    page_ids: Iterable[str],
) -> ConfluenceExportSummary:
    normalized = _normalized_page_ids(page_ids)
    return _run_confluence_page_export(
        out_dir,
        client=client,
        site_url=site_url,
        config=config,
        command="page",
        scope_type="page",
        scope_value=",".join(normalized),
        since=None,
        force=True,
        exact_page_ids=normalized,
        concurrency=1,
        attachment_options=AttachmentOptions(),
    )


def run_confluence_comments(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    site_url: str,
    config: ExportConfig,
    page_ids: Iterable[str],
    force: bool,
) -> ConfluenceExportSummary:
    if not force:
        raise ExportCommandError("comments requires --force so comment refresh is explicit.")
    normalized = _normalized_page_ids(page_ids)
    result = initialize_confluence_output(out_dir)
    run_id = start_confluence_export_run(
        result.state_path,
        command="comments",
        scope_type="page",
        scope_value=",".join(normalized),
        force=True,
        exact_page_ids=normalized,
    )
    _log_confluence(
        logging.INFO,
        "started confluence comments export",
        command="comments",
        site_url=site_url,
        operation="confluence_export_start",
        page_ids=normalized,
        output_path=result.out_dir,
    )
    failures: list[str] = []
    written: list[str] = []
    try:
        for page_id in normalized:
            try:
                local = _read_local_confluence_page_source(result.out_dir, page_id)
                footer_comments = (
                    _fetch_confluence_footer_comments(
                        client,
                        page_id,
                        command="comments",
                        site_url=site_url,
                        body_format=config.content.body_format,
                    )
                    if config.content.include_footer_comments
                    else ()
                )
                inline_comments = (
                    _fetch_inline_comments(
                        client,
                        page_id,
                        config=config,
                        command="comments",
                        site_url=site_url,
                    )
                    if config.content.include_inline_comments
                    else ()
                )
                page = normalize_confluence_page(
                    local.raw_page,
                    footer_comments=footer_comments,
                    inline_comments=inline_comments,
                    attachments=local.attachments,
                    labels=local.labels,
                    ancestors=local.ancestors,
                    child_pages=local.child_pages,
                    site_url=site_url,
                    space_key=local.space_key,
                    url=local.url,
                )
                _write_confluence_page(
                    result.out_dir,
                    result.state_path,
                    page,
                    config,
                    exported_pages=_local_confluence_exported_pages(
                        result.out_dir,
                        replacement=page,
                        site_url=site_url,
                    ),
                    command="comments",
                    site_url=site_url,
                )
                written.append(page.id)
            except (AtlassianClientError, OSError, ValueError) as error:
                failures.append(f"{page_id}: {error}")

        generate_confluence_indexes(result.out_dir)
        if failures:
            finish_confluence_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message="; ".join(failures),
            )
            update_confluence_manifest(result.out_dir, site_host=_site_host(site_url))
            raise ExportCommandError(
                _partial_failure_message("comments", failures, provider="confluence")
            )

        finish_confluence_export_run(result.state_path, run_id, succeeded=True)
        update_confluence_manifest(result.out_dir, site_host=_site_host(site_url))
        _log_confluence(
            logging.INFO,
            "finished confluence comments export",
            command="comments",
            site_url=site_url,
            operation="confluence_export_finish",
            page_count=len(written),
            output_path=result.out_dir,
        )
        return ConfluenceExportSummary(page_ids=tuple(sorted(written)))
    except Exception as error:
        if not isinstance(error, ExportCommandError):
            finish_confluence_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message=str(error),
            )
        raise


def run_confluence_attachments(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    site_url: str,
    config: ExportConfig,
    page_ids: Iterable[str],
    attachment_options: AttachmentOptions,
) -> ConfluenceExportSummary:
    normalized = _normalized_page_ids(page_ids)
    result = initialize_confluence_output(out_dir)
    run_id = start_confluence_export_run(
        result.state_path,
        command="attachments",
        scope_type="page",
        scope_value=",".join(normalized),
        force=True,
        exact_page_ids=normalized,
    )
    active_options = AttachmentOptions(
        download=True,
        max_mb=attachment_options.max_mb,
        include_patterns=attachment_options.include_patterns,
    )
    _log_confluence(
        logging.INFO,
        "started confluence attachments export",
        command="attachments",
        site_url=site_url,
        operation="confluence_export_start",
        page_ids=normalized,
        output_path=result.out_dir,
    )
    failures: list[str] = []
    written: list[str] = []
    try:
        for page_id in normalized:
            try:
                local = _read_local_confluence_page_source(result.out_dir, page_id)
                _log_confluence(
                    logging.DEBUG,
                    "fetching confluence attachment metadata",
                    command="attachments",
                    site_url=site_url,
                    operation="confluence_attachment_metadata_fetch",
                    page_id=page_id,
                )
                attachments = list(client.fetch_attachment_metadata(page_id))
                page = normalize_confluence_page(
                    local.raw_page,
                    footer_comments=local.footer_comments,
                    inline_comments=local.inline_comments,
                    attachments=attachments,
                    labels=local.labels,
                    ancestors=local.ancestors,
                    child_pages=local.child_pages,
                    site_url=site_url,
                    space_key=local.space_key,
                    url=local.url,
                )
                page, downloads, download_failures = _prepare_confluence_attachment_downloads(
                    result.out_dir,
                    client=client,
                    page=page,
                    options=active_options,
                    command="attachments",
                    site_url=site_url,
                )
                failures.extend(download_failures)
                page = _write_prepared_confluence_attachment_downloads(
                    page,
                    downloads,
                    failures=failures,
                    command="attachments",
                    site_url=site_url,
                )
                _write_confluence_page(
                    result.out_dir,
                    result.state_path,
                    page,
                    config,
                    exported_pages=_local_confluence_exported_pages(
                        result.out_dir,
                        replacement=page,
                        site_url=site_url,
                    ),
                    command="attachments",
                    site_url=site_url,
                )
                written.append(page.id)
            except (AtlassianClientError, OSError, ValueError) as error:
                failures.append(f"{page_id}: {error}")

        generate_confluence_indexes(result.out_dir)
        if failures:
            finish_confluence_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message="; ".join(failures),
            )
            update_confluence_manifest(result.out_dir, site_host=_site_host(site_url))
            raise ExportCommandError(
                _partial_failure_message("attachments", failures, provider="confluence")
            )

        finish_confluence_export_run(result.state_path, run_id, succeeded=True)
        update_confluence_manifest(result.out_dir, site_host=_site_host(site_url))
        _log_confluence(
            logging.INFO,
            "finished confluence attachments export",
            command="attachments",
            site_url=site_url,
            operation="confluence_export_finish",
            page_count=len(written),
            output_path=result.out_dir,
        )
        return ConfluenceExportSummary(page_ids=tuple(sorted(written)))
    except Exception as error:
        if not isinstance(error, ExportCommandError):
            finish_confluence_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message=str(error),
            )
        raise


def run_pull(
    out_dir: Path,
    *,
    client: JiraClient,
    site_url: str,
    config: ExportConfig,
    project: str | None = None,
    jql: str | None = None,
    issue: str | None = None,
    since: str | None = None,
    force: bool = False,
    concurrency: int = 4,
    attachment_options: AttachmentOptions = AttachmentOptions(),
) -> ExportSummary:
    scope_type, scope_value, base_jql, exact_keys = _pull_scope(
        project=project, jql=jql, issue=issue
    )
    return _run_search_export(
        out_dir,
        client=client,
        site_url=site_url,
        config=config,
        command="pull",
        scope_type=scope_type,
        scope_value=scope_value,
        base_jql=base_jql,
        since=since,
        force=force,
        exact_issue_keys=exact_keys,
        concurrency=concurrency,
        attachment_options=attachment_options,
    )


def run_issue(
    out_dir: Path,
    *,
    client: JiraClient,
    site_url: str,
    config: ExportConfig,
    keys: Iterable[str],
    attachment_options: AttachmentOptions = AttachmentOptions(),
) -> ExportSummary:
    issue_keys = _normalized_keys(keys)
    return _run_search_export(
        out_dir,
        client=client,
        site_url=site_url,
        config=config,
        command="issue",
        scope_type="issue",
        scope_value=",".join(issue_keys),
        base_jql=exact_issue_jql(issue_keys),
        since=None,
        force=True,
        exact_issue_keys=issue_keys,
        concurrency=config.sync.concurrency,
        attachment_options=attachment_options,
    )


def run_comments(
    out_dir: Path,
    *,
    client: JiraClient,
    site_url: str,
    config: ExportConfig,
    keys: Iterable[str],
    force: bool,
) -> ExportSummary:
    if not force:
        raise ExportCommandError("comments requires --force so comment refresh is explicit.")
    issue_keys = _normalized_keys(keys)
    result = initialize_output(out_dir)
    run_id = start_export_run(
        result.state_path,
        command="comments",
        scope_type="issue",
        scope_value=",".join(issue_keys),
        force=True,
        exact_issue_keys=issue_keys,
    )
    failures: list[str] = []
    written: list[str] = []
    try:
        for key in issue_keys:
            try:
                raw_issue, metadata = _read_local_issue_source(result.out_dir, key)
                comments = client.fetch_comments(key)
                issue = normalize_jira_issue(
                    raw_issue,
                    comments=comments,
                    site_url=site_url,
                    custom_fields=_writer_custom_fields(config.custom_fields),
                )
                issue = _apply_attachment_metadata(issue, metadata)
                _write_issue(result.out_dir, result.state_path, issue, config)
                written.append(issue.key)
            except (AtlassianClientError, OSError, ValueError) as error:
                failures.append(f"{key}: {error}")

        generate_indexes(result.out_dir)
        if failures:
            finish_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message="; ".join(failures),
            )
            update_manifest(result.out_dir, site_host=_site_host(site_url))
            raise ExportCommandError(_partial_failure_message("comments", failures))

        finish_export_run(result.state_path, run_id, succeeded=True)
        update_manifest(result.out_dir, site_host=_site_host(site_url))
        return ExportSummary(issue_keys=tuple(sorted(written)))
    except Exception as error:
        if not isinstance(error, ExportCommandError):
            finish_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message=str(error),
            )
        raise


def run_attachments(
    out_dir: Path,
    *,
    client: JiraClient,
    site_url: str,
    config: ExportConfig,
    keys: Iterable[str],
    attachment_options: AttachmentOptions,
) -> ExportSummary:
    issue_keys = _normalized_keys(keys)
    result = initialize_output(out_dir)
    run_id = start_export_run(
        result.state_path,
        command="attachments",
        scope_type="issue",
        scope_value=",".join(issue_keys),
        force=True,
        exact_issue_keys=issue_keys,
    )
    failures: list[str] = []
    written: list[str] = []
    active_options = AttachmentOptions(
        download=True,
        max_mb=attachment_options.max_mb,
        include_patterns=attachment_options.include_patterns,
    )
    try:
        with client.http.build_client() as http_client:
            for key in issue_keys:
                try:
                    raw_issue, metadata = _read_local_issue_source(result.out_dir, key)
                    comments = _read_local_comments(result.out_dir, key)
                    issue = normalize_jira_issue(
                        raw_issue,
                        comments=comments,
                        site_url=site_url,
                        custom_fields=_writer_custom_fields(config.custom_fields),
                    )
                    issue = _apply_attachment_metadata(issue, metadata)
                    issue = _download_attachments(
                        result.out_dir,
                        client=client,
                        http_client=http_client,
                        issue=issue,
                        options=active_options,
                        failures=failures,
                    )
                    _write_issue(result.out_dir, result.state_path, issue, config)
                    written.append(issue.key)
                except (AtlassianClientError, OSError, ValueError) as error:
                    failures.append(f"{key}: {error}")

        generate_indexes(result.out_dir)
        if failures:
            finish_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message="; ".join(failures),
            )
            update_manifest(result.out_dir, site_host=_site_host(site_url))
            raise ExportCommandError(_partial_failure_message("attachments", failures))

        finish_export_run(result.state_path, run_id, succeeded=True)
        update_manifest(result.out_dir, site_host=_site_host(site_url))
        return ExportSummary(issue_keys=tuple(sorted(written)))
    except Exception as error:
        if not isinstance(error, ExportCommandError):
            finish_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message=str(error),
            )
        raise


def regenerate_indexes(out_dir: Path) -> tuple[Path, ...]:
    result = initialize_output(out_dir)
    paths = tuple(generate_indexes(result.out_dir))
    update_manifest(result.out_dir)
    return paths


def update_manifest(out_dir: Path, *, site_host: str | None = None) -> Path:
    result = initialize_output(out_dir)
    payloads = _read_issue_payloads(result.out_dir)
    issue_keys = sorted(_issue_key(payload, path) for path, payload in payloads)
    comments = sum(len(_list(payload.get("fetched_comments"))) for _path, payload in payloads)
    attachments = sum(len(_list(payload.get("attachment_metadata"))) for _path, payload in payloads)
    manifest = Manifest(
        generator=GeneratorInfo(name="atlassian-md-export", version=__version__),
        jira_site_host=site_host or _site_host_from_payloads(payloads),
        output=OutputMetadata(path=str(result.out_dir.resolve())),
        last_successful_representative_run=_manifest_representative_run(result.state_path),
        exported_issue_keys=issue_keys,
        counts=ExportCounts(
            issues=len(issue_keys),
            comments=comments,
            attachments=attachments,
        ),
        hashes=_file_hashes(result.out_dir),
    )
    manifest_path = result.out_dir / "manifest.json"
    atomic_write_text(manifest_path, manifest_json(manifest))
    return manifest_path


def verify_export(out_dir: Path) -> VerificationResult:
    out = out_dir.resolve()
    errors: list[str] = []

    for directory in (out / "issues", issue_raw_dir(out), out / "attachments", out / "indexes"):
        if not directory.is_dir():
            errors.append(f"Missing required directory: {_display_path(directory)}")

    manifest_path = out / "manifest.json"
    manifest: Manifest | None = None
    if not manifest_path.is_file():
        errors.append(f"Missing required file: {_display_path(manifest_path)}")
    else:
        try:
            manifest = Manifest.model_validate(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
        except ValueError as error:
            errors.append(f"Manifest is not parseable: {_display_path(manifest_path)}: {error}")

    state_path = out / "state.sqlite"
    if not state_path.is_file():
        errors.append(f"Missing required file: {_display_path(state_path)}")
    else:
        errors.extend(_verify_sqlite(state_path))
        errors.extend(_verify_state_issue_hashes(out, state_path))

    for path in required_index_paths(out):
        if not path.is_file():
            errors.append(f"Missing required index: {_display_path(path)}")

    if manifest is not None:
        errors.extend(_verify_manifest_issue_files(out, manifest))
        errors.extend(_verify_manifest_hashes(out, manifest))

    errors.extend(_verify_index_links(out))
    errors.extend(_verify_attachment_references(out))
    return VerificationResult(errors=tuple(errors))


def clean_export(out_dir: Path, *, remove_missing: bool) -> CleanResult:
    if not remove_missing:
        raise ExportCommandError("clean requires --remove-missing before deleting local files.")

    result = initialize_output(out_dir)
    representative = latest_successful_representative_run(result.state_path)
    if representative is None:
        raise ExportCommandError(
            "No successful representative pull exists; clean refused to delete local files."
        )

    keep = set(representative.representative_issue_keys)
    local_keys = _local_issue_keys(result.out_dir)
    removed: list[str] = []
    for key in sorted(local_keys - keep):
        for path in (issue_markdown_path(result.out_dir, key), issue_raw_path(result.out_dir, key)):
            if path.exists():
                path.unlink()
        attachment_dir = result.out_dir / "attachments" / key
        if attachment_dir.exists():
            shutil.rmtree(attachment_dir)
        clear_issue_export_artifacts(result.state_path, key)
        removed.append(key)

    generate_indexes(result.out_dir)
    update_manifest(result.out_dir)
    return CleanResult(removed_issue_keys=tuple(removed))


def regenerate_confluence_indexes(out_dir: Path) -> tuple[Path, ...]:
    result = initialize_confluence_output(out_dir)
    paths = tuple(generate_confluence_indexes(result.out_dir))
    update_confluence_manifest(result.out_dir)
    return paths


def update_confluence_manifest(out_dir: Path, *, site_host: str | None = None) -> Path:
    result = initialize_confluence_output(out_dir)
    payloads = _read_confluence_page_payloads(result.out_dir)
    page_ids = sorted(_confluence_page_id(payload, path) for path, payload in payloads)
    footer_comments = sum(
        len(dict_list(payload.get("fetched_footer_comments"))) for _path, payload in payloads
    )
    inline_comments = sum(
        len(dict_list(payload.get("fetched_inline_comments"))) for _path, payload in payloads
    )
    attachments = sum(
        len(dict_list(payload.get("attachment_metadata"))) for _path, payload in payloads
    )
    manifest = _confluence_manifest_payload(
        result.out_dir,
        site_host=site_host or _confluence_site_host_from_payloads(payloads),
        page_ids=page_ids,
        footer_comments=footer_comments,
        inline_comments=inline_comments,
        attachments=attachments,
        representative_run=_confluence_manifest_representative_run(result.state_path),
        hashes=_confluence_file_hashes(result.out_dir),
    )
    manifest_path = result.out_dir / "manifest.json"
    atomic_write_text(manifest_path, canonical_json(manifest))
    return manifest_path


def verify_confluence_export(out_dir: Path) -> VerificationResult:
    out = out_dir.resolve()
    errors: list[str] = []

    for directory in (
        out / "pages",
        confluence_page_raw_dir(out),
        out / "attachments",
        out / "indexes",
    ):
        if not directory.is_dir():
            errors.append(f"Missing required directory: {_display_path(directory)}")

    manifest_path = out / "manifest.json"
    manifest: dict[str, Any] | None = None
    if not manifest_path.is_file():
        errors.append(f"Missing required file: {_display_path(manifest_path)}")
    else:
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(raw_manifest, dict):
                raise ValueError("manifest root is not an object")
            manifest = raw_manifest
        except ValueError as error:
            errors.append(f"Manifest is not parseable: {_display_path(manifest_path)}: {error}")

    state_path = out / "state.sqlite"
    if not state_path.is_file():
        errors.append(f"Missing required file: {_display_path(state_path)}")
    else:
        errors.extend(_verify_sqlite(state_path))
        errors.extend(_verify_state_confluence_page_hashes(out, state_path))

    for path in confluence_required_index_paths(out):
        if not path.is_file():
            errors.append(f"Missing required index: {_display_path(path)}")

    if manifest is not None:
        errors.extend(_verify_manifest_confluence_page_files(out, manifest))
        errors.extend(_verify_manifest_hashes(out, manifest))

    errors.extend(_verify_index_links(out))
    errors.extend(_verify_confluence_attachment_references(out))
    return VerificationResult(errors=tuple(errors))


def clean_confluence_export(out_dir: Path, *, remove_missing: bool) -> ConfluenceCleanResult:
    if not remove_missing:
        raise ExportCommandError("clean requires --remove-missing before deleting local files.")

    result = initialize_confluence_output(out_dir)
    representative = latest_successful_confluence_representative_run(result.state_path)
    if representative is None:
        raise ExportCommandError(
            "No successful representative Confluence pull exists; clean refused to delete local files."
        )

    keep = set(representative.representative_page_ids)
    local_page_ids = _local_confluence_page_ids(result.out_dir)
    removed: list[str] = []
    for page_id in sorted(local_page_ids - keep):
        raw_path = confluence_page_raw_path(result.out_dir, page_id)
        markdown_paths = _confluence_markdown_paths_for_page_id(result.out_dir, page_id)
        for path in (*markdown_paths, raw_path):
            if path.exists():
                path.unlink()
        attachment_dir = result.out_dir / "attachments" / page_id
        if attachment_dir.exists():
            shutil.rmtree(attachment_dir)
        clear_confluence_page_export_artifacts(result.state_path, page_id)
        removed.append(page_id)

    generate_confluence_indexes(result.out_dir)
    update_confluence_manifest(result.out_dir)
    return ConfluenceCleanResult(removed_page_ids=tuple(removed))


def _run_search_export(
    out_dir: Path,
    *,
    client: JiraClient,
    site_url: str,
    config: ExportConfig,
    command: str,
    scope_type: str,
    scope_value: str,
    base_jql: str,
    since: str | None,
    force: bool,
    exact_issue_keys: tuple[str, ...],
    concurrency: int,
    attachment_options: AttachmentOptions,
) -> ExportSummary:
    result = initialize_output(out_dir)
    decision = decide_incremental_sync(
        result.state_path,
        command="pull" if command == "pull" else command,
        scope_type=scope_type,
        scope_value=scope_value,
        since=since,
        force=force,
        exact_issue_keys=exact_issue_keys,
        overlap_minutes=config.sync.overlap_minutes,
    )
    active_jql = base_jql
    if decision.since is not None:
        active_jql = updated_since_jql(
            base_jql,
            decision.since,
            timezone_name=client.user_timezone(),
        )

    run_id = start_export_run(
        result.state_path,
        command=command,
        scope_type=scope_type,
        scope_value=scope_value,
        sync_since=decision.since,
        force=force,
        exact_issue_keys=exact_issue_keys,
    )
    failures: list[str] = []
    try:
        search_result = client.fetch_issues_with_comments(
            active_jql,
            fields=_search_fields(config),
            concurrency=concurrency,
        )
        fetched_keys = tuple(sorted(issue.key for issue in search_result.issues))
        missing_keys = sorted(set(exact_issue_keys) - set(fetched_keys))
        if missing_keys:
            failures.append(f"Missing issue(s) from Jira response: {', '.join(missing_keys)}")

        with client.http.build_client() as http_client:
            for jira_issue in search_result.issues:
                try:
                    normalized = normalize_jira_issue(
                        jira_issue.raw,
                        comments=jira_issue.comments,
                        site_url=site_url,
                        custom_fields=_writer_custom_fields(config.custom_fields),
                    )
                    normalized = _download_attachments(
                        result.out_dir,
                        client=client,
                        http_client=http_client,
                        issue=normalized,
                        options=attachment_options,
                        failures=failures,
                    )
                    _write_issue(result.out_dir, result.state_path, normalized, config)
                except OSError as error:
                    raise OSError(f"{jira_issue.key}: {error}") from error
                except ValueError as error:
                    raise ValueError(f"{jira_issue.key}: {error}") from error

        generate_indexes(result.out_dir)
        if failures:
            finish_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message="; ".join(failures),
            )
            update_manifest(result.out_dir, site_host=_site_host(site_url))
            raise ExportCommandError(_partial_failure_message(command, failures))

        representative_keys = _representative_issue_keys(
            result.state_path,
            decision=decision,
            scope_type=scope_type,
            scope_value=scope_value,
            fetched_keys=fetched_keys,
        )
        finish_export_run(
            result.state_path,
            run_id,
            succeeded=True,
            representative_issue_keys=representative_keys,
        )
        update_manifest(result.out_dir, site_host=_site_host(site_url))
        return ExportSummary(issue_keys=fetched_keys)
    except Exception as error:
        if not isinstance(error, ExportCommandError):
            finish_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message=str(error),
            )
        raise


def _run_confluence_page_export(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    site_url: str,
    config: ExportConfig,
    command: str,
    scope_type: str,
    scope_value: str,
    since: str | None,
    force: bool,
    exact_page_ids: tuple[str, ...],
    concurrency: int = 1,
    attachment_options: AttachmentOptions,
) -> ConfluenceExportSummary:
    result = initialize_confluence_output(out_dir)
    decision = decide_confluence_incremental_sync(
        result.state_path,
        command="pull" if command == "pull" else command,
        scope_type=scope_type,
        scope_value=scope_value,
        since=since,
        force=force,
        exact_page_ids=exact_page_ids,
        overlap_minutes=config.sync.overlap_minutes,
    )
    run_id = start_confluence_export_run(
        result.state_path,
        command=command,
        scope_type=scope_type,
        scope_value=scope_value,
        sync_since=decision.since,
        force=force,
        exact_page_ids=exact_page_ids,
    )
    _log_confluence(
        logging.INFO,
        "started confluence page export",
        command=command,
        site_url=site_url,
        operation="confluence_export_start",
        output_path=result.out_dir,
        concurrency=concurrency,
        force=force,
        sync_since=decision.since,
        **_confluence_scope_log_context(scope_type, scope_value, exact_page_ids),
    )
    failures: list[str] = []
    try:
        fetched_pages = _fetch_confluence_scope_pages(
            client,
            command=command,
            site_url=site_url,
            scope_type=scope_type,
            scope_value=scope_value,
            decision=decision,
            config=config,
        )
        fetched_page_ids = tuple(sorted(page.id for page in fetched_pages))
        _log_confluence(
            logging.INFO,
            "fetched confluence pages",
            command=command,
            site_url=site_url,
            operation="confluence_pages_fetched",
            page_count=len(fetched_page_ids),
            **_confluence_scope_log_context(scope_type, scope_value, exact_page_ids),
        )
        missing_page_ids = sorted(set(exact_page_ids) - set(fetched_page_ids))
        if missing_page_ids:
            failures.append(
                f"Missing page(s) from Confluence response: {', '.join(missing_page_ids)}"
            )

        prepared_pages = _prepare_confluence_page_exports(
            result.out_dir,
            client=client,
            pages=fetched_pages,
            config=config,
            site_url=site_url,
            attachment_options=attachment_options,
            command=command,
            concurrency=concurrency,
        )
        normalized_pages: list[NormalizedConfluencePage] = []
        for prepared in prepared_pages:
            failures.extend(prepared.failures)
            if prepared.page is None:
                continue
            page = _write_prepared_confluence_attachment_downloads(
                prepared.page,
                prepared.attachment_downloads,
                failures=failures,
                command=command,
                site_url=site_url,
            )
            normalized_pages.append(page)

        exported_pages = tuple(normalized_pages)
        export_context = _confluence_export_context(
            result.out_dir,
            replacements=exported_pages,
            site_url=site_url,
        )
        for page in exported_pages:
            try:
                _write_confluence_page(
                    result.out_dir,
                    result.state_path,
                    page,
                    config,
                    exported_pages=export_context,
                    command=command,
                    site_url=site_url,
                )
            except OSError as error:
                raise OSError(f"{page.id}: {error}") from error
            except ValueError as error:
                raise ValueError(f"{page.id}: {error}") from error

        generate_confluence_indexes(result.out_dir)
        if failures:
            finish_confluence_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message="; ".join(failures),
            )
            update_confluence_manifest(result.out_dir, site_host=_site_host(site_url))
            raise ExportCommandError(
                _partial_failure_message(command, failures, provider="confluence")
            )

        representative_page_ids = confluence_representative_page_ids(decision, fetched_page_ids)
        finish_confluence_export_run(
            result.state_path,
            run_id,
            succeeded=True,
            representative_page_ids=representative_page_ids,
        )
        update_confluence_manifest(result.out_dir, site_host=_site_host(site_url))
        _log_confluence(
            logging.INFO,
            "finished confluence page export",
            command=command,
            site_url=site_url,
            operation="confluence_export_finish",
            page_count=len(fetched_page_ids),
            output_path=result.out_dir,
            **_confluence_scope_log_context(scope_type, scope_value, exact_page_ids),
        )
        return ConfluenceExportSummary(page_ids=fetched_page_ids)
    except Exception as error:
        if not isinstance(error, ExportCommandError):
            finish_confluence_export_run(
                result.state_path,
                run_id,
                succeeded=False,
                partial_failure=True,
                failure_message=str(error),
            )
        raise


def _prepare_confluence_page_exports(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    pages: Sequence[ConfluencePage],
    config: ExportConfig,
    site_url: str,
    attachment_options: AttachmentOptions,
    command: str,
    concurrency: int,
) -> tuple[_PreparedConfluencePage, ...]:
    worker_count = max(1, concurrency)

    def prepare(page: ConfluencePage) -> _PreparedConfluencePage:
        return _prepare_confluence_page_export(
            out_dir,
            client=client,
            confluence_page=page,
            config=config,
            site_url=site_url,
            attachment_options=attachment_options,
            command=command,
        )

    if worker_count == 1 or len(pages) <= 1:
        return tuple(prepare(page) for page in pages)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return tuple(executor.map(prepare, pages))


def _prepare_confluence_page_export(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    confluence_page: ConfluencePage,
    config: ExportConfig,
    site_url: str,
    attachment_options: AttachmentOptions,
    command: str,
) -> _PreparedConfluencePage:
    try:
        page = _hydrate_confluence_page(
            client,
            confluence_page,
            config=config,
            site_url=site_url,
            command=command,
        )
        page, attachment_downloads, failures = _prepare_confluence_attachment_downloads(
            out_dir,
            client=client,
            page=page,
            options=attachment_options,
            command=command,
            site_url=site_url,
        )
        return _PreparedConfluencePage(
            page=page,
            attachment_downloads=attachment_downloads,
            failures=failures,
        )
    except (AtlassianClientError, OSError, ValueError) as error:
        return _PreparedConfluencePage(page=None, failures=(f"{confluence_page.id}: {error}",))


def _fetch_confluence_scope_pages(
    client: ConfluenceClient,
    *,
    command: str,
    site_url: str,
    scope_type: str,
    scope_value: str,
    decision: ConfluenceSyncDecision,
    config: ExportConfig,
) -> tuple[ConfluencePage, ...]:
    body_format = config.content.body_format
    _log_confluence(
        logging.DEBUG,
        "fetching confluence scope",
        command=command,
        site_url=site_url,
        operation="confluence_scope_fetch",
        **_confluence_scope_log_context(scope_type, scope_value, decision.exact_page_ids),
    )
    if scope_type == "space":
        if decision.since is not None:
            cql = confluence_updated_since_cql(
                f'space = "{_escape_cql_string(scope_value)}"',
                decision.since,
            )
            return client.search_pages(cql, body_format=body_format)
        return client.fetch_space_pages(scope_value, body_format=body_format)
    if scope_type == "cql":
        active_cql = (
            confluence_updated_since_cql(scope_value, decision.since)
            if decision.since is not None
            else scope_value
        )
        return client.search_pages(active_cql, body_format=body_format)
    if scope_type == "ancestor":
        return client.fetch_ancestor_subtree(scope_value, body_format=body_format)
    if scope_type == "page":
        page_ids = decision.exact_page_ids or (scope_value,)
        return tuple(client.fetch_page(page_id, body_format=body_format) for page_id in page_ids)
    raise ExportCommandError(
        "Choose exactly one Confluence pull scope: --space, --cql, --ancestor, or --page."
    )


def _hydrate_confluence_page(
    client: ConfluenceClient,
    page: ConfluencePage,
    *,
    config: ExportConfig,
    site_url: str,
    command: str,
) -> NormalizedConfluencePage:
    footer_comments: Sequence[Mapping[str, Any]] = ()
    inline_comments: Sequence[Mapping[str, Any]] = ()
    if config.content.include_footer_comments:
        footer_comments = _fetch_confluence_footer_comments(
            client,
            page.id,
            command=command,
            site_url=site_url,
            body_format=config.content.body_format,
        )
    if config.content.include_inline_comments:
        inline_comments = _fetch_inline_comments(
            client,
            page.id,
            config=config,
            command=command,
            site_url=site_url,
        )
    _log_confluence(
        logging.DEBUG,
        "fetching confluence attachment metadata",
        command=command,
        site_url=site_url,
        operation="confluence_attachment_metadata_fetch",
        page_id=page.id,
        space_key=page.space_key,
    )
    attachments = list(client.fetch_attachment_metadata(page.id))
    _log_confluence(
        logging.DEBUG,
        "fetching confluence labels",
        command=command,
        site_url=site_url,
        operation="confluence_labels_fetch",
        page_id=page.id,
        space_key=page.space_key,
    )
    labels = list(client.fetch_labels(page.id))
    _log_confluence(
        logging.DEBUG,
        "fetching confluence ancestors",
        command=command,
        site_url=site_url,
        operation="confluence_ancestors_fetch",
        page_id=page.id,
        space_key=page.space_key,
    )
    ancestors = list(client.fetch_ancestors(page.id))
    _log_confluence(
        logging.DEBUG,
        "fetching confluence descendants",
        command=command,
        site_url=site_url,
        operation="confluence_descendants_fetch",
        page_id=page.id,
        space_key=page.space_key,
    )
    descendants = list(client.fetch_descendants(page.id))
    return normalize_confluence_page(
        page.raw,
        footer_comments=footer_comments,
        inline_comments=inline_comments,
        attachments=attachments,
        labels=labels,
        ancestors=ancestors,
        child_pages=descendants,
        site_url=site_url,
        space_key=page.space_key,
    )


def _fetch_confluence_footer_comments(
    client: ConfluenceClient,
    page_id: str,
    *,
    command: str,
    site_url: str,
    body_format: str,
) -> list[dict[str, Any]]:
    _log_confluence(
        logging.DEBUG,
        "fetching confluence footer comments",
        command=command,
        site_url=site_url,
        operation="confluence_footer_comments_fetch",
        page_id=page_id,
    )
    return list(client.fetch_footer_comments(page_id, body_format=body_format))


def _fetch_inline_comments(
    client: ConfluenceClient,
    page_id: str,
    *,
    config: ExportConfig,
    command: str,
    site_url: str,
) -> list[dict[str, Any]]:
    resolution_status = None if config.content.include_resolved_inline_comments else "open"
    _log_confluence(
        logging.DEBUG,
        "fetching confluence inline comments",
        command=command,
        site_url=site_url,
        operation="confluence_inline_comments_fetch",
        page_id=page_id,
    )
    return list(
        client.fetch_inline_comments(
            page_id,
            body_format=config.content.body_format,
            resolution_status=resolution_status,
        )
    )


def _escape_cql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _pull_scope(
    *,
    project: str | None,
    jql: str | None,
    issue: str | None,
) -> tuple[str, str, str, tuple[str, ...]]:
    selected = [value is not None for value in (project, jql, issue)]
    if sum(selected) != 1:
        raise ExportCommandError("Choose exactly one of --project, --jql, or --issue.")
    if project is not None:
        return "project", project, project_jql(project), ()
    if jql is not None:
        return "jql", ordered_jql(jql), ordered_jql(jql), ()
    if issue is None:
        raise ExportCommandError("Choose exactly one of --project, --jql, or --issue.")
    key = issue.strip()
    if not key:
        raise ExportCommandError("--issue must not be empty.")
    return "issue", key, exact_issue_jql((key,)), (key,)


def _confluence_pull_scope(
    *,
    space: str | None,
    cql: str | None,
    ancestor: str | None,
    page: str | None,
) -> tuple[str, str, tuple[str, ...]]:
    selected = [
        ("space", space.strip() if space else None),
        ("cql", cql.strip() if cql else None),
        ("ancestor", ancestor.strip() if ancestor else None),
        ("page", page.strip() if page else None),
    ]
    active = [(scope_type, value) for scope_type, value in selected if value]
    if len(active) != 1:
        raise ExportCommandError(
            "Choose exactly one Confluence pull scope: --space, --cql, --ancestor, or --page."
        )
    scope_type, scope_value = active[0]
    exact_page_ids = (scope_value,) if scope_type == "page" else ()
    return scope_type, scope_value, exact_page_ids


def _normalized_keys(keys: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(key.strip() for key in keys if key.strip())
    if not normalized:
        raise ExportCommandError("At least one Jira issue key is required.")
    return normalized


def _normalized_page_ids(page_ids: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(page_id.strip() for page_id in page_ids if page_id.strip())
    if not normalized:
        raise ExportCommandError("At least one Confluence page id is required.")
    return normalized


def _download_attachments(
    out_dir: Path,
    *,
    client: JiraClient,
    http_client: Any,
    issue: NormalizedJiraIssue,
    options: AttachmentOptions,
    failures: list[str],
) -> NormalizedJiraIssue:
    if not options.download:
        return issue

    attachments: list[NormalizedJiraAttachment] = []
    for attachment in issue.attachments:
        if not should_download_attachment(
            filename=attachment.filename,
            size=attachment.size,
            max_bytes=options.max_bytes,
            include_patterns=options.include_patterns,
        ):
            attachments.append(attachment.model_copy(update={"local_path": None}))
            continue

        if not attachment.content_url:
            failures.append(
                f"{issue.key}/{attachment.id or attachment.filename}: missing content URL"
            )
            attachments.append(attachment.model_copy(update={"local_path": None}))
            continue

        target_path = attachment_path(out_dir, issue.key, attachment.id, attachment.filename)
        relative_path = attachment_relative_path(issue.key, attachment.id, attachment.filename)
        download_target, validation_error = _attachment_download_target(
            attachment.content_url,
            site_url=client.http.base_url,
        )
        if validation_error is not None:
            failures.append(
                f"{issue.key}/{attachment.id or attachment.filename or 'attachment'}: "
                f"{validation_error}"
            )
            attachments.append(attachment.model_copy(update={"local_path": None}))
            continue

        if download_target is None:
            raise AssertionError("validated attachment download target cannot be None")
        try:
            content = client.http.request_bytes(http_client, "GET", download_target)
            atomic_write_bytes(target_path, content)
            attachments.append(attachment.model_copy(update={"local_path": relative_path}))
        except (AtlassianClientError, OSError) as error:
            failures.append(
                f"{issue.key}/{attachment.id or attachment.filename or 'attachment'}: {error}"
            )
            attachments.append(attachment.model_copy(update={"local_path": None}))
    return issue.model_copy(update={"attachments": attachments})


def _prepare_confluence_attachment_downloads(
    out_dir: Path,
    *,
    client: ConfluenceClient,
    page: NormalizedConfluencePage,
    options: AttachmentOptions,
    command: str,
    site_url: str,
) -> tuple[
    NormalizedConfluencePage,
    tuple[_PreparedConfluenceAttachmentDownload, ...],
    tuple[str, ...],
]:
    if not options.download:
        return page, (), ()

    attachments: list[NormalizedConfluenceAttachment] = []
    downloads: list[_PreparedConfluenceAttachmentDownload] = []
    failures: list[str] = []
    markdown_path = confluence_page_markdown_path(out_dir, page)
    with client.http.build_client() as http_client:
        for attachment_index, attachment in enumerate(page.attachments):
            if not should_download_attachment(
                filename=attachment.filename,
                size=attachment.size,
                max_bytes=options.max_bytes,
                include_patterns=options.include_patterns,
            ):
                attachments.append(attachment.model_copy(update={"local_path": None}))
                continue

            if not attachment.download_url:
                failures.append(
                    f"{page.id}/{attachment.id or attachment.filename}: missing download URL"
                )
                attachments.append(attachment.model_copy(update={"local_path": None}))
                continue

            target_path = confluence_attachment_path(
                out_dir,
                page.id,
                attachment.id,
                attachment.filename,
            )
            relative_path = os.path.relpath(target_path, start=markdown_path.parent).replace(
                os.sep,
                "/",
            )
            download_target, validation_error = _confluence_attachment_download_target(
                attachment.download_url,
                site_url=client.http.base_url,
            )
            if validation_error is not None:
                failures.append(
                    f"{page.id}/{attachment.id or attachment.filename or 'attachment'}: "
                    f"{validation_error}"
                )
                attachments.append(attachment.model_copy(update={"local_path": None}))
                continue

            if download_target is None:
                raise AssertionError("validated attachment download target cannot be None")
            try:
                _log_confluence(
                    logging.DEBUG,
                    "downloading confluence attachment",
                    command=command,
                    site_url=site_url,
                    operation="confluence_attachment_download",
                    page_id=page.id,
                    space_key=page.space_key,
                    attachment_id=attachment.id,
                    resource_path=_safe_resource_path(download_target),
                )
                content = client.http.request_bytes(http_client, "GET", download_target)
            except AtlassianClientError as error:
                failures.append(
                    f"{page.id}/{attachment.id or attachment.filename or 'attachment'}: {error}"
                )
                attachments.append(attachment.model_copy(update={"local_path": None}))
                continue
            attachments.append(attachment.model_copy(update={"local_path": relative_path}))
            downloads.append(
                _PreparedConfluenceAttachmentDownload(
                    attachment_index=attachment_index,
                    target_path=target_path,
                    relative_path=relative_path,
                    content=content,
                )
            )
    return page.model_copy(update={"attachments": attachments}), tuple(downloads), tuple(failures)


def _write_prepared_confluence_attachment_downloads(
    page: NormalizedConfluencePage,
    downloads: Sequence[_PreparedConfluenceAttachmentDownload],
    *,
    failures: list[str],
    command: str,
    site_url: str,
) -> NormalizedConfluencePage:
    if not downloads:
        return page

    attachments = list(page.attachments)
    for download in downloads:
        attachment = attachments[download.attachment_index]
        try:
            atomic_write_bytes(download.target_path, download.content)
        except OSError as error:
            failures.append(
                f"{page.id}/{attachment.id or attachment.filename or 'attachment'}: {error}"
            )
            attachments[download.attachment_index] = attachment.model_copy(
                update={"local_path": None}
            )
            continue
        attachments[download.attachment_index] = attachment.model_copy(
            update={"local_path": download.relative_path}
        )
        _log_confluence(
            logging.INFO,
            "wrote confluence attachment file",
            command=command,
            site_url=site_url,
            operation="confluence_attachment_write",
            page_id=page.id,
            space_key=page.space_key,
            attachment_id=attachment.id,
            output_path=download.target_path,
        )
    return page.model_copy(update={"attachments": attachments})


def _attachment_download_target(
    content_url: str, *, site_url: str
) -> tuple[str | None, str | None]:
    parsed = urlparse(content_url)
    if not parsed.scheme and not parsed.netloc:
        return content_url, None

    site = urlparse(site_url)
    if parsed.scheme in {"http", "https"} and _same_origin(parsed, site):
        return content_url, None

    return (
        None,
        f"attachment content URL origin {_origin(parsed)} does not match Jira site {_origin(site)}",
    )


def _confluence_attachment_download_target(
    download_url: str,
    *,
    site_url: str,
) -> tuple[str | None, str | None]:
    stripped = download_url.strip()
    if not stripped:
        return None, "attachment download URL is empty"

    parsed = urlparse(stripped)
    if parsed.netloc and not parsed.scheme:
        return None, "attachment download URL is ambiguous; scheme-relative URLs are not allowed"
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None, f"attachment download URL scheme is not allowed: {parsed.scheme}"
    if parsed.scheme and not parsed.netloc:
        return None, "attachment download URL is ambiguous; absolute URL lacks a host"
    if not _safe_download_path(parsed.path):
        return None, "attachment download URL path is not safe"

    if not parsed.scheme and not parsed.netloc:
        return stripped, None

    site = urlparse(site_url)
    if _same_origin(parsed, site):
        return stripped, None
    return (
        None,
        f"attachment download URL origin {_origin(parsed)} does not match Confluence site {_origin(site)}",
    )


def _safe_download_path(path: str) -> bool:
    if not path or "\\" in path:
        return False
    decoded = unquote(path)
    if any(ord(character) < 32 or ord(character) == 127 for character in decoded):
        return False
    parts = [part for part in decoded.split("/") if part]
    return all(part not in {".", ".."} for part in parts)


def _same_origin(first: Any, second: Any) -> bool:
    if not first.scheme or not second.scheme:
        return False
    if first.scheme.lower() != second.scheme.lower():
        return False
    if first.hostname is None or second.hostname is None:
        return False
    return first.hostname.lower() == second.hostname.lower() and _origin_port(
        first
    ) == _origin_port(second)


def _origin(value: Any) -> str:
    scheme = value.scheme or "<none>"
    host = value.hostname or value.netloc or "<none>"
    port = _origin_port(value)
    if port is None:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def _origin_port(value: Any) -> int | None:
    try:
        explicit_port = value.port
    except ValueError:
        return None
    if explicit_port is not None:
        return int(explicit_port)
    if value.scheme == "http":
        return 80
    if value.scheme == "https":
        return 443
    return None


def _write_issue(
    out_dir: Path,
    state_path: Path,
    issue: NormalizedJiraIssue,
    config: ExportConfig,
) -> None:
    renderer = AdfMarkdownRenderer(
        include_raw_adf_on_unknown_nodes=config.markdown.include_raw_adf_on_unknown_nodes
    )
    result = write_issue_files(
        out_dir,
        issue,
        renderer=renderer,
        stable_exported_at=config.markdown.stable_exported_at,
    )
    observed_at = now_iso()
    upsert_issue_state(
        state_path,
        IssueState(
            issue_key=issue.key,
            issue_id=issue.id,
            updated_at=issue.updated,
            stable_content_hash=result.content_hash,
            raw_json_hash=result.raw_json_hash,
            markdown_hash=result.markdown_hash,
            last_seen_at=observed_at,
            last_exported_at=result.exported_at,
        ),
    )


def _write_confluence_page(
    out_dir: Path,
    state_path: Path,
    page: NormalizedConfluencePage,
    config: ExportConfig,
    *,
    exported_pages: Sequence[NormalizedConfluencePage],
    command: str | None = None,
    site_url: str | None = None,
) -> None:
    renderer = AdfMarkdownRenderer(
        include_raw_adf_on_unknown_nodes=config.markdown.include_raw_adf_on_unknown_nodes
    )
    result = write_confluence_page_files(
        out_dir,
        page,
        renderer=renderer,
        stable_exported_at=config.markdown.stable_exported_at,
        exported_pages=exported_pages,
    )
    observed_at = now_iso()
    upsert_confluence_page_state(
        state_path,
        ConfluencePageState(
            page_id=page.id,
            space_id=page.space_id,
            space_key=page.space_key,
            title=page.title,
            status=page.status,
            parent_id=page.parent.id if page.parent is not None else None,
            updated_at=page.updated,
            version=page.version,
            content_hash=result.content_hash,
            raw_json_hash=result.raw_json_hash,
            markdown_hash=result.markdown_hash,
            last_seen_at=observed_at,
            last_exported_at=result.exported_at,
        ),
    )
    if command is not None and site_url is not None:
        _log_confluence(
            logging.INFO,
            "wrote confluence page files",
            command=command,
            site_url=site_url,
            operation="confluence_page_write",
            page_id=page.id,
            space_key=page.space_key,
            output_path=result.markdown_path,
            markdown_path=result.markdown_path,
            raw_json_path=result.json_path,
        )


def _representative_issue_keys(
    state_path: Path,
    *,
    decision: SyncDecision,
    scope_type: str,
    scope_value: str,
    fetched_keys: tuple[str, ...],
) -> tuple[str, ...] | None:
    if not decision.representative:
        return None
    if decision.full_refresh:
        return fetched_keys
    return None


def _read_local_issue_source(
    out_dir: Path,
    key: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _read_issue_payload(issue_raw_path(out_dir, key))
    raw_issue = payload.get("raw_issue")
    metadata = payload.get("attachment_metadata")
    if not isinstance(raw_issue, dict):
        raise ValueError(f"Local issue JSON lacks raw_issue: {key}")
    return raw_issue, dict_list(metadata)


def _read_local_comments(out_dir: Path, key: str) -> list[dict[str, Any]]:
    payload = _read_issue_payload(issue_raw_path(out_dir, key))
    return dict_list(payload.get("fetched_comments"))


def _read_issue_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Issue JSON is not an object: {path}")
    return payload


def _read_issue_payloads(out_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    raw_dir = issue_raw_dir(out_dir)
    if not raw_dir.exists():
        return []
    return [(path, _read_issue_payload(path)) for path in sorted(raw_dir.glob("*.json"))]


@dataclass(frozen=True)
class _LocalConfluencePageSource:
    raw_page: dict[str, Any]
    space_key: str | None
    url: str | None
    footer_comments: list[dict[str, Any]]
    inline_comments: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    labels: list[dict[str, Any]]
    ancestors: list[dict[str, Any]]
    child_pages: list[dict[str, Any]]


def _read_local_confluence_page_source(
    out_dir: Path,
    page_id: str,
) -> _LocalConfluencePageSource:
    payload = _read_confluence_page_payload(confluence_page_raw_path(out_dir, page_id))
    raw_page = payload.get("raw_page")
    if not isinstance(raw_page, dict):
        raise ValueError(f"Local Confluence page JSON lacks raw_page: {page_id}")
    return _LocalConfluencePageSource(
        raw_page=raw_page,
        space_key=confluence_payload_space_key(payload),
        url=confluence_payload_url(payload),
        footer_comments=dict_list(payload.get("fetched_footer_comments")),
        inline_comments=dict_list(payload.get("fetched_inline_comments")),
        attachments=dict_list(payload.get("attachment_metadata")),
        labels=dict_list(payload.get("labels")),
        ancestors=dict_list(payload.get("ancestors")),
        child_pages=dict_list(payload.get("child_page_references")),
    )


def _read_confluence_page_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Confluence page JSON is not an object: {path}")
    return payload


def _read_confluence_page_payloads(out_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    raw_dir = confluence_page_raw_dir(out_dir)
    if not raw_dir.exists():
        return []
    return [(path, _read_confluence_page_payload(path)) for path in sorted(raw_dir.glob("*.json"))]


def _local_confluence_exported_pages(
    out_dir: Path,
    *,
    replacement: NormalizedConfluencePage,
    site_url: str,
) -> tuple[NormalizedConfluencePage, ...]:
    return _confluence_export_context(out_dir, replacements=(replacement,), site_url=site_url)


def _confluence_export_context(
    out_dir: Path,
    *,
    replacements: Sequence[NormalizedConfluencePage],
    site_url: str,
) -> tuple[NormalizedConfluencePage, ...]:
    pages_by_id = {page.id: page for page in replacements}
    for _path, payload in _read_confluence_page_payloads(out_dir):
        raw_page = payload.get("raw_page")
        if not isinstance(raw_page, dict):
            continue
        page_id = raw_page.get("id")
        if not isinstance(page_id, str) or page_id in pages_by_id:
            continue
        pages_by_id[page_id] = normalize_confluence_page(
            raw_page,
            footer_comments=dict_list(payload.get("fetched_footer_comments")),
            inline_comments=dict_list(payload.get("fetched_inline_comments")),
            attachments=dict_list(payload.get("attachment_metadata")),
            labels=dict_list(payload.get("labels")),
            ancestors=dict_list(payload.get("ancestors")),
            child_pages=dict_list(payload.get("child_page_references")),
            site_url=site_url,
            space_key=confluence_payload_space_key(payload),
            url=confluence_payload_url(payload),
        )
    return tuple(page for _page_id, page in sorted(pages_by_id.items()))


def _apply_attachment_metadata(
    issue: NormalizedJiraIssue,
    metadata: list[dict[str, Any]],
) -> NormalizedJiraIssue:
    paths_by_id = {
        str(item["id"]): item.get("local_path")
        for item in metadata
        if isinstance(item.get("id"), str) and isinstance(item.get("local_path"), str)
    }
    attachments = [
        attachment.model_copy(update={"local_path": paths_by_id.get(attachment.id or "")})
        for attachment in issue.attachments
    ]
    return issue.model_copy(update={"attachments": attachments})


def _writer_custom_fields(configured: dict[str, str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for label_or_field_id, field_or_label in configured.items():
        if label_or_field_id.startswith("customfield_"):
            fields[label_or_field_id] = field_or_label
        else:
            fields[field_or_label] = label_or_field_id.replace("_", " ").title()
    return fields


def _search_fields(config: ExportConfig) -> tuple[str, ...]:
    base_fields = config.fields.include or list(DEFAULT_FIELD_INCLUDE)
    fields = list(base_fields)
    fields.extend(_writer_custom_fields(config.custom_fields))
    return tuple(dict.fromkeys(field for field in fields if field))


def _manifest_representative_run(state_path: Path) -> dict[str, Any] | None:
    run = latest_successful_representative_run(state_path)
    if run is None:
        return None
    return {
        "id": run.id,
        "command": run.command,
        "scope_type": run.scope_type,
        "scope_value": run.scope_value,
        "finished_at": run.finished_at,
        "issue_keys": list(run.representative_issue_keys),
    }


def _confluence_manifest_representative_run(state_path: Path) -> dict[str, Any] | None:
    run = latest_successful_confluence_representative_run(state_path)
    if run is None:
        return None
    return {
        "id": run.id,
        "command": run.command,
        "scope_type": run.scope_type,
        "scope_value": run.scope_value,
        "finished_at": run.finished_at,
        "page_ids": list(run.representative_page_ids),
    }


def _confluence_manifest_payload(
    out_dir: Path,
    *,
    site_host: str | None = None,
    page_ids: Sequence[str] = (),
    footer_comments: int = 0,
    inline_comments: int = 0,
    attachments: int = 0,
    representative_run: dict[str, Any] | None = None,
    hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generator": {"name": "atlassian-md-export", "version": __version__},
        "confluence_site_host": site_host,
        "output": {"path": str(out_dir.resolve()), "layout_version": 1},
        "last_successful_representative_run": representative_run,
        "exported_page_ids": list(page_ids),
        "counts": {
            "pages": len(page_ids),
            "footer_comments": footer_comments,
            "inline_comments": inline_comments,
            "attachments": attachments,
        },
        "hashes": hashes or {},
    }


def _file_hashes(out_dir: Path) -> dict[str, str]:
    paths: list[Path] = []
    for pattern in (
        "issues/*.md",
        "issues/_raw/*.json",
        "indexes/*.md",
        "attachments/*/*",
    ):
        paths.extend(path for path in out_dir.glob(pattern) if path.is_file())
    return {
        path.relative_to(out_dir).as_posix(): _sha256_file(path)
        for path in sorted(paths, key=lambda item: item.relative_to(out_dir).as_posix())
    }


def _confluence_file_hashes(out_dir: Path) -> dict[str, str]:
    paths: list[Path] = []
    for pattern in (
        "pages/*/*.md",
        "pages/_raw/*.json",
        "indexes/*.md",
        "attachments/*/*",
    ):
        paths.extend(path for path in out_dir.glob(pattern) if path.is_file())
    return {
        path.relative_to(out_dir).as_posix(): _sha256_file(path)
        for path in sorted(paths, key=lambda item: item.relative_to(out_dir).as_posix())
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _issue_key(payload: dict[str, Any], path: Path) -> str:
    raw_issue = payload.get("raw_issue")
    if isinstance(raw_issue, dict):
        key = raw_issue.get("key")
        if isinstance(key, str):
            return key
    return path.stem


def _confluence_page_id(payload: dict[str, Any], path: Path) -> str:
    raw_page = payload.get("raw_page")
    if isinstance(raw_page, dict):
        page_id = raw_page.get("id")
        if isinstance(page_id, str):
            return page_id
    return path.stem


def _site_host_from_payloads(payloads: list[tuple[Path, dict[str, Any]]]) -> str | None:
    for _path, payload in payloads:
        host = _payload_exporter_site_host(payload) or _payload_raw_url_host(
            payload, raw_key="raw_issue", url_keys=("self",)
        )
        if host:
            return host
    return None


def _confluence_site_host_from_payloads(payloads: list[tuple[Path, dict[str, Any]]]) -> str | None:
    for _path, payload in payloads:
        host = _payload_exporter_site_host(payload) or _payload_raw_url_host(
            payload, raw_key="raw_page", url_keys=("self", "url")
        )
        if host:
            return host
    return None


def _payload_exporter_site_host(payload: Mapping[str, Any]) -> str | None:
    exporter = payload.get("exporter")
    if not isinstance(exporter, Mapping):
        return None
    site_host = exporter.get("site_host")
    return site_host if isinstance(site_host, str) else None


def _payload_raw_url_host(
    payload: Mapping[str, Any],
    *,
    raw_key: str,
    url_keys: tuple[str, ...],
) -> str | None:
    raw_payload = payload.get(raw_key)
    if not isinstance(raw_payload, Mapping):
        return None
    for key in url_keys:
        host = _site_host(str(raw_payload.get(key) or ""))
        if host:
            return host
    return None


def _verify_sqlite(path: Path) -> list[str]:
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as error:
        return [f"SQLite state is not parseable: {_display_path(path)}: {error}"]
    if row is None or row[0] != "ok":
        return [
            f"SQLite integrity check failed: {_display_path(path)}: {row[0] if row else 'no result'}"
        ]
    return []


def _verify_state_issue_hashes(out_dir: Path, state_path: Path) -> list[str]:
    try:
        with sqlite3.connect(state_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT issue_key, stable_content_hash, raw_json_hash, markdown_hash
                FROM issues
                ORDER BY issue_key
                """
            ).fetchall()
    except sqlite3.Error as error:
        return [f"SQLite issue state is not readable: {_display_path(state_path)}: {error}"]

    errors: list[str] = []
    for row in rows:
        issue_key = str(row["issue_key"])
        errors.extend(_verify_issue_state_hash_row(out_dir, issue_key, row))
    return errors


def _verify_state_confluence_page_hashes(out_dir: Path, state_path: Path) -> list[str]:
    try:
        with sqlite3.connect(state_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT page_id, content_hash, raw_json_hash, markdown_hash
                FROM confluence_pages
                ORDER BY page_id
                """
            ).fetchall()
    except sqlite3.Error as error:
        return [
            f"SQLite Confluence page state is not readable: {_display_path(state_path)}: {error}"
        ]

    errors: list[str] = []
    for row in rows:
        page_id = str(row["page_id"])
        errors.extend(_verify_confluence_state_hash_row(out_dir, page_id, row))
    return errors


def _verify_issue_state_hash_row(
    out_dir: Path,
    issue_key: str,
    row: sqlite3.Row,
) -> list[str]:
    markdown_path = issue_markdown_path(out_dir, issue_key)
    raw_path = issue_raw_path(out_dir, issue_key)
    errors = _verify_state_markdown_hashes(
        markdown_path,
        row["markdown_hash"],
        row["stable_content_hash"],
        missing_message=f"State issue Markdown missing: {_display_path(markdown_path)}",
        hash_label="State Markdown hash mismatch",
        content_label="State content hash",
    )
    errors.extend(
        _verify_state_file_hash(
            raw_path,
            row["raw_json_hash"],
            missing_message=f"State issue JSON missing: {_display_path(raw_path)}",
            mismatch_label="State raw JSON hash mismatch",
        )
    )
    return errors


def _verify_confluence_state_hash_row(
    out_dir: Path,
    page_id: str,
    row: sqlite3.Row,
) -> list[str]:
    raw_path = confluence_page_raw_path(out_dir, page_id)
    markdown_path = _confluence_markdown_path_for_page_id(out_dir, page_id)
    missing_markdown_path = _display_confluence_markdown_path(out_dir, page_id)
    errors = _verify_state_markdown_hashes(
        markdown_path,
        row["markdown_hash"],
        row["content_hash"],
        missing_message=(
            f"State Confluence page Markdown missing: {_display_path(missing_markdown_path)}"
        ),
        hash_label="State Confluence Markdown hash mismatch",
        content_label="State Confluence content hash",
    )
    errors.extend(
        _verify_state_file_hash(
            raw_path,
            row["raw_json_hash"],
            missing_message=f"State Confluence page JSON missing: {_display_path(raw_path)}",
            mismatch_label="State Confluence raw JSON hash mismatch",
        )
    )
    return errors


def _verify_state_markdown_hashes(
    path: Path | None,
    expected_markdown_hash: object,
    expected_content_hash: object,
    *,
    missing_message: str,
    hash_label: str,
    content_label: str,
) -> list[str]:
    if path is None or not path.is_file():
        return (
            [missing_message]
            if _has_hash(expected_markdown_hash) or _has_hash(expected_content_hash)
            else []
        )
    errors = _verify_state_file_hash(
        path,
        expected_markdown_hash,
        missing_message=missing_message,
        mismatch_label=hash_label,
    )
    errors.extend(_verify_state_content_hash(path, expected_content_hash, label=content_label))
    return errors


def _verify_state_file_hash(
    path: Path,
    expected_hash: object,
    *,
    missing_message: str,
    mismatch_label: str,
) -> list[str]:
    if not path.is_file():
        return [missing_message] if _has_hash(expected_hash) else []
    if not _has_hash(expected_hash):
        return []
    actual_hash = _sha256_file(path)
    if actual_hash == expected_hash:
        return []
    return [f"{mismatch_label}: {_display_path(path)} expected {expected_hash} got {actual_hash}"]


def _verify_state_content_hash(
    path: Path,
    expected_hash: object,
    *,
    label: str,
) -> list[str]:
    if not _has_hash(expected_hash):
        return []
    content_hash, content_error = _markdown_frontmatter_content_hash(path)
    if content_error is not None:
        return [f"{label} unreadable: {content_error}"]
    if content_hash == expected_hash:
        return []
    return [
        f"{label} mismatch: {_display_path(path)} expected {expected_hash} "
        f"got {content_hash or '<missing>'}"
    ]


def _markdown_frontmatter_content_hash(path: Path) -> tuple[str | None, str | None]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        return None, f"{_display_path(path)}: {error}"

    parts = content.split("---\n", 2)
    if len(parts) < 3 or parts[0] != "":
        return None, f"{_display_path(path)} lacks YAML frontmatter"

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as error:
        return None, f"{_display_path(path)} frontmatter is not parseable: {error}"

    if not isinstance(frontmatter, dict):
        return None, f"{_display_path(path)} frontmatter is not a mapping"

    value = frontmatter.get("content_hash")
    return value if isinstance(value, str) else None, None


def _has_hash(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value)


def _verify_manifest_issue_files(out_dir: Path, manifest: Manifest) -> list[str]:
    errors: list[str] = []
    for key in manifest.exported_issue_keys:
        md_path = issue_markdown_path(out_dir, key)
        json_path = issue_raw_path(out_dir, key)
        if not md_path.is_file():
            errors.append(f"Manifest issue Markdown missing: {_display_path(md_path)}")
        if not json_path.is_file():
            errors.append(f"Manifest issue JSON missing: {_display_path(json_path)}")
        else:
            try:
                _read_issue_payload(json_path)
            except (OSError, ValueError) as error:
                errors.append(
                    f"Manifest issue JSON not parseable: {_display_path(json_path)}: {error}"
                )
    return errors


def _verify_manifest_confluence_page_files(
    out_dir: Path,
    manifest: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    raw_page_ids = manifest.get("exported_page_ids", [])
    if not isinstance(raw_page_ids, list):
        return ["Manifest exported_page_ids is not a list."]
    for page_id_value in raw_page_ids:
        if not isinstance(page_id_value, str):
            errors.append("Manifest exported page id is not a string.")
            continue
        page_id = page_id_value
        json_path = confluence_page_raw_path(out_dir, page_id)
        if not json_path.is_file():
            errors.append(f"Manifest Confluence page JSON missing: {_display_path(json_path)}")
            continue
        try:
            payload = _read_confluence_page_payload(json_path)
        except (OSError, ValueError) as error:
            errors.append(
                f"Manifest Confluence page JSON not parseable: {_display_path(json_path)}: {error}"
            )
            continue
        markdown_path = _confluence_markdown_path_from_payload(out_dir, payload)
        if markdown_path is None or not markdown_path.is_file():
            display_path = markdown_path or _display_confluence_markdown_path(out_dir, page_id)
            errors.append(
                f"Manifest Confluence page Markdown missing: {_display_path(display_path)}"
            )
    return errors


def _verify_manifest_hashes(out_dir: Path, manifest: Manifest | Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    hashes = manifest.hashes if isinstance(manifest, Manifest) else manifest.get("hashes", {})
    if not isinstance(hashes, dict):
        return ["Manifest hashes is not an object."]
    for relative_path, expected_hash in sorted(hashes.items()):
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            errors.append("Manifest hash entry is not a string path/hash pair.")
            continue
        target = _safe_relative_target(out_dir, relative_path)
        if target is None:
            errors.append(f"Manifest hash path escapes export dir: {relative_path}")
            continue
        if not target.is_file():
            errors.append(f"Manifest hashed file missing: {_display_path(target)}")
            continue
        actual_hash = _sha256_file(target)
        if actual_hash != expected_hash:
            errors.append(
                f"Manifest hash mismatch: {_display_path(target)} expected {expected_hash} got {actual_hash}"
            )
    return errors


def _verify_index_links(out_dir: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted((out_dir / "indexes").glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            errors.append(f"Index not readable: {_display_path(path)}: {error}")
            continue
        for link in _MARKDOWN_LINK_RE.findall(content):
            if _is_external_or_anchor(link):
                continue
            target = (path.parent / link).resolve()
            if not _within(out_dir, target):
                errors.append(f"Index link escapes export dir: {_display_path(path)} -> {link}")
            elif not target.is_file():
                errors.append(f"Index link target missing: {_display_path(path)} -> {link}")
    return errors


def _verify_attachment_references(out_dir: Path) -> list[str]:
    errors: list[str] = []
    raw_dir = issue_raw_dir(out_dir)
    if not raw_dir.exists():
        return errors
    for path in sorted(raw_dir.glob("*.json")):
        try:
            payload = _read_issue_payload(path)
        except (OSError, ValueError) as error:
            errors.append(
                f"Issue JSON not parseable for attachment check: {_display_path(path)}: {error}"
            )
            continue
        errors.extend(_verify_issue_attachment_metadata(out_dir, path, payload))
        markdown_path = issue_markdown_path(out_dir, path.stem)
        if markdown_path.exists():
            errors.extend(_verify_markdown_attachment_links(out_dir, markdown_path))
    return errors


def _verify_confluence_attachment_references(out_dir: Path) -> list[str]:
    errors: list[str] = []
    raw_dir = confluence_page_raw_dir(out_dir)
    if not raw_dir.exists():
        return errors
    for path in sorted(raw_dir.glob("*.json")):
        try:
            payload = _read_confluence_page_payload(path)
        except (OSError, ValueError) as error:
            errors.append(
                f"Confluence page JSON not parseable for attachment check: {_display_path(path)}: {error}"
            )
            continue
        markdown_path = _confluence_markdown_path_from_payload(out_dir, payload)
        errors.extend(_verify_confluence_attachment_metadata(out_dir, path, payload, markdown_path))
        if markdown_path is not None and markdown_path.exists():
            errors.extend(
                _verify_markdown_attachment_links(
                    out_dir,
                    markdown_path,
                    escape_label="Confluence Markdown attachment link escapes export dir",
                    missing_label="Confluence Markdown attachment link target missing",
                )
            )
    return errors


def _verify_issue_attachment_metadata(
    out_dir: Path,
    source_path: Path,
    payload: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    for metadata in dict_list(payload.get("attachment_metadata")):
        local_path = metadata.get("local_path")
        if isinstance(local_path, str):
            errors.extend(
                _verify_relative_file_reference(
                    out_dir,
                    source_path,
                    out_dir / "issues",
                    local_path,
                    escape_label="Attachment path escapes export dir",
                    missing_label="Downloaded attachment missing",
                )
            )
    return errors


def _verify_confluence_attachment_metadata(
    out_dir: Path,
    source_path: Path,
    payload: Mapping[str, Any],
    markdown_path: Path | None,
) -> list[str]:
    errors: list[str] = []
    for metadata in dict_list(payload.get("attachment_metadata")):
        local_path = metadata.get("local_path")
        if not isinstance(local_path, str):
            continue
        if markdown_path is None or not markdown_path.is_file():
            errors.append(
                "Downloaded Confluence attachment cannot be resolved because "
                f"page Markdown is missing: {_display_path(source_path)} -> {local_path}"
            )
            continue
        errors.extend(
            _verify_relative_file_reference(
                out_dir,
                source_path,
                markdown_path.parent,
                local_path,
                escape_label="Confluence attachment path escapes export dir",
                missing_label="Downloaded Confluence attachment missing",
            )
        )
    return errors


def _verify_markdown_attachment_links(
    out_dir: Path,
    markdown_path: Path,
    *,
    escape_label: str = "Markdown attachment link escapes export dir",
    missing_label: str = "Markdown attachment link target missing",
) -> list[str]:
    content = markdown_path.read_text(encoding="utf-8")
    errors: list[str] = []
    for link in _MARKDOWN_LINK_RE.findall(content):
        if not _is_attachment_link(link):
            continue
        errors.extend(
            _verify_relative_file_reference(
                out_dir,
                markdown_path,
                markdown_path.parent,
                link,
                escape_label=escape_label,
                missing_label=missing_label,
            )
        )
    return errors


def _is_attachment_link(link: str) -> bool:
    return not _is_external_or_anchor(link) and "attachments/" in link


def _verify_relative_file_reference(
    out_dir: Path,
    source_path: Path,
    base_path: Path,
    relative_path: str,
    *,
    escape_label: str,
    missing_label: str,
) -> list[str]:
    target = (base_path / relative_path).resolve()
    if not _within(out_dir, target):
        return [f"{escape_label}: {_display_path(source_path)} -> {relative_path}"]
    if not target.is_file():
        return [f"{missing_label}: {_display_path(source_path)} -> {relative_path}"]
    return []


def _local_issue_keys(out_dir: Path) -> set[str]:
    keys = {path.stem for path in (out_dir / "issues").glob("*.md")}
    keys.update(path.stem for path in issue_raw_dir(out_dir).glob("*.json"))
    keys.update(path.name for path in (out_dir / "attachments").iterdir() if path.is_dir())
    return keys


def _local_confluence_page_ids(out_dir: Path) -> set[str]:
    page_ids: set[str] = set()
    for path in confluence_page_raw_dir(out_dir).glob("*.json"):
        try:
            page_ids.add(_confluence_page_id(_read_confluence_page_payload(path), path))
        except (OSError, ValueError):
            page_ids.add(path.stem)
    for path in (out_dir / "pages").glob("*/*.md"):
        page_id = _markdown_frontmatter_page_id(path)
        if page_id:
            page_ids.add(page_id)
    attachments_dir = out_dir / "attachments"
    if attachments_dir.is_dir():
        page_ids.update(path.name for path in attachments_dir.iterdir() if path.is_dir())
    return page_ids


def _confluence_markdown_path_for_page_id(out_dir: Path, page_id: str) -> Path | None:
    raw_path = confluence_page_raw_path(out_dir, page_id)
    if raw_path.is_file():
        try:
            path = _confluence_markdown_path_from_payload(
                out_dir,
                _read_confluence_page_payload(raw_path),
            )
            if path is not None and path.is_file():
                return path
        except (OSError, ValueError):
            pass
    candidates = _confluence_markdown_paths_for_page_id(out_dir, page_id)
    return candidates[0] if candidates else None


def _confluence_markdown_paths_for_page_id(out_dir: Path, page_id: str) -> tuple[Path, ...]:
    matches: list[Path] = []
    for path in sorted((out_dir / "pages").glob("*/*.md")):
        if _markdown_frontmatter_page_id(path) == page_id:
            matches.append(path)
    return tuple(matches)


def _confluence_markdown_path_from_payload(
    out_dir: Path,
    payload: Mapping[str, Any],
) -> Path | None:
    raw_page = payload.get("raw_page")
    if not isinstance(raw_page, Mapping):
        return None
    page = normalize_confluence_page(
        raw_page,
        labels=dict_list(payload.get("labels")),
        ancestors=dict_list(payload.get("ancestors")),
        child_pages=dict_list(payload.get("child_page_references")),
        space_key=confluence_payload_space_key(payload),
        url=confluence_payload_url(payload),
    )
    return confluence_page_markdown_path(out_dir, page)


def _display_confluence_markdown_path(out_dir: Path, page_id: str) -> Path:
    raw_path = confluence_page_raw_path(out_dir, page_id)
    if raw_path.is_file():
        try:
            path = _confluence_markdown_path_from_payload(
                out_dir,
                _read_confluence_page_payload(raw_path),
            )
            if path is not None:
                return path
        except (OSError, ValueError):
            pass
    return out_dir / "pages" / "*" / f"{page_id}-*.md"


def _markdown_frontmatter_page_id(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    parts = content.split("---\n", 2)
    if len(parts) < 3 or parts[0] != "":
        return None
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(frontmatter, dict):
        return None
    value = frontmatter.get("id")
    return value if isinstance(value, str) else None


def _safe_relative_target(out_dir: Path, relative_path: str) -> Path | None:
    if relative_path.startswith("/") or ".." in Path(relative_path).parts:
        return None
    target = (out_dir / relative_path).resolve()
    return target if _within(out_dir, target) else None


def _within(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _is_external_or_anchor(link: str) -> bool:
    return link.startswith("#") or bool(urlparse(link).scheme)


def _site_host(site_url: str | None) -> str | None:
    if not site_url:
        return None
    return urlparse(site_url).hostname


def _log_confluence(
    level: int,
    message: str,
    *,
    command: str,
    site_url: str,
    operation: str,
    page_id: str | None = None,
    space_key: str | None = None,
    **extra: Any,
) -> None:
    context: dict[str, Any] = {
        "provider": "confluence",
        "command": command,
        "operation": operation,
    }
    site_host = _site_host(site_url)
    if site_host is not None:
        context["site_host"] = site_host
    if page_id is not None:
        context["page_id"] = page_id
    if space_key is not None:
        context["space_key"] = space_key
    for key, value in extra.items():
        if value is not None:
            context[key] = _log_value(value)
    logger.log(level, message, extra=context)


def _log_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return tuple(_log_value(item) for item in value)
    if isinstance(value, list):
        return [_log_value(item) for item in value]
    return value


def _confluence_scope_log_context(
    scope_type: str,
    scope_value: str,
    exact_page_ids: tuple[str, ...],
) -> dict[str, Any]:
    context: dict[str, Any] = {"scope_type": scope_type}
    if scope_type == "space":
        context["space_key"] = scope_value
    elif scope_type == "ancestor":
        context["ancestor_page_id"] = scope_value
    elif scope_type == "page":
        page_ids = exact_page_ids or (scope_value,)
        context["page_ids"] = page_ids
        if len(page_ids) == 1:
            context["page_id"] = page_ids[0]
    elif scope_type == "cql":
        context["cql_scope"] = True
    return context


def _safe_resource_path(path_or_url: str) -> str:
    parsed = urlparse(path_or_url)
    if parsed.scheme or parsed.netloc:
        return parsed.path or "/"
    path = path_or_url.split("?", 1)[0]
    return path or "/"


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return [item for item in value]


def _display_path(path: Path) -> str:
    return str(path)


def _partial_failure_message(
    command: str,
    failures: list[str],
    *,
    provider: str = "jira",
) -> str:
    executable = "confluence-md-export" if provider == "confluence" else "jira-md-export"
    return (
        f"{executable} {command} had partial failures; existing completed files remain atomic: "
        + "; ".join(failures)
    )
