"""Shared HTTP and authentication foundations for Atlassian providers."""

from __future__ import annotations

import os
import logging
import random
import time
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any
from typing import Callable
from typing import Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, SecretStr

logger = logging.getLogger(__name__)


class MissingCredentialsError(ValueError):
    """Raised when required Jira credentials are absent."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing required environment variable(s): {', '.join(missing)}")


class AtlassianClientError(RuntimeError):
    """Base exception for Atlassian HTTP client failures."""


class AtlassianAuthenticationError(AtlassianClientError):
    """Raised when an Atlassian provider rejects credentials."""


class AtlassianHttpError(AtlassianClientError):
    """Raised for non-retryable HTTP failures."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


class AtlassianRetryError(AtlassianHttpError):
    """Raised after retryable responses exhaust the retry budget."""


class JiraCredentials(BaseModel):
    email: str
    api_token: SecretStr

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> "JiraCredentials":
        values = env if env is not None else os.environ
        missing = [name for name in ("JIRA_EMAIL", "JIRA_API_TOKEN") if not values.get(name)]
        if missing:
            raise MissingCredentialsError(missing)
        return cls(email=values["JIRA_EMAIL"], api_token=SecretStr(values["JIRA_API_TOKEN"]))


class AtlassianCredentials(Protocol):
    email: str
    api_token: SecretStr


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 30.0
    jitter_seconds: float = 0.25


