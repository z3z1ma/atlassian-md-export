"""Jira Cloud REST API v3 client."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime
from datetime import timezone
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

import httpx

from atlassian_md_export.client import AtlassianClientError
from atlassian_md_export.client import AtlassianHttpClient

SEARCH_JQL_PATH = "/rest/api/3/search/jql"
MYSELF_PATH = "/rest/api/3/myself"
DEFAULT_SEARCH_PAGE_SIZE = 100
DEFAULT_COMMENT_PAGE_SIZE = 100
_ORDER_BY_RE = re.compile(r"\border\s+by\b", re.IGNORECASE)
_JIRA_DATE_LITERAL_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}(?: \d{2}:\d{2})?$")


@dataclass(frozen=True)
class JiraIssue:
    id: str
    key: str
    updated: str | None
    raw: dict[str, Any]
    comments: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class JiraSearchDiagnostics:
    pages: int
    stopped_on_is_last: bool
    stopped_without_next_token: bool


@dataclass(frozen=True)
class JiraSearchResult:
    issues: tuple[JiraIssue, ...]
    diagnostics: JiraSearchDiagnostics


@dataclass(frozen=True)
class JiraClient:
    http: AtlassianHttpClient

    def search_issues(
        self,
        jql: str,
        *,
        fields: Sequence[str] | None = None,
        max_results: int = DEFAULT_SEARCH_PAGE_SIZE,
    ) -> JiraSearchResult:
        with self.http.build_client() as client:
            return self._search_issues(client, jql, fields=fields, max_results=max_results)

    def search_issue_keys(
        self,
        issue_keys: Sequence[str],
        *,
        fields: Sequence[str] | None = None,
        max_results: int = DEFAULT_SEARCH_PAGE_SIZE,
    ) -> JiraSearchResult:
        return self.search_issues(
            exact_issue_jql(issue_keys),
            fields=fields,
            max_results=max_results,
        )

    def fetch_comments(
        self,
        issue_id_or_key: str,
        *,
        max_results: int = DEFAULT_COMMENT_PAGE_SIZE,
    ) -> tuple[dict[str, Any], ...]:
        with self.http.build_client() as client:
            return self._fetch_comments(client, issue_id_or_key, max_results=max_results)

    def user_timezone(self) -> str:
        with self.http.build_client() as client:
            payload = self.http.request_json(client, "GET", MYSELF_PATH)
        timezone_name = payload.get("timeZone")
        if not isinstance(timezone_name, str) or not timezone_name:
            raise AtlassianClientError("Jira user profile did not include a timeZone value.")
        return timezone_name

    def fetch_issues_with_comments(
        self,
        jql: str,
        *,
        fields: Sequence[str] | None = None,
        max_results: int = DEFAULT_SEARCH_PAGE_SIZE,
        comment_page_size: int = DEFAULT_COMMENT_PAGE_SIZE,
        concurrency: int = 1,
    ) -> JiraSearchResult:
        with self.http.build_client() as client:
            result = self._search_issues(client, jql, fields=fields, max_results=max_results)
            if concurrency > 1 and len(result.issues) > 1:
                return JiraSearchResult(
                    issues=self._with_comments_concurrently(
                        result.issues,
                        max_results=comment_page_size,
                        concurrency=concurrency,
                    ),
                    diagnostics=result.diagnostics,
                )
            issues = tuple(
                replace(
                    issue,
                    comments=self._fetch_comments(
                        client,
                        issue.key,
                        max_results=comment_page_size,
                    ),
                )
                for issue in result.issues
            )
            return JiraSearchResult(issues=issues, diagnostics=result.diagnostics)

    def _search_issues(
        self,
        client: httpx.Client,
        jql: str,
        *,
        fields: Sequence[str] | None,
        max_results: int,
    ) -> JiraSearchResult:
        issues: list[JiraIssue] = []
        next_page_token: str | None = None
        pages = 0
        stopped_on_is_last = False
        stopped_without_next_token = False

        while True:
            payload = self.http.request_json(
                client,
                "GET",
                SEARCH_JQL_PATH,
                params=_search_params(
                    jql,
                    fields=fields,
                    max_results=max_results,
                    next_page_token=next_page_token,
                ),
            )
            pages += 1
            issues.extend(_search_page_issues(payload))
            next_page_token, stop_reason = _next_search_page(payload)
            if stop_reason == "is_last":
                stopped_on_is_last = True
                break
            if stop_reason == "no_next_token":
                stopped_without_next_token = True
                break

        return JiraSearchResult(
            issues=tuple(issues),
            diagnostics=JiraSearchDiagnostics(
                pages=pages,
                stopped_on_is_last=stopped_on_is_last,
                stopped_without_next_token=stopped_without_next_token,
            ),
        )

    def _fetch_comments(
        self,
        client: httpx.Client,
        issue_id_or_key: str,
        *,
        max_results: int,
    ) -> tuple[dict[str, Any], ...]:
        comments: list[dict[str, Any]] = []
        start_at = 0
        path = f"/rest/api/3/issue/{quote(issue_id_or_key, safe='')}/comment"

        while True:
            payload = self.http.request_json(
                client,
                "GET",
                path,
                params={"startAt": start_at, "maxResults": max_results},
            )
            if "comments" not in payload:
                raise AtlassianClientError(
                    "Jira comments response did not include a comments list."
                )
            raw_comments = payload["comments"]
            if not isinstance(raw_comments, list):
                raise AtlassianClientError(
                    "Jira comments response did not include a comments list."
                )
            page_comments = _comment_objects(raw_comments)
            comments.extend(page_comments)

            total = payload.get("total")
            next_start = start_at + len(page_comments)
            if isinstance(total, int) and next_start >= total:
                break
            if not page_comments:
                break
            start_at = next_start

        return tuple(comments)

    def _with_comments_concurrently(
        self,
        issues: tuple[JiraIssue, ...],
        *,
        max_results: int,
        concurrency: int,
    ) -> tuple[JiraIssue, ...]:
        worker_count = max(1, concurrency)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            comments = tuple(
                executor.map(
                    lambda issue: self.fetch_comments(issue.key, max_results=max_results),
                    issues,
                )
            )
        return tuple(
            replace(issue, comments=issue_comments)
            for issue, issue_comments in zip(issues, comments, strict=True)
        )


def project_jql(project_key: str) -> str:
    return f"project = {_jql_string(project_key)} ORDER BY updated ASC, key ASC"


def exact_issue_jql(issue_keys: Sequence[str]) -> str:
    keys = [key for key in issue_keys if key]
    if not keys:
        raise ValueError("At least one Jira issue key is required.")
    if len(keys) == 1:
        return f"key = {_jql_string(keys[0])} ORDER BY updated ASC, key ASC"
    values = ", ".join(_jql_string(key) for key in keys)
    return f"key in ({values}) ORDER BY updated ASC, key ASC"


def ordered_jql(jql: str) -> str:
    stripped = jql.strip()
    if not stripped:
        raise ValueError("JQL must not be empty.")
    if _find_order_by(stripped) is not None:
        return stripped
    return f"{stripped} ORDER BY updated ASC, key ASC"


def updated_since_jql(jql: str, since: str, *, timezone_name: str = "UTC") -> str:
    filter_jql, order_by = _split_order_by(jql)
    return f"({filter_jql}) AND updated >= {_jql_string(_jira_date_literal(since, timezone_name))} {order_by}"


def _search_params(
    jql: str,
    *,
    fields: Sequence[str] | None,
    max_results: int,
    next_page_token: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"jql": jql, "maxResults": max_results}
    if fields:
        params["fields"] = ",".join(fields)
    if next_page_token:
        params["nextPageToken"] = next_page_token
    return params


def _search_page_issues(payload: dict[str, Any]) -> list[JiraIssue]:
    raw_issues = payload.get("issues")
    if not isinstance(raw_issues, list):
        raise AtlassianClientError("Jira search response did not include an issues list.")

    issues: list[JiraIssue] = []
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            raise AtlassianClientError("Jira search response contained a non-object issue.")
        issues.append(_normalize_issue(raw_issue))
    return issues


def _next_search_page(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    if payload.get("isLast") is True:
        return None, "is_last"
    next_token = payload.get("nextPageToken")
    if not isinstance(next_token, str) or not next_token:
        return None, "no_next_token"
    return next_token, None


def _split_order_by(jql: str) -> tuple[str, str]:
    stripped = ordered_jql(jql)
    order_by_index = _find_order_by(stripped)
    if order_by_index is None:
        raise ValueError("Ordered JQL unexpectedly lacked an ORDER BY clause.")
    filter_jql = stripped[:order_by_index].strip()
    order_by = stripped[order_by_index:].strip()
    if not filter_jql:
        raise ValueError("JQL must include a filter before ORDER BY.")
    return filter_jql, order_by


def _find_order_by(jql: str) -> int | None:
    quote: str | None = None
    index = 0
    while index < len(jql):
        char = jql[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if match := _ORDER_BY_RE.match(jql, index):
            return match.start()
        index += 1
    return None


def _jira_date_literal(value: str, timezone_name: str) -> str:
    stripped = value.strip()
    if _JIRA_DATE_LITERAL_RE.fullmatch(stripped):
        return stripped

    normalized = stripped.removesuffix("Z") + "+00:00" if stripped.endswith("Z") else stripped
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(
            "--since must be an ISO timestamp or Jira date literal like '2026-07-01 18:46'."
        ) from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        active_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Jira user timeZone is not recognized: {timezone_name}") from error

    local = parsed.astimezone(active_timezone).replace(second=0, microsecond=0)
    return local.strftime("%Y-%m-%d %H:%M")


def _jql_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _normalize_issue(raw_issue: dict[str, Any]) -> JiraIssue:
    issue_id = raw_issue.get("id")
    key = raw_issue.get("key")
    fields = raw_issue.get("fields")
    updated = fields.get("updated") if isinstance(fields, dict) else None

    if not isinstance(issue_id, str) or not isinstance(key, str):
        raise AtlassianClientError("Jira issue response lacked string id/key values.")
    if updated is not None and not isinstance(updated, str):
        raise AtlassianClientError("Jira issue response had a non-string updated value.")

    return JiraIssue(id=issue_id, key=key, updated=updated, raw=raw_issue)


def _comment_objects(raw_comments: list[Any]) -> tuple[dict[str, Any], ...]:
    comments: list[dict[str, Any]] = []
    for raw_comment in raw_comments:
        if not isinstance(raw_comment, dict):
            raise AtlassianClientError("Jira comments response contained a non-object comment.")
        comments.append(raw_comment)
    return tuple(comments)
