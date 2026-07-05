from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

import atlassian_md_export.operations as operations
from atlassian_md_export.attachments import confluence_attachment_path
from atlassian_md_export.client import AtlassianHttpClient
from atlassian_md_export.client import RetryConfig
from atlassian_md_export.config import ConfluenceCredentials
from atlassian_md_export.config import ExportConfig
from atlassian_md_export.config import MarkdownConfig
from atlassian_md_export.confluence.client import ConfluenceClient
from atlassian_md_export.indexes import generate_confluence_indexes
from atlassian_md_export.operations import AttachmentOptions
from atlassian_md_export.operations import ExportCommandError
from atlassian_md_export.operations import clean_confluence_export
from atlassian_md_export.operations import initialize_confluence_output
from atlassian_md_export.operations import run_confluence_attachments
from atlassian_md_export.operations import run_confluence_comments
from atlassian_md_export.operations import run_confluence_page
from atlassian_md_export.operations import run_confluence_pull
from atlassian_md_export.operations import verify_confluence_export
from atlassian_md_export.state import ConfluencePageState
from atlassian_md_export.state import finish_confluence_export_run
from atlassian_md_export.state import latest_successful_confluence_representative_run
from atlassian_md_export.state import start_confluence_export_run
from atlassian_md_export.state import upsert_confluence_page_state
from atlassian_md_export.writer import normalize_confluence_page
from atlassian_md_export.writer import write_confluence_page_files

SITE = "https://example.atlassian.net"


def test_confluence_pull_fetches_resources_downloads_filtered_attachments_and_verifies(
    tmp_path: Path,
) -> None:
    requested_paths: list[str] = []

    summary = run_confluence_pull(
        tmp_path,
        client=_client(_full_pull_handler(requested_paths)),
        site_url=SITE,
        config=_config(),
        space="DOC",
        concurrency=0,
        attachment_options=AttachmentOptions(
            download=True,
            max_mb=1,
            include_patterns=("*.log",),
        ),
    )

    downloaded = _assert_full_confluence_pull_outputs(
        tmp_path,
        page_ids=summary.page_ids,
        requested_paths=requested_paths,
    )
    _assert_missing_confluence_download_fails_verification(tmp_path, downloaded)


def test_confluence_pull_logs_safe_structured_context(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="atlassian_md_export.operations")
    caplog.set_level(logging.DEBUG, logger="atlassian_md_export.client")

    summary = run_confluence_pull(
        tmp_path,
        client=_client(_single_page_pull_handler("Launch with hidden body text")),
        site_url=SITE,
        config=_config(),
        space="DOC",
        concurrency=1,
    )

    _assert_safe_confluence_log_context(caplog, page_ids=summary.page_ids)
    assert "hidden body text body" not in caplog.text
    assert "Authorization" not in caplog.text


def test_confluence_pull_honors_concurrency_and_preserves_export_order(
    tmp_path: Path,
) -> None:
    probe = _ConcurrencyProbe()

    summary = run_confluence_pull(
        tmp_path,
        client=_client(probe.handler),
        site_url=SITE,
        config=_config(),
        space="DOC",
        concurrency=2,
        attachment_options=AttachmentOptions(download=True),
    )

    assert summary.page_ids == ("1", "2", "3")
    assert probe.max_active_network_requests == 2
    assert probe.download_order.index("2") < probe.download_order.index("1")
    with sqlite3.connect(tmp_path / "state.sqlite") as connection:
        rows = connection.execute("SELECT page_id FROM confluence_pages ORDER BY rowid").fetchall()
    assert rows == [("1",), ("2",), ("3",)]
    assert (tmp_path / "attachments" / "1" / "att-1-page-1.txt").read_bytes() == b"download-1"
    assert verify_confluence_export(tmp_path).ok


