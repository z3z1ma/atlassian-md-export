from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tomllib

import pytest
import typer
from typer.core import TyperGroup
from typer.core import TyperOption
from typer.main import get_command
from pydantic import ValidationError
from typer.testing import CliRunner

from atlassian_md_export.cli import app, confluence_app
from atlassian_md_export.config import ConfluenceCredentials
from atlassian_md_export.config import ExportConfig
from atlassian_md_export.config import MissingConfluenceCredentialsError
from atlassian_md_export.config import load_confluence_config
from atlassian_md_export.log import JsonLogFormatter
from atlassian_md_export.log import redact


def _command_options(typer_app: typer.Typer, command_name: str) -> dict[str, TyperOption]:
    root_command = get_command(typer_app)
    assert isinstance(root_command, TyperGroup)
    command = root_command.commands[command_name]
    return {
        option_name: parameter
        for parameter in command.params
        if isinstance(parameter, TyperOption)
        for option_name in parameter.opts
    }


def _assert_command_options(
    typer_app: typer.Typer,
    command_name: str,
    expected_options: tuple[str, ...],
) -> dict[str, TyperOption]:
    options = _command_options(typer_app, command_name)
    for option in expected_options:
        assert option in options
    return options


def test_pull_reports_missing_credentials_without_secret_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_SITE", raising=False)
    monkeypatch.setenv("JIRA_API_TOKEN", "super-secret-token")

    result = CliRunner().invoke(
        app,
        [
            "pull",
            "--out",
            str(tmp_path),
            "--site",
            "https://example.atlassian.net",
            "--project",
            "ABC",
            "--since",
            "2026-07-01T00:00:00+00:00",
        ],
    )

    assert result.exit_code == 2
    assert "JIRA_EMAIL" in result.output
    assert "super-secret-token" not in result.output


def test_local_cli_commands_use_real_paths(tmp_path: Path) -> None:
    runner = CliRunner()

    init_result = runner.invoke(app, ["init", "--out", str(tmp_path)])
    index_result = runner.invoke(app, ["index", "--out", str(tmp_path)])
    verify_result = runner.invoke(app, ["verify", "--out", str(tmp_path)])
    clean_result = runner.invoke(app, ["clean", "--out", str(tmp_path), "--remove-missing"])

    assert init_result.exit_code == 0
    assert (tmp_path / "issues" / "_raw").is_dir()
    assert index_result.exit_code == 0
    assert "Regenerated" in index_result.output
    assert verify_result.exit_code == 0
    assert "Verified" in verify_result.output
    assert clean_result.exit_code == 1
    assert "No successful representative pull exists" in clean_result.output


def test_rendering_commands_expose_stable_exported_at_flag() -> None:
    for command in ("pull", "issue", "comments", "attachments"):
        _assert_command_options(app, command, ("--stable-exported-at",))


def test_config_rejects_negative_sync_overlap_and_allows_zero() -> None:
    assert ExportConfig.model_validate({"sync": {"overlap_minutes": 0}}).sync.overlap_minutes == 0

    with pytest.raises(ValidationError):
        ExportConfig.model_validate({"sync": {"overlap_minutes": -1}})


def test_pyproject_exposes_confluence_console_script() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["jira-md-export"] == "atlassian_md_export.cli:app"
    assert (
        pyproject["project"]["scripts"]["confluence-md-export"]
        == "atlassian_md_export.cli:confluence_app"
    )


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("init", []),
        ("pull", ["--site", "https://example.atlassian.net", "--space", "DOCS"]),
        ("page", ["123"]),
        ("comments", ["123", "--force"]),
        ("attachments", ["123"]),
        ("verify", []),
        ("index", []),
        ("clean", ["--remove-missing"]),
    ],
)
def test_confluence_stateful_commands_require_explicit_out(
    command: str,
    args: list[str],
) -> None:
    result = CliRunner().invoke(confluence_app, [command, *args])

    assert result.exit_code != 0
    assert "No such command" not in result.output
    assert _command_options(confluence_app, command)["--out"].required is True


