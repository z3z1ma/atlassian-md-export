from __future__ import annotations

import sqlite3
from pathlib import Path

from atlassian_md_export.confluence.client import confluence_updated_since_cql
from atlassian_md_export.state import ConfluencePageState
from atlassian_md_export.state import IssueState
from atlassian_md_export.state import confluence_representative_page_ids
from atlassian_md_export.state import decide_confluence_incremental_sync
from atlassian_md_export.state import decide_incremental_sync
from atlassian_md_export.state import finish_confluence_export_run
from atlassian_md_export.state import finish_export_run
from atlassian_md_export.state import initialize_state
from atlassian_md_export.state import last_successful_confluence_representative_run
from atlassian_md_export.state import last_successful_confluence_scope_run
from atlassian_md_export.state import last_successful_representative_run
from atlassian_md_export.state import last_successful_scope_run
from atlassian_md_export.state import start_confluence_export_run
from atlassian_md_export.state import stable_json_hash
from atlassian_md_export.state import start_export_run
from atlassian_md_export.state import upsert_confluence_page_state
from atlassian_md_export.state import upsert_issue_state


def test_issue_state_tracks_required_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    raw_hash = stable_json_hash({"key": "ABC-1", "fields": {"updated": "2026-07-01"}})

    upsert_issue_state(
        db_path,
        IssueState(
            issue_key="ABC-1",
            issue_id="10001",
            updated_at="2026-07-01T12:00:00+00:00",
            stable_content_hash="stable",
            raw_json_hash=raw_hash,
            markdown_hash="markdown",
            last_seen_at="2026-07-01T12:01:00+00:00",
            last_exported_at="2026-07-01T12:02:00+00:00",
        ),
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM issues WHERE issue_key = 'ABC-1'").fetchone()

    assert row["issue_id"] == "10001"
    assert row["updated_at"] == "2026-07-01T12:00:00+00:00"
    assert row["stable_content_hash"] == "stable"
    assert row["raw_json_hash"] == raw_hash
    assert row["markdown_hash"] == "markdown"
    assert row["last_seen_at"] == "2026-07-01T12:01:00+00:00"
    assert row["last_exported_at"] == "2026-07-01T12:02:00+00:00"


def test_incremental_decision_uses_successful_representative_run_overlap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.sqlite"
    run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_export_run(
        db_path,
        run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:00+00:00",
        representative_issue_keys=("ABC-1",),
    )

    decision = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )

    assert decision.full_refresh is False
    assert decision.since == "2026-07-01T12:20:00+00:00"
    assert decision.reason == "previous_success_with_overlap"
    assert decision.representative is True


def test_since_force_and_exact_issue_decisions(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    initialize_state(db_path)

    explicit_since = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        since="2026-07-01T00:00:00+00:00",
    )
    forced = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        force=True,
    )
    exact = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="issue",
        scope_value="ABC-1",
        exact_issue_keys=("ABC-1",),
    )

    assert explicit_since.since == "2026-07-01T00:00:00+00:00"
    assert explicit_since.full_refresh is False
    assert forced.full_refresh is True
    assert forced.reason == "force"
    assert exact.full_refresh is True
    assert exact.since is None
    assert exact.representative is False
    assert exact.reason == "exact_issue"


def test_partial_failure_does_not_advance_representative_run(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_export_run(
        db_path,
        run_id,
        succeeded=True,
        partial_failure=True,
        failure_message="ABC-2 failed",
        finished_at="2026-07-01T12:30:00+00:00",
        representative_issue_keys=("ABC-1",),
    )

    assert last_successful_representative_run(
        db_path,
        scope_type="project",
        scope_value="ABC",
    ) is None

    decision = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )
    assert decision.full_refresh is True
    assert decision.reason == "no_previous_success"


def test_incremental_success_advances_sync_without_becoming_cleanup_authority(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.sqlite"
    full_run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_export_run(
        db_path,
        full_run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:00+00:00",
        representative_issue_keys=("ABC-1", "ABC-2"),
    )
    incremental_run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T13:00:00+00:00",
    )
    finish_export_run(
        db_path,
        incremental_run_id,
        succeeded=True,
        finished_at="2026-07-01T13:30:00+00:00",
    )

    decision = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )
    representative = last_successful_representative_run(
        db_path,
        scope_type="project",
        scope_value="ABC",
    )
    latest_scope = last_successful_scope_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )

    assert decision.since == "2026-07-01T13:20:00+00:00"
    assert representative is not None
    assert representative.id == full_run_id
    assert representative.representative_issue_keys == ("ABC-1", "ABC-2")
    assert latest_scope is not None
    assert latest_scope.id == incremental_run_id


