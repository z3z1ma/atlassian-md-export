"""Helpers for reading exporter-owned JSON payload fragments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {str(key): item_value for key, item_value in item.items()}
        for item in value
        if isinstance(item, Mapping)
    ]


def confluence_payload_space_key(payload: Mapping[str, Any]) -> str | None:
    normalized = payload.get("normalized_page")
    if isinstance(normalized, Mapping):
        normalized_space_key = normalized.get("space_key")
        if isinstance(normalized_space_key, str) and normalized_space_key:
            return normalized_space_key
    raw_page = payload.get("raw_page")
    if isinstance(raw_page, Mapping):
        raw_space_key = raw_page.get("spaceKey")
        if isinstance(raw_space_key, str) and raw_space_key:
            return raw_space_key
        raw_space = raw_page.get("space")
        if isinstance(raw_space, Mapping):
            embedded_space_key = raw_space.get("key")
            if isinstance(embedded_space_key, str) and embedded_space_key:
                return embedded_space_key
    return None


def confluence_payload_url(payload: Mapping[str, Any]) -> str | None:
    normalized = payload.get("normalized_page")
    if isinstance(normalized, Mapping):
        normalized_url = normalized.get("url")
        if isinstance(normalized_url, str) and normalized_url:
            return normalized_url
    return None