def test_confluence_pull_exposes_ratified_scope_options() -> None:
    options = _assert_command_options(
        confluence_app,
        "pull",
        (
            "--site",
            "--space",
            "--cql",
            "--ancestor",
            "--page",
            "--since",
            "--force",
            "--concurrency",
            "--attachment-max-mb",
            "--attachment-include",
            "--stable-exported-at",
            "--config",
            "--out",
            "--download-attachments",
        ),
    )
    assert "Download eligible" in (options["--download-attachments"].help or "")


def test_confluence_exact_commands_expose_rendering_and_attachment_options() -> None:
    for command in ("page", "comments", "attachments"):
        _assert_command_options(confluence_app, command, ("--stable-exported-at",))

    _assert_command_options(
        confluence_app,
        "attachments",
        (
            "--attachment-max-mb",
            "--attachment-include",
        ),
    )


def test_confluence_init_creates_skeleton_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "CONFLUENCE_SITE",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
        "ATLASSIAN_SITE",
        "ATLASSIAN_EMAIL",
        "ATLASSIAN_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)

    result = CliRunner().invoke(confluence_app, ["init", "--out", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / "pages" / "_raw").is_dir()
    assert (tmp_path / "attachments").is_dir()
    assert (tmp_path / "indexes").is_dir()
    assert (tmp_path / "state.sqlite").is_file()
    assert (tmp_path / "manifest.json").is_file()


def test_confluence_local_cli_commands_use_real_paths(tmp_path: Path) -> None:
    runner = CliRunner()

    init_result = runner.invoke(confluence_app, ["init", "--out", str(tmp_path)])
    index_result = runner.invoke(confluence_app, ["index", "--out", str(tmp_path)])
    verify_result = runner.invoke(confluence_app, ["verify", "--out", str(tmp_path)])
    clean_result = runner.invoke(
        confluence_app,
        ["clean", "--out", str(tmp_path), "--remove-missing"],
    )

    assert init_result.exit_code == 0
    assert (tmp_path / "pages" / "_raw").is_dir()
    assert index_result.exit_code == 0
    assert "Regenerated" in index_result.output
    assert verify_result.exit_code == 0
    assert "Verified Confluence" in verify_result.output
    assert clean_result.exit_code == 1
    assert "No successful representative Confluence pull exists" in clean_result.output


@pytest.mark.parametrize(
    "filename",
    ["confluence-md-export.yaml", "atlassian-md-export.yaml", ".confluence-md-export.yaml"],
)
def test_confluence_config_default_filenames_and_keys(tmp_path: Path, filename: str) -> None:
    (tmp_path / filename).write_text(
        """
site: https://example.atlassian.net
space: DOCS
out: ./confluence-export
content:
  body_format: atlas_doc_format
  include_footer_comments: true
  include_inline_comments: false
  include_resolved_inline_comments: true
sync:
  overlap_minutes: 12
  concurrency: 3
  download_attachments: true
markdown:
  stable_exported_at: true
  include_raw_adf_on_unknown_nodes: false
""".lstrip(),
        encoding="utf-8",
    )

    config = load_confluence_config(cwd=tmp_path)

    assert config.site == "https://example.atlassian.net"
    assert config.space == "DOCS"
    assert config.out == Path("confluence-export")
    assert config.content.body_format == "atlas_doc_format"
    assert config.content.include_footer_comments is True
    assert config.content.include_inline_comments is False
    assert config.content.include_resolved_inline_comments is True
    assert config.sync.overlap_minutes == 12
    assert config.sync.concurrency == 3
    assert config.sync.download_attachments is True
    assert config.markdown.stable_exported_at is True
    assert config.markdown.include_raw_adf_on_unknown_nodes is False


def test_confluence_credentials_use_confluence_then_atlassian_without_jira() -> None:
    with pytest.raises(MissingConfluenceCredentialsError):
        ConfluenceCredentials.from_environment(
            {"JIRA_EMAIL": "jira@example.com", "JIRA_API_TOKEN": "jira-secret"}
        )

    confluence = ConfluenceCredentials.from_environment(
        {"CONFLUENCE_EMAIL": "conf@example.com", "CONFLUENCE_API_TOKEN": "conf-secret"}
    )
    atlassian = ConfluenceCredentials.from_environment(
        {"ATLASSIAN_EMAIL": "team@example.com", "ATLASSIAN_API_TOKEN": "team-secret"}
    )

    assert confluence.email == "conf@example.com"
    assert confluence.api_token.get_secret_value() == "conf-secret"
    assert atlassian.email == "team@example.com"
    assert atlassian.api_token.get_secret_value() == "team-secret"


def test_confluence_missing_credentials_are_friendly_and_ignore_jira(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
        "ATLASSIAN_EMAIL",
        "ATLASSIAN_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JIRA_EMAIL", "jira@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-secret")

    result = CliRunner().invoke(
        confluence_app,
        [
            "pull",
            "--out",
            str(tmp_path),
            "--site",
            "https://example.atlassian.net",
            "--space",
            "DOCS",
        ],
    )

    assert result.exit_code == 2
    assert "Missing Confluence configuration" in result.output
    assert "CONFLUENCE_EMAIL or ATLASSIAN_EMAIL" in result.output
    assert "CONFLUENCE_API_TOKEN or ATLASSIAN_API_TOKEN" in result.output
    assert "JIRA_" not in result.output
    assert "jira-secret" not in result.output


def test_confluence_dotenv_loading_for_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "CONFLUENCE_SITE",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
        "ATLASSIAN_SITE",
        "ATLASSIAN_EMAIL",
        "ATLASSIAN_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "CONFLUENCE_SITE=https://example.atlassian.net",
                "CONFLUENCE_EMAIL=conf@example.com",
                "CONFLUENCE_API_TOKEN=dotenv-secret",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    class Summary:
        page_ids = ("123",)

    def fake_pull(*_args: object, **_kwargs: object) -> Summary:
        assert os.environ["CONFLUENCE_API_TOKEN"] == "dotenv-secret"
        return Summary()

    monkeypatch.setattr("atlassian_md_export.cli.build_confluence_client", lambda _site: object())
    monkeypatch.setattr("atlassian_md_export.cli.run_confluence_pull", fake_pull)

    result = CliRunner().invoke(confluence_app, ["pull", "--out", "out", "--space", "DOCS"])

    assert result.exit_code == 0
    assert "Exported 1 page(s)." in result.output
    assert "Missing Confluence configuration" not in result.output
    assert "dotenv-secret" not in result.output
    assert os.environ["CONFLUENCE_API_TOKEN"] == "dotenv-secret"


def test_confluence_json_logs_and_redaction_do_not_leak_tokens(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "confluence-secret")
    monkeypatch.setenv("ATLASSIAN_API_TOKEN", "atlassian-secret")

    result = CliRunner().invoke(
        confluence_app,
        ["--verbose", "--json-logs", "init", "--out", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "confluence-secret" not in result.output
    assert "atlassian-secret" not in result.output
    assert redact("token=confluence-secret") == "token=[REDACTED]"
    assert redact("token=atlassian-secret") == "token=[REDACTED]"


def test_json_log_formatter_redacts_nested_confluence_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "confluence-secret")
    record = logging.getLogger("atlassian_md_export.operations").makeRecord(
        "atlassian_md_export.operations",
        logging.INFO,
        __file__,
        1,
        "Authorization: Bearer confluence-secret",
        args=(),
        exc_info=None,
        extra={
            "provider": "confluence",
            "command": "pull",
            "site_host": "example.atlassian.net",
            "page_id": "123",
            "space_key": "DOC",
            "operation": "confluence_page_write",
            "output_path": "/tmp/export/pages/DOC/123-Launch.md",
            "authorization": "Bearer confluence-secret",
            "nested": {"api_token": "confluence-secret", "safe": "ok"},
        },
    )

    formatted = JsonLogFormatter().format(record)
    payload = json.loads(formatted)

    assert "confluence-secret" not in formatted
    assert payload["message"] == "Authorization: [REDACTED]"
    assert payload["provider"] == "confluence"
    assert payload["command"] == "pull"
    assert payload["page_id"] == "123"
    assert payload["space_key"] == "DOC"
    assert payload["authorization"] == "[REDACTED]"
    assert payload["nested"] == {"api_token": "[REDACTED]", "safe": "ok"}
