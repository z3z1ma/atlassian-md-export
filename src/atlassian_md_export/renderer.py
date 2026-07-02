"""Repository-owned Atlassian Document Format to Markdown renderer."""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
import json
import re
from typing import Any

_MARK_ORDER = {
    "code": 0,
    "strong": 10,
    "em": 20,
    "underline": 30,
    "strike": 40,
    "link": 50,
}
_TASK_ITEM_MARKERS = {
    "TODO": " ",
    "DONE": "x",
}
_TEXT_ESCAPE_RE = re.compile(r"([\\`*_{}\[\]<>#~])")
_BACKTICK_RE = re.compile(r"`+")


def escape_markdown_text(value: object) -> str:
    """Escape literal inline text so Markdown metacharacters stay literal."""

    return _TEXT_ESCAPE_RE.sub(r"\\\1", str(value))


def escape_markdown_table_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", "<br>")


class AdfMarkdownRenderer:
    def __init__(self, include_raw_adf_on_unknown_nodes: bool = True) -> None:
        self.include_raw_adf_on_unknown_nodes = include_raw_adf_on_unknown_nodes

    def render(self, adf: Mapping[str, Any] | None) -> str:
        if not adf:
            return ""
        if adf.get("type") == "doc":
            return self._render_blocks(_content(adf)).strip()
        return self._unknown_node(adf)

    def _render_blocks(self, nodes: Iterable[Mapping[str, Any]]) -> str:
        rendered = [self._render_block(node) for node in nodes]
        return "\n\n".join(part for part in rendered if part).strip()

    def _render_block(self, node: Mapping[str, Any]) -> str:
        node_type = node.get("type")
        if node_type == "paragraph":
            return self._render_inlines(_content(node)).strip()
        if node_type == "heading":
            return self._render_heading(node)
        if node_type == "bulletList":
            return self._render_list(node, ordered=False)
        if node_type == "orderedList":
            return self._render_list(node, ordered=True)
        if node_type == "taskList":
            return self._render_task_list(node)
        if node_type == "taskItem":
            return self._render_task_item(node, indent=0)
        if node_type == "codeBlock":
            return self._render_code_block(node)
        if node_type == "blockquote":
            return self._render_blockquote(node)
        if node_type == "panel":
            return self._render_panel(node)
        if node_type == "rule":
            return "---"
        if node_type == "table":
            return self._render_table(node)
        if node_type in {"mediaSingle", "mediaGroup"}:
            return self._render_media_container(node)
        if node_type == "media":
            return self._render_media(node)
        return self._unknown_node(node)

    def _render_heading(self, node: Mapping[str, Any]) -> str:
        attrs = _attrs(node)
        raw_level = attrs.get("level", 1)
        level = raw_level if isinstance(raw_level, int) else 1
        level = min(max(level, 1), 6)
        text = self._render_inlines(_content(node)).strip()
        return f"{'#' * level} {text}".rstrip()

    def _render_list(self, node: Mapping[str, Any], *, ordered: bool, indent: int = 0) -> str:
        attrs = _attrs(node)
        raw_start = attrs.get("order", 1)
        start = raw_start if isinstance(raw_start, int) else 1
        lines: list[str] = []
        for index, item in enumerate(_content(node)):
            if item.get("type") != "listItem":
                lines.append(self._indent(self._unknown_node(item), indent))
                continue

            marker = f"{start + index}. " if ordered else "- "
            prefix = " " * indent + marker
            continuation = " " * len(prefix)
            item_lines = self._render_list_item(item, indent + 2).splitlines()
            if not item_lines:
                lines.append(prefix.rstrip())
                continue
            lines.append(prefix + item_lines[0])
            lines.extend(continuation + line if line else "" for line in item_lines[1:])
        return "\n".join(lines)

    def _render_list_item(self, node: Mapping[str, Any], indent: int) -> str:
        parts: list[str] = []
        for child in _content(node):
            child_type = child.get("type")
            if child_type == "paragraph":
                parts.append(self._render_inlines(_content(child)).strip())
            elif child_type == "bulletList":
                parts.append(self._render_list(child, ordered=False, indent=indent))
            elif child_type == "orderedList":
                parts.append(self._render_list(child, ordered=True, indent=indent))
            else:
                parts.append(self._render_block(child))
        return "\n".join(part for part in parts if part)

    def _render_task_list(self, node: Mapping[str, Any], indent: int = 0) -> str:
        content = _required_mapping_content(node)
        if content is None or not content:
            return self._indent(self._unknown_node(node), indent)

        lines: list[str] = []
        for child in content:
            child_type = child.get("type")
            if child_type == "taskItem":
                rendered = self._render_task_item(child, indent)
            elif child_type == "taskList":
                rendered = self._render_task_list(child, indent + 2)
            else:
                rendered = self._indent(self._unknown_node(child), indent)
            if rendered:
                lines.append(rendered)
        return "\n".join(lines)

    def _render_task_item(self, node: Mapping[str, Any], indent: int) -> str:
        marker = _task_item_marker(node)
        content = _optional_mapping_content(node)
        if marker is None or content is None:
            return self._indent(self._unknown_node(node), indent)

        prefix = " " * indent + f"- [{marker}] "
        continuation = " " * len(prefix)
        lines: list[str] = []
        inline_nodes: list[Mapping[str, Any]] = []

        def append_inline_nodes() -> None:
            nonlocal inline_nodes
            if not inline_nodes:
                return
            rendered = self._render_inlines(inline_nodes).strip()
            inline_nodes = []
            if not rendered:
                return
            inline_lines = rendered.splitlines()
            if not lines:
                lines.append(prefix + inline_lines[0])
                inline_lines = inline_lines[1:]
            lines.extend(continuation + line if line else "" for line in inline_lines)

        for child in content:
            if child.get("type") == "taskList":
                append_inline_nodes()
                if not lines:
                    lines.append(prefix.rstrip())
                nested = self._render_task_list(child, indent + 2)
                lines.extend(nested.splitlines())
            else:
                inline_nodes.append(child)

        append_inline_nodes()
        if not lines:
            return prefix.rstrip()
        return "\n".join(lines)

    def _render_code_block(self, node: Mapping[str, Any]) -> str:
        attrs = _attrs(node)
        language = attrs.get("language")
        info = str(language).strip() if language is not None else ""
        code = "".join(_text_content(child) for child in _content(node))
        return _fenced_block(info, code.rstrip("\n"))

    def _render_blockquote(self, node: Mapping[str, Any]) -> str:
        body = self._render_blocks(_content(node))
        return "\n".join(f"> {line}" if line else ">" for line in body.splitlines())

    def _render_panel(self, node: Mapping[str, Any]) -> str:
        panel_type = str(_attrs(node).get("panelType", "info")).upper()
        body = self._render_blocks(_content(node))
        lines = [f"> [!{escape_markdown_text(panel_type)}]"]
        lines.extend(f"> {line}" if line else ">" for line in body.splitlines())
        return "\n".join(lines)

    def _render_table(self, node: Mapping[str, Any]) -> str:
        rows = [
            [self._render_table_cell(cell) for cell in _content(row)]
            for row in _content(node)
            if row.get("type") == "tableRow"
        ]
        if not rows:
            return ""

        column_count = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
        header = normalized_rows[0]
        separator = ["---"] * column_count
        body_rows = normalized_rows[1:]
        table_lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        table_lines.extend("| " + " | ".join(row) + " |" for row in body_rows)
        return "\n".join(table_lines)

    def _render_table_cell(self, node: Mapping[str, Any]) -> str:
        rendered = self._render_blocks(_content(node))
        return escape_markdown_table_cell(rendered.strip())

    def _render_media_container(self, node: Mapping[str, Any]) -> str:
        rendered = [
            self._render_media(child) for child in _content(node) if child.get("type") == "media"
        ]
        if rendered:
            return "\n".join(rendered)
        return self._unknown_node(node)

    def _render_media(self, node: Mapping[str, Any]) -> str:
        attrs = _attrs(node)
        parts = _named_attrs(
            attrs,
            ("id", "collection", "alt", "fileName", "filename", "type"),
        )
        detail = " ".join(parts) if parts else "no metadata"
        return f"[Media: {escape_markdown_text(detail)}]"

    def _render_inlines(self, nodes: Iterable[Mapping[str, Any]]) -> str:
        return "".join(self._render_inline(node) for node in nodes)

    def _render_inline(self, node: Mapping[str, Any]) -> str:
        node_type = node.get("type")
        if node_type == "text":
            return self._render_text(node)
        if node_type == "hardBreak":
            return "  \n"
        if node_type == "mention":
            return self._render_mention(node)
        if node_type == "date":
            return self._render_date(node)
        if node_type == "emoji":
            return self._render_emoji(node)
        if node_type == "inlineCard":
            return self._render_inline_card(node)
        if node_type == "media":
            return self._render_media(node)
        return self._unknown_node(node)

    def _render_text(self, node: Mapping[str, Any]) -> str:
        text = str(node.get("text", ""))
        marks = sorted(_marks(node), key=_mark_sort_key)
        has_code = any(mark.get("type") == "code" for mark in marks)
        rendered = _code_span(text) if has_code else escape_markdown_text(text)

        for mark in marks:
            mark_type = mark.get("type")
            if mark_type == "code":
                continue
            if mark_type == "strong":
                rendered = f"**{rendered}**"
            elif mark_type == "em":
                rendered = f"_{rendered}_"
            elif mark_type == "underline":
                rendered = f"<u>{rendered}</u>"
            elif mark_type == "strike":
                rendered = f"~~{rendered}~~"
            elif mark_type == "link":
                rendered = self._apply_link_mark(rendered, mark)
        return rendered

    def _apply_link_mark(self, rendered: str, mark: Mapping[str, Any]) -> str:
        attrs = _attrs(mark)
        href = attrs.get("href")
        if not isinstance(href, str) or not href:
            return f"{rendered} [Unsupported ADF mark: link without href]"
        title = attrs.get("title")
        if isinstance(title, str) and title:
            escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
            return f'[{rendered}]({_escape_url(href)} "{escaped_title}")'
        return f"[{rendered}]({_escape_url(href)})"

    def _render_mention(self, node: Mapping[str, Any]) -> str:
        attrs = _attrs(node)
        text = attrs.get("text") or attrs.get("displayName")
        if isinstance(text, str) and text:
            display = text if text.startswith("@") else f"@{text}"
            return escape_markdown_text(display)
        mention_id = attrs.get("id") or attrs.get("accountId")
        if isinstance(mention_id, str) and mention_id:
            return f"[Mention: {escape_markdown_text(mention_id)}]"
        return "[Mention]"

    def _render_date(self, node: Mapping[str, Any]) -> str:
        attrs = _attrs(node)
        timestamp = attrs.get("timestamp")
        date_value = _date_from_timestamp(timestamp)
        if date_value is None:
            raw_date = attrs.get("date")
            date_value = raw_date if isinstance(raw_date, str) and raw_date else None
        return escape_markdown_text(date_value or "[Date]")

    def _render_emoji(self, node: Mapping[str, Any]) -> str:
        attrs = _attrs(node)
        for key in ("text", "shortName", "id"):
            value = attrs.get(key)
            if isinstance(value, str) and value:
                return escape_markdown_text(value)
        return "[Emoji]"

    def _render_inline_card(self, node: Mapping[str, Any]) -> str:
        url = _attrs(node).get("url")
        if isinstance(url, str) and url:
            return f"[Inline card]({_escape_url(url)})"
        return "[Inline card: no URL]"

    def _unknown_node(self, node: Mapping[str, Any]) -> str:
        node_type = node.get("type", "unknown")
        placeholder = f"[Unsupported ADF node: {escape_markdown_text(node_type)}]"
        if not self.include_raw_adf_on_unknown_nodes:
            return placeholder
        raw = json.dumps(node, ensure_ascii=False, sort_keys=True, indent=2)
        return f"{placeholder}\n\n{_fenced_block('json', raw)}"

    def _indent(self, value: str, spaces: int) -> str:
        prefix = " " * spaces
        return "\n".join(prefix + line if line else "" for line in value.splitlines())


