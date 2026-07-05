"""Typer entrypoints for Atlassian Markdown export commands."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated
from typing import Callable
from typing import TypeVar

import typer
from rich.console import Console
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TextColumn

from atlassian_md_export.client import AtlassianClientError
from atlassian_md_export.client import JiraCredentials
from atlassian_md_export.client import MissingCredentialsError
from atlassian_md_export.config import ConfluenceCredentials
from atlassian_md_export.config import ExportConfig
from atlassian_md_export.config import MissingConfluenceCredentialsError
from atlassian_md_export.config import load_config, load_dotenv
from atlassian_md_export.config import load_confluence_config
from atlassian_md_export.log import configure_logging
from atlassian_md_export.operations import AttachmentOptions
from atlassian_md_export.operations import ExportCommandError
from atlassian_md_export.operations import build_confluence_client
from atlassian_md_export.operations import build_jira_client
from atlassian_md_export.operations import clean_confluence_export
from atlassian_md_export.operations import clean_export
from atlassian_md_export.operations import initialize_confluence_output
from atlassian_md_export.operations import regenerate_confluence_indexes
from atlassian_md_export.operations import regenerate_indexes
from atlassian_md_export.operations import run_attachments
from atlassian_md_export.operations import run_comments
from atlassian_md_export.operations import run_confluence_attachments
from atlassian_md_export.operations import run_confluence_comments
from atlassian_md_export.operations import run_confluence_page
from atlassian_md_export.operations import run_confluence_pull
from atlassian_md_export.operations import run_issue
from atlassian_md_export.operations import run_pull
from atlassian_md_export.operations import verify_confluence_export
from atlassian_md_export.operations import verify_export
from atlassian_md_export.writer import initialize_output

T = TypeVar("T")
app = typer.Typer(
    help="Export Jira Cloud issues to deterministic Markdown and JSON.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
confluence_app = typer.Typer(
    help="Export Confluence Cloud pages to deterministic Markdown and JSON.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
console = Console()
logger = logging.getLogger(__name__)


def _config_option() -> Path | None:
    return None


@app.callback()
def main(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Enable diagnostic logging."),
    ] = False,
    json_logs: Annotated[
        bool,
        typer.Option("--json-logs", help="Emit one JSON object per log event."),
    ] = False,
) -> None:
    configure_logging(verbose=verbose, json_logs=json_logs)


@confluence_app.callback()
def confluence_main(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Enable diagnostic logging."),
    ] = False,
    json_logs: Annotated[
        bool,
        typer.Option("--json-logs", help="Emit one JSON object per log event."),
    ] = False,
) -> None:
    configure_logging(verbose=verbose, json_logs=json_logs)


@app.command("init")
def init_command(
    out: Annotated[
        Path,
        typer.Option("--out", help="Export directory to initialize.", file_okay=False),
    ],
) -> None:
    """Initialize a local export directory without contacting Jira."""

    result = initialize_output(out)
    logger.info(
        "initialized export directory",
        extra={
            "command": "init",
            "output_path": str(result.out_dir),
            "manifest_path": str(result.manifest_path),
            "state_path": str(result.state_path),
        },
    )
    console.print(f"Initialized Jira Markdown export at {result.out_dir}")


@confluence_app.command("init")
def confluence_init_command(
    out: Annotated[
        Path,
        typer.Option("--out", help="Export directory to initialize.", file_okay=False),
    ],
) -> None:
    """Initialize a local Confluence export directory without contacting Confluence."""

    result = initialize_confluence_output(out)
    logger.info(
        "initialized confluence export directory",
        extra={
            "command": "init",
            "output_path": str(result.out_dir),
            "manifest_path": str(result.manifest_path),
            "state_path": str(result.state_path),
        },
    )
    console.print(f"Initialized Confluence Markdown export at {result.out_dir}")


@confluence_app.command("pull")
def confluence_pull(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    site: Annotated[str | None, typer.Option("--site", help="Confluence site URL.")] = None,
    space: Annotated[str | None, typer.Option("--space", help="Confluence space key.")] = None,
    cql: Annotated[str | None, typer.Option("--cql", help="Confluence CQL query.")] = None,
    ancestor: Annotated[
        str | None,
        typer.Option("--ancestor", help="Root Confluence page id for descendant export."),
    ] = None,
    page: Annotated[str | None, typer.Option("--page", help="Exact Confluence page id.")] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Only fetch pages updated at or after this timestamp."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Refetch all pages in scope.")] = False,
    concurrency: Annotated[
        int | None,
        typer.Option("--concurrency", min=1, help="Maximum concurrent Confluence operations."),
    ] = None,
    download_attachments: Annotated[
        bool,
        typer.Option("--download-attachments", help="Download eligible attachment binaries."),
    ] = False,
    attachment_max_mb: Annotated[
        float | None,
        typer.Option("--attachment-max-mb", min=0.0, help="Maximum attachment size in MiB."),
    ] = None,
    attachment_include: Annotated[
        list[str] | None,
        typer.Option(
            "--attachment-include",
            help="Shell-style filename glob for attachments; repeatable.",
        ),
    ] = None,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Export Confluence pages for a representative or exact pull scope."""

    config_values = _load_confluence_context(config, site)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    scope_type, scope_value = _confluence_pull_scope(
        config_values=config_values,
        space=space,
        cql=cql,
        ancestor=ancestor,
        page=page,
    )
    resolved_site = _resolved_confluence_site(site, config_values)
    scope_kwargs = _confluence_scope_kwargs(scope_type, scope_value)
    summary = _with_progress(
        "Exporting Confluence pages...",
        lambda: run_confluence_pull(
            out,
            client=build_confluence_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            since=since,
            force=force,
            concurrency=concurrency or config_values.sync.concurrency,
            attachment_options=_attachment_options(
                download=download_attachments or config_values.sync.download_attachments,
                max_mb=attachment_max_mb,
                include=attachment_include,
            ),
            **scope_kwargs,
        ),
    )
    console.print(f"Exported {len(summary.page_ids)} page(s).")