def test_confluence_page_repull_uses_existing_local_link_context(tmp_path: Path) -> None:
    initialize_confluence_output(tmp_path)
    root = normalize_confluence_page(_raw_page("100", "Root"), site_url=SITE)
    write_confluence_page_files(tmp_path, root, stable_exported_at=True, exported_pages=(root,))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/123":
            return httpx.Response(
                200,
                json=_raw_page("123", "Child", parent_id="100"),
            )
        if request.url.path == "/wiki/api/v2/pages/123/footer-comments":
            return httpx.Response(200, json={"results": []})
        if request.url.path == "/wiki/api/v2/pages/123/inline-comments":
            return httpx.Response(200, json={"results": []})
        if request.url.path == "/wiki/api/v2/pages/123/attachments":
            return httpx.Response(200, json={"results": []})
        if request.url.path == "/wiki/api/v2/pages/123/labels":
            return httpx.Response(200, json={"results": []})
        if request.url.path == "/wiki/api/v2/pages/123/ancestors":
            return httpx.Response(
                200,
                json={"results": [{"id": "100", "title": "Root", "spaceKey": "DOC"}]},
            )
        if request.url.path == "/wiki/api/v2/pages/123/descendants":
            return httpx.Response(200, json={"results": []})
        raise AssertionError(f"unexpected request: {request.url}")

    run_confluence_page(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        page_ids=["123"],
    )

    markdown = (tmp_path / "pages" / "DOC" / "123-Child.md").read_text(encoding="utf-8")
    assert "- Parent: [Root](100-Root.md)" in markdown
    assert "- [Root](100-Root.md) (id=100)" in markdown
    assert verify_confluence_export(tmp_path).ok


