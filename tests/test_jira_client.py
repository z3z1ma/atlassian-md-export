from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from pydantic import SecretStr

from atlassian_md_export.client import AtlassianClientError
from atlassian_md_export.client import AtlassianAuthenticationError
from atlassian_md_export.client import AtlassianHttpClient
from atlassian_md_export.client import JiraCredentials
from atlassian_md_export.client import RetryConfig
from atlassian_md_export.jira.client import MYSELF_PATH
from atlassian_md_export.jira.client import SEARCH_JQL_PATH
from atlassian_md_export.jira.client import JiraClient
from atlassian_md_export.jira.client import exact_issue_jql
from atlassian_md_export.jira.client import ordered_jql
from atlassian_md_export.jira.client import updated_since_jql


def test_search_issues_uses_enhanced_endpoint_and_next_page_token() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == SEARCH_JQL_PATH
        token = request.url.params.get("nextPageToken")
        if token is None:
            return httpx.Response(
                200,
                json={
                    "issues": [
                        {"id": "10001", "key": "ABC-1", "fields": {"updated": "2026-07-01"}}
                    ],
                    "nextPageToken": "page-2",
                    "isLast": False,
                },
            )
        assert token == "page-2"
        return httpx.Response(
            200,
            json={
                "issues": [{"id": "10002", "key": "ABC-2", "fields": {"updated": "2026-07-02"}}],
                "isLast": True,
            },
        )

    result = _client(handler).search_issues("project = ABC", fields=["summary"], max_results=1)

    assert [issue.key for issue in result.issues] == ["ABC-1", "ABC-2"]
    assert result.diagnostics.pages == 2
    assert result.diagnostics.stopped_on_is_last is True
    assert requests[0].url.params["fields"] == "summary"
    assert requests[1].url.params["nextPageToken"] == "page-2"
    assert all(request.url.path != "/rest/api/3/search" for request in requests)


def test_search_issues_rejects_missing_issues_success_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == SEARCH_JQL_PATH
        return httpx.Response(200, json={"isLast": True})

    with pytest.raises(AtlassianClientError, match="issues list"):
        _client(handler).search_issues("project = ABC")


def test_fetch_comments_paginates_until_total() -> None:
    starts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/issue/ABC-1/comment"
        starts.append(request.url.params["startAt"])
        if request.url.params["startAt"] == "0":
            return httpx.Response(
                200,
                json={
                    "startAt": 0,
                    "maxResults": 2,
                    "total": 3,
                    "comments": [{"id": "1"}, {"id": "2"}],
                },
            )
        return httpx.Response(
            200,
            json={
                "startAt": 2,
                "maxResults": 2,
                "total": 3,
                "comments": [{"id": "3"}],
            },
        )

    comments = _client(handler).fetch_comments("ABC-1", max_results=2)

    assert [comment["id"] for comment in comments] == ["1", "2", "3"]
    assert starts == ["0", "2"]


def test_fetch_comments_rejects_missing_comments_success_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/issue/ABC-1/comment"
        return httpx.Response(200, json={"startAt": 0, "maxResults": 100, "total": 0})

    with pytest.raises(AtlassianClientError, match="comments list"):
        _client(handler).fetch_comments("ABC-1")


def test_fetch_comments_accepts_empty_comments_success_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/issue/ABC-1/comment"
        return httpx.Response(
            200,
            json={"startAt": 0, "maxResults": 100, "total": 0, "comments": []},
        )

    assert _client(handler).fetch_comments("ABC-1") == ()


def test_fetch_issues_with_comments_ignores_embedded_search_comments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == SEARCH_JQL_PATH:
            return httpx.Response(
                200,
                json={
                    "issues": [
                        {
                            "id": "10001",
                            "key": "ABC-1",
                            "fields": {
                                "updated": "2026-07-01",
                                "comment": {"comments": [{"id": "embedded"}]},
                            },
                        }
                    ],
                    "isLast": True,
                },
            )
        assert request.url.path == "/rest/api/3/issue/ABC-1/comment"
        return httpx.Response(
            200,
            json={"startAt": 0, "maxResults": 100, "total": 1, "comments": [{"id": "real"}]},
        )

    result = _client(handler).fetch_issues_with_comments("key = ABC-1")

    assert [comment["id"] for comment in result.issues[0].comments] == ["real"]


