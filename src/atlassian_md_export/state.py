"""SQLite state for local export directories."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3
REPRESENTATIVE_SCOPE_TYPES = frozenset({"project", "jql"})
CONFLUENCE_STATE_COMPATIBILITY_VERSION = "confluence-v1"
CONFLUENCE_REPRESENTATIVE_SCOPE_TYPES = frozenset({"space", "cql", "ancestor"})
_SCHEMA_VERSION_STATEMENTS = {3: "PRAGMA user_version = 3"}
_CONFLUENCE_COMPATIBILITY_COLUMN = "TEXT NOT NULL DEFAULT 'confluence-v1'"
_COLUMN_MIGRATION_STATEMENTS = {
    ("export_runs", "partial_failure", "INTEGER NOT NULL DEFAULT 0"): (
        "ALTER TABLE export_runs ADD COLUMN partial_failure INTEGER NOT NULL DEFAULT 0"
    ),
    ("export_runs", "failure_message", "TEXT"): (
        "ALTER TABLE export_runs ADD COLUMN failure_message TEXT"
    ),
    ("export_runs", "sync_since", "TEXT"): "ALTER TABLE export_runs ADD COLUMN sync_since TEXT",
    ("export_runs", "force", "INTEGER NOT NULL DEFAULT 0"): (
        "ALTER TABLE export_runs ADD COLUMN force INTEGER NOT NULL DEFAULT 0"
    ),
    ("export_runs", "exact_issue_keys_json", "TEXT"): (
        "ALTER TABLE export_runs ADD COLUMN exact_issue_keys_json TEXT"
    ),
    ("confluence_export_runs", "partial_failure", "INTEGER NOT NULL DEFAULT 0"): (
        "ALTER TABLE confluence_export_runs ADD COLUMN partial_failure INTEGER NOT NULL DEFAULT 0"
    ),
    ("confluence_export_runs", "failure_message", "TEXT"): (
        "ALTER TABLE confluence_export_runs ADD COLUMN failure_message TEXT"
    ),
    ("confluence_export_runs", "sync_since", "TEXT"): (
        "ALTER TABLE confluence_export_runs ADD COLUMN sync_since TEXT"
    ),
    ("confluence_export_runs", "force", "INTEGER NOT NULL DEFAULT 0"): (
        "ALTER TABLE confluence_export_runs ADD COLUMN force INTEGER NOT NULL DEFAULT 0"
    ),
    ("confluence_export_runs", "exact_page_ids_json", "TEXT"): (
        "ALTER TABLE confluence_export_runs ADD COLUMN exact_page_ids_json TEXT"
    ),
    ("confluence_export_runs", "compatibility_version", _CONFLUENCE_COMPATIBILITY_COLUMN): (
        "ALTER TABLE confluence_export_runs "
        "ADD COLUMN compatibility_version TEXT NOT NULL DEFAULT 'confluence-v1'"
    ),
    ("confluence_pages", "space_id", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN space_id TEXT"
    ),
    ("confluence_pages", "space_key", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN space_key TEXT"
    ),
    ("confluence_pages", "title", "TEXT"): "ALTER TABLE confluence_pages ADD COLUMN title TEXT",
    ("confluence_pages", "status", "TEXT"): "ALTER TABLE confluence_pages ADD COLUMN status TEXT",
    ("confluence_pages", "parent_id", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN parent_id TEXT"
    ),
    ("confluence_pages", "updated_at", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN updated_at TEXT"
    ),
    ("confluence_pages", "version", "INTEGER"): (
        "ALTER TABLE confluence_pages ADD COLUMN version INTEGER"
    ),
    ("confluence_pages", "content_hash", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN content_hash TEXT"
    ),
    ("confluence_pages", "raw_json_hash", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN raw_json_hash TEXT"
    ),
    ("confluence_pages", "markdown_hash", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN markdown_hash TEXT"
    ),
    ("confluence_pages", "last_seen_at", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN last_seen_at TEXT"
    ),
    ("confluence_pages", "last_exported_at", "TEXT"): (
        "ALTER TABLE confluence_pages ADD COLUMN last_exported_at TEXT"
    ),
}


@dataclass(frozen=True)
class IssueState:
    issue_key: str
    issue_id: str | None = None
    updated_at: str | None = None
    stable_content_hash: str | None = None
    raw_json_hash: str | None = None
    markdown_hash: str | None = None
    last_seen_at: str | None = None
    last_exported_at: str | None = None


@dataclass(frozen=True)
class ExportRun:
    id: int
    command: str
    scope_type: str | None
    scope_value: str | None
    started_at: str | None
    finished_at: str | None
    succeeded: bool
    partial_failure: bool
    representative_issue_keys: tuple[str, ...]
    sync_since: str | None
    force: bool
    exact_issue_keys: tuple[str, ...]


@dataclass(frozen=True)
class SyncDecision:
    full_refresh: bool
    since: str | None
    force: bool
    representative: bool
    exact_issue_keys: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ConfluencePageState:
    page_id: str
    space_id: str | None = None
    space_key: str | None = None
    title: str | None = None
    status: str | None = None
    parent_id: str | None = None
    updated_at: str | None = None
    version: int | None = None
    content_hash: str | None = None
    raw_json_hash: str | None = None
    markdown_hash: str | None = None
    last_seen_at: str | None = None
    last_exported_at: str | None = None


@dataclass(frozen=True)
class ConfluenceExportRun:
    id: int
    command: str
    scope_type: str | None
    scope_value: str | None
    started_at: str | None
    finished_at: str | None
    succeeded: bool
    partial_failure: bool
    representative_page_ids: tuple[str, ...]
    sync_since: str | None
    force: bool
    exact_page_ids: tuple[str, ...]
    compatibility_version: str


@dataclass(frozen=True)
class ConfluenceSyncDecision:
    full_refresh: bool
    since: str | None
    force: bool
    representative: bool
    exact_page_ids: tuple[str, ...]
    reason: str


def initialize_state(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS export_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                scope_type TEXT,
                scope_value TEXT,
                started_at TEXT,
                finished_at TEXT,
                succeeded INTEGER NOT NULL DEFAULT 0,
                partial_failure INTEGER NOT NULL DEFAULT 0,
                failure_message TEXT,
                representative_issue_keys_json TEXT,
                sync_since TEXT,
                force INTEGER NOT NULL DEFAULT 0,
                exact_issue_keys_json TEXT
            );

            CREATE TABLE IF NOT EXISTS issues (
                issue_key TEXT PRIMARY KEY,
                issue_id TEXT,
                updated_at TEXT,
                stable_content_hash TEXT,
                raw_json_hash TEXT,
                markdown_hash TEXT,
                last_seen_at TEXT,
                last_exported_at TEXT
            );

            CREATE TABLE IF NOT EXISTS confluence_export_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                scope_type TEXT,
                scope_value TEXT,
                started_at TEXT,
                finished_at TEXT,
                succeeded INTEGER NOT NULL DEFAULT 0,
                partial_failure INTEGER NOT NULL DEFAULT 0,
                failure_message TEXT,
                representative_page_ids_json TEXT,
                sync_since TEXT,
                force INTEGER NOT NULL DEFAULT 0,
                exact_page_ids_json TEXT,
                compatibility_version TEXT NOT NULL DEFAULT 'confluence-v1'
            );

            CREATE TABLE IF NOT EXISTS confluence_pages (
                page_id TEXT PRIMARY KEY,
                space_id TEXT,
                space_key TEXT,
                title TEXT,
                status TEXT,
                parent_id TEXT,
                updated_at TEXT,
                version INTEGER,
                content_hash TEXT,
                raw_json_hash TEXT,
                markdown_hash TEXT,
                last_seen_at TEXT,
                last_exported_at TEXT
            );
            """
        )
        _ensure_column(connection, "export_runs", "partial_failure", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "export_runs", "failure_message", "TEXT")
        _ensure_column(connection, "export_runs", "sync_since", "TEXT")
        _ensure_column(connection, "export_runs", "force", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "export_runs", "exact_issue_keys_json", "TEXT")
        _ensure_column(
            connection,
            "confluence_export_runs",
            "partial_failure",
            "INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(connection, "confluence_export_runs", "failure_message", "TEXT")
        _ensure_column(connection, "confluence_export_runs", "sync_since", "TEXT")
        _ensure_column(
            connection,
            "confluence_export_runs",
            "force",
            "INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(connection, "confluence_export_runs", "exact_page_ids_json", "TEXT")
        _ensure_column(
            connection,
            "confluence_export_runs",
            "compatibility_version",
            _CONFLUENCE_COMPATIBILITY_COLUMN,
        )
        _ensure_column(connection, "confluence_pages", "space_id", "TEXT")
        _ensure_column(connection, "confluence_pages", "space_key", "TEXT")
        _ensure_column(connection, "confluence_pages", "title", "TEXT")
        _ensure_column(connection, "confluence_pages", "status", "TEXT")
        _ensure_column(connection, "confluence_pages", "parent_id", "TEXT")
        _ensure_column(connection, "confluence_pages", "updated_at", "TEXT")
        _ensure_column(connection, "confluence_pages", "version", "INTEGER")
        _ensure_column(connection, "confluence_pages", "content_hash", "TEXT")
        _ensure_column(connection, "confluence_pages", "raw_json_hash", "TEXT")
        _ensure_column(connection, "confluence_pages", "markdown_hash", "TEXT")
        _ensure_column(connection, "confluence_pages", "last_seen_at", "TEXT")
        _ensure_column(connection, "confluence_pages", "last_exported_at", "TEXT")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_export_runs_representative
            ON export_runs (command, scope_type, scope_value, succeeded, partial_failure)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_confluence_export_runs_scope
            ON confluence_export_runs (
                command,
                scope_type,
                scope_value,
                compatibility_version,
                succeeded,
                partial_failure
            )
            """
        )
        connection.execute(_SCHEMA_VERSION_STATEMENTS[SCHEMA_VERSION])


def upsert_issue_state(db_path: Path, issue: IssueState) -> None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO issues (
                issue_key,
                issue_id,
                updated_at,
                stable_content_hash,
                raw_json_hash,
                markdown_hash,
                last_seen_at,
                last_exported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(issue_key) DO UPDATE SET
                issue_id = excluded.issue_id,
                updated_at = excluded.updated_at,
                stable_content_hash = excluded.stable_content_hash,
                raw_json_hash = excluded.raw_json_hash,
                markdown_hash = excluded.markdown_hash,
                last_seen_at = excluded.last_seen_at,
                last_exported_at = excluded.last_exported_at
            """,
            (
                issue.issue_key,
                issue.issue_id,
                issue.updated_at,
                issue.stable_content_hash,
                issue.raw_json_hash,
                issue.markdown_hash,
                issue.last_seen_at,
                issue.last_exported_at,
            ),
        )


def upsert_confluence_page_state(db_path: Path, page: ConfluencePageState) -> None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO confluence_pages (
                page_id,
                space_id,
                space_key,
                title,
                status,
                parent_id,
                updated_at,
                version,
                content_hash,
                raw_json_hash,
                markdown_hash,
                last_seen_at,
                last_exported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                space_id = excluded.space_id,
                space_key = excluded.space_key,
                title = excluded.title,
                status = excluded.status,
                parent_id = excluded.parent_id,
                updated_at = excluded.updated_at,
                version = excluded.version,
                content_hash = excluded.content_hash,
                raw_json_hash = excluded.raw_json_hash,
                markdown_hash = excluded.markdown_hash,
                last_seen_at = excluded.last_seen_at,
                last_exported_at = excluded.last_exported_at
            """,
            (
                page.page_id,
                page.space_id,
                page.space_key,
                page.title,
                page.status,
                page.parent_id,
                page.updated_at,
                page.version,
                page.content_hash,
                page.raw_json_hash,
                page.markdown_hash,
                page.last_seen_at,
                page.last_exported_at,
            ),
        )


def clear_issue_export_artifacts(db_path: Path, issue_key: str) -> None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE issues
            SET
                stable_content_hash = NULL,
                raw_json_hash = NULL,
                markdown_hash = NULL,
                last_exported_at = NULL
            WHERE issue_key = ?
            """,
            (issue_key,),
        )


def clear_confluence_page_export_artifacts(db_path: Path, page_id: str) -> None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE confluence_pages
            SET
                content_hash = NULL,
                raw_json_hash = NULL,
                markdown_hash = NULL,
                last_exported_at = NULL
            WHERE page_id = ?
            """,
            (page_id,),
        )


def start_export_run(
    db_path: Path,
    *,
    command: str,
    scope_type: str | None = None,
    scope_value: str | None = None,
    started_at: str | None = None,
    sync_since: str | None = None,
    force: bool = False,
    exact_issue_keys: tuple[str, ...] = (),
) -> int:
    initialize_state(db_path)
    started = started_at or now_iso()
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO export_runs (
                command,
                scope_type,
                scope_value,
                started_at,
                sync_since,
                force,
                exact_issue_keys_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command,
                scope_type,
                scope_value,
                started,
                sync_since,
                int(force),
                _json_list(exact_issue_keys) if exact_issue_keys else None,
            ),
        )
        run_id = cursor.lastrowid
    if run_id is None:
        raise RuntimeError("SQLite did not return an export run id.")
    return run_id


def start_confluence_export_run(
    db_path: Path,
    *,
    command: str,
    scope_type: str | None = None,
    scope_value: str | None = None,
    started_at: str | None = None,
    sync_since: str | None = None,
    force: bool = False,
    exact_page_ids: tuple[str, ...] = (),
    compatibility_version: str = CONFLUENCE_STATE_COMPATIBILITY_VERSION,
) -> int:
    initialize_state(db_path)
    started = started_at or now_iso()
    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO confluence_export_runs (
                command,
                scope_type,
                scope_value,
                started_at,
                sync_since,
                force,
                exact_page_ids_json,
                compatibility_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command,
                scope_type,
                scope_value,
                started,
                sync_since,
                int(force),
                _json_list(exact_page_ids) if exact_page_ids else None,
                compatibility_version,
            ),
        )
        run_id = cursor.lastrowid
    if run_id is None:
        raise RuntimeError("SQLite did not return a Confluence export run id.")
    return run_id


def finish_export_run(
    db_path: Path,
    run_id: int,
    *,
    succeeded: bool,
    finished_at: str | None = None,
    representative_issue_keys: tuple[str, ...] | None = None,
    partial_failure: bool = False,
    failure_message: str | None = None,
) -> None:
    initialize_state(db_path)
    final_success = succeeded and not partial_failure
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE export_runs
            SET
                finished_at = ?,
                succeeded = ?,
                partial_failure = ?,
                failure_message = ?,
                representative_issue_keys_json = ?
            WHERE id = ?
            """,
            (
                finished_at or now_iso(),
                int(final_success),
                int(partial_failure),
                failure_message,
                _json_list(representative_issue_keys)
                if final_success and representative_issue_keys is not None
                else None,
                run_id,
            ),
        )