def test_failed_scope_run_does_not_advance_incremental_cursor(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    successful_run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_export_run(
        db_path,
        successful_run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:00+00:00",
        representative_issue_keys=("ABC-1",),
    )
    failed_run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T13:00:00+00:00",
    )
    finish_export_run(
        db_path,
        failed_run_id,
        succeeded=False,
        partial_failure=True,
        failure_message="malformed search payload",
        finished_at="2026-07-01T13:30:00+00:00",
    )

    decision = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )

    assert decision.full_refresh is False
    assert decision.since == "2026-07-01T12:20:00+00:00"


def test_incremental_cursor_uses_same_command_and_scope(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    abc_run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_export_run(
        db_path,
        abc_run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:00+00:00",
        representative_issue_keys=("ABC-1",),
    )
    other_scope_run_id = start_export_run(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="DEF",
        started_at="2026-07-01T13:00:00+00:00",
    )
    finish_export_run(
        db_path,
        other_scope_run_id,
        succeeded=True,
        finished_at="2026-07-01T13:30:00+00:00",
        representative_issue_keys=("DEF-1",),
    )
    other_command_run_id = start_export_run(
        db_path,
        command="issue",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T14:00:00+00:00",
    )
    finish_export_run(
        db_path,
        other_command_run_id,
        succeeded=True,
        finished_at="2026-07-01T14:30:00+00:00",
    )

    decision = decide_incremental_sync(
        db_path,
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )

    assert decision.since == "2026-07-01T12:20:00+00:00"


def test_confluence_page_state_tracks_required_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    raw_hash = stable_json_hash({"id": "123", "title": "Roadmap"})

    upsert_confluence_page_state(
        db_path,
        ConfluencePageState(
            page_id="123",
            space_id="space-1",
            space_key="DOC",
            title="Roadmap",
            status="current",
            parent_id="100",
            updated_at="2026-07-01T12:00:00+00:00",
            version=7,
            content_hash="content",
            raw_json_hash=raw_hash,
            markdown_hash="markdown",
            last_seen_at="2026-07-01T12:01:00+00:00",
            last_exported_at="2026-07-01T12:02:00+00:00",
        ),
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM confluence_pages WHERE page_id = '123'"
        ).fetchone()

    assert row["space_id"] == "space-1"
    assert row["space_key"] == "DOC"
    assert row["title"] == "Roadmap"
    assert row["status"] == "current"
    assert row["parent_id"] == "100"
    assert row["updated_at"] == "2026-07-01T12:00:00+00:00"
    assert row["version"] == 7
    assert row["content_hash"] == "content"
    assert row["raw_json_hash"] == raw_hash
    assert row["markdown_hash"] == "markdown"
    assert row["last_seen_at"] == "2026-07-01T12:01:00+00:00"
    assert row["last_exported_at"] == "2026-07-01T12:02:00+00:00"


def test_initialize_state_repairs_early_confluence_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE confluence_export_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                scope_type TEXT,
                scope_value TEXT,
                started_at TEXT,
                finished_at TEXT,
                succeeded INTEGER NOT NULL DEFAULT 0,
                representative_page_ids_json TEXT
            );
            CREATE TABLE confluence_pages (
                page_id TEXT PRIMARY KEY
            );
            """
        )

    initialize_state(db_path)
    upsert_confluence_page_state(
        db_path,
        ConfluencePageState(
            page_id="123",
            space_id="space-1",
            space_key="DOC",
            title="Page",
            content_hash="content",
            raw_json_hash="raw",
            markdown_hash="markdown",
        ),
    )
    run_id = start_confluence_export_run(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
        exact_page_ids=("123",),
    )
    finish_confluence_export_run(
        db_path,
        run_id,
        succeeded=True,
        representative_page_ids=("123",),
    )

    with sqlite3.connect(db_path) as connection:
        page_row = connection.execute(
            "SELECT space_key, content_hash FROM confluence_pages WHERE page_id = '123'"
        ).fetchone()
        run_row = connection.execute(
            """
            SELECT partial_failure, exact_page_ids_json, compatibility_version
            FROM confluence_export_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    assert page_row == ("DOC", "content")
    assert run_row == (0, '["123"]', "confluence-v1")


