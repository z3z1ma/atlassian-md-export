"""Attachment path and download eligibility helpers."""

from __future__ import annotations

import fnmatch
import hashlib
import re
import unicodedata
from pathlib import Path

_INVALID_FILENAME_CHARS = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]+")
_REPEATED_DASHES = re.compile(r"-{2,}")
_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_MAX_FILENAME_CHARS = 180


def sanitize_attachment_filename(filename: str | None, fallback: str = "attachment") -> str:
    """Return a deterministic single path segment safe for local attachment storage."""

    normalized = unicodedata.normalize("NFKC", filename or "")
    cleaned = _INVALID_FILENAME_CHARS.sub("-", normalized)
    cleaned = "".join(" " if character.isspace() else character for character in cleaned)
    cleaned = _REPEATED_DASHES.sub("-", cleaned).strip(" .-")
    cleaned = cleaned.lstrip(".").strip(" .-")
    if cleaned in {"", ".", ".."}:
        return fallback

    stem = cleaned.split(".", 1)[0].upper()
    if stem in _RESERVED_BASENAMES:
        cleaned = f"_{cleaned}"

    if len(cleaned) <= _MAX_FILENAME_CHARS:
        return cleaned

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    suffix = Path(cleaned).suffix
    suffix_budget = min(len(suffix), 24)
    suffix = suffix[-suffix_budget:] if suffix_budget else ""
    prefix_budget = _MAX_FILENAME_CHARS - len(digest) - len(suffix) - 1
    return f"{cleaned[:prefix_budget].rstrip(' .-')}-{digest}{suffix}"


def safe_attachment_name(attachment_id: str | None, filename: str | None) -> str:
    safe_id = sanitize_attachment_filename(attachment_id, fallback="attachment")
    safe_name = sanitize_attachment_filename(filename)
    return f"{safe_id}-{safe_name}"


def attachment_path(
    out_dir: Path,
    issue_key: str,
    attachment_id: str | None,
    filename: str | None,
) -> Path:
    return out_dir / "attachments" / issue_key / safe_attachment_name(attachment_id, filename)


def attachment_relative_path(issue_key: str, attachment_id: str | None, filename: str | None) -> str:
    return f"../attachments/{issue_key}/{safe_attachment_name(attachment_id, filename)}"


def confluence_attachment_path(
    out_dir: Path,
    page_id: str,
    attachment_id: str | None,
    filename: str | None,
) -> Path:
    safe_page_id = sanitize_attachment_filename(page_id, fallback="page")
    return out_dir / "attachments" / safe_page_id / safe_attachment_name(attachment_id, filename)


def should_download_attachment(
    *,
    filename: str | None,
    size: int | None,
    max_bytes: int | None,
    include_patterns: tuple[str, ...],
) -> bool:
    if max_bytes is not None and size is not None and size > max_bytes:
        return False
    if not include_patterns:
        return True
    candidate = filename or ""
    return any(fnmatch.fnmatchcase(candidate, pattern) for pattern in include_patterns)