def test_search_issue_keys_uses_key_constrained_jql() -> None:
    seen_jql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_jql.append(request.url.params["jql"])
        return httpx.Response(200, json={"issues": [], "isLast": True})

    _client(handler).search_issue_keys(["ABC-1", "ABC-2"])

    assert seen_jql == ['key in ("ABC-1", "ABC-2") ORDER BY updated ASC, key ASC']
    assert exact_issue_jql(["ABC-1"]) == 'key = "ABC-1" ORDER BY updated ASC, key ASC'


def test_updated_since_jql_formats_iso_in_jira_user_timezone() -> None:
    assert updated_since_jql(
        'project = "ABC" ORDER BY updated ASC, key ASC',
        "2026-07-01T12:20:59.999999+00:00",
        timezone_name="America/Los_Angeles",
    ) == ('(project = "ABC") AND updated >= "2026-07-01 05:20" ORDER BY updated ASC, key ASC')


def test_ordered_jql_ignores_order_by_inside_quoted_literal() -> None:
    assert ordered_jql('summary ~ "order by"') == (
        'summary ~ "order by" ORDER BY updated ASC, key ASC'
    )


def test_updated_since_jql_ignores_order_by_inside_quoted_literal() -> None:
    assert updated_since_jql('summary ~ "order by"', "2026-07-01 12:20") == (
        '(summary ~ "order by") AND updated >= "2026-07-01 12:20" ORDER BY updated ASC, key ASC'
    )


def test_ordered_jql_ignores_order_by_inside_escaped_quotes() -> None:
    jql = r'summary ~ "escaped \"order by\" literal"'

    assert ordered_jql(jql) == f"{jql} ORDER BY updated ASC, key ASC"


def test_updated_since_jql_preserves_real_order_by_after_quoted_literal() -> None:
    assert updated_since_jql(
        'summary ~ "needle" ORDER BY created DESC',
        "2026-07-01 12:20",
    ) == ('(summary ~ "needle") AND updated >= "2026-07-01 12:20" ORDER BY created DESC')


def test_user_timezone_reads_myself_profile() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == MYSELF_PATH
        return httpx.Response(200, json={"timeZone": "America/Los_Angeles"})

    assert _client(handler).user_timezone() == "America/Los_Angeles"


def test_search_jql_can_return_empty_success_for_invalid_date_literal() -> None:
    seen_jql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_jql.append(request.url.params["jql"])
        return httpx.Response(200, json={"issues": [], "isLast": True})

    result = _client(handler).search_issues(
        '(project = "ABC") AND updated >= "2026-07-01T12:20:00+00:00" ORDER BY updated ASC, key ASC'
    )

    assert result.issues == ()
    assert "T12:20:00+00:00" in seen_jql[0]


def test_retry_uses_retry_after_for_429() -> None:
    attempts = 0
    sleep_values: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, json={})
        return httpx.Response(200, json={"issues": [], "isLast": True})

    _client(handler, sleep_values=sleep_values).search_issues("project = ABC")

    assert attempts == 2
    assert sleep_values == [2.0]


def test_401_fails_fast_without_retry() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"errorMessages": ["bad auth"]})

    with pytest.raises(AtlassianAuthenticationError):
        _client(handler).search_issues("project = ABC")

    assert attempts == 1


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    sleep_values: list[float] | None = None,
) -> JiraClient:
    transport = httpx.MockTransport(handler)
    retry = RetryConfig(max_attempts=3, base_delay_seconds=0, jitter_seconds=0)
    credentials = JiraCredentials(email="user@example.com", api_token=SecretStr("token"))
    sleep = sleep_values.append if sleep_values is not None else lambda _delay: None
    return JiraClient(
        AtlassianHttpClient(
            "https://example.atlassian.net",
            credentials,
            retry=retry,
            transport=transport,
            sleep=sleep,
        )
    )