@confluence_app.command("page")
def confluence_page(
    page_ids: Annotated[list[str], typer.Argument(metavar="PAGE_ID")],
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    site: Annotated[str | None, typer.Option("--site", help="Confluence site URL.")] = None,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Repull exact Confluence pages."""

    config_values = _load_confluence_context(config, site)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    resolved_site = _resolved_confluence_site(site, config_values)
    summary = _with_progress(
        "Repulling Confluence pages...",
        lambda: run_confluence_page(
            out,
            client=build_confluence_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            page_ids=page_ids,
        ),
    )
    console.print(f"Repulled {len(summary.page_ids)} page(s).")


@confluence_app.command("comments")
def confluence_comments(
    page_ids: Annotated[list[str], typer.Argument(metavar="PAGE_ID")],
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    site: Annotated[str | None, typer.Option("--site", help="Confluence site URL.")] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Refresh comments even if cached."),
    ] = False,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Refresh authoritative comments for existing local Confluence page JSON."""

    config_values = _load_confluence_context(config, site)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    resolved_site = _resolved_confluence_site(site, config_values)
    summary = _with_progress(
        "Refreshing Confluence comments...",
        lambda: run_confluence_comments(
            out,
            client=build_confluence_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            page_ids=page_ids,
            force=force,
        ),
    )
    console.print(f"Refreshed comments for {len(summary.page_ids)} page(s).")


@confluence_app.command("attachments")
def confluence_attachments(
    page_ids: Annotated[list[str], typer.Argument(metavar="PAGE_ID")],
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    site: Annotated[str | None, typer.Option("--site", help="Confluence site URL.")] = None,
    attachment_max_mb: Annotated[
        float | None,
        typer.Option("--attachment-max-mb", min=0.0, help="Maximum attachment size in MiB."),
    ] = None,
    attachment_include: Annotated[
        list[str] | None,
        typer.Option(
            "--attachment-include",
            help="Shell-style filename glob for attachments; repeatable.",
        ),
    ] = None,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Download attachments for existing local Confluence page JSON."""

    config_values = _load_confluence_context(config, site)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    resolved_site = _resolved_confluence_site(site, config_values)
    summary = _with_progress(
        "Downloading Confluence attachments...",
        lambda: run_confluence_attachments(
            out,
            client=build_confluence_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            page_ids=page_ids,
            attachment_options=_attachment_options(
                download=True,
                max_mb=attachment_max_mb,
                include=attachment_include,
            ),
        ),
    )
    console.print(f"Processed attachments for {len(summary.page_ids)} page(s).")


@confluence_app.command("verify")
def confluence_verify(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Verify local Confluence export consistency without contacting Confluence."""

    load_dotenv()
    load_confluence_config(config)
    result = verify_confluence_export(out)
    if not result.ok:
        console.print("Verification failed:")
        for error in result.errors:
            console.print(f"- {error}")
        raise typer.Exit(1)
    console.print(f"Verified Confluence Markdown export at {out.resolve()}")


@confluence_app.command("index")
def confluence_index(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
) -> None:
    """Regenerate local deterministic Confluence indexes."""

    load_dotenv()
    load_confluence_config(config)
    paths = _friendly_call(lambda: regenerate_confluence_indexes(out))
    console.print(f"Regenerated {len(paths)} Confluence index file(s).")


@confluence_app.command("clean")
def confluence_clean(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    remove_missing: Annotated[
        bool,
        typer.Option("--remove-missing", help="Remove pages absent from representative pull."),
    ] = False,
) -> None:
    """Remove local pages absent from the last representative Confluence pull."""

    load_dotenv()
    load_confluence_config(config)
    result = _friendly_call(lambda: clean_confluence_export(out, remove_missing=remove_missing))
    console.print(f"Removed {len(result.removed_page_ids)} page(s).")


@app.command()
def pull(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    site: Annotated[str | None, typer.Option("--site", help="Jira site URL.")] = None,
    project: Annotated[str | None, typer.Option("--project", help="Jira project key.")] = None,
    jql: Annotated[str | None, typer.Option("--jql", help="Jira JQL query.")] = None,
    issue: Annotated[str | None, typer.Option("--issue", help="Exact Jira issue key.")] = None,
    since: Annotated[
        str | None,
        typer.Option("--since", help="Only fetch issues updated at or after this timestamp."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Refetch all issues in scope.")] = False,
    concurrency: Annotated[
        int | None,
        typer.Option("--concurrency", min=1, help="Maximum concurrent Jira operations."),
    ] = None,
    download_attachments: Annotated[
        bool,
        typer.Option("--download-attachments", help="Download eligible attachment binaries."),
    ] = False,
    attachment_max_mb: Annotated[
        float | None,
        typer.Option("--attachment-max-mb", min=0.0, help="Maximum attachment size in MiB."),
    ] = None,
    attachment_include: Annotated[
        list[str] | None,
        typer.Option(
            "--attachment-include",
            help="Shell-style filename glob for attachments; repeatable.",
        ),
    ] = None,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Export Jira issues and authoritative comments."""

    config_values = _load_jira_context(config, site)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    resolved_site = _resolved_site(site, config_values)
    resolved_project = project or (config_values.project if not jql and not issue else None)
    resolved_concurrency = concurrency or config_values.sync.concurrency
    summary = _with_progress(
        "Exporting Jira issues...",
        lambda: run_pull(
            out,
            client=build_jira_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            project=resolved_project,
            jql=jql,
            issue=issue,
            since=since,
            force=force,
            concurrency=resolved_concurrency,
            attachment_options=_attachment_options(
                download=download_attachments or config_values.sync.download_attachments,
                max_mb=attachment_max_mb,
                include=attachment_include,
            ),
        ),
    )
    console.print(f"Exported {len(summary.issue_keys)} issue(s).")


@app.command()
def issue(
    keys: Annotated[list[str], typer.Argument(metavar="KEY")],
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    download_attachments: Annotated[
        bool,
        typer.Option("--download-attachments", help="Download eligible attachment binaries."),
    ] = False,
    attachment_max_mb: Annotated[
        float | None,
        typer.Option("--attachment-max-mb", min=0.0, help="Maximum attachment size in MiB."),
    ] = None,
    attachment_include: Annotated[
        list[str] | None,
        typer.Option(
            "--attachment-include",
            help="Shell-style filename glob for attachments; repeatable.",
        ),
    ] = None,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Repull exact Jira issue keys."""

    config_values = _load_jira_context(config, None)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    resolved_site = _resolved_site(None, config_values)
    summary = _with_progress(
        "Repulling Jira issues...",
        lambda: run_issue(
            out,
            client=build_jira_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            keys=keys,
            attachment_options=_attachment_options(
                download=download_attachments or config_values.sync.download_attachments,
                max_mb=attachment_max_mb,
                include=attachment_include,
            ),
        ),
    )
    console.print(f"Repulled {len(summary.issue_keys)} issue(s).")


@app.command()
def comments(
    keys: Annotated[list[str], typer.Argument(metavar="KEY")],
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Refresh comments even if cached.")
    ] = False,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Refresh authoritative comments for existing local issue JSON."""

    config_values = _load_jira_context(config, None)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    resolved_site = _resolved_site(None, config_values)
    summary = _with_progress(
        "Refreshing Jira comments...",
        lambda: run_comments(
            out,
            client=build_jira_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            keys=keys,
            force=force,
        ),
    )
    console.print(f"Refreshed comments for {len(summary.issue_keys)} issue(s).")


@app.command()
def attachments(
    keys: Annotated[list[str], typer.Argument(metavar="KEY")],
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="YAML config path.", exists=True, dir_okay=False),
    ] = None,
    attachment_max_mb: Annotated[
        float | None,
        typer.Option("--attachment-max-mb", min=0.0, help="Maximum attachment size in MiB."),
    ] = None,
    attachment_include: Annotated[
        list[str] | None,
        typer.Option(
            "--attachment-include",
            help="Shell-style filename glob for attachments; repeatable.",
        ),
    ] = None,
    stable_exported_at: Annotated[
        bool,
        typer.Option("--stable-exported-at", help="Freeze exported_at for cleaner diffs."),
    ] = False,
) -> None:
    """Download attachments for existing local issue JSON."""

    config_values = _load_jira_context(config, None)
    config_values = _with_stable_exported_at(config_values, stable_exported_at)
    resolved_site = _resolved_site(None, config_values)
    summary = _with_progress(
        "Downloading Jira attachments...",
        lambda: run_attachments(
            out,
            client=build_jira_client(resolved_site),
            site_url=resolved_site,
            config=config_values,
            keys=keys,
            attachment_options=_attachment_options(
                download=True,
                max_mb=attachment_max_mb,
                include=attachment_include,
            ),
        ),
    )
    console.print(f"Processed attachments for {len(summary.issue_keys)} issue(s).")


@app.command()
def verify(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
) -> None:
    """Verify local export consistency without contacting Jira."""

    result = verify_export(out)
    if not result.ok:
        console.print("Verification failed:")
        for error in result.errors:
            console.print(f"- {error}")
        raise typer.Exit(1)
    console.print(f"Verified Jira Markdown export at {out.resolve()}")


@app.command()
def index(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
) -> None:
    """Regenerate local deterministic indexes."""

    paths = _friendly_call(lambda: regenerate_indexes(out))
    console.print(f"Regenerated {len(paths)} index file(s).")


@app.command()
def clean(
    out: Annotated[Path, typer.Option("--out", help="Export directory.", file_okay=False)],
    remove_missing: Annotated[
        bool,
        typer.Option("--remove-missing", help="Remove issues absent from representative pull."),
    ] = False,
) -> None:
    """Remove local issues absent from the last representative pull."""

    result = _friendly_call(lambda: clean_export(out, remove_missing=remove_missing))
    console.print(f"Removed {len(result.removed_issue_keys)} issue(s).")


def _load_confluence_context(config_path: Path | None, site: str | None) -> ExportConfig:
    load_dotenv()
    config_values = load_confluence_config(config_path)
    missing: list[str] = []
    if not _confluence_site(site, config_values):
        missing.append("CONFLUENCE_SITE or ATLASSIAN_SITE or --site")
    try:
        ConfluenceCredentials.from_environment()
    except MissingConfluenceCredentialsError as error:
        missing.extend(error.missing)

    if missing:
        console.print(
            "Missing Confluence configuration: set "
            f"{', '.join(missing)}. API tokens are never printed."
        )
        raise typer.Exit(2)

    return config_values


def _resolved_confluence_site(site: str | None, config_values: ExportConfig) -> str:
    resolved = _confluence_site(site, config_values)
    if not resolved:
        raise ExportCommandError(
            "Missing Confluence site: set CONFLUENCE_SITE, ATLASSIAN_SITE, config site, or --site."
        )
    return resolved


def _confluence_site(site: str | None, config_values: ExportConfig) -> str | None:
    return (
        site
        or config_values.site
        or os.environ.get("CONFLUENCE_SITE")
        or os.environ.get("ATLASSIAN_SITE")
    )


def _confluence_pull_scope(
    *,
    config_values: ExportConfig,
    space: str | None,
    cql: str | None,
    ancestor: str | None,
    page: str | None,
) -> tuple[str, str]:
    resolved_space = space or (config_values.space if not any((cql, ancestor, page)) else None)
    scopes = [
        ("space", resolved_space),
        ("cql", cql),
        ("ancestor", ancestor),
        ("page", page),
    ]
    selected = [(scope_type, value) for scope_type, value in scopes if value]
    if len(selected) != 1:
        console.print(
            "Choose exactly one Confluence pull scope: --space, --cql, --ancestor, or --page."
        )
        raise typer.Exit(2)
    return selected[0]


def _confluence_scope_kwargs(scope_type: str, scope_value: str) -> dict[str, str | None]:
    return {
        "space": scope_value if scope_type == "space" else None,
        "cql": scope_value if scope_type == "cql" else None,
        "ancestor": scope_value if scope_type == "ancestor" else None,
        "page": scope_value if scope_type == "page" else None,
    }


def _load_jira_context(config_path: Path | None, site: str | None) -> ExportConfig:
    load_dotenv()
    config_values = load_config(config_path)
    missing: list[str] = []
    if not site and not config_values.site and not os.environ.get("JIRA_SITE"):
        missing.append("JIRA_SITE or --site")
    try:
        JiraCredentials.from_environment()
    except MissingCredentialsError as error:
        missing.extend(error.missing)

    if missing:
        console.print(
            f"Missing Jira configuration: set {', '.join(missing)}. API tokens are never printed."
        )
        raise typer.Exit(2)

    return config_values


def _resolved_site(site: str | None, config_values: ExportConfig) -> str:
    resolved = site or config_values.site or os.environ.get("JIRA_SITE")
    if not resolved:
        raise ExportCommandError("Missing Jira site: set JIRA_SITE, config site, or --site.")
    return resolved


def _attachment_options(
    *,
    download: bool,
    max_mb: float | None,
    include: list[str] | None,
) -> AttachmentOptions:
    return AttachmentOptions(
        download=download,
        max_mb=max_mb,
        include_patterns=tuple(include or ()),
    )


def _with_stable_exported_at(config_values: ExportConfig, enabled: bool) -> ExportConfig:
    if not enabled:
        return config_values
    return config_values.model_copy(
        update={"markdown": config_values.markdown.model_copy(update={"stable_exported_at": True})}
    )


def _with_progress(message: str, callback: Callable[[], T]) -> T:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(message, total=None)
        return _friendly_call(callback)


def _friendly_call(callback: Callable[[], T]) -> T:
    try:
        return callback()
    except (ExportCommandError, AtlassianClientError, ValueError, OSError) as error:
        console.print(str(error))
        raise typer.Exit(1) from error
