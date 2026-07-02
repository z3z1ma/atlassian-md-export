from __future__ import annotations

from atlassian_md_export.renderer import AdfMarkdownRenderer


def test_renderer_supports_required_nodes_and_marks() -> None:
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Plan #1"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "bold", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": " "},
                    {"type": "text", "text": "italic", "marks": [{"type": "em"}]},
                    {"type": "text", "text": " "},
                    {"type": "text", "text": "under", "marks": [{"type": "underline"}]},
                    {"type": "text", "text": " "},
                    {"type": "text", "text": "strike", "marks": [{"type": "strike"}]},
                    {"type": "text", "text": " "},
                    {"type": "text", "text": "code", "marks": [{"type": "code"}]},
                    {"type": "text", "text": " "},
                    {
                        "type": "text",
                        "text": "link",
                        "marks": [{"type": "link", "attrs": {"href": "https://example.com/a b"}}],
                    },
                    {"type": "hardBreak"},
                    {"type": "text", "text": "next"},
                    {"type": "mention", "attrs": {"text": "Ada"}},
                    {"type": "date", "attrs": {"timestamp": "0"}},
                    {"type": "emoji", "attrs": {"shortName": ":rocket:"}},
                    {"type": "inlineCard", "attrs": {"url": "https://example.com/card"}},
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "bullet"}],
                            }
                        ],
                    }
                ],
            },
            {
                "type": "orderedList",
                "attrs": {"order": 3},
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "ordered"}],
                            }
                        ],
                    }
                ],
            },
            {
                "type": "codeBlock",
                "attrs": {"language": "python"},
                "content": [{"type": "text", "text": "print('x')\n"}],
            },
            {
                "type": "blockquote",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "quote"}]}
                ],
            },
            {
                "type": "panel",
                "attrs": {"panelType": "info"},
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "panel"}]}
                ],
            },
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableHeader",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "A|B"}]}
                                ],
                            },
                            {
                                "type": "tableHeader",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "Value"}]}
                                ],
                            },
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "one"}]}
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "two"}]}
                                ],
                            },
                        ],
                    },
                ],
            },
            {"type": "rule"},
            {
                "type": "mediaSingle",
                "content": [
                    {
                        "type": "media",
                        "attrs": {
                            "id": "media-1",
                            "collection": "jira",
                            "alt": "diagram",
                            "fileName": "diagram.png",
                            "type": "file",
                        },
                    }
                ],
            },
        ],
    }

    rendered = AdfMarkdownRenderer().render(adf)

    assert "## Plan \\#1" in rendered
    assert "**bold** _italic_ <u>under</u> ~~strike~~ `code`" in rendered
    assert "[link](https://example.com/a%20b)" in rendered
    assert "next@Ada1970-01-01:rocket:[Inline card](https://example.com/card)" in rendered
    assert "- bullet" in rendered
    assert "3. ordered" in rendered
    assert "```python\nprint('x')\n```" in rendered
    assert "> quote" in rendered
    assert "> [!INFO]\n> panel" in rendered
    assert "| A\\|B | Value |" in rendered
    assert "\n---\n\n[Media: id=media-1 collection=jira alt=diagram fileName=diagram.png type=file]" in rendered


def test_task_list_renders_checked_unchecked_and_rich_inline_content() -> None:
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "taskList",
                "attrs": {"localId": "list-1"},
                "content": [
                    {
                        "type": "taskItem",
                        "attrs": {"localId": "item-1", "state": "TODO"},
                        "content": [
                            {"type": "text", "text": "Write "},
                            {
                                "type": "text",
                                "text": "renderer",
                                "marks": [{"type": "strong"}],
                            },
                            {"type": "text", "text": " docs "},
                            {
                                "type": "text",
                                "text": "now",
                                "marks": [
                                    {
                                        "type": "link",
                                        "attrs": {"href": "https://example.com/task"},
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "type": "taskItem",
                        "attrs": {"localId": "item-2", "state": "DONE"},
                        "content": [
                            {"type": "text", "text": "Review with "},
                            {"type": "mention", "attrs": {"text": "Ada"}},
                            {"type": "text", "text": " after break"},
                            {"type": "hardBreak"},
                            {"type": "text", "text": "done"},
                        ],
                    },
                ],
            }
        ],
    }

    assert AdfMarkdownRenderer().render(adf) == (
        "- [ ] Write **renderer** docs [now](https://example.com/task)\n"
        "- [x] Review with @Ada after break  \n"
        "      done"
    )


def test_task_list_renders_nested_task_lists_deterministically() -> None:
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "taskList",
                "attrs": {"localId": "root"},
                "content": [
                    {
                        "type": "taskItem",
                        "attrs": {"localId": "parent", "state": "TODO"},
                        "content": [{"type": "text", "text": "Parent"}],
                    },
                    {
                        "type": "taskList",
                        "attrs": {"localId": "nested"},
                        "content": [
                            {
                                "type": "taskItem",
                                "attrs": {"localId": "child", "state": "DONE"},
                                "content": [{"type": "text", "text": "Child"}],
                            }
                        ],
                    },
                ],
            }
        ],
    }

    assert AdfMarkdownRenderer().render(adf) == "- [ ] Parent\n  - [x] Child"


def test_malformed_task_list_content_uses_unknown_fallback_and_raw_json() -> None:
    renderer = AdfMarkdownRenderer(include_raw_adf_on_unknown_nodes=True)

    rendered = renderer.render(
        {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "taskList", "attrs": {"localId": "empty-list"}, "content": []},
                {"type": "taskList", "attrs": {"localId": "bad-list"}, "content": "not a list"},
                {
                    "type": "taskList",
                    "attrs": {"localId": "mixed-list"},
                    "content": [
                        {
                            "type": "taskItem",
                            "attrs": {"localId": "bad-item", "state": "todo"},
                            "content": [{"type": "text", "text": "lowercase state"}],
                        },
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "block child"}],
                        },
                        {
                            "type": "taskItem",
                            "attrs": {"localId": "unknown-inline", "state": "TODO"},
                            "content": [{"type": "unknownInline", "attrs": {"z": 1}}],
                        },
                    ],
                },
            ],
        }
    )

    assert "[Unsupported ADF node: taskList]" in rendered
    assert '"localId": "empty-list"' in rendered
    assert '"content": "not a list"' in rendered
    assert "[Unsupported ADF node: taskItem]" in rendered
    assert '"state": "todo"' in rendered
    assert '"text": "lowercase state"' in rendered
    assert "[Unsupported ADF node: paragraph]" in rendered
    assert '"text": "block child"' in rendered
    assert "- [ ] [Unsupported ADF node: unknownInline]" in rendered
    assert '"z": 1' in rendered


def test_unknown_node_placeholder_can_include_deterministic_raw_json() -> None:
    renderer = AdfMarkdownRenderer(include_raw_adf_on_unknown_nodes=True)

    rendered = renderer.render(
        {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "before"}]},
                {"type": "mystery", "attrs": {"z": 2, "a": 1}},
                {"type": "paragraph", "content": [{"type": "text", "text": "after"}]},
            ],
        }
    )

    assert "before" in rendered
    assert "[Unsupported ADF node: mystery]" in rendered
    assert '"a": 1' in rendered
    assert rendered.index('"a": 1') < rendered.index('"z": 2')
    assert "after" in rendered


def test_unknown_node_placeholder_can_omit_raw_json() -> None:
    renderer = AdfMarkdownRenderer(include_raw_adf_on_unknown_nodes=False)

    assert renderer.render({"type": "mystery", "attrs": {"secret": "not emitted"}}) == (
        "[Unsupported ADF node: mystery]"
    )