def _attrs(node: Mapping[str, Any]) -> Mapping[str, Any]:
    attrs = node.get("attrs")
    return attrs if isinstance(attrs, Mapping) else {}


def _content(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    content = node.get("content")
    if not isinstance(content, list):
        return []
    return [child for child in content if isinstance(child, Mapping)]


def _required_mapping_content(node: Mapping[str, Any]) -> list[Mapping[str, Any]] | None:
    content = node.get("content")
    if not isinstance(content, list):
        return None

    result: list[Mapping[str, Any]] = []
    for child in content:
        if not isinstance(child, Mapping):
            return None
        result.append(child)
    return result


def _optional_mapping_content(node: Mapping[str, Any]) -> list[Mapping[str, Any]] | None:
    if "content" not in node:
        return []
    return _required_mapping_content(node)


def _marks(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    marks = node.get("marks")
    if not isinstance(marks, list):
        return []
    return [mark for mark in marks if isinstance(mark, Mapping)]


def _mark_sort_key(mark: Mapping[str, Any]) -> tuple[int, str]:
    mark_type = str(mark.get("type", ""))
    return (_MARK_ORDER.get(mark_type, 100), mark_type)


def _text_content(node: Mapping[str, Any]) -> str:
    if node.get("type") == "text":
        return str(node.get("text", ""))
    return ""


def _task_item_marker(node: Mapping[str, Any]) -> str | None:
    state = _attrs(node).get("state")
    if not isinstance(state, str):
        return None
    return _TASK_ITEM_MARKERS.get(state)


def _code_span(value: str) -> str:
    longest = max((len(match.group(0)) for match in _BACKTICK_RE.finditer(value)), default=0)
    fence = "`" * (longest + 1)
    body = value.replace("\n", " ")
    if body.startswith("`") or body.endswith("`"):
        body = f" {body} "
    return f"{fence}{body}{fence}"


def _fenced_block(info: str, body: str) -> str:
    longest = max((len(match.group(0)) for match in _BACKTICK_RE.finditer(body)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{info}\n{body}\n{fence}"


def _escape_url(url: str) -> str:
    return url.replace("\\", "%5C").replace(" ", "%20").replace(")", "%29")


def _named_attrs(attrs: Mapping[str, Any], names: tuple[str, ...]) -> list[str]:
    parts: list[str] = []
    for name in names:
        value = attrs.get(name)
        if isinstance(value, str) and value:
            parts.append(f"{name}={value}")
    return parts


def _date_from_timestamp(value: object) -> str | None:
    if isinstance(value, int | float):
        return _date_from_epoch(float(value))
    if isinstance(value, str) and value:
        try:
            return _date_from_epoch(float(value))
        except ValueError:
            return value
    return None


def _date_from_epoch(value: float) -> str:
    seconds = value / 1000 if value > 10_000_000_000 else value
    return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