def test_confluence_incremental_decision_uses_successful_compatible_run_overlap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.sqlite"
    incompatible_run_id = start_confluence_export_run(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
        started_at="2026-07-01T13:00:00+00:00",
        compatibility_version="future-version",
    )
    finish_confluence_export_run(
        db_path,
        incompatible_run_id,
        succeeded=True,
        finished_at="2026-07-01T13:30:00+00:00",
        representative_page_ids=("999",),
    )
    run_id = start_confluence_export_run(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_confluence_export_run(
        db_path,
        run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:00+00:00",
        representative_page_ids=("123",),
    )

    decision = decide_confluence_incremental_sync(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
    )

    assert decision.full_refresh is False
    assert decision.since == "2026-07-01T12:20:00+00:00"
    assert decision.reason == "previous_success_with_overlap"
    assert decision.representative is True


def test_confluence_since_force_exact_and_representative_cleanup_semantics(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.sqlite"
    initialize_state(db_path)

    explicit_since = decide_confluence_incremental_sync(
        db_path,
        command="pull",
        scope_type="cql",
        scope_value='space = "DOC"',
        since="2026-07-01T00:00:00+00:00",
    )
    forced = decide_confluence_incremental_sync(
        db_path,
        command="pull",
        scope_type="ancestor",
        scope_value="123",
        force=True,
    )
    default_ancestor = decide_confluence_incremental_sync(
        db_path,
        command="pull",
        scope_type="ancestor",
        scope_value="123",
    )
    exact = decide_confluence_incremental_sync(
        db_path,
        command="pull",
        scope_type="page",
        scope_value="123",
        exact_page_ids=("123",),
    )

    assert explicit_since.since == "2026-07-01T00:00:00+00:00"
    assert explicit_since.full_refresh is False
    assert confluence_representative_page_ids(explicit_since, ("123",)) is None
    assert forced.full_refresh is True
    assert forced.reason == "force"
    assert confluence_representative_page_ids(forced, ("123", "456")) == ("123", "456")
    assert default_ancestor.full_refresh is True
    assert default_ancestor.since is None
    assert default_ancestor.reason == "ancestor_full_scope"
    assert confluence_representative_page_ids(default_ancestor, ("123", "456")) == (
        "123",
        "456",
    )
    assert exact.full_refresh is True
    assert exact.since is None
    assert exact.representative is False
    assert exact.reason == "exact_page"


def test_confluence_partial_failure_does_not_advance_cursor_or_cleanup_authority(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.sqlite"
    successful_run_id = start_confluence_export_run(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_confluence_export_run(
        db_path,
        successful_run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:00+00:00",
        representative_page_ids=("123",),
    )
    failed_run_id = start_confluence_export_run(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
        started_at="2026-07-01T13:00:00+00:00",
    )
    finish_confluence_export_run(
        db_path,
        failed_run_id,
        succeeded=False,
        partial_failure=True,
        failure_message="malformed page payload",
        finished_at="2026-07-01T13:30:00+00:00",
        representative_page_ids=("999",),
    )

    decision = decide_confluence_incremental_sync(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
    )
    representative = last_successful_confluence_representative_run(
        db_path,
        scope_type="space",
        scope_value="DOC",
    )
    latest_scope = last_successful_confluence_scope_run(
        db_path,
        command="pull",
        scope_type="space",
        scope_value="DOC",
    )

    assert decision.since == "2026-07-01T12:20:00+00:00"
    assert representative is not None
    assert representative.id == successful_run_id
    assert representative.representative_page_ids == ("123",)
    assert latest_scope is not None
    assert latest_scope.id == successful_run_id


def test_confluence_cql_date_literal_formats_iso_without_seconds_or_timezone() -> None:
    cql = confluence_updated_since_cql(
        'space = "DOC" ORDER BY lastmodified DESC',
        "2026-07-01T12:20:59.999999+00:00",
    )

    assert cql == (
        '(space = "DOC") AND lastmodified >= "2026-07-01 12:20" '
        "ORDER BY lastmodified DESC"
    )
    assert "T12:20:59" not in cql
    assert "+00:00" not in cql
