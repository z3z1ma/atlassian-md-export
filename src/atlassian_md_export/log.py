"""Structured logging setup with conservative secret redaction."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from typing import Any

SECRET_KEY_HINTS = ("token", "secret", "password", "authorization", "cookie")
SECRET_ENV_VARS = ("JIRA_API_TOKEN", "CONFLUENCE_API_TOKEN", "ATLASSIAN_API_TOKEN")
_AUTH_HEADER_RE = re.compile(r"(?i)(authorization:\s*)(basic|bearer)\s+[^\s,;]+")


class RedactingTextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.msg = redact(record.getMessage())
        record.args = ()
        return super().format(record)


class JsonLogFormatter(logging.Formatter):
    _standard_attrs = set(logging.makeLogRecord({}).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in self._standard_attrs and key not in {"message", "asctime"}:
                payload[key] = redact(value, key=key)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def configure_logging(verbose: bool = False, json_logs: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(RedactingTextFormatter("%(levelname)s %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)


def redact(value: Any, key: str | None = None) -> Any:
    if key and any(hint in key.lower() for hint in SECRET_KEY_HINTS):
        return "[REDACTED]"

    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, Mapping):
        return {item_key: redact(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def _redact_string(value: str) -> str:
    redacted = _AUTH_HEADER_RE.sub(r"\1[REDACTED]", value)
    for env_name in SECRET_ENV_VARS:
        secret = os.environ.get(env_name)
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted
