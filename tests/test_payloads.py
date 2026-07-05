from __future__ import annotations

import pytest

from atlassian_md_export.payloads import confluence_payload_space_key
from atlassian_md_export.payloads import confluence_payload_url
from atlassian_md_export.payloads import dict_list


def test_dict_list_materializes_mapping_items_and_ignores_other_values() -> None:
    assert dict_list([{"id": "1"}, [("id", "2")], "bad", {"name": "Page"}]) == [
        {"id": "1"},
        {"name": "Page"},
    ]
    assert dict_list({"id": "1"}) == []


def test_confluence_payload_metadata_prefers_normalized_page_values() -> None:
    payload = {
        "normalized_page": {
            "space_key": "DOC",
            "url": "https://example.atlassian.net/wiki/spaces/DOC/pages/123/Launch",
        },
        "raw_page": {"spaceKey": "RAW", "space": {"key": "EMBED"}},
    }

    assert confluence_payload_space_key(payload) == "DOC"
    assert confluence_payload_url(payload) == (
        "https://example.atlassian.net/wiki/spaces/DOC/pages/123/Launch"
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"raw_page": {"spaceKey": "RAW"}}, "RAW"),
        ({"raw_page": {"space": {"key": "EMBED"}}}, "EMBED"),
        ({"raw_page": {"spaceKey": ""}}, None),
        ({}, None),
    ],
)
def test_confluence_payload_space_key_falls_back_to_raw_payload(
    payload: dict[str, object],
    expected: str | None,
) -> None:
    assert confluence_payload_space_key(payload) == expected
    assert confluence_payload_url(payload) is None
