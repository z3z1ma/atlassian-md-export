from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

import atlassian_md_export.operations as operations
from atlassian_md_export.attachments import attachment_path
from atlassian_md_export.attachments import sanitize_attachment_filename
from atlassian_md_export.client import AtlassianClientError
from atlassian_md_export.client import AtlassianHttpClient
from atlassian_md_export.client import JiraCredentials
from atlassian_md_export.client import RetryConfig
from atlassian_md_export.config import ExportConfig
from atlassian_md_export.config import MarkdownConfig
from atlassian_md_export.indexes import generate_indexes
from atlassian_md_export.jira.client import JiraClient
from atlassian_md_export.operations import AttachmentOptions
from atlassian_md_export.operations import ExportCommandError
from atlassian_md_export.operations import clean_export
from atlassian_md_export.operations import run_comments
from atlassian_md_export.operations import run_pull
from atlassian_md_export.operations import verify_export
from atlassian_md_export.state import decide_incremental_sync
from atlassian_md_export.state import IssueState
from atlassian_md_export.state import finish_export_run
from atlassian_md_export.state import latest_successful_representative_run
from atlassian_md_export.state import start_export_run
from atlassian_md_export.state import upsert_issue_state
from atlassian_md_export.writer import initialize_output
from atlassian_md_export.writer import normalize_jira_issue
from atlassian_md_export.writer import write_issue_files

SITE = "https://example.atlassian.net"


def test_attachment_filename_safety_blocks_path_tricks(tmp_path: Path) -> None:
    assert sanitize_attachment_filename("../.env") == "env"
    assert sanitize_attachment_filename(".hidden") == "hidden"
    assert sanitize_attachment_filename("CON") == "_CON"
    assert sanitize_attachment_filename("\x00\t") == "attachment"

    long_name = f"{'a' * 240}.log"
    first = sanitize_attachment_filename(long_name)
    second = sanitize_attachment_filename(long_name)

    assert first == second
    assert len(first) <= 180

    path = attachment_path(tmp_path, "ABC-1", "../id", "../../.secret")
    assert path.parent == tmp_path / "attachments" / "ABC-1"
    assert "/" not in path.name
    assert "\\" not in path.name
    assert not path.name.startswith(".")