def finish_confluence_export_run(
    db_path: Path,
    run_id: int,
    *,
    succeeded: bool,
    finished_at: str | None = None,
    representative_page_ids: tuple[str, ...] | None = None,
    partial_failure: bool = False,
    failure_message: str | None = None,
) -> None:
    initialize_state(db_path)
    final_success = succeeded and not partial_failure
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE confluence_export_runs
            SET
                finished_at = ?,
                succeeded = ?,
                partial_failure = ?,
                failure_message = ?,
                representative_page_ids_json = ?
            WHERE id = ?
            """,
            (
                finished_at or now_iso(),
                int(final_success),
                int(partial_failure),
                failure_message,
                _json_list(representative_page_ids)
                if final_success and representative_page_ids is not None
                else None,
                run_id,
            ),
        )


def last_successful_representative_run(
    db_path: Path,
    *,
    scope_type: str,
    scope_value: str,
) -> ExportRun | None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM export_runs
            WHERE command = 'pull'
                AND scope_type = ?
                AND scope_value = ?
                AND succeeded = 1
                AND partial_failure = 0
                AND finished_at IS NOT NULL
                AND representative_issue_keys_json IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (scope_type, scope_value),
        ).fetchone()
    if row is None:
        return None
    return _run_from_row(row)


def last_successful_confluence_representative_run(
    db_path: Path,
    *,
    scope_type: str,
    scope_value: str,
    compatibility_version: str = CONFLUENCE_STATE_COMPATIBILITY_VERSION,
) -> ConfluenceExportRun | None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM confluence_export_runs
            WHERE command = 'pull'
                AND scope_type = ?
                AND scope_value = ?
                AND compatibility_version = ?
                AND succeeded = 1
                AND partial_failure = 0
                AND finished_at IS NOT NULL
                AND representative_page_ids_json IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (scope_type, scope_value, compatibility_version),
        ).fetchone()
    if row is None:
        return None
    return _confluence_run_from_row(row)


def last_successful_scope_run(
    db_path: Path,
    *,
    command: str,
    scope_type: str,
    scope_value: str,
) -> ExportRun | None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM export_runs
            WHERE command = ?
                AND scope_type = ?
                AND scope_value = ?
                AND succeeded = 1
                AND partial_failure = 0
                AND finished_at IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (command, scope_type, scope_value),
        ).fetchone()
    if row is None:
        return None
    return _run_from_row(row)


def last_successful_confluence_scope_run(
    db_path: Path,
    *,
    command: str,
    scope_type: str,
    scope_value: str,
    compatibility_version: str = CONFLUENCE_STATE_COMPATIBILITY_VERSION,
) -> ConfluenceExportRun | None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM confluence_export_runs
            WHERE command = ?
                AND scope_type = ?
                AND scope_value = ?
                AND compatibility_version = ?
                AND succeeded = 1
                AND partial_failure = 0
                AND finished_at IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (command, scope_type, scope_value, compatibility_version),
        ).fetchone()
    if row is None:
        return None
    return _confluence_run_from_row(row)


def latest_successful_representative_run(db_path: Path) -> ExportRun | None:
    initialize_state(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM export_runs
            WHERE command = 'pull'
                AND scope_type IN ('project', 'jql')
                AND succeeded = 1
                AND partial_failure = 0
                AND finished_at IS NOT NULL
                AND representative_issue_keys_json IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return _run_from_row(row)


def latest_successful_confluence_representative_run(
    db_path: Path,
    *,
    compatibility_version: str = CONFLUENCE_STATE_COMPATIBILITY_VERSION,
) -> ConfluenceExportRun | None:
    initialize_state(db_path)
    scope_types = tuple(sorted(CONFLUENCE_REPRESENTATIVE_SCOPE_TYPES))
    params = (*scope_types, compatibility_version)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM confluence_export_runs
            WHERE command = 'pull'
                AND scope_type IN (?, ?, ?)
                AND compatibility_version = ?
                AND succeeded = 1
                AND partial_failure = 0
                AND finished_at IS NOT NULL
                AND representative_page_ids_json IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    if row is None:
        return None
    return _confluence_run_from_row(row)


def decide_incremental_sync(
    db_path: Path,
    *,
    command: str,
    scope_type: str,
    scope_value: str,
    since: str | None = None,
    force: bool = False,
    exact_issue_keys: tuple[str, ...] = (),
    overlap_minutes: int = 10,
) -> SyncDecision:
    representative = _is_representative_scope(command, scope_type)
    if exact_issue_keys or scope_type == "issue":
        return SyncDecision(
            full_refresh=True,
            since=None,
            force=force,
            representative=False,
            exact_issue_keys=exact_issue_keys,
            reason="exact_issue",
        )

    if force:
        return SyncDecision(
            full_refresh=True,
            since=None,
            force=True,
            representative=representative,
            exact_issue_keys=(),
            reason="force",
        )

    if since is not None:
        return SyncDecision(
            full_refresh=False,
            since=since,
            force=False,
            representative=representative,
            exact_issue_keys=(),
            reason="explicit_since",
        )

    prior = last_successful_scope_run(
        db_path,
        command=command,
        scope_type=scope_type,
        scope_value=scope_value,
    )
    if prior is None or prior.finished_at is None:
        return SyncDecision(
            full_refresh=True,
            since=None,
            force=False,
            representative=representative,
            exact_issue_keys=(),
            reason="no_previous_success",
        )

    overlapped_since = _format_iso(
        _parse_iso(prior.finished_at) - timedelta(minutes=overlap_minutes)
    )
    return SyncDecision(
        full_refresh=False,
        since=overlapped_since,
        force=False,
        representative=representative,
        exact_issue_keys=(),
        reason="previous_success_with_overlap",
    )


def decide_confluence_incremental_sync(
    db_path: Path,
    *,
    command: str,
    scope_type: str,
    scope_value: str,
    since: str | None = None,
    force: bool = False,
    exact_page_ids: tuple[str, ...] = (),
    overlap_minutes: int = 10,
    compatibility_version: str = CONFLUENCE_STATE_COMPATIBILITY_VERSION,
) -> ConfluenceSyncDecision:
    representative = _is_confluence_representative_scope(command, scope_type)
    if exact_page_ids or scope_type == "page":
        return ConfluenceSyncDecision(
            full_refresh=True,
            since=None,
            force=force,
            representative=False,
            exact_page_ids=exact_page_ids,
            reason="exact_page",
        )

    if force:
        return ConfluenceSyncDecision(
            full_refresh=True,
            since=None,
            force=True,
            representative=representative,
            exact_page_ids=(),
            reason="force",
        )

    if command == "pull" and scope_type == "ancestor":
        return ConfluenceSyncDecision(
            full_refresh=True,
            since=None,
            force=False,
            representative=representative,
            exact_page_ids=(),
            reason="ancestor_full_scope",
        )

    if since is not None:
        return ConfluenceSyncDecision(
            full_refresh=False,
            since=since,
            force=False,
            representative=representative,
            exact_page_ids=(),
            reason="explicit_since",
        )

    prior = last_successful_confluence_scope_run(
        db_path,
        command=command,
        scope_type=scope_type,
        scope_value=scope_value,
        compatibility_version=compatibility_version,
    )
    if prior is None or prior.finished_at is None:
        return ConfluenceSyncDecision(
            full_refresh=True,
            since=None,
            force=False,
            representative=representative,
            exact_page_ids=(),
            reason="no_previous_success",
        )

    overlapped_since = _format_iso(
        _parse_iso(prior.finished_at) - timedelta(minutes=overlap_minutes)
    )
    return ConfluenceSyncDecision(
        full_refresh=False,
        since=overlapped_since,
        force=False,
        representative=representative,
        exact_page_ids=(),
        reason="previous_success_with_overlap",
    )


def confluence_representative_page_ids(
    decision: ConfluenceSyncDecision,
    fetched_page_ids: tuple[str, ...],
) -> tuple[str, ...] | None:
    if not decision.representative:
        return None
    if decision.full_refresh:
        return fetched_page_ids
    return None


def stable_json_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM pragma_table_info(?)",
            (table_name,),
        ).fetchall()
    }
    if column_name not in columns:
        statement = _COLUMN_MIGRATION_STATEMENTS[(table_name, column_name, definition)]
        connection.execute(statement)


def _run_from_row(row: sqlite3.Row) -> ExportRun:
    return ExportRun(
        id=int(row["id"]),
        command=str(row["command"]),
        scope_type=_optional_str(row["scope_type"]),
        scope_value=_optional_str(row["scope_value"]),
        started_at=_optional_str(row["started_at"]),
        finished_at=_optional_str(row["finished_at"]),
        succeeded=bool(row["succeeded"]),
        partial_failure=bool(row["partial_failure"]),
        representative_issue_keys=_tuple_from_json(row["representative_issue_keys_json"]),
        sync_since=_optional_str(row["sync_since"]),
        force=bool(row["force"]),
        exact_issue_keys=_tuple_from_json(row["exact_issue_keys_json"]),
    )


def _confluence_run_from_row(row: sqlite3.Row) -> ConfluenceExportRun:
    return ConfluenceExportRun(
        id=int(row["id"]),
        command=str(row["command"]),
        scope_type=_optional_str(row["scope_type"]),
        scope_value=_optional_str(row["scope_value"]),
        started_at=_optional_str(row["started_at"]),
        finished_at=_optional_str(row["finished_at"]),
        succeeded=bool(row["succeeded"]),
        partial_failure=bool(row["partial_failure"]),
        representative_page_ids=_tuple_from_json(row["representative_page_ids_json"]),
        sync_since=_optional_str(row["sync_since"]),
        force=bool(row["force"]),
        exact_page_ids=_tuple_from_json(row["exact_page_ids_json"]),
        compatibility_version=str(row["compatibility_version"]),
    )


def _is_representative_scope(command: str, scope_type: str) -> bool:
    return command == "pull" and scope_type in REPRESENTATIVE_SCOPE_TYPES


def _is_confluence_representative_scope(command: str, scope_type: str) -> bool:
    return command == "pull" and scope_type in CONFLUENCE_REPRESENTATIVE_SCOPE_TYPES


def _json_list(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _tuple_from_json(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        return ()
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        return ()
    return tuple(item for item in parsed if isinstance(item, str))


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _parse_iso(value: str) -> datetime:
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()
