from __future__ import annotations

import logging
from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from atlassian_md_export.client import AtlassianAuthenticationError
from atlassian_md_export.client import AtlassianClientError
from atlassian_md_export.client import AtlassianHttpClient
from atlassian_md_export.client import AtlassianHttpError
from atlassian_md_export.client import RetryConfig
from atlassian_md_export.config import ConfluenceCredentials
from atlassian_md_export.confluence.client import DEFAULT_BODY_FORMAT
from atlassian_md_export.confluence.client import V1_SEARCH_PATH
from atlassian_md_export.confluence.client import V2_SPACE_PATH
from atlassian_md_export.confluence.client import ConfluenceClient


def test_space_discovery_uses_v2_link_pagination_and_hydrates_pages() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == V2_SPACE_PATH:
            assert request.url.params["keys"] == "DOC"
            return httpx.Response(200, json={"results": [{"id": "space-1", "key": "DOC"}]})
        if request.url.path == "/wiki/api/v2/spaces/space-1/pages":
            if request.url.params.get("cursor") == "next":
                return httpx.Response(200, json={"results": [{"id": "2", "title": "Child"}]})
            return httpx.Response(
                200,
                headers={
                    "Link": '</wiki/api/v2/spaces/space-1/pages?cursor=next>; rel="next"'
                },
                json={"results": [{"id": "1", "title": "Root"}]},
            )
        if request.url.path in {"/wiki/api/v2/pages/1", "/wiki/api/v2/pages/2"}:
            assert request.url.params["body-format"] == DEFAULT_BODY_FORMAT
            page_id = request.url.path.rsplit("/", 1)[1]
            return httpx.Response(
                200,
                json={
                    "id": page_id,
                    "title": f"Hydrated {page_id}",
                    "status": "current",
                    "spaceId": "space-1",
                    "version": {"number": int(page_id), "createdAt": "2026-07-01T12:00:00Z"},
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    pages = _client(handler).fetch_space_pages("DOC", limit=1)

    assert [page.id for page in pages] == ["1", "2"]
    assert [page.title for page in pages] == ["Hydrated 1", "Hydrated 2"]
    assert all(request.url.path != V1_SEARCH_PATH for request in requests)


def test_fetch_page_resolves_space_key_by_id_without_mutating_raw() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/wiki/api/v2/pages/123":
            return httpx.Response(
                200,
                json={
                    "id": "123",
                    "title": "Live Page",
                    "spaceId": "space-1",
                    "version": {"number": 1},
                },
            )
        if request.url.path == "/wiki/api/v2/spaces/space-1":
            return httpx.Response(200, json={"id": "space-1", "key": "DOC"})
        raise AssertionError(f"unexpected request: {request.url}")

    page = _client(handler).fetch_page("123")

    assert page.space_key == "DOC"
    assert "spaceKey" not in page.raw
    assert requested_paths == ["/wiki/api/v2/pages/123", "/wiki/api/v2/spaces/space-1"]


def test_v2_pagination_accepts_same_origin_absolute_links_and_rejects_cross_origin() -> None:
    def same_origin_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/123/labels":
            if request.url.params.get("cursor") == "next":
                return httpx.Response(200, json={"results": [{"id": "2", "name": "beta"}]})
            return httpx.Response(
                200,
                headers={
                    "Link": (
                        "<https://example.atlassian.net/wiki/api/v2/pages/123/labels"
                        "?cursor=next>; rel=\"next\""
                    )
                },
                json={"results": [{"id": "1", "name": "alpha"}]},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    assert [label["name"] for label in _client(same_origin_handler).fetch_labels("123")] == [
        "alpha",
        "beta",
    ]

    def cross_origin_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/123/labels":
            return httpx.Response(
                200,
                headers={
                    "Link": (
                        "<https://evil.example.test/wiki/api/v2/pages/123/labels"
                        "?cursor=next>; rel=\"next\""
                    )
                },
                json={"results": [{"id": "1", "name": "alpha"}]},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(AtlassianClientError, match="origin does not match"):
        _client(cross_origin_handler).fetch_labels("123")


def test_cql_pagination_rejects_scheme_relative_next_links() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == V1_SEARCH_PATH:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"content": {"id": "10", "type": "page", "title": "Search 10"}}
                    ],
                    "_links": {"next": "//evil.example.test/wiki/rest/api/search?cursor=bad"},
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(AtlassianClientError, match="scheme-relative"):
        _client(handler).search_pages('space = "DOC"', limit=1)


def test_cql_discovery_uses_v1_search_then_v2_page_hydration() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == V1_SEARCH_PATH:
            if request.url.params.get("cursor") == "page-2":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {"content": {"id": "11", "type": "page", "title": "Search 11"}}
                        ]
                    },
                )
            assert request.url.params["cql"] == 'space = "DOC"'
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"content": {"id": "10", "type": "page", "title": "Search 10"}}
                    ],
                    "_links": {"next": "/wiki/rest/api/search?cursor=page-2"},
                },
            )
        if request.url.path in {"/wiki/api/v2/pages/10", "/wiki/api/v2/pages/11"}:
            assert request.url.params["body-format"] == DEFAULT_BODY_FORMAT
            page_id = request.url.path.rsplit("/", 1)[1]
            return httpx.Response(
                200,
                json={"id": page_id, "title": f"Hydrated {page_id}", "version": {"number": 1}},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    pages = _client(handler).search_pages('space = "DOC"', limit=1)

    assert [page.title for page in pages] == ["Hydrated 10", "Hydrated 11"]
    assert [request.url.path for request in requests].count(V1_SEARCH_PATH) == 2


def test_ancestor_subtree_includes_root_and_hydrated_page_descendants() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/root":
            assert request.url.params["body-format"] == DEFAULT_BODY_FORMAT
            return httpx.Response(200, json={"id": "root", "title": "Root"})
        if request.url.path == "/wiki/api/v2/pages/root/descendants":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "child",
                            "title": "Child Summary",
                            "type": "page",
                            "parentId": "root",
                        },
                        {
                            "id": "whiteboard",
                            "title": "Board",
                            "type": "whiteboard",
                            "parentId": "root",
                        },
                    ]
                },
            )
        if request.url.path == "/wiki/api/v2/pages/child":
            assert request.url.params["body-format"] == DEFAULT_BODY_FORMAT
            return httpx.Response(200, json={"id": "child", "title": "Hydrated Child"})
        raise AssertionError(f"unexpected request: {request.url}")

    pages = _client(handler).fetch_ancestor_subtree("root")

    assert [page.id for page in pages] == ["root", "child"]
    assert [page.title for page in pages] == ["Root", "Hydrated Child"]


