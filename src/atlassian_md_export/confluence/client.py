"""Confluence Cloud REST API client."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import TypeVar
from urllib.parse import quote
from urllib.parse import urlparse

import httpx

from atlassian_md_export.client import AtlassianClientError
from atlassian_md_export.client import AtlassianHttpClient

V2_SPACE_PATH = "/wiki/api/v2/spaces"
V1_SEARCH_PATH = "/wiki/rest/api/search"
DEFAULT_BODY_FORMAT = "atlas_doc_format"
DEFAULT_PAGE_SIZE = 100
_ORDER_BY_RE = re.compile(r"\border\s+by\b", re.IGNORECASE)
_CONFLUENCE_DATE_LITERAL_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}(?: \d{2}:\d{2})?$")


@dataclass(frozen=True)
class ConfluenceSpace:
    id: str
    key: str
    name: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class ConfluencePage:
    id: str
    title: str
    status: str | None
    space_id: str | None
    space_key: str | None
    parent_id: str | None
    updated_at: str | None
    version: int | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class ConfluenceClient:
    http: AtlassianHttpClient
    body_format: str = DEFAULT_BODY_FORMAT

    def resolve_space(self, space_key: str) -> ConfluenceSpace:
        with self.http.build_client() as client:
            spaces = self._list_spaces(client, key=space_key)
        for space in spaces:
            if space.key == space_key:
                return space
        raise AtlassianClientError(f"Confluence space was not found: {space_key}")

    def list_spaces(self, *, limit: int = DEFAULT_PAGE_SIZE) -> tuple[ConfluenceSpace, ...]:
        with self.http.build_client() as client:
            return self._list_spaces(client, limit=limit)

    def fetch_space_by_id(self, space_id: str) -> ConfluenceSpace:
        with self.http.build_client() as client:
            return self._fetch_space_by_id(client, space_id)

    def fetch_page(
        self,
        page_id: str,
        *,
        body_format: str | None = None,
    ) -> ConfluencePage:
        with self.http.build_client() as client:
            return self._fetch_page(client, page_id, body_format=body_format, space_key_by_id={})

    def fetch_space_pages(
        self,
        space_key: str,
        *,
        body_format: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[ConfluencePage, ...]:
        with self.http.build_client() as client:
            space = self._resolve_space(client, space_key)
            summaries = self._paginate_v2(
                client,
                f"/wiki/api/v2/spaces/{quote(space.id, safe='')}/pages",
                params={"limit": limit},
                endpoint="Confluence space pages",
                validator=_page_summary,
            )
            space_key_by_id = {space.id: space.key}
            return tuple(
                self._fetch_page(
                    client,
                    summary["id"],
                    body_format=body_format,
                    space_key_by_id=space_key_by_id,
                )
                for summary in summaries
            )

    def search_pages(
        self,
        cql: str,
        *,
        body_format: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[ConfluencePage, ...]:
        with self.http.build_client() as client:
            page_ids = self._search_page_ids(client, cql, limit=limit)
            space_key_by_id: dict[str, str] = {}
            return tuple(
                self._fetch_page(
                    client,
                    page_id,
                    body_format=body_format,
                    space_key_by_id=space_key_by_id,
                )
                for page_id in page_ids
            )

    def fetch_ancestor_subtree(
        self,
        page_id: str,
        *,
        body_format: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[ConfluencePage, ...]:
        with self.http.build_client() as client:
            space_key_by_id: dict[str, str] = {}
            root = self._fetch_page(
                client,
                page_id,
                body_format=body_format,
                space_key_by_id=space_key_by_id,
            )
            descendants = self._paginate_v2(
                client,
                f"/wiki/api/v2/pages/{quote(page_id, safe='')}/descendants",
                params={"limit": limit},
                endpoint="Confluence page descendants",
                validator=_descendant_summary,
            )
            descendant_pages = tuple(
                self._fetch_page(
                    client,
                    descendant["id"],
                    body_format=body_format,
                    space_key_by_id=space_key_by_id,
                )
                for descendant in descendants
                if descendant["type"] == "page"
            )
            return (root, *descendant_pages)

    def fetch_footer_comments(
        self,
        page_id: str,
        *,
        body_format: str | None = None,
        status: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[dict[str, Any], ...]:
        params: dict[str, Any] = {
            "body-format": body_format or self.body_format,
            "limit": limit,
        }
        if status:
            params["status"] = status
        return self._fetch_page_results(
            f"/wiki/api/v2/pages/{quote(page_id, safe='')}/footer-comments",
            params=params,
            endpoint="Confluence footer comments",
            validator=_comment_object,
        )

    def fetch_inline_comments(
        self,
        page_id: str,
        *,
        body_format: str | None = None,
        status: str | None = None,
        resolution_status: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[dict[str, Any], ...]:
        params: dict[str, Any] = {
            "body-format": body_format or self.body_format,
            "limit": limit,
        }
        if status:
            params["status"] = status
        if resolution_status:
            params["resolution-status"] = resolution_status
        return self._fetch_page_results(
            f"/wiki/api/v2/pages/{quote(page_id, safe='')}/inline-comments",
            params=params,
            endpoint="Confluence inline comments",
            validator=_comment_object,
        )

    def fetch_labels(
        self,
        page_id: str,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[dict[str, Any], ...]:
        return self._fetch_page_results(
            f"/wiki/api/v2/pages/{quote(page_id, safe='')}/labels",
            params={"limit": limit},
            endpoint="Confluence page labels",
            validator=_label_object,
        )

    def fetch_ancestors(
        self,
        page_id: str,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[dict[str, Any], ...]:
        return self._fetch_page_results(
            f"/wiki/api/v2/pages/{quote(page_id, safe='')}/ancestors",
            params={"limit": limit},
            endpoint="Confluence page ancestors",
            validator=_page_summary,
        )

    def fetch_descendants(
        self,
        page_id: str,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[dict[str, Any], ...]:
        return self._fetch_page_results(
            f"/wiki/api/v2/pages/{quote(page_id, safe='')}/descendants",
            params={"limit": limit},
            endpoint="Confluence page descendants",
            validator=_descendant_summary,
        )

    def fetch_attachment_metadata(
        self,
        page_id: str,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[dict[str, Any], ...]:
        return self._fetch_page_results(
            f"/wiki/api/v2/pages/{quote(page_id, safe='')}/attachments",
            params={"limit": limit},
            endpoint="Confluence page attachments",
            validator=_attachment_object,
        )

    def _resolve_space(self, client: httpx.Client, space_key: str) -> ConfluenceSpace:
        for space in self._list_spaces(client, key=space_key):
            if space.key == space_key:
                return space
        raise AtlassianClientError(f"Confluence space was not found: {space_key}")

    def _fetch_space_by_id(self, client: httpx.Client, space_id: str) -> ConfluenceSpace:
        payload = self.http.request_json(
            client,
            "GET",
            f"/wiki/api/v2/spaces/{quote(space_id, safe='')}",
        )
        return _space_object(payload, "Confluence space")

    def _list_spaces(
        self,
        client: httpx.Client,
        *,
        key: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[ConfluenceSpace, ...]:
        params: dict[str, Any] = {"limit": limit}
        if key:
            params["keys"] = key
        return self._paginate_v2(
            client,
            V2_SPACE_PATH,
            params=params,
            endpoint="Confluence spaces",
            validator=_space_object,
        )

    def _fetch_page(
        self,
        client: httpx.Client,
        page_id: str,
        *,
        body_format: str | None,
        space_key_by_id: dict[str, str] | None = None,
    ) -> ConfluencePage:
        payload = self.http.request_json(
            client,
            "GET",
            f"/wiki/api/v2/pages/{quote(page_id, safe='')}",
            params={"body-format": body_format or self.body_format},
        )
        page = _page_object(payload)
        if page.space_key or not page.space_id:
            return page
        space_key = _cached_space_key(
            client,
            page.space_id,
            cache=space_key_by_id,
            fetch=self._fetch_space_by_id,
        )
        return ConfluencePage(
            id=page.id,
            title=page.title,
            status=page.status,
            space_id=page.space_id,
            space_key=space_key,
            parent_id=page.parent_id,
            updated_at=page.updated_at,
            version=page.version,
            raw=page.raw,
        )

    def _fetch_page_results(
        self,
        path: str,
        *,
        params: dict[str, Any],
        endpoint: str,
        validator: _Validator[dict[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        with self.http.build_client() as client:
            return self._paginate_v2(
                client,
                path,
                params=params,
                endpoint=endpoint,
                validator=validator,
            )

    def _paginate_v2(
        self,
        client: httpx.Client,
        path: str,
        *,
        params: dict[str, Any],
        endpoint: str,
        validator: _Validator[_T],
    ) -> tuple[_T, ...]:
        results: list[_T] = []
        next_path: str | None = path
        next_params: dict[str, Any] | None = dict(params)

        while next_path is not None:
            payload, headers = self.http.request_json_response(
                client,
                "GET",
                next_path,
                params=next_params,
            )
            raw_results = _required_results(payload, endpoint)
            results.extend(validator(raw_result, endpoint) for raw_result in raw_results)
            next_path = _next_link(
                headers,
                base_url=self.http.base_url,
                endpoint=endpoint,
            )
            next_params = None

        return tuple(results)

    def _search_page_ids(
        self,
        client: httpx.Client,
        cql: str,
        *,
        limit: int,
    ) -> tuple[str, ...]:
        page_ids: list[str] = []
        next_path: str | None = V1_SEARCH_PATH
        params: dict[str, Any] | None = {"cql": cql, "limit": limit}

        while next_path is not None:
            payload = self.http.request_json(client, "GET", next_path, params=params)
            raw_results = _required_results(payload, "Confluence CQL search")
            page_ids.extend(
                _cql_result_page_id(raw_result, "Confluence CQL search")
                for raw_result in raw_results
            )
            next_path, params = _next_cql_target(
                payload,
                base_url=self.http.base_url,
                endpoint="Confluence CQL search",
            )

        return tuple(page_ids)


_T = TypeVar("_T")
_Validator = Callable[[Any, str], _T]


def confluence_updated_since_cql(cql: str, since: str) -> str:
    filter_cql, order_by = _split_order_by(cql)
    updated_filter = f'lastmodified >= "{confluence_cql_date_literal(since)}"'
    if order_by:
        return f"({filter_cql}) AND {updated_filter} {order_by}"
    return f"({filter_cql}) AND {updated_filter}"


def confluence_cql_date_literal(value: str) -> str:
    stripped = value.strip()
    if _CONFLUENCE_DATE_LITERAL_RE.fullmatch(stripped):
        return stripped

    normalized = stripped.removesuffix("Z") + "+00:00" if stripped.endswith("Z") else stripped
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(
            "--since must be an ISO timestamp or Confluence date literal like "
            "'2026-07-01 18:46'."
        ) from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    utc_value = parsed.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return utc_value.strftime("%Y-%m-%d %H:%M")


def _split_order_by(cql: str) -> tuple[str, str]:
    stripped = cql.strip()
    if not stripped:
        raise ValueError("CQL must not be empty.")
    order_by_index = _find_order_by(stripped)
    if order_by_index is None:
        return stripped, ""
    filter_cql = stripped[:order_by_index].strip()
    order_by = stripped[order_by_index:].strip()
    if not filter_cql:
        raise ValueError("CQL must include a filter before ORDER BY.")
    return filter_cql, order_by


def _find_order_by(cql: str) -> int | None:
    quote: str | None = None
    index = 0
    while index < len(cql):
        char = cql[index]
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
        if match := _ORDER_BY_RE.match(cql, index):
            return match.start()
        index += 1
    return None


def _required_results(payload: dict[str, Any], endpoint: str) -> list[Any]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise AtlassianClientError(f"{endpoint} response did not include a results list.")
    return raw_results


def _space_object(value: Any, endpoint: str) -> ConfluenceSpace:
    raw = _dict_payload(value, endpoint, "space")
    space_id = raw.get("id")
    key = raw.get("key")
    name = raw.get("name")
    if not isinstance(space_id, str) or not isinstance(key, str):
        raise AtlassianClientError(f"{endpoint} response contained a space without id/key.")
    if name is not None and not isinstance(name, str):
        raise AtlassianClientError(f"{endpoint} response contained a non-string space name.")
    return ConfluenceSpace(id=space_id, key=key, name=name, raw=raw)


def _cached_space_key(
    client: httpx.Client,
    space_id: str,
    *,
    cache: dict[str, str] | None,
    fetch: Callable[[httpx.Client, str], ConfluenceSpace],
) -> str:
    if cache is not None and space_id in cache:
        return cache[space_id]
    space = fetch(client, space_id)
    if cache is not None:
        cache[space_id] = space.key
    return space.key


def _page_object(value: Any, endpoint: str = "Confluence page") -> ConfluencePage:
    raw = _dict_payload(value, endpoint, "page")
    page_id = raw.get("id")
    title = raw.get("title")
    if not isinstance(page_id, str) or not isinstance(title, str):
        raise AtlassianClientError(f"{endpoint} response contained a page without id/title.")

    status = _optional_string(raw.get("status"), endpoint, "status")
    space_id = _optional_string(raw.get("spaceId"), endpoint, "spaceId")
    space_key = _optional_string(raw.get("spaceKey"), endpoint, "spaceKey")
    parent_id = _optional_string(raw.get("parentId"), endpoint, "parentId")
    version = _version_number(raw.get("version"), endpoint)
    return ConfluencePage(
        id=page_id,
        title=title,
        status=status,
        space_id=space_id,
        space_key=space_key,
        parent_id=parent_id,
        updated_at=_updated_at(raw, endpoint),
        version=version,
        raw=raw,
    )


def _page_summary(value: Any, endpoint: str) -> dict[str, Any]:
    raw = _dict_payload(value, endpoint, "page")
    if not isinstance(raw.get("id"), str):
        raise AtlassianClientError(f"{endpoint} response contained a page without id.")
    title = raw.get("title")
    if title is not None and not isinstance(title, str):
        raise AtlassianClientError(f"{endpoint} response contained a page with non-string title.")
    return raw


def _descendant_summary(value: Any, endpoint: str) -> dict[str, Any]:
    raw = _page_summary(value, endpoint)
    content_type = raw.get("type")
    if not isinstance(content_type, str):
        raise AtlassianClientError(f"{endpoint} response contained a descendant without type.")
    return raw


def _comment_object(value: Any, endpoint: str) -> dict[str, Any]:
    raw = _dict_payload(value, endpoint, "comment")
    if not isinstance(raw.get("id"), str):
        raise AtlassianClientError(f"{endpoint} response contained a comment without id.")
    return raw


def _label_object(value: Any, endpoint: str) -> dict[str, Any]:
    raw = _dict_payload(value, endpoint, "label")
    if not isinstance(raw.get("id"), str) or not isinstance(raw.get("name"), str):
        raise AtlassianClientError(f"{endpoint} response contained a label without id/name.")
    return raw


def _attachment_object(value: Any, endpoint: str) -> dict[str, Any]:
    raw = _dict_payload(value, endpoint, "attachment")
    if not isinstance(raw.get("id"), str) or not isinstance(raw.get("title"), str):
        raise AtlassianClientError(f"{endpoint} response contained an attachment without id/title.")
    return raw


def _cql_result_page_id(value: Any, endpoint: str) -> str:
    raw = _dict_payload(value, endpoint, "result")
    content = raw.get("content")
    if not isinstance(content, dict):
        raise AtlassianClientError(f"{endpoint} response contained a result without content.")
    content_type = content.get("type")
    if content_type != "page":
        raise AtlassianClientError(f"{endpoint} response contained a non-page result.")
    page_id = content.get("id")
    title = content.get("title")
    if not isinstance(page_id, str) or not isinstance(title, str):
        raise AtlassianClientError(f"{endpoint} response contained a page without id/title.")
    return page_id


def _dict_payload(value: Any, endpoint: str, noun: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AtlassianClientError(f"{endpoint} response contained a non-object {noun}.")
    return value


def _optional_string(value: Any, endpoint: str, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AtlassianClientError(
            f"Confluence page response had a non-string {field_name} value for {endpoint}."
        )
    return value


def _version_number(value: Any, endpoint: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AtlassianClientError(f"{endpoint} response had a non-object version value.")
    number = value.get("number")
    if number is None:
        return None
    if not isinstance(number, int):
        raise AtlassianClientError(f"{endpoint} response had a non-integer version number.")
    return number


def _updated_at(raw: dict[str, Any], endpoint: str) -> str | None:
    updated_at = raw.get("updatedAt")
    if isinstance(updated_at, str):
        return updated_at
    if updated_at is not None:
        raise AtlassianClientError(f"{endpoint} response had a non-string updatedAt value.")

    version = raw.get("version")
    if isinstance(version, dict):
        created_at = version.get("createdAt")
        if isinstance(created_at, str):
            return created_at
        if created_at is not None:
            raise AtlassianClientError(
                f"{endpoint} response had a non-string version.createdAt value."
            )
    return None


def _next_link(
    headers: httpx.Headers,
    *,
    base_url: str,
    endpoint: str,
) -> str | None:
    link_header = headers.get("Link")
    if not link_header:
        return None

    for link_value in link_header.split(","):
        parts = [part.strip() for part in link_value.split(";")]
        if not parts or not parts[0].startswith("<") or not parts[0].endswith(">"):
            continue
        rels = {part.lower().replace('"', "") for part in parts[1:]}
        if "rel=next" in rels:
            return _safe_next_path(parts[0][1:-1], base_url=base_url, endpoint=endpoint)
    return None


def _next_cql_target(
    payload: dict[str, Any],
    *,
    base_url: str,
    endpoint: str,
) -> tuple[str | None, dict[str, Any] | None]:
    links = payload.get("_links")
    if isinstance(links, dict):
        next_link = links.get("next")
        if isinstance(next_link, str) and next_link:
            return _safe_next_path(next_link, base_url=base_url, endpoint=endpoint), None

    next_link = payload.get("next")
    if isinstance(next_link, str) and next_link:
        return _safe_next_path(next_link, base_url=base_url, endpoint=endpoint), None

    next_cursor = payload.get("nextCursor")
    if isinstance(next_cursor, str) and next_cursor:
        return V1_SEARCH_PATH, {"cursor": next_cursor}

    return None, None


def _safe_next_path(value: str, *, base_url: str, endpoint: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise AtlassianClientError(f"{endpoint} pagination next link was empty.")

    parsed = urlparse(stripped)
    if parsed.netloc and not parsed.scheme:
        raise AtlassianClientError(
            f"{endpoint} pagination next link is scheme-relative and unsafe."
        )
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        raise AtlassianClientError(
            f"{endpoint} pagination next link has unsupported scheme: {parsed.scheme}."
        )
    if parsed.scheme and not parsed.netloc:
        raise AtlassianClientError(
            f"{endpoint} pagination next link is absolute but lacks a host."
        )

    if parsed.scheme:
        site = urlparse(base_url)
        if not _same_origin(parsed, site):
            raise AtlassianClientError(
                f"{endpoint} pagination next link origin does not match Confluence site."
            )
        path = parsed.path or "/"
        return _path_with_query(path, parsed.query)

    if not parsed.path.startswith("/"):
        raise AtlassianClientError(
            f"{endpoint} pagination next link must be an absolute path."
        )
    return _path_with_query(parsed.path, parsed.query)


def _path_with_query(path: str, query: str) -> str:
    return f"{path}?{query}" if query else path


def _same_origin(first: Any, second: Any) -> bool:
    if first.scheme.lower() != second.scheme.lower():
        return False
    if first.hostname is None or second.hostname is None:
        return False
    return first.hostname.lower() == second.hostname.lower() and _origin_port(first) == _origin_port(
        second
    )


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