def test_pull_downloads_eligible_attachments_and_verify_checks_local_refs(
    tmp_path: Path,
) -> None:
    raw_issue = _raw_issue(
        "ABC-1",
        attachments=[
            _attachment("att-1", "debug.log", "text/plain", 4),
            _attachment("att-2", "screenshot.png", "image/png", 4),
        ],
    )
    external_attachment_url = "https://github.com/user-attachments/files/1/report.xlsx"
    comment = _comment("1", "first ")
    comment["body"]["content"][0]["content"].append(
        {
            "type": "text",
            "text": "external evidence",
            "marks": [{"type": "link", "attrs": {"href": external_attachment_url}}],
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/search/jql":
            return httpx.Response(200, json={"issues": [raw_issue], "isLast": True})
        if request.url.path == "/rest/api/3/issue/ABC-1/comment":
            return httpx.Response(200, json=_comments_response([comment]))
        if request.url.path == "/secure/attachment/att-1/debug.log":
            return httpx.Response(200, content=b"log!")
        raise AssertionError(f"unexpected request: {request.url}")

    summary = run_pull(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        project="ABC",
        attachment_options=AttachmentOptions(
            download=True,
            max_mb=1,
            include_patterns=("*.log",),
        ),
    )

    downloaded = _assert_pull_download_outputs(
        tmp_path,
        issue_keys=summary.issue_keys,
        external_attachment_url=external_attachment_url,
    )
    _assert_missing_download_fails_verification(tmp_path, downloaded)


def test_pull_renders_configured_custom_fields_from_public_config_shape(
    tmp_path: Path,
) -> None:
    raw_issue = _raw_issue("ABC-1")
    seen_fields: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/search/jql":
            seen_fields.append(request.url.params["fields"])
            return httpx.Response(200, json={"issues": [raw_issue], "isLast": True})
        if request.url.path == "/rest/api/3/issue/ABC-1/comment":
            return httpx.Response(200, json=_comments_response([]))
        raise AssertionError(f"unexpected request: {request.url}")

    run_pull(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=ExportConfig(
            custom_fields={"story_points": "customfield_10016"},
            markdown=MarkdownConfig(stable_exported_at=True),
        ),
        project="ABC",
    )

    markdown = (tmp_path / "issues" / "ABC-1.md").read_text(encoding="utf-8")
    assert seen_fields
    assert "summary" in seen_fields[0].split(",")
    assert "description" in seen_fields[0].split(",")
    assert "customfield_10016" in seen_fields[0].split(",")
    assert "- Story Points: 5" in markdown
    assert "- Story Points (`customfield_10016`): 5" in markdown


def test_pull_malformed_search_payload_fails_run_and_preserves_cursor(
    tmp_path: Path,
) -> None:
    _seed_successful_project_pull(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/myself":
            return httpx.Response(200, json={"timeZone": "UTC"})
        if request.url.path == "/rest/api/3/search/jql":
            return httpx.Response(200, json={"isLast": True})
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(AtlassianClientError, match="issues list"):
        run_pull(
            tmp_path,
            client=_client(handler),
            site_url=SITE,
            config=_config(),
            project="ABC",
        )

    _assert_latest_run_failed(tmp_path, "issues list")
    decision = decide_incremental_sync(
        tmp_path / "state.sqlite",
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )
    assert decision.since == "2026-07-01T12:20:00+00:00"


def test_pull_malformed_comments_payload_fails_run_and_preserves_cursor(
    tmp_path: Path,
) -> None:
    _seed_successful_project_pull(tmp_path)
    raw_issue = _raw_issue("ABC-1")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/myself":
            return httpx.Response(200, json={"timeZone": "UTC"})
        if request.url.path == "/rest/api/3/search/jql":
            return httpx.Response(200, json={"issues": [raw_issue], "isLast": True})
        if request.url.path == "/rest/api/3/issue/ABC-1/comment":
            return httpx.Response(200, json={"startAt": 0, "maxResults": 100, "total": 0})
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(AtlassianClientError, match="comments list"):
        run_pull(
            tmp_path,
            client=_client(handler),
            site_url=SITE,
            config=_config(),
            project="ABC",
        )

    _assert_latest_run_failed(tmp_path, "comments list")
    decision = decide_incremental_sync(
        tmp_path / "state.sqlite",
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )
    assert decision.since == "2026-07-01T12:20:00+00:00"


def test_attachment_partial_failure_does_not_advance_representative_run(
    tmp_path: Path,
) -> None:
    raw_issue = _raw_issue(
        "ABC-1",
        attachments=[
            _attachment("att-1", "first.log", "text/plain", 4),
            _attachment("att-2", "second.log", "text/plain", 4),
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/search/jql":
            return httpx.Response(200, json={"issues": [raw_issue], "isLast": True})
        if request.url.path == "/rest/api/3/issue/ABC-1/comment":
            return httpx.Response(200, json=_comments_response([]))
        if request.url.path == "/secure/attachment/att-1/first.log":
            return httpx.Response(200, content=b"first")
        if request.url.path == "/secure/attachment/att-2/second.log":
            return httpx.Response(500, json={"errorMessages": ["temporary"]})
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(ExportCommandError):
        run_pull(
            tmp_path,
            client=_client(handler),
            site_url=SITE,
            config=_config(),
            project="ABC",
            attachment_options=AttachmentOptions(download=True),
        )

    assert (tmp_path / "issues" / "ABC-1.md").is_file()
    assert (tmp_path / "attachments" / "ABC-1" / "att-1-first.log").read_bytes() == b"first"
    assert latest_successful_representative_run(tmp_path / "state.sqlite") is None
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["last_successful_representative_run"] is None


def test_pull_blocks_external_attachment_content_url_without_request(tmp_path: Path) -> None:
    external_url = "https://files.example.test/secure/attachment/att-1/debug.log"
    attachment = _attachment("att-1", "debug.log", "text/plain", 4)
    attachment["content"] = external_url
    raw_issue = _raw_issue("ABC-1", attachments=[attachment])
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path == "/rest/api/3/search/jql":
            return httpx.Response(200, json={"issues": [raw_issue], "isLast": True})
        if request.url.path == "/rest/api/3/issue/ABC-1/comment":
            return httpx.Response(200, json=_comments_response([]))
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(ExportCommandError) as error:
        run_pull(
            tmp_path,
            client=_client(handler),
            site_url=SITE,
            config=_config(),
            project="ABC",
            attachment_options=AttachmentOptions(download=True),
        )

    assert external_url not in requested_urls
    assert (
        "https://files.example.test:443 does not match Jira site https://example.atlassian.net:443"
    ) in str(error.value)
    assert not (tmp_path / "attachments" / "ABC-1" / "att-1-debug.log").exists()

    payload = json.loads((tmp_path / "issues" / "_raw" / "ABC-1.json").read_text(encoding="utf-8"))
    metadata_by_id = {item["id"]: item for item in payload["attachment_metadata"]}
    assert metadata_by_id["att-1"]["local_path"] is None

    with sqlite3.connect(tmp_path / "state.sqlite") as connection:
        row = connection.execute(
            "SELECT partial_failure, failure_message FROM export_runs"
        ).fetchone()
    assert row[0] == 1
    assert "ABC-1/att-1" in row[1]


def test_pull_blocks_same_host_attachment_content_url_with_wrong_scheme(
    tmp_path: Path,
) -> None:
    attachment = _attachment("att-1", "debug.log", "text/plain", 4)
    attachment["content"] = "http://example.atlassian.net/secure/attachment/att-1/debug.log"
    raw_issue = _raw_issue("ABC-1", attachments=[attachment])
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/rest/api/3/search/jql":
            return httpx.Response(200, json={"issues": [raw_issue], "isLast": True})
        if request.url.path == "/rest/api/3/issue/ABC-1/comment":
            return httpx.Response(200, json=_comments_response([]))
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(ExportCommandError) as error:
        run_pull(
            tmp_path,
            client=_client(handler),
            site_url=SITE,
            config=_config(),
            project="ABC",
            attachment_options=AttachmentOptions(download=True),
        )

    assert requested_paths == ["/rest/api/3/search/jql", "/rest/api/3/issue/ABC-1/comment"]
    assert "http://example.atlassian.net:80 does not match Jira site" in str(error.value)
    assert not (tmp_path / "attachments" / "ABC-1" / "att-1-debug.log").exists()


def test_pull_attributes_write_failure_to_issue_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_issue = _raw_issue("ABC-1")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/search/jql":
            return httpx.Response(200, json={"issues": [raw_issue], "isLast": True})
        if request.url.path == "/rest/api/3/issue/ABC-1/comment":
            return httpx.Response(200, json=_comments_response([]))
        raise AssertionError(f"unexpected request: {request.url}")

    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("cannot write issue")

    monkeypatch.setattr(operations, "write_issue_files", fail_write)

    with pytest.raises(OSError, match="ABC-1: cannot write issue"):
        run_pull(
            tmp_path,
            client=_client(handler),
            site_url=SITE,
            config=_config(),
            project="ABC",
        )

    with sqlite3.connect(tmp_path / "state.sqlite") as connection:
        row = connection.execute(
            "SELECT partial_failure, failure_message FROM export_runs"
        ).fetchone()
    assert row[0] == 1
    assert row[1] == "ABC-1: cannot write issue"


def test_incremental_pull_formats_since_as_jira_date_literal(tmp_path: Path) -> None:
    initialize_output(tmp_path)
    run_id = start_export_run(
        tmp_path / "state.sqlite",
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_export_run(
        tmp_path / "state.sqlite",
        run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:59.999999+00:00",
        representative_issue_keys=("ABC-1",),
    )
    seen_jql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/myself":
            return httpx.Response(200, json={"timeZone": "America/Los_Angeles"})
        if request.url.path == "/rest/api/3/search/jql":
            seen_jql.append(request.url.params["jql"])
            return httpx.Response(200, json={"issues": [], "isLast": True})
        raise AssertionError(f"unexpected request: {request.url}")

    summary = run_pull(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        project="ABC",
    )

    assert summary.issue_keys == ()
    assert seen_jql == [
        '(project = "ABC") AND updated >= "2026-07-01 05:20" ORDER BY updated ASC, key ASC'
    ]


def test_comments_force_refreshes_existing_raw_issue(tmp_path: Path) -> None:
    _write_local_issue(tmp_path, "ABC-1", [_comment("1", "old comment")])

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/issue/ABC-1/comment"
        return httpx.Response(200, json=_comments_response([_comment("2", "new comment")]))

    run_comments(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        keys=("ABC-1",),
        force=True,
    )

    markdown = (tmp_path / "issues" / "ABC-1.md").read_text(encoding="utf-8")
    assert "new comment" in markdown
    assert "old comment" not in markdown


def test_clean_remove_missing_uses_representative_run_and_preserves_state(
    tmp_path: Path,
) -> None:
    initialize_output(tmp_path)
    _write_local_issue(tmp_path, "ABC-1", [])
    _write_local_issue(tmp_path, "ABC-2", [])
    (tmp_path / "attachments" / "ABC-2").mkdir(parents=True)
    (tmp_path / "attachments" / "ABC-2" / "att-1-debug.log").write_bytes(b"old")
    upsert_issue_state(
        tmp_path / "state.sqlite",
        IssueState(
            issue_key="ABC-2",
            issue_id="10002",
            stable_content_hash="old-content-hash",
            raw_json_hash="old-raw-hash",
            markdown_hash="old-markdown-hash",
        ),
    )
    run_id = start_export_run(
        tmp_path / "state.sqlite",
        command="pull",
        scope_type="project",
        scope_value="ABC",
    )
    finish_export_run(
        tmp_path / "state.sqlite",
        run_id,
        succeeded=True,
        representative_issue_keys=("ABC-1",),
    )

    result = clean_export(tmp_path, remove_missing=True)

    assert result.removed_issue_keys == ("ABC-2",)
    assert not (tmp_path / "issues" / "ABC-2.md").exists()
    assert not (tmp_path / "issues" / "_raw" / "ABC-2.json").exists()
    assert not (tmp_path / "attachments" / "ABC-2").exists()
    with sqlite3.connect(tmp_path / "state.sqlite") as connection:
        row = connection.execute(
            """
            SELECT issue_key, stable_content_hash, raw_json_hash, markdown_hash
            FROM issues
            WHERE issue_key = 'ABC-2'
            """
        ).fetchone()
    assert row == ("ABC-2", None, None, None)
    assert verify_export(tmp_path).ok


def test_verify_compares_state_hashes_against_current_issue_files(tmp_path: Path) -> None:
    initialize_output(tmp_path)
    issue = normalize_jira_issue(_raw_issue("ABC-1"), site_url=SITE)
    write_result = write_issue_files(tmp_path, issue, stable_exported_at=True)
    upsert_issue_state(
        tmp_path / "state.sqlite",
        IssueState(
            issue_key="ABC-1",
            issue_id=issue.id,
            updated_at=issue.updated,
            stable_content_hash=write_result.content_hash,
            raw_json_hash=write_result.raw_json_hash,
            markdown_hash=write_result.markdown_hash,
            last_seen_at="2026-07-01T12:01:00+00:00",
            last_exported_at=write_result.exported_at,
        ),
    )
    generate_indexes(tmp_path)
    operations.update_manifest(tmp_path, site_host="example.atlassian.net")

    assert verify_export(tmp_path).ok

    write_result.markdown_path.write_text(
        write_result.markdown_path.read_text(encoding="utf-8") + "\nlocal edit\n",
        encoding="utf-8",
    )
    failure = verify_export(tmp_path)

    assert not failure.ok
    assert any("State Markdown hash mismatch" in error for error in failure.errors)


def test_verify_reports_state_rows_missing_issue_files(tmp_path: Path) -> None:
    initialize_output(tmp_path)
    issue = normalize_jira_issue(_raw_issue("ABC-1"), site_url=SITE)
    write_result = write_issue_files(tmp_path, issue, stable_exported_at=True)
    upsert_issue_state(
        tmp_path / "state.sqlite",
        IssueState(
            issue_key="ABC-1",
            stable_content_hash=write_result.content_hash,
            raw_json_hash=write_result.raw_json_hash,
            markdown_hash=write_result.markdown_hash,
        ),
    )
    generate_indexes(tmp_path)
    operations.update_manifest(tmp_path, site_host="example.atlassian.net")

    write_result.markdown_path.unlink()
    write_result.json_path.unlink()
    failure = verify_export(tmp_path)

    assert not failure.ok
    assert any("State issue Markdown missing" in error for error in failure.errors)
    assert any("State issue JSON missing" in error for error in failure.errors)


def test_stale_index_uses_issue_data_not_wall_clock(tmp_path: Path) -> None:
    initialize_output(tmp_path)
    old_issue = normalize_jira_issue(
        _raw_issue("ABC-1", updated="2026-01-01T00:00:00.000+0000"),
        site_url=SITE,
    )
    recent_issue = normalize_jira_issue(
        _raw_issue("ABC-2", updated="2026-01-20T00:00:00.000+0000"),
        site_url=SITE,
    )
    write_issue_files(tmp_path, old_issue, stable_exported_at=True)
    write_issue_files(tmp_path, recent_issue, stable_exported_at=True)

    generate_indexes(tmp_path, stale_days=10)

    stale = (tmp_path / "indexes" / "stale.md").read_text(encoding="utf-8")
    assert "[ABC-1]" in stale
    assert "[ABC-2]" not in stale


def _assert_pull_download_outputs(
    tmp_path: Path,
    *,
    issue_keys: tuple[str, ...],
    external_attachment_url: str,
) -> Path:
    assert issue_keys == ("ABC-1",)
    downloaded = tmp_path / "attachments" / "ABC-1" / "att-1-debug.log"
    skipped = tmp_path / "attachments" / "ABC-1" / "att-2-screenshot.png"
    assert (downloaded.read_bytes(), skipped.exists()) == (b"log!", False)

    _assert_pull_download_markdown(tmp_path, external_attachment_url)
    _assert_pull_download_payload(tmp_path)
    _assert_pull_download_manifest(tmp_path)
    assert verify_export(tmp_path).ok
    return downloaded


def _assert_pull_download_markdown(tmp_path: Path, external_attachment_url: str) -> None:
    markdown = (tmp_path / "issues" / "ABC-1.md").read_text(encoding="utf-8")
    assert all(
        fragment in markdown
        for fragment in (
            "[local file](../attachments/ABC-1/att-1-debug.log)",
            f"[external evidence]({external_attachment_url})",
            "screenshot.png",
        )
    )


def _assert_pull_download_payload(tmp_path: Path) -> None:
    payload = json.loads((tmp_path / "issues" / "_raw" / "ABC-1.json").read_text(encoding="utf-8"))
    metadata_by_id = {item["id"]: item for item in payload["attachment_metadata"]}
    assert {
        "legacy_raw_exists": (tmp_path / "issues" / "ABC-1.json").exists(),
        "att-1": metadata_by_id["att-1"]["local_path"],
        "att-2": metadata_by_id["att-2"]["local_path"],
    } == {
        "legacy_raw_exists": False,
        "att-1": "../attachments/ABC-1/att-1-debug.log",
        "att-2": None,
    }


def _assert_pull_download_manifest(tmp_path: Path) -> None:
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert {
        "counts": manifest["counts"],
        "issue_keys": manifest["last_successful_representative_run"]["issue_keys"],
        "has_attachment_hash": "attachments/ABC-1/att-1-debug.log" in manifest["hashes"],
        "has_status_index_link": "[ABC-1](../issues/ABC-1.md)"
        in (tmp_path / "indexes" / "by-status.md").read_text(encoding="utf-8"),
    } == {
        "counts": {"attachments": 2, "comments": 1, "issues": 1},
        "issue_keys": ["ABC-1"],
        "has_attachment_hash": True,
        "has_status_index_link": True,
    }


def _assert_missing_download_fails_verification(tmp_path: Path, downloaded: Path) -> None:
    downloaded.unlink()
    failure = verify_export(tmp_path)
    assert not failure.ok
    assert any("Downloaded attachment missing" in error for error in failure.errors)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> JiraClient:
    transport = httpx.MockTransport(handler)
    credentials = JiraCredentials(email="user@example.com", api_token=SecretStr("token"))
    return JiraClient(
        AtlassianHttpClient(
            SITE,
            credentials,
            retry=RetryConfig(max_attempts=1, base_delay_seconds=0, jitter_seconds=0),
            transport=transport,
            sleep=lambda _delay: None,
        )
    )


def _config() -> ExportConfig:
    return ExportConfig(markdown=MarkdownConfig(stable_exported_at=True))


def _write_local_issue(tmp_path: Path, key: str, comments: list[dict[str, Any]]) -> None:
    initialize_output(tmp_path)
    issue = normalize_jira_issue(_raw_issue(key), comments=comments, site_url=SITE)
    write_issue_files(tmp_path, issue, stable_exported_at=True)


def _seed_successful_project_pull(tmp_path: Path) -> None:
    initialize_output(tmp_path)
    run_id = start_export_run(
        tmp_path / "state.sqlite",
        command="pull",
        scope_type="project",
        scope_value="ABC",
        started_at="2026-07-01T12:00:00+00:00",
    )
    finish_export_run(
        tmp_path / "state.sqlite",
        run_id,
        succeeded=True,
        finished_at="2026-07-01T12:30:00+00:00",
        representative_issue_keys=("ABC-1",),
    )


def _assert_latest_run_failed(tmp_path: Path, expected_message: str) -> None:
    with sqlite3.connect(tmp_path / "state.sqlite") as connection:
        row = connection.execute(
            """
            SELECT succeeded, partial_failure, failure_message
            FROM export_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert row is not None
    assert row[0] == 0
    assert row[1] == 1
    assert expected_message in row[2]


def _raw_issue(
    key: str,
    *,
    attachments: list[dict[str, Any]] | None = None,
    updated: str = "2026-06-01T00:00:00.000+0000",
) -> dict[str, Any]:
    number = key.split("-", 1)[1]
    return {
        "id": f"1000{number}",
        "key": key,
        "self": f"{SITE}/rest/api/3/issue/1000{number}",
        "fields": {
            "summary": f"Summary {key}",
            "description": None,
            "project": {"key": "ABC"},
            "issuetype": {"name": "Task"},
            "status": {"name": "To Do"},
            "priority": None,
            "assignee": {"displayName": "Ada"},
            "reporter": {"displayName": "Rae"},
            "created": "2026-06-01T00:00:00.000+0000",
            "updated": updated,
            "resolution": None,
            "resolutiondate": None,
            "labels": [],
            "components": [],
            "fixVersions": [],
            "versions": [],
            "parent": None,
            "customfield_10014": "EPIC-1",
            "customfield_10016": 5,
            "issuelinks": [],
            "subtasks": [],
            "attachment": attachments or [],
        },
    }


def _attachment(
    attachment_id: str,
    filename: str,
    mime_type: str,
    size: int,
) -> dict[str, Any]:
    return {
        "id": attachment_id,
        "filename": filename,
        "mimeType": mime_type,
        "size": size,
        "created": "2026-06-01T00:00:00.000+0000",
        "author": {"displayName": "File Person"},
        "content": f"{SITE}/secure/attachment/{attachment_id}/{filename}",
    }


def _comments_response(comments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "startAt": 0,
        "maxResults": 100,
        "total": len(comments),
        "comments": comments,
    }


def _comment(comment_id: str, text: str) -> dict[str, Any]:
    return {
        "id": comment_id,
        "author": {"displayName": "Commenter"},
        "created": "2026-06-01T00:00:00.000+0000",
        "updated": "2026-06-01T00:00:00.000+0000",
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        },
    }
