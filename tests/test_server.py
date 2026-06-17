"""Tests for the MCP tool layer, exercising the lazy client + read-only guard."""

import httpx
import pytest
import respx

from jira_mcp import server
from jira_mcp.client import JiraClient
from jira_mcp.config import JiraSettings

JIRA = "https://works.digikala.com"


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset module globals around each test."""
    server._settings = None
    server._client = None
    yield
    if server._client is not None:
        # Tests run in an event loop; close via the loop if still open.
        server._client = None
    server._settings = None


def _install(read_only=False):
    settings = JiraSettings(
        host=JIRA,
        pat="t",
        read_only=read_only,
    )
    server._settings = settings
    server._client = JiraClient(settings)


@respx.mock
async def test_get_current_user_tool():
    _install()
    respx.get(f"{JIRA}/rest/api/2/myself").mock(
        return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Me"})
    )
    out = await server.get_current_user()
    assert out["display_name"] == "Me"
    await server._client.aclose()


@respx.mock
async def test_search_issues_clamps_max_results():
    _install()
    route = respx.post(f"{JIRA}/rest/api/2/search").mock(
        return_value=httpx.Response(200, json={"issues": [], "total": 0})
    )
    await server.search_issues("project = P", max_results=9999)
    import json

    body = json.loads(route.calls.last.request.content)
    assert body["maxResults"] == 100
    await server._client.aclose()


@respx.mock
async def test_get_issue_with_comments():
    _install()
    respx.get(f"{JIRA}/rest/api/2/issue/P-1").mock(
        return_value=httpx.Response(200, json={"key": "P-1", "fields": {"summary": "s"}})
    )
    respx.get(f"{JIRA}/rest/api/2/issue/P-1/comment").mock(
        return_value=httpx.Response(
            200,
            json={"comments": [{"id": "1", "author": {"displayName": "A"}, "body": "hi"}]},
        )
    )
    out = await server.get_issue("P-1", include_comments=True)
    assert out["key"] == "P-1"
    assert out["comments"][0]["body"] == "hi"
    await server._client.aclose()


async def test_write_tool_blocked_in_read_only():
    _install(read_only=True)
    with pytest.raises(server.ToolError):
        await server.create_issue(project_key="P", summary="x")
    await server._client.aclose()


async def test_update_issue_requires_fields():
    _install()
    with pytest.raises(server.ToolError):
        await server.update_issue("P-1")
    await server._client.aclose()


@respx.mock
async def test_create_issue_returns_url():
    _install()
    respx.post(f"{JIRA}/rest/api/2/issue").mock(
        return_value=httpx.Response(201, json={"key": "P-7"})
    )
    out = await server.create_issue(project_key="P", summary="hi")
    assert out["key"] == "P-7"
    assert out["url"].endswith("/browse/P-7")
    await server._client.aclose()


@respx.mock
async def test_jira_error_becomes_tool_error():
    _install()
    respx.get(f"{JIRA}/rest/api/2/issue/BAD").mock(
        return_value=httpx.Response(404, json={"errorMessages": ["not found"]})
    )
    with pytest.raises(server.ToolError) as exc:
        await server.get_issue("BAD")
    assert "not found" in str(exc.value)
    await server._client.aclose()
