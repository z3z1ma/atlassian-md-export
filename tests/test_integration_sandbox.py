from __future__ import annotations

import os
from pathlib import Path

import pytest

from atlassian_md_export.client import AtlassianHttpClient
from atlassian_md_export.client import JiraCredentials
from atlassian_md_export.config import ConfluenceCredentials
from atlassian_md_export.config import ExportConfig
from atlassian_md_export.config import MarkdownConfig
from atlassian_md_export.confluence.client import ConfluenceClient
from atlassian_md_export.jira.client import JiraClient
from atlassian_md_export.operations import run_confluence_page
from atlassian_md_export.operations import verify_confluence_export


pytestmark = pytest.mark.integration


def test_real_jira_sandbox_issue_can_be_read() -> None:
    required = (
        "JIRA_SITE",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_MD_EXPORT_SANDBOX_ISSUE",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.skip(f"missing Jira sandbox env vars: {', '.join(missing)}")

    site = os.environ["JIRA_SITE"]
    issue_key = os.environ["JIRA_MD_EXPORT_SANDBOX_ISSUE"]
    client = JiraClient(AtlassianHttpClient(site, JiraCredentials.from_environment()))

    result = client.search_issue_keys([issue_key], fields=["summary", "updated"])
    comments = client.fetch_comments(issue_key)

    assert [issue.key for issue in result.issues] == [issue_key]
    assert isinstance(comments, tuple)


def test_real_confluence_sandbox_page_can_be_exported(tmp_path: Path) -> None:
    required = (
        "CONFLUENCE_SITE",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
        "CONFLUENCE_MD_EXPORT_SANDBOX_PAGE",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.skip(f"missing Confluence sandbox env vars: {', '.join(missing)}")

    site = os.environ["CONFLUENCE_SITE"]
    page_id = os.environ["CONFLUENCE_MD_EXPORT_SANDBOX_PAGE"]
    client = ConfluenceClient(
        AtlassianHttpClient(
            site,
            ConfluenceCredentials.from_environment(),
            provider_name="Confluence",
            auth_hint="Check CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN, and site access.",
        )
    )
    config = ExportConfig(markdown=MarkdownConfig(stable_exported_at=True))

    summary = run_confluence_page(
        tmp_path,
        client=client,
        site_url=site,
        config=config,
        page_ids=[page_id],
    )
    verification = verify_confluence_export(tmp_path)

    assert summary.page_ids == (page_id,)
    assert (tmp_path / "pages" / "_raw" / f"{page_id}.json").is_file()
    assert verification.ok, "\n".join(verification.errors)