def test_footer_and_inline_comments_paginate_with_default_body_format() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["body-format"] == DEFAULT_BODY_FORMAT
        if request.url.path == "/wiki/api/v2/pages/123/footer-comments":
            if request.url.params.get("cursor") == "footer-2":
                return httpx.Response(200, json={"results": [{"id": "footer-2"}]})
            return httpx.Response(
                200,
                headers={
                    "Link": (
                        "</wiki/api/v2/pages/123/footer-comments"
                        "?cursor=footer-2&body-format=atlas_doc_format>; rel=\"next\""
                    )
                },
                json={"results": [{"id": "footer-1"}]},
            )
        if request.url.path == "/wiki/api/v2/pages/123/inline-comments":
            assert request.url.params["resolution-status"] == "resolved"
            return httpx.Response(200, json={"results": [{"id": "inline-1"}]})
        raise AssertionError(f"unexpected request: {request.url}")

    client = _client(handler)

    assert [comment["id"] for comment in client.fetch_footer_comments("123")] == [
        "footer-1",
        "footer-2",
    ]
    assert [
        comment["id"]
        for comment in client.fetch_inline_comments("123", resolution_status="resolved")
    ] == ["inline-1"]


def test_labels_ancestors_descendants_and_attachment_metadata_methods_validate_payloads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/123/labels":
            return httpx.Response(200, json={"results": [{"id": "label-1", "name": "team"}]})
        if request.url.path == "/wiki/api/v2/pages/123/ancestors":
            return httpx.Response(
                200,
                json={"results": [{"id": "root", "type": "page"}, {"id": "folder", "type": "folder"}]},
            )
        if request.url.path == "/wiki/api/v2/pages/123/descendants":
            return httpx.Response(
                200,
                json={"results": [{"id": "child", "type": "page"}]},
            )
        if request.url.path == "/wiki/api/v2/pages/123/attachments":
            return httpx.Response(200, json={"results": [{"id": "att-1", "title": "a.png"}]})
        raise AssertionError(f"unexpected request: {request.url}")

    client = _client(handler)

    assert client.fetch_labels("123")[0]["name"] == "team"
    assert client.fetch_ancestors("123")[0]["id"] == "root"
    assert client.fetch_ancestors("123")[1]["type"] == "folder"
    assert client.fetch_descendants("123")[0]["type"] == "page"
    assert client.fetch_attachment_metadata("123")[0]["title"] == "a.png"