@dataclass(frozen=True)
class AtlassianHttpClient:
    """Thin wrapper kept provider-neutral for future Atlassian surfaces."""

    base_url: str
    credentials: AtlassianCredentials
    provider_name: str = "Jira"
    auth_hint: str = "Check JIRA_EMAIL, JIRA_API_TOKEN, and site access."
    retry: RetryConfig = field(default_factory=RetryConfig)
    transport: httpx.BaseTransport | None = field(default=None, repr=False, compare=False)
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False, compare=False)

    def build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url.rstrip("/"),
            auth=(self.credentials.email, self.credentials.api_token.get_secret_value()),
            headers={"Accept": "application/json"},
            timeout=30.0,
            transport=self.transport,
        )

    def request_json(
        self,
        client: httpx.Client,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request JSON with bounded Atlassian rate-limit/server-error retry handling."""

        payload, _headers = self.request_json_response(client, method, path, params=params)
        return payload

    def request_json_response(
        self,
        client: httpx.Client,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], httpx.Headers]:
        """Request JSON and retain response headers for provider-specific pagination."""

        attempts = max(1, self.retry.max_attempts)
        for attempt in range(1, attempts + 1):
            response = client.request(method, path, params=params)
            log_context = _http_log_context(
                self.provider_name,
                method,
                path,
                response.status_code,
                attempt,
                attempts,
            )
            if response.status_code == 401:
                logger.error("atlassian http request failed", extra=log_context)
                raise AtlassianAuthenticationError(
                    f"{self.provider_name} authentication failed (401). {self.auth_hint}"
                )

            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if attempt == attempts:
                    logger.error("atlassian http request exhausted retries", extra=log_context)
                    raise AtlassianRetryError(
                        response.status_code,
                        _http_error_message(
                            response,
                            f"{self.provider_name} request failed after retries",
                        ),
                    )
                logger.warning("atlassian http request will retry", extra=log_context)
                self.sleep(_retry_delay(response, attempt, self.retry))
                continue

            if response.status_code >= 400:
                logger.error("atlassian http request failed", extra=log_context)
                raise AtlassianHttpError(
                    response.status_code,
                    _http_error_message(response, f"{self.provider_name} request failed"),
                )

            payload = response.json()
            if not isinstance(payload, dict):
                raise AtlassianClientError(
                    f"{self.provider_name} returned a non-object JSON response."
                )
            logger.debug("atlassian http request succeeded", extra=log_context)
            return payload, response.headers

        raise AtlassianClientError(
            f"{self.provider_name} request failed before receiving a response."
        )

    def request_bytes(
        self,
        client: httpx.Client,
        method: str,
        path_or_url: str,
    ) -> bytes:
        """Request binary content with the same bounded retry rules as JSON requests."""

        attempts = max(1, self.retry.max_attempts)
        for attempt in range(1, attempts + 1):
            response = client.request(method, path_or_url)
            log_context = _http_log_context(
                self.provider_name,
                method,
                path_or_url,
                response.status_code,
                attempt,
                attempts,
            )
            if response.status_code == 401:
                logger.error("atlassian http binary request failed", extra=log_context)
                raise AtlassianAuthenticationError(
                    f"{self.provider_name} authentication failed (401). {self.auth_hint}"
                )

            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if attempt == attempts:
                    logger.error(
                        "atlassian http binary request exhausted retries",
                        extra=log_context,
                    )
                    raise AtlassianRetryError(
                        response.status_code,
                        _http_error_message(
                            response,
                            f"{self.provider_name} binary request failed after retries",
                        ),
                    )
                logger.warning("atlassian http binary request will retry", extra=log_context)
                self.sleep(_retry_delay(response, attempt, self.retry))
                continue

            if response.status_code >= 400:
                logger.error("atlassian http binary request failed", extra=log_context)
                raise AtlassianHttpError(
                    response.status_code,
                    _http_error_message(
                        response,
                        f"{self.provider_name} binary request failed",
                    ),
                )

            logger.debug("atlassian http binary request succeeded", extra=log_context)
            return response.content

        raise AtlassianClientError(
            f"{self.provider_name} binary request failed before receiving a response."
        )


def _retry_delay(response: httpx.Response, attempt: int, retry: RetryConfig) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        parsed = _parse_retry_after(retry_after)
        if parsed is not None:
            return parsed

    exponential = float(retry.base_delay_seconds * (2 ** (attempt - 1)))
    bounded = float(min(exponential, retry.max_delay_seconds))
    if retry.jitter_seconds <= 0:
        return bounded
    return bounded + float(random.uniform(0, retry.jitter_seconds))


def _parse_retry_after(value: str) -> float | None:
    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _http_error_message(response: httpx.Response, prefix: str) -> str:
    detail = _atlassian_error_detail(response)
    if detail:
        return f"{prefix}: HTTP {response.status_code}: {detail}"
    return f"{prefix}: HTTP {response.status_code}"


def _atlassian_error_detail(response: httpx.Response) -> str | None:
    payload = _response_json_or_text(response)
    if not isinstance(payload, Mapping):
        return payload if isinstance(payload, str) else None
    return (
        _atlassian_scalar_error_detail(payload)
        or _atlassian_message_list_detail(payload)
        or _atlassian_error_map_detail(payload)
    )


def _response_json_or_text(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else None


def _atlassian_scalar_error_detail(payload: Mapping[Any, Any]) -> str | None:
    scalar_messages: list[str] = []
    for key in ("message", "detail", "title", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            scalar_messages.append(value)
    status_code = payload.get("statusCode")
    if isinstance(status_code, int | str) and scalar_messages:
        scalar_messages.append(f"statusCode={status_code}")
    if scalar_messages:
        return "; ".join(dict.fromkeys(scalar_messages))
    return None


def _atlassian_message_list_detail(payload: Mapping[Any, Any]) -> str | None:
    messages = payload.get("errorMessages")
    if isinstance(messages, list):
        text_messages = [item for item in messages if isinstance(item, str)]
        if text_messages:
            return "; ".join(text_messages)
    return None


def _atlassian_error_map_detail(payload: Mapping[Any, Any]) -> str | None:
    errors = payload.get("errors")
    if isinstance(errors, dict):
        values = [str(value) for value in errors.values()]
        if values:
            return "; ".join(values)

    return None


def _http_log_context(
    provider_name: str,
    method: str,
    path_or_url: str,
    status_code: int,
    retry_attempt: int,
    retry_count: int,
) -> dict[str, Any]:
    return {
        "provider": provider_name.lower(),
        "operation": "http_request",
        "method": method.upper(),
        "resource_path": _safe_request_path(path_or_url),
        "status_code": status_code,
        "retry_attempt": retry_attempt,
        "retry_count": retry_count,
    }


def _safe_request_path(path_or_url: str) -> str:
    parsed = urlparse(path_or_url)
    if parsed.scheme or parsed.netloc:
        return parsed.path or "/"
    path = path_or_url.split("?", 1)[0]
    return path or "/"