def test_confluence_page_resolves_space_key_and_wiki_urls_for_v2_page_payload(
    tmp_path: Path,
) -> None:
    requested_paths: list[str] = []
    raw_page = _raw_page("123", "Live")
    raw_page.pop("spaceKey")
    raw_page["_links"] = {
        "base": "https://example.atlassian.net/wiki",
        "webui": "/spaces/DOC/pages/123/Live",
    }

    run_confluence_page(
        tmp_path,
        client=_client(_space_resolution_handler(requested_paths, raw_page)),
        site_url=SITE,
        config=_config(),
        page_ids=["123"],
    )

    markdown = (tmp_path / "pages" / "DOC" / "123-Live.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "pages" / "_raw" / "123.json").read_text(encoding="utf-8"))

    assert "/wiki/api/v2/spaces/space-1" in requested_paths
    assert "url: https://example.atlassian.net/wiki/spaces/DOC/pages/123/Live" in markdown
    assert "space_key: DOC" in markdown
    assert "https://example.atlassian.net/wiki/spaces/DOC/pages/100" in markdown
    assert payload["normalized_page"]["space_key"] == "DOC"
    assert "spaceKey" not in payload["raw_page"]
    assert verify_confluence_export(tmp_path).ok


def test_confluence_refresh_commands_preserve_normalized_page_metadata(
    tmp_path: Path,
) -> None:
    initialize_confluence_output(tmp_path)
    raw_page = _raw_page("123", "Live")
    raw_page.pop("spaceKey")
    raw_page.pop("_links")
    page = normalize_confluence_page(
        raw_page,
        site_url=SITE,
        space_key="DOC",
        url="https://example.atlassian.net/wiki/spaces/DOC/pages/123/Live",
    )
    write_confluence_page_files(tmp_path, page, stable_exported_at=True, exported_pages=(page,))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/123/footer-comments":
            return httpx.Response(
                200,
                json={"results": [_comment("1", "Fresh footer", "2026-07-01T11:00:00Z")]},
            )
        if request.url.path == "/wiki/api/v2/pages/123/inline-comments":
            return httpx.Response(200, json={"results": []})
        if request.url.path == "/wiki/api/v2/pages/123/attachments":
            return httpx.Response(
                200,
                json={"results": [_attachment("att-1", "debug.log", "text/plain", 4)]},
            )
        if request.url.path == "/download/attachments/att-1/debug.log":
            return httpx.Response(200, content=b"log!")
        raise AssertionError(f"unexpected request: {request.url}")

    comments = run_confluence_comments(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        page_ids=["123"],
        force=True,
    )
    attachments = run_confluence_attachments(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        page_ids=["123"],
        attachment_options=AttachmentOptions(download=True),
    )

    markdown_path = tmp_path / "pages" / "DOC" / "123-Live.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "pages" / "_raw" / "123.json").read_text(encoding="utf-8"))

    assert comments.page_ids == ("123",)
    assert attachments.page_ids == ("123",)
    assert not (tmp_path / "pages" / "unknown-space").exists()
    assert "url: https://example.atlassian.net/wiki/spaces/DOC/pages/123/Live" in markdown
    assert "space_key: DOC" in markdown
    assert "Fresh footer" in markdown
    assert "[local file](../../attachments/123/att-1-debug.log)" in markdown
    assert (tmp_path / "attachments" / "123" / "att-1-debug.log").read_bytes() == b"log!"
    assert payload["normalized_page"]["space_key"] == "DOC"
    assert payload["normalized_page"]["url"] == (
        "https://example.atlassian.net/wiki/spaces/DOC/pages/123/Live"
    )
    assert "spaceKey" not in payload["raw_page"]
    assert verify_confluence_export(tmp_path).ok


def test_confluence_ancestor_pull_refreshes_cleanup_authority(
    tmp_path: Path,
) -> None:
    root_descendant_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal root_descendant_calls
        if request.url.path == "/wiki/api/v2/pages/100":
            return httpx.Response(200, json=_raw_page("100", "Root"))
        if request.url.path == "/wiki/api/v2/pages/123":
            return httpx.Response(200, json=_raw_page("123", "Removed", parent_id="100"))
        if request.url.path == "/wiki/api/v2/pages/100/descendants":
            root_descendant_calls += 1
            if root_descendant_calls <= 2:
                return httpx.Response(
                    200,
                    json={"results": [{"id": "123", "title": "Removed", "type": "page"}]},
                )
            return httpx.Response(200, json={"results": []})
        if request.url.path.endswith(
            (
                "/footer-comments",
                "/inline-comments",
                "/attachments",
                "/labels",
                "/ancestors",
                "/descendants",
            )
        ):
            return httpx.Response(200, json={"results": []})
        raise AssertionError(f"unexpected request: {request.url}")

    first = run_confluence_pull(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        ancestor="100",
        concurrency=1,
    )
    second = run_confluence_pull(
        tmp_path,
        client=_client(handler),
        site_url=SITE,
        config=_config(),
        ancestor="100",
        concurrency=1,
    )

    assert first.page_ids == ("100", "123")
    assert second.page_ids == ("100",)
    representative = latest_successful_confluence_representative_run(tmp_path / "state.sqlite")
    assert representative is not None
    assert representative.representative_page_ids == ("100",)

    result = clean_confluence_export(tmp_path, remove_missing=True)

    assert result.removed_page_ids == ("123",)
    assert not (tmp_path / "pages" / "DOC" / "123-Removed.md").exists()
    assert not (tmp_path / "pages" / "_raw" / "123.json").exists()
    assert verify_confluence_export(tmp_path).ok


def test_confluence_attachment_filename_and_url_safety(tmp_path: Path) -> None:
    path = confluence_attachment_path(tmp_path, "../123", "../att", "../../.secret")

    assert path.parent == tmp_path / "attachments" / "123"
    assert "/" not in path.name
    assert "\\" not in path.name
    assert not path.name.startswith(".")

    assert operations._confluence_attachment_download_target(
        "/wiki/download/attachments/123/file.txt",
        site_url=SITE,
    ) == ("/wiki/download/attachments/123/file.txt", None)
    assert operations._confluence_attachment_download_target(
        "https://example.atlassian.net/wiki/download/attachments/123/file.txt",
        site_url=SITE,
    ) == ("https://example.atlassian.net/wiki/download/attachments/123/file.txt", None)

    rejected_urls = [
        "https://files.example.test/wiki/download/attachments/123/file.txt",
        "http://example.atlassian.net/wiki/download/attachments/123/file.txt",
        "//files.example.test/wiki/download/attachments/123/file.txt",
        "../download/attachments/123/file.txt",
        "/wiki/download/%2e%2e/file.txt",
        "javascript:alert(1)",
    ]
    for url in rejected_urls:
        _target, error = operations._confluence_attachment_download_target(url, site_url=SITE)
        assert error is not None


def test_confluence_indexes_cover_all_groupings_and_stale_pages(tmp_path: Path) -> None:
    initialize_confluence_output(tmp_path)
    root = normalize_confluence_page(
        _raw_page("100", "Root", updated="2026-07-01T00:00:00Z"), site_url=SITE
    )
    old = normalize_confluence_page(
        _raw_page("123", "Old Page", parent_id="100", updated="2026-01-01T00:00:00Z"),
        labels=[{"id": "label-1", "prefix": "team", "name": "alpha"}],
        ancestors=[{"id": "100", "title": "Root", "spaceKey": "DOC"}],
        site_url=SITE,
    )
    recent = normalize_confluence_page(
        _raw_page("124", "Recent Page", updated="2026-01-20T00:00:00Z"),
        site_url=SITE,
    )
    exported_pages = (root, old, recent)
    write_confluence_page_files(
        tmp_path, old, stable_exported_at=True, exported_pages=exported_pages
    )
    write_confluence_page_files(
        tmp_path, recent, stable_exported_at=True, exported_pages=exported_pages
    )

    paths = generate_confluence_indexes(tmp_path, stale_days=10)

    assert {path.name for path in paths} == {
        "all.md",
        "by-label.md",
        "by-parent.md",
        "by-space.md",
        "stale.md",
    }
    assert "[Old Page](../pages/DOC/123-Old-Page.md)" in (
        tmp_path / "indexes" / "all.md"
    ).read_text(encoding="utf-8")
    assert "## DOC" in (tmp_path / "indexes" / "by-space.md").read_text(encoding="utf-8")
    assert "## team:alpha" in (tmp_path / "indexes" / "by-label.md").read_text(encoding="utf-8")
    assert "## No Labels" in (tmp_path / "indexes" / "by-label.md").read_text(encoding="utf-8")
    assert "## Root (100)" in (tmp_path / "indexes" / "by-parent.md").read_text(encoding="utf-8")
    stale = (tmp_path / "indexes" / "stale.md").read_text(encoding="utf-8")
    assert "[Old Page]" in stale
    assert "[Recent Page]" not in stale


def test_confluence_clean_remove_missing_uses_representative_authority_and_preserves_state(
    tmp_path: Path,
) -> None:
    initialize_confluence_output(tmp_path)
    page_1 = normalize_confluence_page(_raw_page("123", "Keep"), site_url=SITE)
    page_2 = normalize_confluence_page(_raw_page("456", "Remove"), site_url=SITE)
    write_confluence_page_files(
        tmp_path, page_1, stable_exported_at=True, exported_pages=(page_1, page_2)
    )
    write_confluence_page_files(
        tmp_path, page_2, stable_exported_at=True, exported_pages=(page_1, page_2)
    )
    (tmp_path / "attachments" / "456").mkdir(parents=True)
    (tmp_path / "attachments" / "456" / "att-old.txt").write_bytes(b"old")
    upsert_confluence_page_state(tmp_path / "state.sqlite", ConfluencePageState(page_id="456"))
    run_id = start_confluence_export_run(
        tmp_path / "state.sqlite",
        command="pull",
        scope_type="space",
        scope_value="DOC",
    )
    finish_confluence_export_run(
        tmp_path / "state.sqlite",
        run_id,
        succeeded=True,
        representative_page_ids=("123",),
    )

    result = clean_confluence_export(tmp_path, remove_missing=True)

    assert result.removed_page_ids == ("456",)
    assert not (tmp_path / "pages" / "DOC" / "456-Remove.md").exists()
    assert not (tmp_path / "pages" / "_raw" / "456.json").exists()
    assert not (tmp_path / "attachments" / "456").exists()
    with sqlite3.connect(tmp_path / "state.sqlite") as connection:
        row = connection.execute(
            "SELECT page_id FROM confluence_pages WHERE page_id = '456'"
        ).fetchone()
    assert row == ("456",)
    assert verify_confluence_export(tmp_path).ok


def test_confluence_attachment_partial_failure_does_not_advance_representative_run(
    tmp_path: Path,
) -> None:
    with pytest.raises(ExportCommandError, match="partial failures"):
        run_confluence_pull(
            tmp_path,
            client=_client(_attachment_partial_failure_handler()),
            site_url=SITE,
            config=_config(),
            space="DOC",
            attachment_options=AttachmentOptions(download=True),
        )

    assert (tmp_path / "pages" / "DOC" / "123-Launch.md").is_file()
    assert latest_successful_confluence_representative_run(tmp_path / "state.sqlite") is None
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["last_successful_representative_run"] is None


type _Route = Callable[[httpx.Request], httpx.Response]


def _assert_full_confluence_pull_outputs(
    tmp_path: Path,
    *,
    page_ids: tuple[str, ...],
    requested_paths: list[str],
) -> Path:
    assert page_ids == ("123",)
    assert {
        "/wiki/api/v2/pages/123/footer-comments",
        "/wiki/api/v2/pages/123/inline-comments",
        "/wiki/api/v2/pages/123/attachments",
        "/wiki/api/v2/pages/123/labels",
        "/wiki/api/v2/pages/123/ancestors",
        "/wiki/api/v2/pages/123/descendants",
    } <= set(requested_paths)

    downloaded = tmp_path / "attachments" / "123" / "att-1-debug.log"
    skipped = tmp_path / "attachments" / "123" / "att-2-screenshot.png"
    assert (downloaded.read_bytes(), skipped.exists()) == (b"log!", False)

    _assert_full_confluence_pull_markdown(tmp_path)
    _assert_full_confluence_pull_payload(tmp_path)
    _assert_full_confluence_pull_manifest(tmp_path)
    assert verify_confluence_export(tmp_path).ok
    return downloaded


def _assert_full_confluence_pull_markdown(tmp_path: Path) -> None:
    markdown = (tmp_path / "pages" / "DOC" / "123-Launch.md").read_text(encoding="utf-8")
    assert all(
        fragment in markdown
        for fragment in (
            "[local file](../../attachments/123/att-1-debug.log)",
            "screenshot.png",
            "First",
            "Second",
            "Inline Resolution Status: open",
        )
    )
    assert markdown.index("### Footer Comment 1") < markdown.index("### Footer Comment 2")


def _assert_full_confluence_pull_payload(tmp_path: Path) -> None:
    payload = json.loads((tmp_path / "pages" / "_raw" / "123.json").read_text(encoding="utf-8"))
    metadata_by_id = {item["id"]: item for item in payload["attachment_metadata"]}
    assert {
        "att-1": metadata_by_id["att-1"]["local_path"],
        "att-2": metadata_by_id["att-2"]["local_path"],
        "footer_comment_ids": [comment["id"] for comment in payload["fetched_footer_comments"]],
        "inline_comment_ids": [comment["id"] for comment in payload["fetched_inline_comments"]],
    } == {
        "att-1": "../../attachments/123/att-1-debug.log",
        "att-2": None,
        "footer_comment_ids": ["1", "2"],
        "inline_comment_ids": ["10"],
    }


def _assert_full_confluence_pull_manifest(tmp_path: Path) -> None:
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert {
        "counts": manifest["counts"],
        "page_ids": manifest["last_successful_representative_run"]["page_ids"],
        "has_attachment_hash": "attachments/123/att-1-debug.log" in manifest["hashes"],
        "has_all_index_link": "[Launch](../pages/DOC/123-Launch.md)"
        in (tmp_path / "indexes" / "all.md").read_text(encoding="utf-8"),
    } == {
        "counts": {
            "attachments": 2,
            "footer_comments": 2,
            "inline_comments": 1,
            "pages": 1,
        },
        "page_ids": ["123"],
        "has_attachment_hash": True,
        "has_all_index_link": True,
    }


def _assert_missing_confluence_download_fails_verification(
    tmp_path: Path,
    downloaded: Path,
) -> None:
    downloaded.unlink()
    failure = verify_confluence_export(tmp_path)
    assert not failure.ok
    assert any("Downloaded Confluence attachment missing" in error for error in failure.errors)


def _assert_safe_confluence_log_context(
    caplog: pytest.LogCaptureFixture,
    *,
    page_ids: tuple[str, ...],
) -> None:
    assert page_ids == ("123",)
    write_record = _log_record(caplog, "confluence_page_write")
    assert _record_attrs(
        write_record, "provider", "command", "site_host", "page_id", "space_key"
    ) == {
        "provider": "confluence",
        "command": "pull",
        "site_host": "example.atlassian.net",
        "page_id": "123",
        "space_key": "DOC",
    }
    assert str(getattr(write_record, "output_path")).endswith(
        "pages/DOC/123-Launch-with-hidden-body-text.md"
    )
    assert str(getattr(write_record, "raw_json_path")).endswith("pages/_raw/123.json")

    fetch_record = _log_record(caplog, "confluence_footer_comments_fetch")
    assert _record_attrs(fetch_record, "command", "page_id") == {
        "command": "pull",
        "page_id": "123",
    }

    http_record = _log_record(caplog, "http_request", logger_name="atlassian_md_export.client")
    assert _record_attrs(
        http_record,
        "provider",
        "resource_path",
        "status_code",
        "retry_attempt",
        "retry_count",
    ) == {
        "provider": "confluence",
        "resource_path": "/wiki/api/v2/spaces",
        "status_code": 200,
        "retry_attempt": 1,
        "retry_count": 1,
    }


def _record_attrs(record: logging.LogRecord, *names: str) -> dict[str, object]:
    return {name: getattr(record, name) for name in names}


def _route_handler(
    routes: Mapping[str, _Route],
    requested_paths: list[str] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path) if requested_paths is not None else None
        route = routes.get(request.url.path)
        if route is None:
            raise AssertionError(f"unexpected request: {request.url}")
        return route(request)

    return handler


def _json_response(payload: object) -> httpx.Response:
    return httpx.Response(200, json=payload)


def _empty_results(_request: httpx.Request) -> httpx.Response:
    return _json_response({"results": []})


def _space_response(request: httpx.Request) -> httpx.Response:
    assert request.url.params["keys"] == "DOC"
    return _json_response({"results": [{"id": "space-1", "key": "DOC"}]})


def _full_pull_handler(requested_paths: list[str]) -> Callable[[httpx.Request], httpx.Response]:
    def page_response(request: httpx.Request) -> httpx.Response:
        assert request.url.params["body-format"] == "atlas_doc_format"
        return _json_response(_raw_page("123", "Launch", updated="2026-07-01T00:00:00Z"))

    return _route_handler(
        {
            "/wiki/api/v2/spaces": _space_response,
            "/wiki/api/v2/spaces/space-1/pages": lambda _request: _json_response(
                {"results": [{"id": "123", "title": "Launch"}]}
            ),
            "/wiki/api/v2/pages/123": page_response,
            "/wiki/api/v2/pages/123/footer-comments": lambda _request: _json_response(
                {
                    "results": [
                        _comment("2", "Second", "2026-07-01T12:00:00Z"),
                        _comment("1", "First", "2026-07-01T11:00:00Z"),
                    ]
                }
            ),
            "/wiki/api/v2/pages/123/inline-comments": lambda _request: _json_response(
                {
                    "results": [
                        _comment(
                            "10",
                            "Inline",
                            "2026-07-01T13:00:00Z",
                            resolution_status="open",
                        )
                    ]
                }
            ),
            "/wiki/api/v2/pages/123/attachments": lambda _request: _json_response(
                {
                    "results": [
                        _attachment("att-1", "debug.log", "text/plain", 4),
                        _attachment("att-2", "screenshot.png", "image/png", 4),
                    ]
                }
            ),
            "/wiki/api/v2/pages/123/labels": lambda _request: _json_response(
                {"results": [{"id": "label-1", "prefix": "team", "name": "alpha"}]}
            ),
            "/wiki/api/v2/pages/123/ancestors": _empty_results,
            "/wiki/api/v2/pages/123/descendants": lambda _request: _json_response(
                {"results": [{"id": "124", "title": "Child", "type": "page"}]}
            ),
            "/download/attachments/att-1/debug.log": lambda _request: httpx.Response(
                200, content=b"log!"
            ),
        },
        requested_paths,
    )


def _single_page_pull_handler(title: str) -> Callable[[httpx.Request], httpx.Response]:
    return _route_handler(
        {
            "/wiki/api/v2/spaces": lambda _request: _json_response(
                {"results": [{"id": "space-1", "key": "DOC"}]}
            ),
            "/wiki/api/v2/spaces/space-1/pages": lambda _request: _json_response(
                {"results": [{"id": "123", "title": "Launch"}]}
            ),
            "/wiki/api/v2/pages/123": lambda _request: _json_response(_raw_page("123", title)),
            "/wiki/api/v2/pages/123/footer-comments": _empty_results,
            "/wiki/api/v2/pages/123/inline-comments": _empty_results,
            "/wiki/api/v2/pages/123/attachments": _empty_results,
            "/wiki/api/v2/pages/123/labels": _empty_results,
            "/wiki/api/v2/pages/123/ancestors": _empty_results,
            "/wiki/api/v2/pages/123/descendants": _empty_results,
        }
    )


class _ConcurrencyProbe:
    def __init__(self) -> None:
        self._active_lock = threading.Lock()
        self._page_1_footer_started = threading.Event()
        self._page_2_downloaded = threading.Event()
        self._active_network_requests = 0
        self.max_active_network_requests = 0
        self.download_order: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/wiki/api/v2/spaces":
            return _json_response({"results": [{"id": "space-1", "key": "DOC"}]})
        if path == "/wiki/api/v2/spaces/space-1/pages":
            return _json_response(
                {
                    "results": [
                        {"id": "1", "title": "One"},
                        {"id": "2", "title": "Two"},
                        {"id": "3", "title": "Three"},
                    ]
                }
            )
        if path.startswith("/wiki/api/v2/pages/"):
            return self._page_response(path.removeprefix("/wiki/api/v2/pages/"))
        if path.startswith("/download/attachments/att-"):
            page_id = path.split("/", 4)[3].removeprefix("att-")
            return self._tracked_download(page_id)
        raise AssertionError(f"unexpected request: {request.url}")

    def _page_response(self, page_path: str) -> httpx.Response:
        if "/" not in page_path:
            return _json_response(_raw_page(page_path, f"Page {page_path}"))
        page_id, resource = page_path.split("/", 1)
        return self._tracked_page_resource(page_id, resource)

    def _tracked_page_resource(self, page_id: str, resource: str) -> httpx.Response:
        self._enter_network_request()
        try:
            self._coordinate_page_fetch(page_id, resource)
            if resource == "attachments":
                return _json_response(
                    {
                        "results": [
                            _attachment(
                                f"att-{page_id}",
                                f"page-{page_id}.txt",
                                "text/plain",
                                10,
                            )
                        ]
                    }
                )
            return _json_response({"results": []})
        finally:
            self._leave_network_request()

    def _coordinate_page_fetch(self, page_id: str, resource: str) -> None:
        if page_id == "1" and resource == "footer-comments":
            self._page_1_footer_started.set()
            self._page_2_downloaded.wait(timeout=2)
        if page_id == "2" and resource == "footer-comments":
            assert self._page_1_footer_started.wait(timeout=2)

    def _tracked_download(self, page_id: str) -> httpx.Response:
        self._enter_network_request()
        try:
            self.download_order.append(page_id)
            if page_id == "2":
                self._page_2_downloaded.set()
            return httpx.Response(200, content=f"download-{page_id}".encode())
        finally:
            self._leave_network_request()

    def _enter_network_request(self) -> None:
        with self._active_lock:
            self._active_network_requests += 1
            self.max_active_network_requests = max(
                self.max_active_network_requests,
                self._active_network_requests,
            )

    def _leave_network_request(self) -> None:
        with self._active_lock:
            self._active_network_requests -= 1


def _space_resolution_handler(
    requested_paths: list[str],
    raw_page: dict[str, Any],
) -> Callable[[httpx.Request], httpx.Response]:
    return _route_handler(
        {
            "/wiki/api/v2/pages/123": lambda _request: _json_response(raw_page),
            "/wiki/api/v2/spaces/space-1": lambda _request: _json_response(
                {"id": "space-1", "key": "DOC"}
            ),
            "/wiki/api/v2/pages/123/footer-comments": _empty_results,
            "/wiki/api/v2/pages/123/inline-comments": _empty_results,
            "/wiki/api/v2/pages/123/attachments": _empty_results,
            "/wiki/api/v2/pages/123/labels": _empty_results,
            "/wiki/api/v2/pages/123/ancestors": lambda _request: _json_response(
                {"results": [{"id": "100", "type": "page"}]}
            ),
            "/wiki/api/v2/pages/123/descendants": _empty_results,
        },
        requested_paths,
    )


def _attachment_partial_failure_handler() -> Callable[[httpx.Request], httpx.Response]:
    def attachments(_request: httpx.Request) -> httpx.Response:
        attachment = _attachment("att-1", "debug.log", "text/plain", 4)
        attachment["downloadLink"] = "https://files.example.test/download/debug.log"
        return _json_response({"results": [attachment]})

    return _route_handler(
        {
            "/wiki/api/v2/spaces": lambda _request: _json_response(
                {"results": [{"id": "space-1", "key": "DOC"}]}
            ),
            "/wiki/api/v2/spaces/space-1/pages": lambda _request: _json_response(
                {"results": [{"id": "123", "title": "Launch"}]}
            ),
            "/wiki/api/v2/pages/123": lambda _request: _json_response(_raw_page("123", "Launch")),
            "/wiki/api/v2/pages/123/footer-comments": _empty_results,
            "/wiki/api/v2/pages/123/inline-comments": _empty_results,
            "/wiki/api/v2/pages/123/attachments": attachments,
            "/wiki/api/v2/pages/123/labels": _empty_results,
            "/wiki/api/v2/pages/123/ancestors": _empty_results,
            "/wiki/api/v2/pages/123/descendants": _empty_results,
        }
    )


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> ConfluenceClient:
    transport = httpx.MockTransport(handler)
    credentials = ConfluenceCredentials(email="user@example.com", api_token=SecretStr("token"))
    return ConfluenceClient(
        AtlassianHttpClient(
            SITE,
            credentials,
            provider_name="Confluence",
            auth_hint="Check CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN, and site access.",
            retry=RetryConfig(max_attempts=1, base_delay_seconds=0, jitter_seconds=0),
            transport=transport,
            sleep=lambda _delay: None,
        )
    )


def _log_record(
    caplog: pytest.LogCaptureFixture,
    operation: str,
    *,
    logger_name: str = "atlassian_md_export.operations",
) -> logging.LogRecord:
    for record in caplog.records:
        if record.name == logger_name and getattr(record, "operation", None) == operation:
            return record
    raise AssertionError(f"missing log operation: {operation}")


def _config() -> ExportConfig:
    return ExportConfig(markdown=MarkdownConfig(stable_exported_at=True))


def _raw_page(
    page_id: str,
    title: str,
    *,
    parent_id: str | None = None,
    updated: str = "2026-06-01T00:00:00Z",
) -> dict[str, Any]:
    return {
        "id": page_id,
        "title": title,
        "status": "current",
        "spaceId": "space-1",
        "spaceKey": "DOC",
        "parentId": parent_id,
        "authorId": "user-1",
        "ownerId": "owner-1",
        "createdAt": "2026-06-01T00:00:00Z",
        "updatedAt": updated,
        "version": {"number": 1, "createdAt": updated},
        "body": {"atlas_doc_format": {"value": _adf_doc(f"{title} body")}},
        "_links": {"webui": f"/wiki/spaces/DOC/pages/{page_id}/{title}"},
    }


def _adf_doc(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def _comment(
    comment_id: str,
    text: str,
    created: str,
    *,
    resolution_status: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": comment_id,
        "author": {"displayName": "Commenter"},
        "createdAt": created,
        "updatedAt": created,
        "status": "current",
        "body": {"atlas_doc_format": {"value": _adf_doc(text)}},
    }
    if resolution_status is not None:
        payload["resolutionStatus"] = resolution_status
    return payload


def _attachment(
    attachment_id: str,
    filename: str,
    mime_type: str,
    size: int,
) -> dict[str, Any]:
    return {
        "id": attachment_id,
        "title": filename,
        "mediaType": mime_type,
        "fileSize": size,
        "createdAt": "2026-06-01T00:00:00Z",
        "author": {"displayName": "File Person"},
        "downloadLink": f"/download/attachments/{attachment_id}/{filename}",
    }