@pytest.mark.parametrize("status_code", [429, 500])
def test_retry_handles_429_and_5xx(
    status_code: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    attempts = 0
    sleep_values: list[float] = []
    caplog.set_level(logging.WARNING, logger="atlassian_md_export.client")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            headers = {"Retry-After": "2"} if status_code == 429 else {}
            return httpx.Response(status_code, headers=headers, json={})
        return httpx.Response(200, json={"id": "123", "title": "Page"})

    page = _client(handler, sleep_values=sleep_values).fetch_page("123")

    assert page.id == "123"
    assert attempts == 2
    assert sleep_values == ([2.0] if status_code == 429 else [0.0])
    retry_record = _log_record(caplog, "http_request")
    assert getattr(retry_record, "provider") == "confluence"
    assert getattr(retry_record, "resource_path") == "/wiki/api/v2/pages/123"
    assert getattr(retry_record, "status_code") == status_code
    assert getattr(retry_record, "retry_attempt") == 1
    assert getattr(retry_record, "retry_count") == 3


def test_401_fails_fast_without_retry() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"message": "bad auth"})

    with pytest.raises(AtlassianAuthenticationError, match="Confluence authentication failed"):
        _client(handler).fetch_page("123")

    assert attempts == 1


def test_confluence_http_error_uses_message_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="atlassian_md_export.client")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "Current user cannot view this page", "statusCode": 403},
        )

    with pytest.raises(AtlassianHttpError, match="Current user cannot view this page"):
        _client(handler).fetch_page("123")

    failure_record = _log_record(caplog, "http_request")
    assert getattr(failure_record, "provider") == "confluence"
    assert getattr(failure_record, "resource_path") == "/wiki/api/v2/pages/123"
    assert getattr(failure_record, "status_code") == 403
    assert getattr(failure_record, "retry_attempt") == 1
    assert getattr(failure_record, "retry_count") == 3


def test_malformed_200_payloads_fail_strict_validation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/123":
            return httpx.Response(200, json={"id": "123"})
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(AtlassianClientError, match="id/title"):
        _client(handler).fetch_page("123")


def test_missing_results_list_fails_strict_validation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wiki/api/v2/pages/123/labels":
            return httpx.Response(200, json={"values": []})
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(AtlassianClientError, match="results list"):
        _client(handler).fetch_labels("123")


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    sleep_values: list[float] | None = None,
) -> ConfluenceClient:
    transport = httpx.MockTransport(handler)
    retry = RetryConfig(max_attempts=3, base_delay_seconds=0, jitter_seconds=0)
    credentials = ConfluenceCredentials(
        email="user@example.com",
        api_token=SecretStr("token"),
    )
    sleep = sleep_values.append if sleep_values is not None else lambda _delay: None
    return ConfluenceClient(
        AtlassianHttpClient(
            "https://example.atlassian.net",
            credentials,
            provider_name="Confluence",
            auth_hint="Check CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN, and site access.",
            retry=retry,
            transport=transport,
            sleep=sleep,
        )
    )


def _log_record(
    caplog: pytest.LogCaptureFixture,
    operation: str,
) -> logging.LogRecord:
    for record in caplog.records:
        if (
            record.name == "atlassian_md_export.client"
            and getattr(record, "operation", None) == operation
        ):
            return record
    raise AssertionError(f"missing log operation: {operation}")
